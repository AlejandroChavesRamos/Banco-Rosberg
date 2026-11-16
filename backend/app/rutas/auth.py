"""Registro, inicio de sesion, renovacion de tokens y cambio de contrasena.

PORTALES SEPARADOS: Banco Rosberg tiene dos puertas de entrada.
  - "app":      App Rosberg, solo para CLIENTES.
  - "intranet": Intranet Rosberg, solo para EMPLEADOS (cajero, analista, admin).
El servidor (no solo las pantallas) rechaza a quien intente entrar por la
puerta equivocada. Cada portal tiene ademas su propia cookie de sesion.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from ..config import settings
from ..db.mysql import consultar_uno, ejecutar, leer_config, obtener_conexion
from ..esquemas import CambioPassword, LoginEntrada, Portal, RecuperarPassword, RegistroEntrada, TokenSalida
from ..seguridad import cifrado
from ..seguridad import contrasenas, tokens
from ..seguridad.dependencias import UsuarioActual, usuario_actual
from ..servicios import auditoria, banco, grafo
from ..utilidades import huella_dispositivo, ip_cliente

router = APIRouter(prefix="/auth", tags=["1. Autenticacion"])

_CREDENCIALES_INVALIDAS = "Correo o contrasena incorrectos"


def _cookie(portal: str) -> str:
    return f"refresh_{portal}"


def _rol_permitido(rol: str, portal: str) -> bool:
    return (rol == "cliente") == (portal == "app")


def _emitir_sesion(conn, response: Response, usuario: dict, portal: str,
                   dispositivo_id: int | None, ip: str) -> TokenSalida:
    jti = str(uuid.uuid4())
    ejecutar(
        conn,
        "INSERT INTO sesiones (id, usuario_id, dispositivo_id, ip, expira_en) "
        "VALUES (%s, %s, %s, %s, NOW() + INTERVAL %s DAY)",
        (jti, usuario["id"], dispositivo_id, ip, settings.refresh_dias),
    )
    response.set_cookie(
        _cookie(portal), tokens.crear_refresh(usuario["id"], jti),
        httponly=True,                 # JavaScript no puede leerla
        secure=settings.cookie_segura,  # solo por HTTPS (se activa en la Fase 6)
        samesite="strict",              # no se envia desde otros sitios (anti-CSRF)
        path="/auth",                   # solo viaja a las rutas de autenticacion
        max_age=settings.refresh_dias * 86400,
    )
    return TokenSalida(
        access_token=tokens.crear_access(usuario["id"], usuario["rol"]),
        expira_en_segundos=settings.access_minutos * 60,
        rol=usuario["rol"],
        nombre=usuario["nombre"],
        debe_cambiar_password=bool(usuario["debe_cambiar_password"]),
    )


def _mensaje_bloqueo(segundos: int | None) -> str:
    minutos = max(1, -(-(segundos or 0) // 60))  # redondea hacia arriba
    return (f"Usuario bloqueado por intentos fallidos. Podra intentar de nuevo en "
            f"{minutos} minuto{'s' if minutos != 1 else ''}.")


def _sumar_intento_fallido(conn, usuario: dict) -> str:
    """Suma un intento fallido, bloquea si llega al maximo y devuelve el aviso para la pantalla.

    El aviso solo se le muestra a quien escribio un correo que SI existe, igual
    que ya pasaba con el mensaje de "usuario bloqueado".
    """
    maximo = leer_config(conn, "MAX_INTENTOS_LOGIN")
    minutos = leer_config(conn, "MINUTOS_BLOQUEO_LOGIN")
    ejecutar(
        conn,
        "UPDATE usuarios SET "
        "bloqueado_hasta = IF(intentos_fallidos + 1 >= %s, NOW() + INTERVAL %s MINUTE, NULL), "
        "intentos_fallidos = IF(intentos_fallidos + 1 >= %s, 0, intentos_fallidos + 1) "
        "WHERE id = %s",
        (maximo, minutos, maximo, usuario["id"]),
    )
    restantes = maximo - (usuario["intentos_fallidos"] + 1)
    if restantes <= 0:
        return f"El usuario quedo bloqueado durante {minutos} minutos."
    return f"Le queda{'n' if restantes != 1 else ''} {restantes} intento{'s' if restantes != 1 else ''}."


@router.post("/registro", status_code=201, summary="Registro en linea de un cliente nuevo")
def registro(datos: RegistroEntrada, request: Request, conn=Depends(obtener_conexion)):
    creado = banco.crear_cliente(
        conn, nombre=datos.nombre, email=datos.email, cedula=datos.cedula, celular=datos.celular,
        password_hash=contrasenas.hashear(datos.password), debe_cambiar=False,
    )
    auditoria.registrar(conn, "REGISTRO_CLIENTE", "usuarios", creado["usuario_id"],
                        usuario_id=creado["usuario_id"], detalle={"canal": "en_linea"},
                        ip=ip_cliente(request))
    return {
        "mensaje": f"Bienvenido a {settings.nombre_banco}. Ya puede iniciar sesion.",
        "cuenta": creado["numero"],
        "tipo_cuenta": "ahorros",
    }


@router.post("/login", response_model=TokenSalida,
             summary="Iniciar sesion (portal 'app' para clientes, 'intranet' para empleados)")
def login(datos: LoginEntrada, request: Request, response: Response, conn=Depends(obtener_conexion)):
    ip = ip_cliente(request)
    huella, agente = huella_dispositivo(request)
    email = datos.email.lower()

    usuario = consultar_uno(
        conn,
        "SELECT id, rol, nombre, password_hash, activo, debe_cambiar_password, intentos_fallidos, "
        "(bloqueado_hasta IS NOT NULL AND bloqueado_hasta > NOW()) AS bloqueado, "
        "TIMESTAMPDIFF(SECOND, NOW(), bloqueado_hasta) AS segundos_bloqueo "
        "FROM usuarios WHERE email = %s",
        (email,),
    )

    def _evento(exito: bool, usuario_id=None, dispositivo_id=None):
        ejecutar(conn, "INSERT INTO eventos_login (usuario_id, email_intentado, ip, dispositivo_id, exito) "
                       "VALUES (%s, %s, %s, %s, %s)", (usuario_id, email, ip, dispositivo_id, exito))

    # 1) El correo no existe: verificamos un hash ficticio para tardar lo mismo
    if not usuario or not usuario["activo"]:
        contrasenas.verificar_ficticio(datos.password)
        _evento(False, usuario["id"] if usuario else None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENCIALES_INVALIDAS)

    # 2) Usuario bloqueado temporalmente por intentos fallidos
    if usuario["bloqueado"]:
        _evento(False, usuario["id"])
        raise HTTPException(status.HTTP_423_LOCKED, _mensaje_bloqueo(usuario["segundos_bloqueo"]))

    # 3) Contrasena incorrecta: sumar intento y bloquear si llega al maximo
    if not contrasenas.verificar(usuario["password_hash"], datos.password):
        aviso = _sumar_intento_fallido(conn, usuario)
        _evento(False, usuario["id"])
        auditoria.registrar(conn, "LOGIN_FALLIDO", "usuarios", usuario["id"], ip=ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"{_CREDENCIALES_INVALIDAS}. {aviso}")

    # 4) Puerta equivocada: un cliente en la Intranet o un empleado en la App
    if not _rol_permitido(usuario["rol"], datos.portal):
        _evento(False, usuario["id"])
        auditoria.registrar(conn, "LOGIN_PORTAL_INCORRECTO", "usuarios", usuario["id"],
                            detalle={"portal": datos.portal, "rol": usuario["rol"]}, ip=ip)
        destino = "la App Rosberg" if usuario["rol"] == "cliente" else "la Intranet Rosberg"
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Esta cuenta debe ingresar por {destino}")

    # 5) Exito
    if contrasenas.necesita_rehash(usuario["password_hash"]):
        ejecutar(conn, "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                 (contrasenas.hashear(datos.password), usuario["id"]))
    ejecutar(conn, "UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s",
             (usuario["id"],))
    dispositivo_id, es_nuevo = banco.registrar_dispositivo(conn, usuario["id"], huella, agente)
    _evento(True, usuario["id"], dispositivo_id)
    auditoria.registrar(conn, "LOGIN", "usuarios", usuario["id"], usuario_id=usuario["id"],
                        detalle={"dispositivo_nuevo": es_nuevo, "portal": datos.portal}, ip=ip)
    if usuario["rol"] == "cliente":
        grafo.sincronizar_conexion(usuario["id"], huella, ip)

    return _emitir_sesion(conn, response, usuario, datos.portal, dispositivo_id, ip)


@router.post("/refresh", response_model=TokenSalida,
             summary="Obtener un access token nuevo usando la cookie de renovacion")
def refresh(request: Request, response: Response, portal: Portal = Query(...),
            conn=Depends(obtener_conexion)):
    token = request.cookies.get(_cookie(portal))
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No hay sesion activa")
    datos = tokens.decodificar(token, "refresh")

    sesion = consultar_uno(
        conn,
        "SELECT id, usuario_id, dispositivo_id, revocada, (expira_en > NOW()) AS vigente "
        "FROM sesiones WHERE id = %s",
        (datos["jti"],),
    )
    if not sesion or not sesion["vigente"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion vencida")

    if sesion["revocada"]:
        # Alguien uso un token de renovacion que ya habia sido usado: posible robo.
        # Por seguridad se cierran TODAS las sesiones del usuario.
        ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE usuario_id = %s", (sesion["usuario_id"],))
        auditoria.registrar(conn, "REFRESH_REUTILIZADO", "sesiones", None, usuario_id=sesion["usuario_id"],
                            detalle={"jti": sesion["id"]}, ip=ip_cliente(request))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion invalidada por seguridad")

    # Rotacion: el token usado se revoca y se entrega uno nuevo
    ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE id = %s", (sesion["id"],))
    usuario = consultar_uno(conn, "SELECT id, rol, nombre, activo, debe_cambiar_password "
                                  "FROM usuarios WHERE id = %s", (sesion["usuario_id"],))
    if not usuario or not usuario["activo"] or not _rol_permitido(usuario["rol"], portal):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion no valida para este portal")
    return _emitir_sesion(conn, response, usuario, portal, sesion["dispositivo_id"], ip_cliente(request))


@router.post("/logout", summary="Cerrar sesion")
def logout(request: Request, response: Response, portal: Portal = Query(...),
           conn=Depends(obtener_conexion)):
    token = request.cookies.get(_cookie(portal))
    if token:
        try:
            datos = tokens.decodificar(token, "refresh")
            ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE id = %s", (datos["jti"],))
        except HTTPException:
            pass
    response.delete_cookie(_cookie(portal), path="/auth")
    return {"mensaje": "Sesion cerrada"}


@router.get("/yo", summary="Datos del usuario autenticado")
def yo(u: UsuarioActual = Depends(usuario_actual)):
    return u


@router.post("/cambiar-password", summary="Cambiar contrasena (obligatorio si es temporal)")
def cambiar_password(datos: CambioPassword, request: Request,
                     u: UsuarioActual = Depends(usuario_actual), conn=Depends(obtener_conexion)):
    fila = consultar_uno(conn, "SELECT password_hash FROM usuarios WHERE id = %s", (u.id,))
    if not contrasenas.verificar(fila["password_hash"], datos.actual):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contrasena actual no es correcta")
    if datos.actual == datos.nueva:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La nueva contrasena debe ser diferente")
    ejecutar(conn, "UPDATE usuarios SET password_hash = %s, debe_cambiar_password = FALSE WHERE id = %s",
             (contrasenas.hashear(datos.nueva), u.id))
    # Cerrar todas las sesiones: si alguien tenia la contrasena vieja, queda fuera
    ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE usuario_id = %s", (u.id,))
    auditoria.registrar(conn, "CAMBIO_PASSWORD", "usuarios", u.id, usuario_id=u.id, ip=ip_cliente(request))
    return {"mensaje": "Contrasena actualizada. Inicie sesion de nuevo."}


@router.post("/recuperar-password", summary="Olvide mi contrasena (solo clientes)")
def recuperar_password(datos: RecuperarPassword, request: Request, conn=Depends(obtener_conexion)):
    """El banco no envia correos, asi que el cliente demuestra quien es con la
    cedula y el celular que registro al abrir la cuenta. Los empleados no usan
    esta ruta: su contrasena la restablece un administrador.

    Los intentos fallidos cuentan igual que los del login: tras varios, el
    usuario queda bloqueado (evita adivinar cedulas o celulares a la fuerza).
    """
    ip = ip_cliente(request)
    no_coincide = HTTPException(status.HTTP_400_BAD_REQUEST, "Los datos no coinciden con los de ninguna cuenta")
    usuario = consultar_uno(
        conn,
        "SELECT id, activo, intentos_fallidos, documento_hash, telefono_cifrado, "
        "(bloqueado_hasta IS NOT NULL AND bloqueado_hasta > NOW()) AS bloqueado, "
        "TIMESTAMPDIFF(SECOND, NOW(), bloqueado_hasta) AS segundos_bloqueo "
        "FROM usuarios WHERE email = %s AND rol = 'cliente'",
        (datos.email.lower(),),
    )
    if not usuario or not usuario["activo"]:
        raise no_coincide
    if usuario["bloqueado"]:
        raise HTTPException(status.HTTP_423_LOCKED, _mensaje_bloqueo(usuario["segundos_bloqueo"]))

    cedula_ok = cifrado.iguales(usuario["documento_hash"] or "", cifrado.indice_ciego(datos.cedula, "cedula"))
    celular_ok = bool(usuario["telefono_cifrado"]) and cifrado.iguales(
        cifrado.descifrar(usuario["telefono_cifrado"]), datos.celular)
    if not (cedula_ok and celular_ok):
        aviso = _sumar_intento_fallido(conn, usuario)
        auditoria.registrar(conn, "RECUPERACION_FALLIDA", "usuarios", usuario["id"], ip=ip)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{no_coincide.detail}. {aviso}")

    ejecutar(conn, "UPDATE usuarios SET password_hash = %s, debe_cambiar_password = FALSE, "
                   "intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s",
             (contrasenas.hashear(datos.nueva), usuario["id"]))
    # Si alguien tenia una sesion abierta con la contrasena vieja, queda fuera
    ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE usuario_id = %s", (usuario["id"],))
    auditoria.registrar(conn, "RECUPERACION_PASSWORD", "usuarios", usuario["id"],
                        usuario_id=usuario["id"], ip=ip)
    return {"mensaje": "Contrasena actualizada. Ya puede iniciar sesion."}
