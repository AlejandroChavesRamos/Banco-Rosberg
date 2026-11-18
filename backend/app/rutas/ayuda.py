"""Chat de ayuda: el cliente conversa con un asesor del banco (tiquetes).

Ciclo de un tiquete:
  1. El CLIENTE lo abre con un tema, un asunto y su primer mensaje -> "nuevo".
  2. Todos los empleados lo ven en la cola. El primero que pulsa "Atender"
     queda a cargo -> "en_atencion". Desde ese momento solo el puede escribir
     (el admin puede reasignarlo).
  3. Lo cierra el asesor, el admin o el propio cliente -> "cerrado".
     Ya no admite mensajes y el cliente puede calificar la atencion (1 a 5).

Las pantallas preguntan cada pocos segundos si hay mensajes nuevos
(?despues_de=<ultimo id>), igual que la cola de alertas: no hace falta
mantener una conexion abierta.

Seguridad:
  - Un cliente solo ve SUS tiquetes; si pide uno ajeno recibe 404 (como no
    existiera), igual que con las cuentas.
  - Los mensajes solo se insertan: la app no tiene permiso para editarlos
    ni borrarlos (ver 08_mensajeria.sh).
  - Limite de mensajes por minuto y de tiquetes abiertos, contra el abuso.
"""
from fastapi import APIRouter, Depends, Query, Request

from ..db.mysql import consultar, consultar_uno, ejecutar, obtener_conexion, transaccion
from ..errores import ErrorNegocio
from ..esquemas import Calificacion, CierreTiquete, MensajeEntrada, NuevoTiquete, Reasignacion
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria
from ..utilidades import ip_cliente

router_cliente = APIRouter(prefix="/ayuda", tags=["8. Ayuda (cliente)"])
router_empleado = APIRouter(prefix="/atencion", tags=["9. Atencion al cliente (empleados)"])

solo_cliente = requiere_rol("cliente")
empleado = requiere_rol("cajero", "analista", "admin")
solo_admin = requiere_rol("admin")

MAX_TIQUETES_ABIERTOS = 3
MAX_MENSAJES_POR_MINUTO = 20

# Lo que se lista de un tiquete (sin los mensajes). %s = id de quien mira,
# para contar los mensajes que escribio la OTRA persona y que aun no vio.
_RESUMEN = """
    SELECT t.id, t.tema, t.asunto, t.estado, t.calificacion, t.creado_en, t.actualizado_en, t.cerrado_en,
           t.cliente_id, c.nombre AS cliente_nombre, c.email AS cliente_email,
           t.asesor_id, a.nombre AS asesor_nombre, a.rol AS asesor_rol,
           (SELECT m.texto FROM mensajes_tiquete m WHERE m.tiquete_id = t.id ORDER BY m.id DESC LIMIT 1) AS ultimo_mensaje,
           (SELECT COUNT(*) FROM mensajes_tiquete m
             WHERE m.tiquete_id = t.id AND m.autor_id <> %s
               AND m.id > IF(t.cliente_id = %s, t.visto_cliente_id, t.visto_asesor_id)) AS no_leidos
    FROM tiquetes t
    JOIN usuarios c ON c.id = t.cliente_id
    LEFT JOIN usuarios a ON a.id = t.asesor_id
"""


def _primer_nombre(nombre: str | None) -> str | None:
    return nombre.split()[0] if nombre else None


def _para_cliente(t: dict) -> dict:
    """El cliente ve solo el primer nombre de su asesor, no su correo ni su rol."""
    return {
        "id": t["id"], "tema": t["tema"], "asunto": t["asunto"], "estado": t["estado"],
        "calificacion": t["calificacion"], "creado_en": t["creado_en"],
        "actualizado_en": t["actualizado_en"], "cerrado_en": t["cerrado_en"],
        "asesor": _primer_nombre(t["asesor_nombre"]),
        "ultimo_mensaje": t["ultimo_mensaje"], "no_leidos": int(t["no_leidos"]),
    }


def _para_empleado(t: dict, yo: int) -> dict:
    return {
        "a_mi_cargo": t["asesor_id"] == yo,
        "id": t["id"], "tema": t["tema"], "asunto": t["asunto"], "estado": t["estado"],
        "calificacion": t["calificacion"], "creado_en": t["creado_en"],
        "actualizado_en": t["actualizado_en"], "cerrado_en": t["cerrado_en"],
        "cliente": {"id": t["cliente_id"], "nombre": t["cliente_nombre"], "email": t["cliente_email"]},
        "asesor": {"id": t["asesor_id"], "nombre": t["asesor_nombre"], "rol": t["asesor_rol"]}
        if t["asesor_id"] else None,
        "ultimo_mensaje": t["ultimo_mensaje"], "no_leidos": int(t["no_leidos"]),
    }


def _tiquete(conn, tiquete_id: int, usuario_id: int) -> dict | None:
    return consultar_uno(conn, _RESUMEN + " WHERE t.id = %s", (usuario_id, usuario_id, tiquete_id))


def _mensajes(conn, tiquete: dict, despues_de: int, quien_mira: int) -> list[dict]:
    filas = consultar(
        conn,
        "SELECT m.id, m.autor_id, m.texto, m.creado_en, u.nombre, u.rol "
        "FROM mensajes_tiquete m JOIN usuarios u ON u.id = m.autor_id "
        "WHERE m.tiquete_id = %s AND m.id > %s ORDER BY m.id LIMIT 500",
        (tiquete["id"], despues_de),
    )
    return [{
        "id": f["id"], "texto": f["texto"], "creado_en": f["creado_en"],
        "de": "cliente" if f["autor_id"] == tiquete["cliente_id"] else "asesor",
        "mio": f["autor_id"] == quien_mira,
        "autor": _primer_nombre(f["nombre"]) if f["autor_id"] != tiquete["cliente_id"] else f["nombre"],
    } for f in filas]


def _marcar_visto(conn, tiquete: dict, mensajes: list[dict], columna: str) -> None:
    # columna es una constante del codigo ("visto_cliente_id" o "visto_asesor_id")
    if mensajes:
        ejecutar(conn, f"UPDATE tiquetes SET {columna} = GREATEST({columna}, %s) WHERE id = %s",
                 (mensajes[-1]["id"], tiquete["id"]))


def _limite_mensajes(conn, usuario_id: int) -> None:
    n = consultar_uno(conn, "SELECT COUNT(*) AS n FROM mensajes_tiquete "
                            "WHERE autor_id = %s AND creado_en > NOW(6) - INTERVAL 1 MINUTE", (usuario_id,))["n"]
    if n >= MAX_MENSAJES_POR_MINUTO:
        raise ErrorNegocio(429, "Estas enviando mensajes muy rapido. Espera un momento.")


def _escribir(conn, tiquete_id: int, autor_id: int, texto: str) -> int:
    with transaccion(conn):
        cur = ejecutar(conn, "INSERT INTO mensajes_tiquete (tiquete_id, autor_id, texto) VALUES (%s, %s, %s)",
                       (tiquete_id, autor_id, texto))
        mensaje_id = cur.lastrowid
        ejecutar(conn, "UPDATE tiquetes SET actualizado_en = NOW(6) WHERE id = %s", (tiquete_id,))
    return mensaje_id


def _cerrar(conn, tiquete: dict, u: UsuarioActual, request: Request, calificacion: int | None = None) -> None:
    if tiquete["estado"] == "cerrado":
        raise ErrorNegocio(409, "El tiquete ya esta cerrado")
    ejecutar(conn, "UPDATE tiquetes SET estado = 'cerrado', cerrado_en = NOW(6), cerrado_por = %s, "
                   "calificacion = %s WHERE id = %s AND estado <> 'cerrado'",
             (u.id, calificacion, tiquete["id"]))
    auditoria.registrar(conn, "TIQUETE_CERRADO", "tiquetes", tiquete["id"], usuario_id=u.id,
                        detalle={"calificacion": calificacion}, ip=ip_cliente(request))


# =================================================================== CLIENTE
@router_cliente.get("/resumen", summary="Cuantos mensajes nuevos del asesor tengo sin leer")
def resumen_cliente(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    fila = consultar_uno(
        conn,
        "SELECT COUNT(*) AS n FROM mensajes_tiquete m JOIN tiquetes t ON t.id = m.tiquete_id "
        "WHERE t.cliente_id = %s AND m.autor_id <> %s AND m.id > t.visto_cliente_id",
        (u.id, u.id),
    )
    return {"no_leidos": int(fila["n"])}


@router_cliente.get("/tiquetes", summary="Mis conversaciones con el banco")
def mis_tiquetes(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    filas = consultar(conn, _RESUMEN + " WHERE t.cliente_id = %s ORDER BY t.estado = 'cerrado', t.actualizado_en DESC "
                                       "LIMIT 100", (u.id, u.id, u.id))
    return [_para_cliente(t) for t in filas]


@router_cliente.post("/tiquetes", status_code=201, summary="Pedir ayuda a un asesor")
def abrir_tiquete(datos: NuevoTiquete, request: Request,
                  u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    abiertos = consultar_uno(conn, "SELECT COUNT(*) AS n FROM tiquetes WHERE cliente_id = %s AND estado <> 'cerrado'",
                             (u.id,))["n"]
    if abiertos >= MAX_TIQUETES_ABIERTOS:
        raise ErrorNegocio(409, f"Ya tienes {abiertos} conversaciones abiertas. "
                                "Continua en una de ellas o espera a que se cierren.")
    _limite_mensajes(conn, u.id)
    with transaccion(conn):
        cur = ejecutar(conn, "INSERT INTO tiquetes (cliente_id, tema, asunto) VALUES (%s, %s, %s)",
                       (u.id, datos.tema, datos.asunto))
        tiquete_id = cur.lastrowid
        cur = ejecutar(conn, "INSERT INTO mensajes_tiquete (tiquete_id, autor_id, texto) VALUES (%s, %s, %s)",
                       (tiquete_id, u.id, datos.mensaje))
        ejecutar(conn, "UPDATE tiquetes SET visto_cliente_id = %s WHERE id = %s", (cur.lastrowid, tiquete_id))
    auditoria.registrar(conn, "TIQUETE_ABIERTO", "tiquetes", tiquete_id, usuario_id=u.id,
                        detalle={"tema": datos.tema}, ip=ip_cliente(request))
    return _para_cliente(_tiquete(conn, tiquete_id, u.id))


def _tiquete_propio(conn, tiquete_id: int, u: UsuarioActual) -> dict:
    t = _tiquete(conn, tiquete_id, u.id)
    if not t or t["cliente_id"] != u.id:
        raise ErrorNegocio(404, "Conversacion no encontrada")  # 404 tambien si es de otro (no revelar)
    return t


@router_cliente.get("/tiquetes/{tiquete_id}", summary="Una conversacion y sus mensajes")
def ver_tiquete_cliente(tiquete_id: int, despues_de: int = Query(default=0, ge=0),
                        u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    t = _tiquete_propio(conn, tiquete_id, u)
    mensajes = _mensajes(conn, t, despues_de, u.id)
    _marcar_visto(conn, t, mensajes, "visto_cliente_id")
    return {"tiquete": _para_cliente(t), "mensajes": mensajes}


@router_cliente.post("/tiquetes/{tiquete_id}/mensajes", status_code=201, summary="Escribir en mi conversacion")
def escribir_cliente(tiquete_id: int, datos: MensajeEntrada,
                     u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    t = _tiquete_propio(conn, tiquete_id, u)
    if t["estado"] == "cerrado":
        raise ErrorNegocio(409, "Esta conversacion ya se cerro. Si necesitas algo mas, abre una nueva.")
    _limite_mensajes(conn, u.id)
    mensaje_id = _escribir(conn, t["id"], u.id, datos.texto)
    ejecutar(conn, "UPDATE tiquetes SET visto_cliente_id = %s WHERE id = %s", (mensaje_id, t["id"]))
    return {"id": mensaje_id}


@router_cliente.post("/tiquetes/{tiquete_id}/cerrar", summary="Cerrar mi conversacion (y calificar)")
def cerrar_cliente(tiquete_id: int, datos: CierreTiquete, request: Request,
                   u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    t = _tiquete_propio(conn, tiquete_id, u)
    _cerrar(conn, t, u, request, datos.calificacion)
    return _para_cliente(_tiquete(conn, t["id"], u.id))


@router_cliente.post("/tiquetes/{tiquete_id}/calificar", summary="Calificar la atencion de una conversacion cerrada")
def calificar(tiquete_id: int, datos: Calificacion, request: Request,
              u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    t = _tiquete_propio(conn, tiquete_id, u)
    if t["estado"] != "cerrado":
        raise ErrorNegocio(409, "Solo se califica una conversacion cerrada")
    if t["calificacion"] is not None:
        raise ErrorNegocio(409, "Ya calificaste esta conversacion")
    ejecutar(conn, "UPDATE tiquetes SET calificacion = %s WHERE id = %s AND calificacion IS NULL",
             (datos.calificacion, t["id"]))
    auditoria.registrar(conn, "TIQUETE_CALIFICADO", "tiquetes", t["id"], usuario_id=u.id,
                        detalle={"calificacion": datos.calificacion}, ip=ip_cliente(request))
    return _para_cliente(_tiquete(conn, t["id"], u.id))


# ================================================================== EMPLEADOS
@router_empleado.get("/resumen", summary="Tiquetes nuevos y mensajes sin leer de los mios")
def resumen_empleado(u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    nuevos = consultar_uno(conn, "SELECT COUNT(*) AS n FROM tiquetes WHERE estado = 'nuevo'")["n"]
    sin_leer = consultar_uno(
        conn,
        "SELECT COUNT(*) AS n FROM mensajes_tiquete m JOIN tiquetes t ON t.id = m.tiquete_id "
        "WHERE t.asesor_id = %s AND t.estado = 'en_atencion' AND m.autor_id <> %s AND m.id > t.visto_asesor_id",
        (u.id, u.id),
    )["n"]
    return {"nuevos": int(nuevos), "mios_no_leidos": int(sin_leer)}


@router_empleado.get("/tiquetes", summary="Cola de atencion")
def cola(vista: str = Query(default="nuevos", pattern="^(nuevos|mios|en_atencion|cerrados)$"),
         u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    filtros = {
        "nuevos": ("t.estado = 'nuevo'", ()),
        "mios": ("t.estado = 'en_atencion' AND t.asesor_id = %s", (u.id,)),
        "en_atencion": ("t.estado = 'en_atencion'", ()),
        "cerrados": ("t.estado = 'cerrado'", ()),
    }
    donde, params = filtros[vista]
    # Los nuevos, del mas antiguo al mas reciente (el que mas lleva esperando primero)
    orden = "t.creado_en ASC" if vista == "nuevos" else "t.actualizado_en DESC"
    filas = consultar(conn, f"{_RESUMEN} WHERE {donde} ORDER BY {orden} LIMIT 200", (u.id, u.id, *params))
    return [_para_empleado(t, u.id) for t in filas]


def _tiquete_existente(conn, tiquete_id: int, u: UsuarioActual) -> dict:
    t = _tiquete(conn, tiquete_id, u.id)
    if not t:
        raise ErrorNegocio(404, "Tiquete no encontrado")
    return t


@router_empleado.get("/tiquetes/{tiquete_id}", summary="Ver un tiquete y sus mensajes")
def ver_tiquete_empleado(tiquete_id: int, despues_de: int = Query(default=0, ge=0),
                         u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    t = _tiquete_existente(conn, tiquete_id, u)
    mensajes = _mensajes(conn, t, despues_de, u.id)
    if t["asesor_id"] == u.id:
        _marcar_visto(conn, t, mensajes, "visto_asesor_id")  # solo el asesor a cargo "lee"
    return {"tiquete": _para_empleado(t, u.id), "mensajes": mensajes}


@router_empleado.post("/tiquetes/{tiquete_id}/atender", summary="Tomar un tiquete nuevo")
def atender(tiquete_id: int, request: Request,
            u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    t = _tiquete_existente(conn, tiquete_id, u)
    # Atomico: si dos empleados pulsan "Atender" a la vez, el UPDATE solo
    # cambia la fila para el primero (la condicion estado = 'nuevo' ya no se
    # cumple para el segundo).
    cur = ejecutar(conn, "UPDATE tiquetes SET estado = 'en_atencion', asesor_id = %s "
                         "WHERE id = %s AND estado = 'nuevo'", (u.id, t["id"]))
    if cur.rowcount == 0:
        actual = _tiquete(conn, t["id"], u.id)
        quien = actual["asesor_nombre"] or "otro empleado"
        raise ErrorNegocio(409, f"Este tiquete ya lo esta atendiendo {quien}" if actual["estado"] == "en_atencion"
                           else "El tiquete ya esta cerrado")
    auditoria.registrar(conn, "TIQUETE_ATENDIDO", "tiquetes", t["id"], usuario_id=u.id, ip=ip_cliente(request))
    return _para_empleado(_tiquete(conn, t["id"], u.id), u.id)


@router_empleado.post("/tiquetes/{tiquete_id}/mensajes", status_code=201, summary="Responder al cliente")
def escribir_empleado(tiquete_id: int, datos: MensajeEntrada,
                      u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    t = _tiquete_existente(conn, tiquete_id, u)
    if t["estado"] == "cerrado":
        raise ErrorNegocio(409, "El tiquete esta cerrado")
    if t["estado"] == "nuevo":
        raise ErrorNegocio(409, "Primero pulsa 'Atender' para tomar este tiquete")
    if t["asesor_id"] != u.id:
        raise ErrorNegocio(403, "Este tiquete lo atiende otro empleado")
    _limite_mensajes(conn, u.id)
    mensaje_id = _escribir(conn, t["id"], u.id, datos.texto)
    ejecutar(conn, "UPDATE tiquetes SET visto_asesor_id = %s WHERE id = %s", (mensaje_id, t["id"]))
    return {"id": mensaje_id}


@router_empleado.post("/tiquetes/{tiquete_id}/cerrar", summary="Cerrar un tiquete (asesor a cargo o admin)")
def cerrar_empleado(tiquete_id: int, request: Request,
                    u: UsuarioActual = Depends(empleado), conn=Depends(obtener_conexion)):
    t = _tiquete_existente(conn, tiquete_id, u)
    if t["asesor_id"] != u.id and u.rol != "admin":
        raise ErrorNegocio(403, "Solo el asesor a cargo o un administrador pueden cerrarlo")
    _cerrar(conn, t, u, request)
    return _para_empleado(_tiquete(conn, t["id"], u.id), u.id)


@router_empleado.get("/asesores", summary="Empleados activos a quienes se puede reasignar (admin)")
def asesores(u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    return consultar(conn, "SELECT id, nombre, rol FROM usuarios WHERE rol <> 'cliente' AND activo ORDER BY nombre")


@router_empleado.post("/tiquetes/{tiquete_id}/reasignar", summary="Pasar un tiquete a otro empleado (admin)")
def reasignar(tiquete_id: int, datos: Reasignacion, request: Request,
              u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    t = _tiquete_existente(conn, tiquete_id, u)
    if t["estado"] == "cerrado":
        raise ErrorNegocio(409, "El tiquete esta cerrado")
    nuevo = consultar_uno(conn, "SELECT id, nombre FROM usuarios WHERE id = %s AND rol <> 'cliente' AND activo",
                          (datos.asesor_id,))
    if not nuevo:
        raise ErrorNegocio(404, "Empleado no encontrado o inactivo")
    # visto_asesor_id se reinicia: el nuevo asesor vera todo como "por leer"
    ejecutar(conn, "UPDATE tiquetes SET estado = 'en_atencion', asesor_id = %s, visto_asesor_id = 0 WHERE id = %s",
             (nuevo["id"], t["id"]))
    auditoria.registrar(conn, "TIQUETE_REASIGNADO", "tiquetes", t["id"], usuario_id=u.id,
                        detalle={"de": t["asesor_id"], "a": nuevo["id"]}, ip=ip_cliente(request))
    return _para_empleado(_tiquete(conn, t["id"], u.id), u.id)
