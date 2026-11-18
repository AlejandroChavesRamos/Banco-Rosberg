"""Operaciones del cliente: cuentas, movimientos, llaves, transferencias y codigos de retiro."""
import secrets

from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Request

from ..antifraude import motor
from ..db.mysql import consultar, consultar_uno, ejecutar, leer_config, llamar_sp, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import (CerrarCuentaEntrada, CodigoRetiroEntrada, MetaEntrada, MovimientoMeta, NuevaCuenta,
                        NuevaLlave, TransferenciaEntrada)
from ..seguridad import cifrado, contrasenas, doble_factor
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, banco, grafo
from ..utilidades import enmascarar_nombre, enmascarar_numero, huella_dispositivo, ip_cliente

router = APIRouter(tags=["2. Cliente"])
solo_cliente = requiere_rol("cliente")
cualquier_rol = requiere_rol("cliente", "cajero", "analista", "admin")


# =================================================================== perfil
@router.get("/perfil", summary="Mis datos (cedula y celular enmascarados)")
def mi_perfil(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    fila = consultar_uno(conn, "SELECT documento_cifrado, telefono_cifrado, creado_en FROM usuarios WHERE id = %s",
                         (u.id,))
    cuentas = consultar_uno(conn, "SELECT COUNT(*) AS n FROM cuentas WHERE usuario_id = %s AND estado <> 'cerrada'",
                            (u.id,))["n"]

    def _ultimos(cifrado_bytes, visibles: int) -> str | None:
        # Solo se muestran los ultimos digitos: la pantalla nunca recibe el dato completo
        if not cifrado_bytes:
            return None
        valor = cifrado.descifrar(cifrado_bytes)
        return "*" * (len(valor) - visibles) + valor[-visibles:]

    return {"nombre": u.nombre, "email": u.email,
            "cedula": _ultimos(fila["documento_cifrado"], 3),
            "celular": _ultimos(fila["telefono_cifrado"], 4),
            "cliente_desde": fila["creado_en"], "cuentas": cuentas}


# ================================================================== cuentas
@router.get("/cuentas", summary="Mis cuentas")
def mis_cuentas(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    # Las cuentas cerradas no se muestran. "apartado" es lo guardado en metas de ahorro.
    return consultar(
        conn,
        "SELECT c.numero, c.tipo, c.saldo, c.estado, c.creada_en, "
        "COALESCE((SELECT SUM(m.apartado) FROM metas_ahorro m WHERE m.cuenta_id = c.id AND m.activa), 0) AS apartado "
        "FROM cuentas c WHERE c.usuario_id = %s AND c.estado <> 'cerrada' ORDER BY c.id",
        (u.id,),
    )


@router.post("/cuentas", status_code=201, summary="Abrir otra cuenta")
def abrir_cuenta(datos: NuevaCuenta, request: Request,
                 u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    total = consultar_uno(conn, "SELECT COUNT(*) AS n FROM cuentas WHERE usuario_id = %s AND estado <> 'cerrada'",
                          (u.id,))["n"]
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
def movimientos(
    numero: str,
    desde: date | None = Query(default=None, description="Solo movimientos desde este dia (AAAA-MM-DD)"),
    hasta: date | None = Query(default=None, description="Solo movimientos hasta este dia, incluido"),
    limite: int = Query(default=50, ge=1, le=500),
    u: UsuarioActual = Depends(cualquier_rol),
    conn=Depends(obtener_conexion),
):
    if u.rol == "cliente":
        cuenta = banco.cuenta_propia(conn, numero, u.id)
    else:
        cuenta = banco.cuenta_por_numero(conn, numero)
        if not cuenta:
            raise ErrorNegocio(404, "Cuenta no encontrada")

    filas = consultar(
        conn,
        "SELECT t.id, t.tipo, t.monto, t.estado, t.creada_en, t.cuenta_origen_id, t.mensaje, "
        "co.numero AS origen, cd.numero AS destino "
        "FROM transacciones t "
        "LEFT JOIN cuentas co ON co.id = t.cuenta_origen_id "
        "LEFT JOIN cuentas cd ON cd.id = t.cuenta_destino_id "
        "WHERE (t.cuenta_origen_id = %s OR t.cuenta_destino_id = %s) "
        "AND (%s IS NULL OR t.creada_en >= %s) "
        "AND (%s IS NULL OR t.creada_en < %s + INTERVAL 1 DAY) "
        "ORDER BY t.creada_en DESC LIMIT %s",
        (cuenta["id"], cuenta["id"], desde, desde, hasta, hasta, limite),
    )
    resultado = []
    for f in filas:
        salida = f["cuenta_origen_id"] == cuenta["id"]
        contraparte = f["destino"] if salida else f["origen"]
        resultado.append({
            "id": f["id"], "tipo": f["tipo"], "sentido": "salida" if salida else "entrada",
            "monto": f["monto"], "estado": f["estado"], "fecha": f["creada_en"],
            "contraparte": enmascarar_numero(contraparte) if contraparte else None,
            "mensaje": f["mensaje"],
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
    banco.exigir_disponible(conn, origen, datos.monto)
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
        evaluacion.puntaje, ip, dispositivo_id, clave, datos.mensaje,
    ])
    tx = consultar_uno(conn, "SELECT id, estado, puntaje_riesgo, creada_en FROM transacciones WHERE id = %s",
                       (tx_id,))

    if tx["estado"] != "aprobada":
        banco.registrar_alerta(conn, origen["id"], tx["puntaje_riesgo"], evaluacion.motivos, tx["id"])
    auditoria.registrar(conn, "TRANSFERENCIA", "transacciones", tx["id"], usuario_id=u.id,
                        detalle={"origen": origen["numero"], "destino": destino["numero"],
                                 "monto": datos.monto, "estado": tx["estado"], "puntaje": tx["puntaje_riesgo"],
                                 "motivos": [m["codigo"] for m in evaluacion.motivos],
                                 "con_mensaje": datos.mensaje is not None},
                        ip=ip)
    grafo.sincronizar_transferencia(tx["id"], origen["id"], destino["id"], datos.monto,
                                    tx["creada_en"], tx["estado"])

    mensajes = {
        "aprobada": "Transferencia exitosa",
        "retenida": "La transferencia esta en revision por seguridad. Le avisaremos cuando se resuelva.",
        "bloqueada": "La transferencia fue bloqueada por seguridad. Comuniquese con el banco.",
    }
    return {"transaccion_id": tx["id"], "estado": tx["estado"], "mensaje": mensajes[tx["estado"]],
            "destinatario": enmascarar_nombre(destino["titular"]), "monto": datos.monto,
            # Datos para el comprobante
            "mensaje_envio": datos.mensaje,  # la nota del cliente ("mensaje" es el texto del resultado)
            "fecha": tx["creada_en"], "cuenta_origen": enmascarar_numero(origen["numero"]),
            "cuenta_destino": enmascarar_numero(destino["numero"])}


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
    banco.exigir_disponible(conn, cuenta, datos.monto)

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


# ============================================================ cerrar cuenta
@router.post("/cuentas/{numero}/cerrar", summary="Cerrar una de mis cuentas")
def cerrar_cuenta(numero: str, datos: CerrarCuentaEntrada, request: Request,
                  u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    """En un banco las cuentas no se borran: se CIERRAN. Sus movimientos y la
    auditoria se conservan; la cuenta deja de mostrarse y no puede volver a usarse.

    Si tiene saldo, primero se traslada a otra cuenta propia (queda como una
    transferencia normal en el historial).
    """
    ip = ip_cliente(request)
    fila = consultar_uno(conn, "SELECT password_hash FROM usuarios WHERE id = %s", (u.id,))
    if not contrasenas.verificar(fila["password_hash"], datos.password):
        raise ErrorNegocio(400, "La contrasena no es correcta")

    cuenta = banco.cuenta_propia(conn, numero, u.id)
    if cuenta["estado"] != "activa":
        raise ErrorNegocio(409, f"La cuenta esta {cuenta['estado']}: comuniquese con el banco")
    otras = consultar_uno(conn, "SELECT COUNT(*) AS n FROM cuentas WHERE usuario_id = %s AND estado = 'activa' "
                                "AND id <> %s", (u.id, cuenta["id"]))["n"]
    if otras == 0:
        raise ErrorNegocio(409, "No puedes cerrar tu unica cuenta activa")
    if consultar_uno(conn, "SELECT 1 FROM transacciones WHERE (cuenta_origen_id = %s OR cuenta_destino_id = %s) "
                           "AND estado = 'retenida' LIMIT 1", (cuenta["id"], cuenta["id"])):
        raise ErrorNegocio(409, "La cuenta tiene operaciones en revision. Espera a que se resuelvan.")

    trasladado = 0
    if cuenta["saldo"] > 0:
        if not datos.destino:
            raise ErrorNegocio(400, "Elige a cual de tus cuentas pasamos el saldo")
        destino = banco.cuenta_propia(conn, datos.destino, u.id)
        banco.exigir_activa(destino)
        if destino["id"] == cuenta["id"]:
            raise ErrorNegocio(400, "Elige una cuenta diferente a la que vas a cerrar")
        huella, agente = huella_dispositivo(request)
        dispositivo_id, _ = banco.registrar_dispositivo(conn, u.id, huella, agente)
        # Traslado entre cuentas del mismo cliente: no pasa por el motor antifraude
        tx_id = llamar_sp(conn, "sp_transferir", [
            cuenta["id"], destino["id"], cuenta["saldo"], "aprobada", 0, ip, dispositivo_id,
            f"{u.id}:cierre:{cuenta['id']}", "Cierre de cuenta: traslado del saldo",
        ])
        tx = consultar_uno(conn, "SELECT creada_en FROM transacciones WHERE id = %s", (tx_id,))
        grafo.sincronizar_transferencia(tx_id, cuenta["id"], destino["id"], cuenta["saldo"], tx["creada_en"], "aprobada")
        trasladado = cuenta["saldo"]

    # Lo que dependia de la cuenta deja de funcionar
    ejecutar(conn, "UPDATE metas_ahorro SET activa = FALSE, apartado = 0 WHERE cuenta_id = %s AND activa",
             (cuenta["id"],))
    ejecutar(conn, "UPDATE llaves SET activa = FALSE WHERE cuenta_id = %s AND activa", (cuenta["id"],))
    banco.cambiar_estado_cuenta(conn, cuenta, "cerrada")  # tambien cancela los codigos de retiro
    auditoria.registrar(conn, "CIERRE_CUENTA", "cuentas", cuenta["id"], usuario_id=u.id,
                        detalle={"canal": "en_linea", "saldo_trasladado": trasladado,
                                 "destino": datos.destino if trasladado else None}, ip=ip)
    return {"cuenta": numero, "estado": "cerrada", "saldo_trasladado": trasladado}


# =========================================================== metas de ahorro
def _meta_propia(conn, meta_id: int, usuario_id: int) -> dict:
    meta = consultar_uno(
        conn,
        "SELECT m.id, m.nombre, m.objetivo, m.apartado, m.cuenta_id, c.numero, c.saldo, c.estado "
        "FROM metas_ahorro m JOIN cuentas c ON c.id = m.cuenta_id "
        "WHERE m.id = %s AND m.usuario_id = %s AND m.activa",
        (meta_id, usuario_id),
    )
    if not meta:
        raise ErrorNegocio(404, "Meta no encontrada")
    return meta


@router.get("/metas", summary="Mis metas de ahorro")
def mis_metas(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    return consultar(
        conn,
        "SELECT m.id, m.nombre, m.objetivo, m.apartado, m.creada_en, c.numero AS cuenta "
        "FROM metas_ahorro m JOIN cuentas c ON c.id = m.cuenta_id "
        "WHERE m.usuario_id = %s AND m.activa ORDER BY m.id",
        (u.id,),
    )


@router.post("/metas", status_code=201, summary="Crear una meta de ahorro")
def crear_meta(datos: MetaEntrada, request: Request, u: UsuarioActual = Depends(solo_cliente),
               conn=Depends(obtener_conexion)):
    cuenta = banco.cuenta_propia(conn, datos.cuenta, u.id)
    banco.exigir_activa(cuenta)
    activas = consultar_uno(conn, "SELECT COUNT(*) AS n FROM metas_ahorro WHERE usuario_id = %s AND activa",
                            (u.id,))["n"]
    if activas >= 10:
        raise ErrorNegocio(409, "Puedes tener hasta 10 metas activas")
    cur = ejecutar(conn, "INSERT INTO metas_ahorro (usuario_id, cuenta_id, nombre, objetivo) VALUES (%s, %s, %s, %s)",
                   (u.id, cuenta["id"], datos.nombre.strip(), datos.objetivo))
    auditoria.registrar(conn, "CREAR_META", "metas_ahorro", cur.lastrowid, usuario_id=u.id,
                        detalle={"objetivo": datos.objetivo}, ip=ip_cliente(request))
    return {"id": cur.lastrowid}


@router.post("/metas/{meta_id}/apartar", summary="Apartar dinero de la cuenta en una meta")
def apartar_en_meta(meta_id: int, datos: MovimientoMeta, request: Request,
                    u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    meta = _meta_propia(conn, meta_id, u.id)
    if meta["estado"] != "activa":
        raise ErrorNegocio(409, f"La cuenta esta {meta['estado']}")
    disponible = meta["saldo"] - banco.apartado_en_metas(conn, meta["cuenta_id"])
    if datos.monto > disponible:
        raise ErrorNegocio(400, f"Solo tienes ${max(disponible, 0):,.0f} disponible en esa cuenta".replace(",", "."))
    ejecutar(conn, "UPDATE metas_ahorro SET apartado = apartado + %s WHERE id = %s", (datos.monto, meta_id))
    auditoria.registrar(conn, "APARTAR_META", "metas_ahorro", meta_id, usuario_id=u.id,
                        detalle={"monto": datos.monto}, ip=ip_cliente(request))
    return {"id": meta_id, "apartado": meta["apartado"] + datos.monto}


@router.post("/metas/{meta_id}/liberar", summary="Devolver dinero de una meta al disponible de la cuenta")
def liberar_de_meta(meta_id: int, datos: MovimientoMeta, request: Request,
                    u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    meta = _meta_propia(conn, meta_id, u.id)
    if datos.monto > meta["apartado"]:
        raise ErrorNegocio(400, "No puedes liberar mas de lo que tienes apartado en la meta")
    ejecutar(conn, "UPDATE metas_ahorro SET apartado = apartado - %s WHERE id = %s", (datos.monto, meta_id))
    auditoria.registrar(conn, "LIBERAR_META", "metas_ahorro", meta_id, usuario_id=u.id,
                        detalle={"monto": datos.monto}, ip=ip_cliente(request))
    return {"id": meta_id, "apartado": meta["apartado"] - datos.monto}


@router.delete("/metas/{meta_id}", summary="Eliminar una meta (lo apartado vuelve al disponible)")
def eliminar_meta(meta_id: int, request: Request, u: UsuarioActual = Depends(solo_cliente),
                  conn=Depends(obtener_conexion)):
    meta = _meta_propia(conn, meta_id, u.id)
    ejecutar(conn, "UPDATE metas_ahorro SET activa = FALSE, apartado = 0 WHERE id = %s", (meta_id,))
    auditoria.registrar(conn, "ELIMINAR_META", "metas_ahorro", meta_id, usuario_id=u.id,
                        detalle={"liberado": meta["apartado"]}, ip=ip_cliente(request))
    return {"id": meta_id, "liberado": meta["apartado"]}
