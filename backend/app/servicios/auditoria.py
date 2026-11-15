"""Registro de auditoria.

El hash encadenado lo calcula el trigger trg_auditoria_hash en MySQL. Aqui
tomamos un candado (GET_LOCK) para que dos peticiones simultaneas no lean el
mismo "hash anterior" y rompan la cadena.
"""
import json

from ..db.mysql import consultar_uno, ejecutar


def registrar(conn, accion: str, entidad: str, entidad_id: int | None = None,
              usuario_id: int | None = None, detalle: dict | None = None,
              ip: str | None = None) -> None:
    consultar_uno(conn, "SELECT GET_LOCK('banco_auditoria', 5) AS ok")
    try:
        ejecutar(
            conn,
            "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id, detalle, ip) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (usuario_id, accion, entidad, entidad_id,
             json.dumps(detalle, default=str, ensure_ascii=False) if detalle is not None else None,
             ip),
        )
    finally:
        consultar_uno(conn, "SELECT RELEASE_LOCK('banco_auditoria') AS ok")
