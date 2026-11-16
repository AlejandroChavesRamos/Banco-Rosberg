"""Registro, inicio de sesion (con 2FA opcional), renovacion de tokens y contrasenas.

PORTALES SEPARADOS: Banco Rosberg tiene dos puertas de entrada.
  - "app":      App Rosberg, solo para CLIENTES.
  - "intranet": Intranet Rosberg, solo para EMPLEADOS (cajero, analista, admin).
El servidor (no solo las pantallas) rechaza a quien intente entrar por la
puerta equivocada. Cada portal tiene ademas su propia cookie de sesion.

LOGIN EN DOS PASOS (si el usuario tiene 2FA activo):
  1. POST /auth/login con correo y contrasena -> {"requiere_2fa": true, "token_2fa": ...}
  2. POST /auth/2fa/verificar con ese token y el codigo del celular -> sesion
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from ..config import settings
from ..db.mysql import consultar_uno, ejecutar, leer_config, obtener_conexion
from ..esquemas import (CambioPassword, CodigoEntrada, Desactivar2FA, LoginEntrada, Portal,
                        RegistroEntrada, TokenSalida, Verificar2FA)
from ..seguridad import cifrado, contrasenas, doble_factor, tokens
from ..seguridad.dependencias import UsuarioActual, usuario_actual
from ..servicios import auditoria, avisos, banco, grafo
from ..utilidades import huella_dispositivo, ip_cliente

router = APIRouter(prefix="/auth", tags=["1. Autenticacion"])

_CREDENCIALES_INVALIDAS = "Correo o contrasena incorrectos"
_SELECT_USUARIO = ("SELECT id, rol, nombre, email, password_hash, activo, debe_cambiar_password, totp_activo, "
                   "(bloqueado_hasta IS NOT NULL AND bloqueado_hasta > NOW()) AS bloqueado FROM usuarios ")


def _cookie(portal: str) -> str:
    return f"refresh_{portal}"


def _rol_permitido(rol: str, portal: str) -> bool:
    return (rol == "cliente") == (portal == "app")


def _registrar_fallo(conn, usuario_id: int, ip: str, accion: str = "LOGIN_FALLIDO") -> None:
    """Suma un intento fallido y bloquea al usuario si llega al maximo."""
    maximo = leer_config(conn, "MAX_INTENTOS_LOGIN")
    minutos = leer_config(conn, "MINUTOS_BLOQUEO_LOGIN")
    ejecutar(
        conn,
        "UPDATE usuarios SET "
        "bloqueado_hasta = IF(intentos_fallidos + 1 >= %s, NOW() + INTERVAL %s MINUTE, NULL), "
        "intentos_fallidos = IF(intentos_fallidos + 1 >= %s, 0, intentos_fallidos + 1) "
        "WHERE id = %s",
        (maximo, minutos, maximo, usuario_id),
    )
    auditoria.registrar(conn, accion, "usuarios", usuario_id, ip=ip)


def _evento(conn, email: str, ip: str, exito: bool, usuario_id=None, dispositivo_id=None) -> None:
    ejecutar(conn, "INSERT INTO eventos_login (usuario_id, email_intentado, ip, dispositivo_id, exito) "
                   "VALUES (%s, %s, %s, %s, %s)", (usuario_id, email, ip, dispositivo_id, exito))


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
        secure=settings.cookie_segura,  # solo por HTTPS (activo en modo produccion)
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
        debe_configurar_2fa=doble_factor.debe_configurar(conn, usuario["rol"], bool(usuario["totp_activo"])),
        tiene_2fa=bool(usuario["totp_activo"]),
    )


def _completar_login(conn, request: Request, response: Response, usuario: dict, portal: str) -> TokenSalida:
    """Ultimo paso comun del login (con o sin 2FA)."""
    ip = ip_cliente(request)
    huella, agente = huella_dispositivo(request)
    ejecutar(conn, "UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s", (usuario["id"],))
    dispositivo_id, es_nuevo = banco.registrar_dispositivo(conn, usuario["id"], huella, agente)
    if usuario["rol"] == "cliente":
        # Aviso al cliente si entra desde un dispositivo o IP que nunca habia usado
        avisos.revisar_inicio_sesion(conn, usuario["id"], dispositivo_id, es_nuevo, ip)
    _evento(conn, usuario["email"], ip, True, usuario["id"], dispositivo_id)
    auditoria.registrar(conn, "LOGIN", "usuarios", usuario["id"], usuario_id=usuario["id"],
                        detalle={"dispositivo_nuevo": es_nuevo, "portal": portal}, ip=ip)
    if usuario["rol"] == "cliente":
        grafo.sincronizar_conexion(usuario["id"], huella, ip)
    return _emitir_sesion(conn, response, usuario, portal, dispositivo_id, ip)


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


@router.post("/login", summary="Iniciar sesion (portal 'app' para clientes, 'intranet' para empleados)")
def login(datos: LoginEntrada, request: Request, response: Response, conn=Depends(obtener_conexion)):
    ip = ip_cliente(request)
    email = datos.email.lower()
    usuario = consultar_uno(conn, _SELECT_USUARIO + "WHERE email = %s", (email,))

    # 1) El correo no existe: verificamos un hash ficticio para tardar lo mismo
    if not usuario or not usuario["activo"]:
        contrasenas.verificar_ficticio(datos.password)
        _evento(conn, email, ip, False, usuario["id"] if usuario else None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENCIALES_INVALIDAS)

    # 2) Usuario bloqueado temporalmente por intentos fallidos
    if usuario["bloqueado"]:
        _evento(conn, email, ip, False, usuario["id"])
        raise HTTPException(status.HTTP_423_LOCKED,
                            "Usuario bloqueado temporalmente por intentos fallidos. Intente mas tarde.")

    # 3) Contrasena incorrecta: sumar intento y bloquear si llega al maximo
    if not contrasenas.verificar(usuario["password_hash"], datos.password):
        _registrar_fallo(conn, usuario["id"], ip)
        _evento(conn, email, ip, False, usuario["id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENCIALES_INVALIDAS)

    # 4) Puerta equivocada: un cliente en la Intranet o un empleado en la App
    if not _rol_permitido(usuario["rol"], datos.portal):
        _evento(conn, email, ip, False, usuario["id"])
        auditoria.registrar(conn, "LOGIN_PORTAL_INCORRECTO", "usuarios", usuario["id"],
                            detalle={"portal": datos.portal, "rol": usuario["rol"]}, ip=ip)
        destino = "la App Rosberg" if usuario["rol"] == "cliente" else "la Intranet Rosberg"
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Esta cuenta debe ingresar por {destino}")

    if contrasenas.necesita_rehash(usuario["password_hash"]):
        ejecutar(conn, "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                 (contrasenas.hashear(datos.password), usuario["id"]))

    # 5) Tiene 2FA activo: falta el codigo del celular
    if usuario["totp_activo"]:
        return {"requiere_2fa": True, "token_2fa": tokens.crear_paso_2fa(usuario["id"], datos.portal),
                "mensaje": "Escribe el codigo de 6 digitos de tu app autenticadora"}

    return _completar_login(conn, request, response, usuario, datos.portal)


@router.post("/2fa/verificar", response_model=TokenSalida, summary="Segundo paso del login: codigo del celular")
def verificar_2fa(datos: Verificar2FA, request: Request, response: Response, conn=Depends(obtener_conexion)):
    paso = tokens.decodificar(datos.token_2fa, "2fa")
    usuario = consultar_uno(conn, _SELECT_USUARIO + "WHERE id = %s", (int(paso["sub"]),))
    if not usuario or not usuario["activo"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no valido")
    if usuario["bloqueado"]:
        raise HTTPException(status.HTTP_423_LOCKED, "Usuario bloqueado temporalmente por intentos fallidos.")
    if not doble_factor.verificar_codigo(conn, usuario["id"], datos.codigo):
        # Los codigos fallidos cuentan para el bloqueo, igual que una contrasena mala
        _registrar_fallo(conn, usuario["id"], ip_cliente(request), "2FA_FALLIDO")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Codigo incorrecto o ya utilizado")
    return _completar_login(conn, request, response, usuario, paso["portal"])


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
    usuario = consultar_uno(conn, _SELECT_USUARIO + "WHERE id = %s", (sesion["usuario_id"],))
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


# ================================================================ 2FA
@router.get("/2fa/estado", summary="Estado de la verificacion en dos pasos")
def estado_2fa(u: UsuarioActual = Depends(usuario_actual), conn=Depends(obtener_conexion)):
    permitido = u.rol != "cliente" or doble_factor.interruptor(conn, "2FA_CLIENTES")
    return {
        "activo": u.tiene_2fa,
        "puede_activar": permitido,
        "obligatorio": u.rol != "cliente" and doble_factor.interruptor(conn, "2FA_EMPLEADOS"),
        "exigido_en_transferencias": u.rol == "cliente" and doble_factor.interruptor(conn, "2FA_TRANSFERENCIAS"),
        "monto_2fa": leer_config(conn, "MONTO_2FA"),
    }


@router.post("/2fa/iniciar", summary="Generar el codigo QR para vincular la app autenticadora")
def iniciar_2fa(u: UsuarioActual = Depends(usuario_actual), conn=Depends(obtener_conexion)):
    if u.tiene_2fa:
        raise HTTPException(status.HTTP_409_CONFLICT, "La verificacion en dos pasos ya esta activa")
    if u.rol == "cliente" and not doble_factor.interruptor(conn, "2FA_CLIENTES"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El banco aun no habilita la verificacion en dos pasos")
    secreto = doble_factor.nuevo_secreto()
    # Se guarda cifrado pero INACTIVO hasta que el usuario demuestre que lo escaneo bien
    ejecutar(conn, "UPDATE usuarios SET totp_secreto_cifrado = %s, totp_activo = FALSE WHERE id = %s",
             (cifrado.cifrar(secreto), u.id))
    uri = doble_factor.uri_configuracion(secreto, u.email)
    return {"qr_svg": doble_factor.qr_svg(uri), "secreto": secreto,
            "mensaje": "Escanea el codigo con Google Authenticator y escribe el codigo que aparece"}


@router.post("/2fa/confirmar", summary="Activar la verificacion en dos pasos con el primer codigo")
def confirmar_2fa(datos: CodigoEntrada, request: Request,
                  u: UsuarioActual = Depends(usuario_actual), conn=Depends(obtener_conexion)):
    fila = consultar_uno(conn, "SELECT totp_secreto_cifrado, totp_activo FROM usuarios WHERE id = %s", (u.id,))
    if fila["totp_activo"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya esta activa")
    if not fila["totp_secreto_cifrado"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Primero genera el codigo QR")
    if not doble_factor.verificar_secreto(cifrado.descifrar(fila["totp_secreto_cifrado"]), datos.codigo):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Codigo incorrecto. Revisa la hora de tu celular.")
    ejecutar(conn, "UPDATE usuarios SET totp_activo = TRUE WHERE id = %s", (u.id,))
    auditoria.registrar(conn, "2FA_ACTIVADO", "usuarios", u.id, usuario_id=u.id, ip=ip_cliente(request))
    return {"mensaje": "Verificacion en dos pasos activada. Desde ahora te pediremos el codigo al ingresar."}


@router.post("/2fa/desactivar", summary="Desactivar la verificacion en dos pasos")
def desactivar_2fa(datos: Desactivar2FA, request: Request,
                   u: UsuarioActual = Depends(usuario_actual), conn=Depends(obtener_conexion)):
    if u.rol != "cliente" and doble_factor.interruptor(conn, "2FA_EMPLEADOS"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Para empleados la verificacion en dos pasos es obligatoria")
    fila = consultar_uno(conn, "SELECT password_hash FROM usuarios WHERE id = %s", (u.id,))
    # Para desactivarla se piden LAS DOS cosas: contrasena y codigo
    if not contrasenas.verificar(fila["password_hash"], datos.password) or \
            not doble_factor.verificar_codigo(conn, u.id, datos.codigo):
        _registrar_fallo(conn, u.id, ip_cliente(request), "2FA_DESACTIVAR_FALLIDO")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Contrasena o codigo incorrectos")
    ejecutar(conn, "UPDATE usuarios SET totp_activo = FALSE, totp_secreto_cifrado = NULL, "
                   "totp_ultimo_paso = NULL WHERE id = %s", (u.id,))
    auditoria.registrar(conn, "2FA_DESACTIVADO", "usuarios", u.id, usuario_id=u.id, ip=ip_cliente(request))
    return {"mensaje": "Verificacion en dos pasos desactivada"}
