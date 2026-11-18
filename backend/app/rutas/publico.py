"""Rutas publicas: no piden iniciar sesion.

Las usan la pantalla de login ("Pedir tarjeta fisica", "Contactanos") y la
pagina "Trabaja con nosotros".

La solicitud queda guardada en MySQL y un empleado la atiende desde la
Intranet como una conversacion: cada respuesta se guarda y se ENVIA al correo
del visitante (en desarrollo llega a Mailpit, http://localhost:8025). El
visitante no tiene cuenta, asi que no puede contestar por la pagina.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db.mysql import consultar, consultar_uno, ejecutar, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import EstadoSolicitud, RespuestaSolicitud, SolicitudPublica
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, correo
from ..utilidades import ip_cliente

router = APIRouter(prefix="/publico", tags=["7. Publico"])

# Como cualquiera puede llamar esta ruta, se limita cuantas solicitudes
# acepta desde una misma IP para que no llenen la tabla.
_MAX_POR_HORA = 5


@router.post("/solicitudes", status_code=201, summary="Pedir la tarjeta fisica, que el banco me escriba o postularme")
def crear_solicitud(datos: SolicitudPublica, request: Request, conn=Depends(obtener_conexion)):
    ip = ip_cliente(request)
    recientes = consultar_uno(
        conn,
        "SELECT COUNT(*) AS n FROM solicitudes_publicas WHERE ip = %s AND creada_en > NOW() - INTERVAL 1 HOUR",
        (ip,),
    )
    if recientes["n"] >= _MAX_POR_HORA:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Ya recibimos varias solicitudes tuyas. Intenta de nuevo en una hora.")
    ejecutar(
        conn,
        "INSERT INTO solicitudes_publicas (tipo, email, mensaje, ip) VALUES (%s, %s, %s, %s)",
        (datos.tipo, datos.email.lower(), datos.mensaje, ip),
    )
    return {"mensaje": "Solicitud recibida"}


# ---------------------------------------------------------------------
# Lo que ve el empleado en la Intranet: la bandeja de solicitudes
# ---------------------------------------------------------------------
empleado = requiere_rol("cajero", "analista", "admin")


@router.get("/solicitudes", summary="Bandeja de solicitudes (solo empleados)")
def listar_solicitudes(atendidas: bool = False, u: UsuarioActual = Depends(empleado),
                       conn=Depends(obtener_conexion)):
    return consultar(
        conn,
        "SELECT s.id, s.tipo, s.email, s.mensaje, s.atendida, s.creada_en, "
        "(SELECT COUNT(*) FROM respuestas_solicitud r WHERE r.solicitud_id = s.id) AS respuestas, "
        "(SELECT r.texto FROM respuestas_solicitud r WHERE r.solicitud_id = s.id "
        " ORDER BY r.id DESC LIMIT 1) AS ultima_respuesta, "
        "(SELECT COUNT(*) FROM respuestas_solicitud r WHERE r.solicitud_id = s.id "
        " AND r.estado_envio <> 'enviado') AS sin_enviar "
        "FROM solicitudes_publicas s "
        "WHERE s.atendida = %s ORDER BY s.creada_en DESC LIMIT 200",
        (atendidas,),
    )


@router.patch("/solicitudes/{solicitud_id}", summary="Marcar una solicitud como atendida o pendiente")
def marcar_solicitud(solicitud_id: int, datos: EstadoSolicitud, request: Request,
                     u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    cur = ejecutar(conn, "UPDATE solicitudes_publicas SET atendida = %s WHERE id = %s",
                   (datos.atendida, solicitud_id))
    if cur.rowcount == 0 and not consultar_uno(conn, "SELECT 1 FROM solicitudes_publicas WHERE id = %s",
                                               (solicitud_id,)):
        raise ErrorNegocio(404, "Solicitud no encontrada")
    auditoria.registrar(conn, "ATENDER_SOLICITUD" if datos.atendida else "REABRIR_SOLICITUD",
                        "solicitudes_publicas", solicitud_id, usuario_id=u.id, ip=ip_cliente(request))
    return {"id": solicitud_id, "atendida": datos.atendida}


# ---------------------------------------------------------------------
# Responder: conversacion de un solo lado. El empleado escribe y el texto
# se envia por correo al visitante.
# ---------------------------------------------------------------------
def _solicitud(conn, solicitud_id: int) -> dict:
    s = consultar_uno(conn, "SELECT id, tipo, email, mensaje, atendida, creada_en FROM solicitudes_publicas "
                            "WHERE id = %s", (solicitud_id,))
    if not s:
        raise ErrorNegocio(404, "Solicitud no encontrada")
    return s


def _respuestas(conn, solicitud_id: int) -> list[dict]:
    return consultar(
        conn,
        "SELECT r.id, r.texto, r.estado_envio, r.error_envio, r.creado_en, r.enviado_en, "
        "u.nombre AS autor, r.autor_id "
        "FROM respuestas_solicitud r JOIN usuarios u ON u.id = r.autor_id "
        "WHERE r.solicitud_id = %s ORDER BY r.id",
        (solicitud_id,),
    )


def _enviar(conn, respuesta_id: int, solicitud: dict, texto: str) -> str:
    """Intenta enviar el correo y guarda el resultado. Devuelve el estado final."""
    try:
        correo.enviar_respuesta_solicitud(solicitud["email"], solicitud["tipo"], texto)
    except correo.CorreoNoEnviado as e:
        ejecutar(conn, "UPDATE respuestas_solicitud SET estado_envio = 'fallido', error_envio = %s WHERE id = %s",
                 (str(e)[:255], respuesta_id))
        return "fallido"
    ejecutar(conn, "UPDATE respuestas_solicitud SET estado_envio = 'enviado', error_envio = NULL, "
                   "enviado_en = NOW(6) WHERE id = %s", (respuesta_id,))
    return "enviado"


@router.get("/solicitudes/{solicitud_id}", summary="Una solicitud con sus respuestas (solo empleados)")
def ver_solicitud(solicitud_id: int, u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    return {"solicitud": _solicitud(conn, solicitud_id), "respuestas": _respuestas(conn, solicitud_id)}


@router.post("/solicitudes/{solicitud_id}/respuestas", status_code=201,
             summary="Responder una solicitud: se envia al correo del visitante")
def responder(solicitud_id: int, datos: RespuestaSolicitud, request: Request,
              u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    s = _solicitud(conn, solicitud_id)
    # Primero se GUARDA (pendiente) y luego se envia: si el servidor de correo
    # esta caido, la respuesta no se pierde y se puede reintentar.
    cur = ejecutar(conn, "INSERT INTO respuestas_solicitud (solicitud_id, autor_id, texto) VALUES (%s, %s, %s)",
                   (s["id"], u.id, datos.texto))
    respuesta_id = cur.lastrowid
    estado = _enviar(conn, respuesta_id, s, datos.texto)
    # Responder la deja atendida (el empleado puede devolverla a pendientes)
    ejecutar(conn, "UPDATE solicitudes_publicas SET atendida = TRUE WHERE id = %s", (s["id"],))
    auditoria.registrar(conn, "RESPONDER_SOLICITUD", "solicitudes_publicas", s["id"], usuario_id=u.id,
                        detalle={"respuesta_id": respuesta_id, "envio": estado}, ip=ip_cliente(request))
    return {"id": respuesta_id, "estado_envio": estado,
            "mensaje": "Respuesta enviada al correo" if estado == "enviado"
            else "La respuesta quedo guardada, pero el correo no se pudo enviar. Puedes reintentar."}


@router.post("/solicitudes/{solicitud_id}/respuestas/{respuesta_id}/reintentar",
             summary="Reintentar el envio de una respuesta que fallo")
def reintentar(solicitud_id: int, respuesta_id: int, request: Request,
               u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    s = _solicitud(conn, solicitud_id)
    r = consultar_uno(conn, "SELECT id, texto, estado_envio FROM respuestas_solicitud "
                            "WHERE id = %s AND solicitud_id = %s", (respuesta_id, s["id"]))
    if not r:
        raise ErrorNegocio(404, "Respuesta no encontrada")
    if r["estado_envio"] == "enviado":
        raise ErrorNegocio(409, "Esa respuesta ya fue enviada")
    estado = _enviar(conn, r["id"], s, r["texto"])
    auditoria.registrar(conn, "REINTENTAR_CORREO", "respuestas_solicitud", r["id"], usuario_id=u.id,
                        detalle={"envio": estado}, ip=ip_cliente(request))
    return {"id": r["id"], "estado_envio": estado}
