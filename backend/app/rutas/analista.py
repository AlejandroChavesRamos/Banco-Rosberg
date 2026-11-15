"""Panel del analista de fraude: alertas, resolucion y congelamiento de cuentas."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, Request

from ..antifraude import barrido
from ..db.mysql import consultar, consultar_uno, ejecutar, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import MotivoCongelar, ResolverAlerta
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, banco, grafo
from ..utilidades import ip_cliente

router = APIRouter(prefix="/analista", tags=["4. Analista de fraude"])
analista = requiere_rol("analista", "admin")


@router.get("/alertas", summary="Alertas pendientes (mayor riesgo primero) o ya resueltas")
def alertas(estado: Literal["pendientes", "resueltas"] = "pendientes",
            u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    if estado == "pendientes":
        filtro, orden = "a.estado IN ('abierta', 'en_revision')", "a.puntaje DESC, a.creada_en DESC"
    else:
        filtro, orden = "a.estado IN ('confirmada', 'descartada')", "a.resuelta_en DESC"
    filas = consultar(
        conn,
        f"""
        SELECT a.id AS alerta_id, a.puntaje, a.motivos, a.estado, a.creada_en, a.resuelta_en, a.nota,
               c.numero AS cuenta, c.estado AS estado_cuenta, u.nombre AS titular,
               t.id AS transaccion_id, t.tipo, t.monto, t.estado AS estado_transaccion,
               an.nombre AS analista
        FROM alertas_fraude a
        JOIN cuentas c       ON c.id = a.cuenta_id
        JOIN usuarios u      ON u.id = c.usuario_id
        LEFT JOIN transacciones t ON t.id = a.transaccion_id
        LEFT JOIN usuarios an     ON an.id = a.analista_id
        WHERE {filtro}
        ORDER BY {orden}
        LIMIT 300
        """,
    )
    for f in filas:
        f["motivos"] = json.loads(f["motivos"])
    return filas


@router.post("/alertas/{alerta_id}/reabrir", summary="Reabrir una alerta resuelta (motivo obligatorio)")
def reabrir(alerta_id: int, datos: MotivoCongelar, request: Request,
            u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    alerta = consultar_uno(conn, "SELECT id, estado, nota FROM alertas_fraude WHERE id = %s", (alerta_id,))
    if not alerta:
        raise ErrorNegocio(404, "Alerta no encontrada")
    if alerta["estado"] not in ("confirmada", "descartada"):
        raise ErrorNegocio(409, "La alerta no esta resuelta")
    # La nota anterior NO se borra: se agrega el motivo de la reapertura
    nota = (alerta["nota"] or "").strip()
    nota += f"\n[Reabierta por {u.nombre}: {datos.motivo}]"
    ejecutar(conn, "UPDATE alertas_fraude SET estado = 'abierta', resuelta_en = NULL, nota = %s WHERE id = %s",
             (nota.strip(), alerta_id))
    auditoria.registrar(conn, "REABRIR_ALERTA", "alertas_fraude", alerta_id, usuario_id=u.id,
                        detalle={"estado_anterior": alerta["estado"], "motivo": datos.motivo},
                        ip=ip_cliente(request))
    return {"mensaje": "Alerta reabierta. Ojo: lo que ya se ejecuto (transaccion aprobada o rechazada, "
                       "cuenta congelada) no se revierte solo; revise la cuenta."}


@router.post("/alertas/{alerta_id}/resolver", summary="Resolver una alerta")
def resolver(alerta_id: int, datos: ResolverAlerta, request: Request,
             u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    alerta = consultar_uno(
        conn,
        "SELECT a.id, a.estado, a.cuenta_id, a.transaccion_id, t.estado AS estado_tx "
        "FROM alertas_fraude a LEFT JOIN transacciones t ON t.id = a.transaccion_id WHERE a.id = %s",
        (alerta_id,),
    )
    if not alerta:
        raise ErrorNegocio(404, "Alerta no encontrada")
    if alerta["estado"] in ("confirmada", "descartada"):
        raise ErrorNegocio(409, "La alerta ya fue resuelta")

    # Si la transaccion estaba retenida, el procedimiento la aprueba (mueve el
    # dinero) o la rechaza, todo dentro de una transaccion ACID.
    if alerta["transaccion_id"] and alerta["estado_tx"] == "retenida":
        with conn.cursor() as cur:
            cur.execute("CALL sp_resolver_retenida(%s, %s, %s)",
                        (alerta["transaccion_id"], u.id, not datos.confirmar_fraude))
        nuevo_estado_tx = "rechazada" if datos.confirmar_fraude else "aprobada"
        grafo.actualizar_estado_transferencia(alerta["transaccion_id"], nuevo_estado_tx)

    ejecutar(conn, "UPDATE alertas_fraude SET estado = %s, analista_id = %s, nota = %s, resuelta_en = NOW() "
                   "WHERE id = %s",
             ("confirmada" if datos.confirmar_fraude else "descartada", u.id, datos.nota, alerta_id))

    if datos.confirmar_fraude:
        cuenta = consultar_uno(conn, "SELECT id, numero, estado FROM cuentas WHERE id = %s", (alerta["cuenta_id"],))
        if cuenta["estado"] == "activa":
            banco.cambiar_estado_cuenta(conn, cuenta, "congelada")

    auditoria.registrar(conn, "ALERTA_RESUELTA", "alertas_fraude", alerta_id, usuario_id=u.id,
                        detalle={"confirmar_fraude": datos.confirmar_fraude, "nota": datos.nota},
                        ip=ip_cliente(request))
    return {"mensaje": "Fraude confirmado: transaccion rechazada y cuenta congelada"
            if datos.confirmar_fraude else "Falsa alarma: transaccion aprobada"}


@router.post("/barrido", summary="Buscar patrones de fraude en todo el historial (solo crea alertas)")
def lanzar_barrido(request: Request, u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    resultado = barrido.barrer(conn)
    auditoria.registrar(conn, "BARRIDO_ANTIFRAUDE", "alertas_fraude", None, usuario_id=u.id,
                        detalle=resultado, ip=ip_cliente(request))
    return resultado


@router.get("/cuentas/{numero}/grafo", summary="Vecindario de la cuenta en el grafo (para dibujar)")
def grafo_de_cuenta(numero: str, u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    cuenta = banco.cuenta_por_numero(conn, numero)
    if not cuenta:
        raise ErrorNegocio(404, "Cuenta no encontrada")
    resultado = grafo.vecindario(cuenta["id"])
    # Marcar las cuentas que tienen alertas abiertas (dato que vive en MySQL)
    ids = [int(n["id"].split("-")[1]) for n in resultado["nodos"] if n["tipo"] == "cuenta"]
    if ids:
        marcadores = ", ".join(["%s"] * len(ids))
        con_alerta = {f["cuenta_id"] for f in consultar(
            conn, f"SELECT DISTINCT cuenta_id FROM alertas_fraude WHERE estado IN ('abierta', 'en_revision') "
                  f"AND cuenta_id IN ({marcadores})", tuple(ids))}
        for n in resultado["nodos"]:
            if n["tipo"] == "cuenta":
                n["alerta_abierta"] = int(n["id"].split("-")[1]) in con_alerta
    return resultado


@router.get("/cuentas/{numero}", summary="Resumen de una cuenta")
def resumen_cuenta(numero: str, u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    fila = consultar_uno(conn, "SELECT * FROM v_resumen_cuentas WHERE numero = %s", (numero,))
    if not fila:
        raise ErrorNegocio(404, "Cuenta no encontrada")
    return fila


def _cambiar_estado(numero: str, nuevo: str, accion: str, motivo: str, u, conn, request):
    cuenta = banco.cuenta_por_numero(conn, numero)
    if not cuenta:
        raise ErrorNegocio(404, "Cuenta no encontrada")
    if cuenta["estado"] == "cerrada":
        raise ErrorNegocio(409, "La cuenta esta cerrada")
    if cuenta["estado"] == nuevo:
        raise ErrorNegocio(409, f"La cuenta ya esta {nuevo}")
    banco.cambiar_estado_cuenta(conn, cuenta, nuevo)
    auditoria.registrar(conn, accion, "cuentas", cuenta["id"], usuario_id=u.id,
                        detalle={"motivo": motivo}, ip=ip_cliente(request))
    return {"cuenta": numero, "estado": nuevo}


@router.post("/cuentas/{numero}/congelar", summary="Congelar una cuenta")
def congelar(numero: str, datos: MotivoCongelar, request: Request,
             u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    return _cambiar_estado(numero, "congelada", "CONGELAR_CUENTA", datos.motivo, u, conn, request)


@router.post("/cuentas/{numero}/descongelar", summary="Descongelar una cuenta")
def descongelar(numero: str, datos: MotivoCongelar, request: Request,
                u: UsuarioActual = Depends(analista), conn=Depends(obtener_conexion)):
    return _cambiar_estado(numero, "activa", "DESCONGELAR_CUENTA", datos.motivo, u, conn, request)
