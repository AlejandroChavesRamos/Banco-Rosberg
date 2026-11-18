"""Operaciones de ventanilla: clientes, cuentas, depositos y canje de codigos de retiro."""
import secrets

from fastapi import APIRouter, Depends, Request

from ..db.mysql import consultar, consultar_uno, ejecutar, leer_config, llamar_sp, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import CanjeRetiro, ClienteVentanilla, CuentaVentanilla, DepositoEntrada
from ..seguridad import cifrado, contrasenas
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, banco, grafo
from ..utilidades import ip_cliente

router = APIRouter(prefix="/cajero", tags=["3. Cajero"])
cajero = requiere_rol("cajero", "admin")


def _cliente_por_cedula(conn, cedula: str) -> dict:
    cliente = consultar_uno(
        conn,
        "SELECT id, nombre, email, telefono_cifrado, activo FROM usuarios "
        "WHERE documento_hash = %s AND rol = 'cliente'",
        (cifrado.indice_ciego(cedula, "cedula"),),
    )
    if not cliente:
        raise ErrorNegocio(404, "No hay un cliente con esa cedula")
    return cliente


@router.post("/clientes", status_code=201, summary="Crear cliente en ventanilla")
def crear_cliente(datos: ClienteVentanilla, request: Request,
                  u: UsuarioActual = Depends(cajero), conn=Depends(obtener_conexion)):
    temporal = contrasenas.generar_temporal()
    creado = banco.crear_cliente(
        conn, nombre=datos.nombre, email=datos.email, cedula=datos.cedula, celular=datos.celular,
        password_hash=contrasenas.hashear(temporal), debe_cambiar=True, tipo_cuenta=datos.tipo_cuenta,
    )
    auditoria.registrar(conn, "REGISTRO_CLIENTE", "usuarios", creado["usuario_id"], usuario_id=u.id,
                        detalle={"canal": "ventanilla"}, ip=ip_cliente(request))
    return {
        "cuenta": creado["numero"],
        "password_temporal": temporal,
        "mensaje": "Entregue la contrasena temporal al cliente. Debera cambiarla al iniciar sesion. "
                   "No se volvera a mostrar.",
    }


@router.get("/clientes/{cedula}", summary="Buscar cliente por cedula")
def buscar_cliente(cedula: str, u: UsuarioActual = Depends(cajero), conn=Depends(obtener_conexion)):
    cliente = _cliente_por_cedula(conn, cedula)
    celular = cifrado.descifrar(cliente["telefono_cifrado"])
    cuentas = consultar(conn, "SELECT numero, tipo, saldo, estado FROM cuentas WHERE usuario_id = %s",
                        (cliente["id"],))
    return {"nombre": cliente["nombre"], "email": cliente["email"], "celular": "******" + celular[-4:],
            "activo": bool(cliente["activo"]), "cuentas": cuentas}


@router.post("/cuentas", status_code=201, summary="Abrir cuenta a un cliente existente")
def abrir_cuenta(datos: CuentaVentanilla, request: Request,
                 u: UsuarioActual = Depends(cajero), conn=Depends(obtener_conexion)):
    cliente = _cliente_por_cedula(conn, datos.cedula)
    total = consultar_uno(conn, "SELECT COUNT(*) AS n FROM cuentas WHERE usuario_id = %s AND estado <> 'cerrada'",
                          (cliente["id"],))["n"]
    if total >= leer_config(conn, "MAX_CUENTAS_CLIENTE"):
        raise ErrorNegocio(409, "El cliente alcanzo el maximo de cuentas")
    numero = banco.generar_numero_cuenta(conn)
    cur = ejecutar(conn, "INSERT INTO cuentas (numero, usuario_id, tipo) VALUES (%s, %s, %s)",
                   (numero, cliente["id"], datos.tipo))
    auditoria.registrar(conn, "APERTURA_CUENTA", "cuentas", cur.lastrowid, usuario_id=u.id,
                        detalle={"canal": "ventanilla", "tipo": datos.tipo}, ip=ip_cliente(request))
    grafo.sincronizar_cuenta(cur.lastrowid, numero, cliente["id"])
    return {"cuenta": numero, "titular": cliente["nombre"], "tipo": datos.tipo}


@router.post("/depositos", status_code=201, summary="Depositar efectivo en una cuenta")
def depositar(datos: DepositoEntrada, request: Request,
              u: UsuarioActual = Depends(cajero), conn=Depends(obtener_conexion)):
    cuenta = banco.cuenta_por_numero(conn, datos.cuenta)
    if not cuenta:
        raise ErrorNegocio(404, "Cuenta no encontrada")
    tx_id = llamar_sp(conn, "sp_depositar", [cuenta["id"], datos.monto, u.id, f"dep:{secrets.token_hex(16)}"])
    auditoria.registrar(conn, "DEPOSITO", "transacciones", tx_id, usuario_id=u.id,
                        detalle={"cuenta": cuenta["numero"], "monto": datos.monto}, ip=ip_cliente(request))
    return {"transaccion_id": tx_id, "cuenta": cuenta["numero"], "titular": cuenta["titular"],
            "monto": datos.monto, "mensaje": "Deposito exitoso"}


@router.post("/retiros/canjear", summary="Canjear un codigo de retiro (entregar efectivo)")
def canjear_retiro(datos: CanjeRetiro, request: Request,
                   u: UsuarioActual = Depends(cajero), conn=Depends(obtener_conexion)):
    ip = ip_cliente(request)
    cuenta = banco.cuenta_por_numero(conn, datos.cuenta)
    if not cuenta:
        raise ErrorNegocio(404, "Cuenta no encontrada")
    banco.exigir_activa(cuenta)

    ejecutar(conn, "UPDATE codigos_retiro SET estado = 'vencido' "
                   "WHERE cuenta_id = %s AND estado = 'activo' AND expira_en <= NOW()", (cuenta["id"],))
    codigo = consultar_uno(conn, "SELECT id, codigo_hash, monto, puntaje_riesgo FROM codigos_retiro "
                                 "WHERE cuenta_id = %s AND estado = 'activo' ORDER BY id DESC LIMIT 1",
                           (cuenta["id"],))
    if not codigo:
        raise ErrorNegocio(404, "La cuenta no tiene un codigo de retiro vigente")

    titular = consultar_uno(conn, "SELECT documento_hash FROM usuarios WHERE id = %s", (cuenta["usuario_id"],))
    cedula_ok = cifrado.iguales(titular["documento_hash"] or "", cifrado.indice_ciego(datos.cedula, "cedula"))
    codigo_ok = cifrado.iguales(codigo["codigo_hash"],
                                cifrado.indice_ciego(datos.codigo, f"retiro:{cuenta['id']}"))

    if not (cedula_ok and codigo_ok):
        maximo = leer_config(conn, "INTENTOS_CODIGO_RETIRO")
        ejecutar(conn,
                 "UPDATE codigos_retiro SET estado = IF(intentos_fallidos + 1 >= %s, 'bloqueado', estado), "
                 "intentos_fallidos = intentos_fallidos + 1 WHERE id = %s",
                 (maximo, codigo["id"]))
        estado = consultar_uno(conn, "SELECT estado FROM codigos_retiro WHERE id = %s", (codigo["id"],))["estado"]
        auditoria.registrar(conn, "CANJE_RETIRO_FALLIDO", "codigos_retiro", codigo["id"], usuario_id=u.id,
                            detalle={"cuenta": cuenta["numero"], "cedula_correcta": cedula_ok}, ip=ip)
        if estado == "bloqueado":
            banco.registrar_alerta(conn, cuenta["id"], 50, [{
                "codigo": "CODIGO_RETIRO_FUERZA_BRUTA", "peso": 50,
                "detalle": f"Codigo bloqueado tras {maximo} intentos fallidos de canje en ventanilla"}])
            raise ErrorNegocio(423, "Codigo bloqueado por demasiados intentos fallidos")
        raise ErrorNegocio(400, "Los datos no coinciden")

    # La clave de idempotencia depende del codigo: aunque dos cajeros lo
    # canjeen al mismo tiempo, el retiro solo se ejecuta una vez.
    tx_id = llamar_sp(conn, "sp_retirar", [
        cuenta["id"], codigo["monto"], "aprobada", codigo["puntaje_riesgo"], ip, None, u.id,
        f"retiro-codigo-{codigo['id']}",
    ])
    ejecutar(conn, "UPDATE codigos_retiro SET estado = 'usado', usado_en = NOW(), canjeado_por = %s, "
                   "transaccion_id = %s WHERE id = %s", (u.id, tx_id, codigo["id"]))
    auditoria.registrar(conn, "RETIRO", "transacciones", tx_id, usuario_id=u.id,
                        detalle={"cuenta": cuenta["numero"], "monto": codigo["monto"], "codigo_id": codigo["id"]},
                        ip=ip)
    return {"transaccion_id": tx_id, "titular": cuenta["titular"], "monto": codigo["monto"],
            "mensaje": "Retiro aprobado. Entregue el efectivo al cliente."}
