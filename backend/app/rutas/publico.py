"""Rutas publicas: no piden iniciar sesion.

Las usan la pantalla de login ("Pedir tarjeta fisica", "Contactanos") y la
pagina "Trabaja con nosotros".

El banco no envia correos reales (proyecto academico): la solicitud queda
guardada en MySQL para que un empleado la atienda.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db.mysql import consultar, consultar_uno, ejecutar, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import EstadoSolicitud, SolicitudPublica
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria
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
        "SELECT id, tipo, email, mensaje, atendida, creada_en FROM solicitudes_publicas "
        "WHERE atendida = %s ORDER BY creada_en DESC LIMIT 200",
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
