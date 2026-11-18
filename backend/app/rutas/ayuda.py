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

Asistente Rosberg (servicios/asistente.py): un contestador por palabras
clave que el admin enciende en un tiquete, o que se enciende solo si nadie
atiende un tiquete nuevo a tiempo. Sus mensajes no tienen autor
(automatico = TRUE). Se apaga en cuanto un empleado toma el tiquete o escribe.
"""
import json

from fastapi import APIRouter, Depends, Query, Request

from ..db.mysql import consultar, consultar_uno, ejecutar, obtener_conexion, transaccion
from ..errores import ErrorNegocio
from ..esquemas import (AsistenteEstado, Calificacion, CambioRespuestaAutomatica, CierreTiquete, Ensenanza,
                        MensajeEntrada, NuevaRespuestaAutomatica, NuevoSinonimo, NuevoTiquete, Reasignacion)
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import asistente, auditoria
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
           t.asistente_activo,
           t.cliente_id, c.nombre AS cliente_nombre, c.email AS cliente_email,
           t.asesor_id, a.nombre AS asesor_nombre, a.rol AS asesor_rol,
           (SELECT m.texto FROM mensajes_tiquete m WHERE m.tiquete_id = t.id ORDER BY m.id DESC LIMIT 1) AS ultimo_mensaje,
           (SELECT COUNT(*) FROM mensajes_tiquete m
             WHERE m.tiquete_id = t.id AND (m.autor_id IS NULL OR m.autor_id <> %s)
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
        "asesor": _primer_nombre(t["asesor_nombre"]), "asistente_activo": bool(t["asistente_activo"]),
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
        "asistente_activo": bool(t["asistente_activo"]),
        "ultimo_mensaje": t["ultimo_mensaje"], "no_leidos": int(t["no_leidos"]),
    }


def _tiquete(conn, tiquete_id: int, usuario_id: int) -> dict | None:
    return consultar_uno(conn, _RESUMEN + " WHERE t.id = %s", (usuario_id, usuario_id, tiquete_id))


def _mensajes(conn, tiquete: dict, despues_de: int, quien_mira: int) -> list[dict]:
    filas = consultar(
        conn,
        "SELECT m.id, m.autor_id, m.automatico, m.texto, m.opciones, m.creado_en, u.nombre, u.rol "
        "FROM mensajes_tiquete m LEFT JOIN usuarios u ON u.id = m.autor_id "
        "WHERE m.tiquete_id = %s AND m.id > %s ORDER BY m.id LIMIT 500",
        (tiquete["id"], despues_de),
    )
    def de(f):
        if f["automatico"]:
            return "asistente"
        return "cliente" if f["autor_id"] == tiquete["cliente_id"] else "asesor"

    return [{
        "id": f["id"], "texto": f["texto"], "creado_en": f["creado_en"], "de": de(f),
        "mio": f["autor_id"] is not None and f["autor_id"] == quien_mira,
        # Botones de respuesta rapida que propone el asistente
        "opciones": json.loads(f["opciones"]) if isinstance(f["opciones"], str) else f["opciones"],
        "autor": asistente.NOMBRE if f["automatico"]
        else f["nombre"] if f["autor_id"] == tiquete["cliente_id"] else _primer_nombre(f["nombre"]),
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
        "WHERE t.cliente_id = %s AND (m.autor_id IS NULL OR m.autor_id <> %s) AND m.id > t.visto_cliente_id",
        (u.id, u.id),
    )
    return {"no_leidos": int(fila["n"])}


@router_cliente.get("/tiquetes", summary="Mis conversaciones con el banco")
def mis_tiquetes(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    asistente.revisar_autoactivacion(conn, u.id)
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
    asistente.revisar_autoactivacion(conn, u.id)
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
    if t["asistente_activo"]:
        if asistente.responder(conn, t["id"], datos.texto) == "derivado":
            auditoria.registrar(conn, "ASISTENTE_DERIVO", "tiquetes", t["id"], usuario_id=u.id)
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
        "WHERE t.asesor_id = %s AND t.estado = 'en_atencion' AND (m.autor_id IS NULL OR m.autor_id <> %s) "
        "AND m.id > t.visto_asesor_id",
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
    # Al tomarlo una persona, el asistente deja de responder
    cur = ejecutar(conn, "UPDATE tiquetes SET estado = 'en_atencion', asesor_id = %s, asistente_activo = FALSE "
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
    if t["asistente_activo"]:
        asistente.apagar_por_humano(conn, t["id"])
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
    ejecutar(conn, "UPDATE tiquetes SET estado = 'en_atencion', asesor_id = %s, visto_asesor_id = 0, "
                   "asistente_activo = FALSE WHERE id = %s",
             (nuevo["id"], t["id"]))
    auditoria.registrar(conn, "TIQUETE_REASIGNADO", "tiquetes", t["id"], usuario_id=u.id,
                        detalle={"de": t["asesor_id"], "a": nuevo["id"]}, ip=ip_cliente(request))
    return _para_empleado(_tiquete(conn, t["id"], u.id), u.id)


# =================================================================== ASISTENTE
@router_empleado.post("/tiquetes/{tiquete_id}/asistente", summary="Encender o apagar el asistente en un tiquete (admin)")
def cambiar_asistente(tiquete_id: int, datos: AsistenteEstado, request: Request,
                      u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    t = _tiquete_existente(conn, tiquete_id, u)
    if t["estado"] == "cerrado":
        raise ErrorNegocio(409, "El tiquete esta cerrado")
    if datos.activo:
        if not asistente.activar(conn, t["id"]):
            raise ErrorNegocio(409, "El asistente ya esta activo en este tiquete")
    else:
        asistente.apagar_por_humano(conn, t["id"])
    auditoria.registrar(conn, "ASISTENTE_ACTIVADO" if datos.activo else "ASISTENTE_DESACTIVADO", "tiquetes", t["id"],
                        usuario_id=u.id, ip=ip_cliente(request))
    return _para_empleado(_tiquete(conn, t["id"], u.id), u.id)


def _respuestas_con_palabras(conn, donde: str = "", params: tuple = ()) -> list[dict]:
    filas = consultar(conn, "SELECT id, clave, titulo, pregunta, respuesta, accion, prioridad, activa, usos, util_si, "
                            f"util_no, actualizada_en FROM respuestas_automaticas {donde} "
                            "ORDER BY activa DESC, usos DESC, titulo", params)
    palabras = consultar(conn, "SELECT respuesta_id, palabra FROM palabras_respuesta ORDER BY palabra")
    relacionadas = consultar(conn, "SELECT respuesta_id, relacionada_id FROM respuestas_relacionadas")
    for f in filas:
        f["activa"] = bool(f["activa"])
        f["palabras"] = [p["palabra"] for p in palabras if p["respuesta_id"] == f["id"]]
        f["relacionadas"] = [r["relacionada_id"] for r in relacionadas if r["respuesta_id"] == f["id"]]
    return filas


def _guardar_palabras(conn, respuesta_id: int, palabras: list[str], reemplazar: bool = True) -> list[str]:
    # Se guardan ya normalizadas, igual que se compara el texto del cliente
    limpias = sorted({asistente.normalizar(p)[:40] for p in palabras} - {""})
    if not limpias:
        raise ErrorNegocio(400, "Escribe al menos una palabra clave")
    if reemplazar:
        ejecutar(conn, "DELETE FROM palabras_respuesta WHERE respuesta_id = %s", (respuesta_id,))
    for p in limpias:
        ejecutar(conn, "INSERT IGNORE INTO palabras_respuesta (respuesta_id, palabra) VALUES (%s, %s)", (respuesta_id, p))
    return limpias


def _guardar_relacionadas(conn, respuesta_id: int, relacionadas: list[int]) -> None:
    validas = {f["id"] for f in consultar(conn, "SELECT id FROM respuestas_automaticas")}
    ejecutar(conn, "DELETE FROM respuestas_relacionadas WHERE respuesta_id = %s", (respuesta_id,))
    for rid in dict.fromkeys(relacionadas):  # sin repetidas, en orden
        if rid in validas and rid != respuesta_id:
            ejecutar(conn, "INSERT INTO respuestas_relacionadas (respuesta_id, relacionada_id) VALUES (%s, %s)",
                     (respuesta_id, rid))


@router_empleado.get("/respuestas", summary="Lo que sabe responder el asistente (admin)")
def respuestas_automaticas(u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    return _respuestas_con_palabras(conn)


@router_empleado.post("/respuestas", status_code=201, summary="Ensenarle una respuesta nueva al asistente (admin)")
def crear_respuesta(datos: NuevaRespuestaAutomatica, request: Request,
                    u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    with transaccion(conn):
        cur = ejecutar(conn, "INSERT INTO respuestas_automaticas (titulo, pregunta, respuesta, accion, prioridad) "
                             "VALUES (%s, %s, %s, %s, %s)",
                       (datos.titulo, datos.pregunta, datos.respuesta, datos.accion, datos.prioridad))
        rid = cur.lastrowid
        _guardar_palabras(conn, rid, datos.palabras)
        _guardar_relacionadas(conn, rid, datos.relacionadas)
    auditoria.registrar(conn, "RESPUESTA_AUTOMATICA_CREADA", "respuestas_automaticas", rid, usuario_id=u.id,
                        detalle={"titulo": datos.titulo}, ip=ip_cliente(request))
    return _respuestas_con_palabras(conn, "WHERE id = %s", (rid,))[0]


@router_empleado.patch("/respuestas/{respuesta_id}", summary="Editar o desactivar una respuesta (admin)")
def editar_respuesta(respuesta_id: int, datos: CambioRespuestaAutomatica, request: Request,
                     u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    if not consultar_uno(conn, "SELECT id FROM respuestas_automaticas WHERE id = %s", (respuesta_id,)):
        raise ErrorNegocio(404, "Respuesta no encontrada")
    cambios = datos.model_dump(exclude_none=True)
    palabras = cambios.pop("palabras", None)
    relacionadas = cambios.pop("relacionadas", None)
    if cambios.get("accion") == "ninguna":
        cambios["accion"] = None
    if cambios.get("pregunta") == "":
        cambios["pregunta"] = None
    with transaccion(conn):
        # Las columnas salen de un modelo fijo (titulo, pregunta, respuesta, accion, prioridad, activa)
        for columna, valor in cambios.items():
            ejecutar(conn, f"UPDATE respuestas_automaticas SET {columna} = %s WHERE id = %s", (valor, respuesta_id))
        if palabras is not None:
            _guardar_palabras(conn, respuesta_id, palabras)
        if relacionadas is not None:
            _guardar_relacionadas(conn, respuesta_id, relacionadas)
    campos = list(cambios) + (["palabras"] if palabras is not None else []) + \
        (["relacionadas"] if relacionadas is not None else [])
    auditoria.registrar(conn, "RESPUESTA_AUTOMATICA_EDITADA", "respuestas_automaticas", respuesta_id, usuario_id=u.id,
                        detalle={"campos": campos}, ip=ip_cliente(request))
    return _respuestas_con_palabras(conn, "WHERE id = %s", (respuesta_id,))[0]


@router_empleado.get("/respuestas/probar", summary="Que responderia el asistente a un texto (admin)")
def probar_asistente(texto: str = Query(min_length=1, max_length=1000),
                     u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    if asistente.pide_persona(texto):
        return {"resultado": "derivar", "respuesta": asistente.PIDE_PERSONA, "coincidencias": []}
    r = asistente.buscar_respuesta(conn, texto)
    if not r:
        return {"resultado": "no_entiende", "respuesta": asistente.NO_ENTENDI, "coincidencias": [],
                "sugeridas": asistente.sugerir_palabras(texto)}
    return {"resultado": "responde", "titulo": r["titulo"], "respuesta": asistente.plantilla(conn, r["respuesta"]),
            "accion": r["accion"], "coincidencias": r["coincidencias"], "puntos": r["puntos"],
            # Lo que el asistente "entendio" despues de normalizar, sinonimos y raices
            "como_lo_lee": " ".join(asistente._raices(texto, asistente._sinonimos(conn)))}


# ------------------------------------------------------ aprender de lo que falla
@router_empleado.get("/asistente/pendientes", summary="Preguntas que el asistente no entendio (admin)")
def pendientes(u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    filas = consultar(conn, "SELECT id, tiquete_id, texto, resultado, creada_en FROM consultas_asistente "
                            "WHERE resultado IN ('no_entendio', 'derivo') AND NOT revisada "
                            "ORDER BY creada_en DESC LIMIT 100")
    for f in filas:
        f["sugeridas"] = asistente.sugerir_palabras(f["texto"])
    return filas


@router_empleado.get("/asistente/resumen", summary="Como le va al asistente (admin)")
def resumen_asistente(u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    fila = consultar_uno(
        conn,
        "SELECT CAST(SUM(resultado = 'respondio') AS UNSIGNED) AS respondio, "
        "CAST(SUM(resultado = 'no_entendio') AS UNSIGNED) AS no_entendio, "
        "CAST(SUM(resultado = 'derivo') AS UNSIGNED) AS derivo, "
        "CAST(SUM(resultado <> 'respondio' AND NOT revisada) AS UNSIGNED) AS por_revisar "
        "FROM consultas_asistente WHERE creada_en > NOW() - INTERVAL 30 DAY")
    votos = consultar_uno(conn, "SELECT CAST(IFNULL(SUM(util_si), 0) AS UNSIGNED) AS si, "
                                "CAST(IFNULL(SUM(util_no), 0) AS UNSIGNED) AS no FROM respuestas_automaticas")
    return {k: int(v or 0) for k, v in fila.items()} | {"util_si": int(votos["si"]), "util_no": int(votos["no"])}


@router_empleado.post("/asistente/pendientes/{consulta_id}/ensenar",
                      summary="Ensenarle al asistente: convertir la pregunta en palabras clave de una respuesta")
def ensenar(consulta_id: int, datos: Ensenanza, request: Request,
            u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    c = consultar_uno(conn, "SELECT id, texto FROM consultas_asistente WHERE id = %s", (consulta_id,))
    if not c:
        raise ErrorNegocio(404, "Consulta no encontrada")
    if not consultar_uno(conn, "SELECT id FROM respuestas_automaticas WHERE id = %s", (datos.respuesta_id,)):
        raise ErrorNegocio(404, "Respuesta no encontrada")
    with transaccion(conn):
        agregadas = _guardar_palabras(conn, datos.respuesta_id, datos.palabras, reemplazar=False)
        ejecutar(conn, "UPDATE consultas_asistente SET revisada = TRUE WHERE id = %s", (c["id"],))
    auditoria.registrar(conn, "ASISTENTE_APRENDIO", "respuestas_automaticas", datos.respuesta_id, usuario_id=u.id,
                        detalle={"consulta": c["id"], "palabras": agregadas}, ip=ip_cliente(request))
    return {"agregadas": agregadas}


@router_empleado.post("/asistente/pendientes/{consulta_id}/descartar", summary="Marcar una pregunta como revisada")
def descartar(consulta_id: int, u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    cur = ejecutar(conn, "UPDATE consultas_asistente SET revisada = TRUE WHERE id = %s", (consulta_id,))
    if cur.rowcount == 0 and not consultar_uno(conn, "SELECT id FROM consultas_asistente WHERE id = %s", (consulta_id,)):
        raise ErrorNegocio(404, "Consulta no encontrada")
    return {"id": consulta_id, "revisada": True}


# --------------------------------------------------------------- sinonimos
@router_empleado.get("/asistente/sinonimos", summary="Palabras que significan lo mismo (admin)")
def sinonimos(u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    return consultar(conn, "SELECT palabra, equivale FROM sinonimos ORDER BY equivale, palabra")


@router_empleado.post("/asistente/sinonimos", status_code=201, summary="Agregar un sinonimo (admin)")
def agregar_sinonimo(datos: NuevoSinonimo, request: Request,
                     u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    palabra, equivale = asistente.normalizar(datos.palabra), asistente.normalizar(datos.equivale)
    if not palabra or not equivale or palabra == equivale:
        raise ErrorNegocio(400, "Escribe dos palabras distintas")
    if " " in palabra:
        raise ErrorNegocio(400, "El sinonimo debe ser una sola palabra")
    if consultar_uno(conn, "SELECT palabra FROM sinonimos WHERE palabra = %s", (palabra,)):
        raise ErrorNegocio(409, f"'{palabra}' ya tiene un sinonimo")
    ejecutar(conn, "INSERT INTO sinonimos (palabra, equivale) VALUES (%s, %s)", (palabra, equivale))
    auditoria.registrar(conn, "SINONIMO_AGREGADO", "sinonimos", None, usuario_id=u.id,
                        detalle={"palabra": palabra, "equivale": equivale}, ip=ip_cliente(request))
    return {"palabra": palabra, "equivale": equivale}


@router_empleado.delete("/asistente/sinonimos/{palabra}", summary="Quitar un sinonimo (admin)")
def quitar_sinonimo(palabra: str, request: Request,
                    u: UsuarioActual = Depends(solo_admin), conn=Depends(obtener_conexion)):
    cur = ejecutar(conn, "DELETE FROM sinonimos WHERE palabra = %s", (asistente.normalizar(palabra),))
    if cur.rowcount == 0:
        raise ErrorNegocio(404, "Ese sinonimo no existe")
    auditoria.registrar(conn, "SINONIMO_QUITADO", "sinonimos", None, usuario_id=u.id,
                        detalle={"palabra": palabra}, ip=ip_cliente(request))
    return {"palabra": palabra, "quitado": True}
