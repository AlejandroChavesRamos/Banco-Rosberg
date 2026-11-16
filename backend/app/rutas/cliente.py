"""Operaciones del cliente: cuentas, movimientos, llaves, transferencias y codigos de retiro."""
import secrets

from fastapi import APIRouter, Depends, Header, Request

from ..antifraude import motor
from ..db.mysql import consultar, consultar_uno, ejecutar, leer_config, llamar_sp, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import CodigoRetiroEntrada, NuevaCuenta, NuevaLlave, TransferenciaEntrada
from ..seguridad import cifrado, doble_factor
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, banco, grafo
from ..utilidades import enmascarar_nombre, enmascarar_numero, huella_dispositivo, ip_cliente

router = APIRouter(tags=["2. Cliente"])
solo_cliente = requiere_rol("cliente")
cualquier_rol = requiere_rol("cliente", "cajero", "analista", "admin")


# ================================================================== cuentas
@router.get("/cuentas", summary="Mis cuentas")
def mis_cuentas(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    return consultar(conn, "SELECT numero, tipo, saldo, estado, creada_en FROM cuentas "
                           "WHERE usuario_id = %s ORDER BY id", (u.id,))


@router.post("/cuentas", status_code=201, summary="Abrir otra cuenta")
def abrir_cuenta(datos: NuevaCuenta, request: Request,
                 u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    total = consultar_uno(conn, "SELECT COUNT(*) AS n FROM cuentas WHERE usuario_id = %s", (u.id,))["n"]
    if total >= leer_config(conn, "MAX_CUENTAS_CLIENTE"):
        raise ErrorNegocio(409, "Alcanzo el maximo de cuentas permitidas")
    numero = banco.generar_numero_cuenta(conn)
    cur = ejecutar(conn, "INSERT INTO cuentas (numero, usuario_id, tipo) VALUES (%s, %s, %s)",
                   (numero, u.id, datos.tipo))
    auditoria.registrar(conn, "APERTURA_CUENTA", "cuentas", cur.lastrowid, usuario_id=u.id,
                        detalle={"canal": "en_linea", "tipo": datos.tipo}, ip=ip_cliente(request))
    grafo.sincronizar_cuenta(cur.lastrowid, numero, u.id)
    return {"cuenta": numero, "tipo": datos.tipo}


@router.get("/cuentas/{numero}/movimientos", summary="Movimientos de una cuenta")
def movimientos(numero: str, u: UsuarioActual = Depends(cualquier_rol), conn=Depends(obtener_conexion)):
    if u.rol == "cliente":
        cuenta = banco.cuenta_propia(conn, numero, u.id)
    else:
        cuenta = banco.cuenta_por_numero(conn, numero)
        if not cuenta:
            raise ErrorNegocio(404, "Cuenta no encontrada")

    filas = consultar(
        conn,
        "SELECT t.id, t.tipo, t.monto, t.estado, t.creada_en, t.cuenta_origen_id, "
        "co.numero AS origen, cd.numero AS destino "
        "FROM transacciones t "
        "LEFT JOIN cuentas co ON co.id = t.cuenta_origen_id "
        "LEFT JOIN cuentas cd ON cd.id = t.cuenta_destino_id "
        "WHERE t.cuenta_origen_id = %s OR t.cuenta_destino_id = %s "
        "ORDER BY t.creada_en DESC LIMIT 50",
        (cuenta["id"], cuenta["id"]),
    )
    resultado = []
    for f in filas:
        salida = f["cuenta_origen_id"] == cuenta["id"]
        contraparte = f["destino"] if salida else f["origen"]
        resultado.append({
            "id": f["id"], "tipo": f["tipo"], "sentido": "salida" if salida else "entrada",
            "monto": f["monto"], "estado": f["estado"], "fecha": f["creada_en"],
            "contraparte": enmascarar_numero(contraparte) if contraparte else None,
        })
    return {"cuenta": cuenta["numero"], "saldo": cuenta["saldo"], "estado": cuenta["estado"],
            "movimientos": resultado}


# =================================================================== llaves
@router.get("/llaves", summary="Mis llaves")
def mis_llaves(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    return consultar(
        conn,
        "SELECT l.id, l.tipo, l.valor, c.numero AS cuenta, l.creada_en FROM llaves l "
        "JOIN cuentas c ON c.id = l.cuenta_id WHERE c.usuario_id = %s AND l.activa ORDER BY l.id",
        (u.id,),
    )


@router.post("/llaves", status_code=201, summary="Registrar mi celular o correo como llave")
def crear_llave(datos: NuevaLlave, request: Request,
                u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    cuenta = banco.cuenta_propia(conn, datos.cuenta, u.id)
    banco.exigir_activa(cuenta)
    # El valor de la llave sale de los datos verificados del cliente, no de lo
    # que escriba: nadie puede registrar el celular o correo de otra persona.
    if datos.tipo == "correo":
        valor = u.email
    else:
        fila = consultar_uno(conn, "SELECT telefono_cifrado FROM usuarios WHERE id = %s", (u.id,))
        valor = cifrado.descifrar(fila["telefono_cifrado"])
    if consultar_uno(conn, "SELECT 1 FROM llaves WHERE tipo = %s AND valor = %s AND activa",
                     (datos.tipo, valor)):
        raise ErrorNegocio(409, f"Su {datos.tipo} ya esta registrado como llave")
    cur = ejecutar(conn, "INSERT INTO llaves (cuenta_id, tipo, valor) VALUES (%s, %s, %s)",
                   (cuenta["id"], datos.tipo, valor))
    auditoria.registrar(conn, "LLAVE_CREADA", "llaves", cur.lastrowid, usuario_id=u.id,
                        detalle={"tipo": datos.tipo, "cuenta": cuenta["numero"]}, ip=ip_cliente(request))
    return {"id": cur.lastrowid, "tipo": datos.tipo, "valor": valor, "cuenta": cuenta["numero"]}


@router.delete("/llaves/{llave_id}", summary="Desactivar una llave")
def borrar_llave(llave_id: int, request: Request,
                 u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    llave = consultar_uno(conn, "SELECT l.id FROM llaves l JOIN cuentas c ON c.id = l.cuenta_id "
                                "WHERE l.id = %s AND c.usuario_id = %s AND l.activa", (llave_id, u.id))
    if not llave:
        raise ErrorNegocio(404, "Llave no encontrada")
    # No se borra (el usuario de la app no tiene DELETE): se desactiva y queda el historial
    ejecutar(conn, "UPDATE llaves SET activa = FALSE WHERE id = %s", (llave_id,))
    auditoria.registrar(conn, "LLAVE_DESACTIVADA", "llaves", llave_id, usuario_id=u.id, ip=ip_cliente(request))
    return {"mensaje": "Llave desactivada"}


# ============================================================ transferencias
@router.get("/transferencias/destinatario", summary="Ver a quien le voy a transferir (datos enmascarados)")
def consultar_destinatario(valor: str, u: UsuarioActual = Depends(solo_cliente),
                           conn=Depends(obtener_conexion)):
    cuenta = banco.resolver_destino(conn, valor)
    return {"titular": enmascarar_nombre(cuenta["titular"]),
            "cuenta": enmascarar_numero(cuenta["numero"]), "tipo": cuenta["tipo"]}


@router.post("/transferencias", status_code=201, summary="Transferir dinero")
def transferir(
    datos: TransferenciaEntrada,
    request: Request,
    idempotency_key: str | None = Header(default=None, max_length=50,
                                         description="Identificador unico de la operacion. Si se repite "
                                                     "(doble clic, reintento) no se duplica la transferencia."),
    u: UsuarioActual = Depends(solo_cliente),
    conn=Depends(obtener_conexion),
):
    origen = banco.cuenta_propia(conn, datos.cuenta_origen, u.id)
    banco.exigir_activa(origen)
    destino = banco.resolver_destino(conn, datos.destino)
    if destino["id"] == origen["id"]:
        raise ErrorNegocio(400, "No puede transferir a la misma cuenta")

    # La clave se prefija con el id del usuario: nadie puede "adivinar" la de otro
    clave = f"{u.id}:{idempotency_key or secrets.token_hex(16)}"
    previa = consultar_uno(conn, "SELECT id, estado FROM transacciones WHERE clave_idempotencia = %s", (clave,))
    if previa:
        return {"transaccion_id": previa["id"], "estado": previa["estado"], "repetida": True}

    # Verificacion en dos pasos para montos grandes (si el admin la encendio)
    monto_2fa = leer_config(conn, "MONTO_2FA")
    if datos.monto >= monto_2fa and doble_factor.interruptor(conn, "2FA_TRANSFERENCIAS"):
        if not u.tiene_2fa:
            raise ErrorNegocio(403, "Para enviar montos desde $" + f"{monto_2fa:,}".replace(",", ".")
                               + " debes activar la verificacion en dos pasos")
        if not datos.codigo_2fa:
            # 428 = "falta una condicion previa": la pantalla pide el codigo y reintenta
            raise ErrorNegocio(428, "Escribe el codigo de tu app autenticadora para confirmar este envio")
        if not doble_factor.verificar_codigo(conn, u.id, datos.codigo_2fa):
            raise ErrorNegocio(400, "Codigo de verificacion incorrecto o ya utilizado")

    ip = ip_cliente(request)
    huella, agente = huella_dispositivo(request)
    dispositivo_id, es_nuevo = banco.registrar_dispositivo(conn, u.id, huella, agente)

    evaluacion = motor.evaluar(conn, motor.ContextoOperacion(
        tipo="transferencia", cuenta_origen_id=origen["id"], cuenta_destino_id=destino["id"],
        monto=datos.monto, usuario_id=u.id, dispositivo_id=dispositivo_id,
        dispositivo_nuevo=es_nuevo, huella=huella, ip=ip,
    ))

    tx_id = llamar_sp(conn, "sp_transferir", [
        origen["id"], destino["id"], datos.monto, evaluacion.decision,
        evaluacion.puntaje, ip, dispositivo_id, clave,
    ])
    tx = consultar_uno(conn, "SELECT id, estado, puntaje_riesgo, creada_en FROM transacciones WHERE id = %s",
                       (tx_id,))

    if tx["estado"] != "aprobada":
        banco.registrar_alerta(conn, origen["id"], tx["puntaje_riesgo"], evaluacion.motivos, tx["id"])
    auditoria.registrar(conn, "TRANSFERENCIA", "transacciones", tx["id"], usuario_id=u.id,
                        detalle={"origen": origen["numero"], "destino": destino["numero"],
                                 "monto": datos.monto, "estado": tx["estado"], "puntaje": tx["puntaje_riesgo"],
                                 "motivos": [m["codigo"] for m in evaluacion.motivos]},
                        ip=ip)
    grafo.sincronizar_transferencia(tx["id"], origen["id"], destino["id"], datos.monto,
                                    tx["creada_en"], tx["estado"])

    mensajes = {
        "aprobada": "Transferencia exitosa",
        "retenida": "La transferencia esta en revision por seguridad. Le avisaremos cuando se resuelva.",
        "bloqueada": "La transferencia fue bloqueada por seguridad. Comuniquese con el banco.",
    }
    return {"transaccion_id": tx["id"], "estado": tx["estado"], "mensaje": mensajes[tx["estado"]],
            "destinatario": enmascarar_nombre(destino["titular"]), "monto": datos.monto}


# ========================================================= codigos de retiro
@router.post("/retiros/codigo", status_code=201, summary="Generar un codigo de retiro sin tarjeta")
def generar_codigo_retiro(datos: CodigoRetiroEntrada, request: Request,
                          u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    cuenta = banco.cuenta_propia(conn, datos.cuenta, u.id)
    banco.exigir_activa(cuenta)
    if datos.monto > leer_config(conn, "RETIRO_MAXIMO"):
        raise ErrorNegocio(400, "El monto supera el maximo permitido por codigo de retiro")
    if cuenta["saldo"] < datos.monto:
        raise ErrorNegocio(400, "Saldo insuficiente")

    ip = ip_cliente(request)
    huella, agente = huella_dispositivo(request)
    dispositivo_id, es_nuevo = banco.registrar_dispositivo(conn, u.id, huella, agente)
    evaluacion = motor.evaluar(conn, motor.ContextoOperacion(
        tipo="retiro", cuenta_origen_id=cuenta["id"], monto=datos.monto, usuario_id=u.id,
        dispositivo_id=dispositivo_id, dispositivo_nuevo=es_nuevo, huella=huella, ip=ip,
    ))
    if evaluacion.decision != "aprobada":
        # Un retiro en efectivo no se puede "devolver": ante la duda, no se entrega codigo
        banco.registrar_alerta(conn, cuenta["id"], evaluacion.puntaje, evaluacion.motivos)
        auditoria.registrar(conn, "CODIGO_RETIRO_" + evaluacion.decision.upper(), "cuentas", cuenta["id"],
                            usuario_id=u.id, ip=ip,
                            detalle={"monto": datos.monto, "puntaje": evaluacion.puntaje,
                                     "motivos": [m["codigo"] for m in evaluacion.motivos]})
        if evaluacion.decision == "bloqueada":
            raise ErrorNegocio(403, "Operacion bloqueada por seguridad. Comuniquese con el banco.")
        raise ErrorNegocio(409, "Por seguridad, este retiro debe hacerse en una oficina con su documento.")

    # Solo un codigo activo por cuenta
    ejecutar(conn, "UPDATE codigos_retiro SET estado = 'cancelado' WHERE cuenta_id = %s AND estado = 'activo'",
             (cuenta["id"],))
    codigo = f"{secrets.randbelow(10**6):06d}"   # 'secrets', no 'random': impredecible
    vigencia = leer_config(conn, "VIGENCIA_CODIGO_RETIRO")
    cur = ejecutar(
        conn,
        "INSERT INTO codigos_retiro (cuenta_id, codigo_hash, monto, puntaje_riesgo, expira_en) "
        "VALUES (%s, %s, %s, %s, NOW() + INTERVAL %s MINUTE)",
        (cuenta["id"], cifrado.indice_ciego(codigo, f"retiro:{cuenta['id']}"), datos.monto,
         evaluacion.puntaje, vigencia),
    )
    expira = consultar_uno(conn, "SELECT expira_en FROM codigos_retiro WHERE id = %s", (cur.lastrowid,))
    # En la auditoria NUNCA se guarda el codigo
    auditoria.registrar(conn, "CODIGO_RETIRO_GENERADO", "codigos_retiro", cur.lastrowid, usuario_id=u.id,
                        detalle={"cuenta": cuenta["numero"], "monto": datos.monto}, ip=ip)
    return {"codigo": codigo, "monto": datos.monto, "expira_en": expira["expira_en"],
            "mensaje": "Presente este codigo y su cedula en ventanilla. Solo se muestra una vez."}


@router.get("/retiros/codigos", summary="Mis codigos de retiro")
def mis_codigos(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    ejecutar(conn, "UPDATE codigos_retiro r JOIN cuentas c ON c.id = r.cuenta_id "
                   "SET r.estado = 'vencido' WHERE c.usuario_id = %s AND r.estado = 'activo' "
                   "AND r.expira_en <= NOW()", (u.id,))
    return consultar(
        conn,
        "SELECT r.id, c.numero AS cuenta, r.monto, r.estado, r.creado_en, r.expira_en, r.usado_en "
        "FROM codigos_retiro r JOIN cuentas c ON c.id = r.cuenta_id "
        "WHERE c.usuario_id = %s ORDER BY r.id DESC LIMIT 20",
        (u.id,),
    )
