"""Acceso a MySQL.

Todas las consultas usan PARAMETROS (%s): PyMySQL escapa los valores, asi
que un texto como  ' OR 1=1 --  se trata como dato y no como SQL.
Nunca se arma SQL concatenando datos del usuario.
"""
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from ..config import settings


def conectar() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.app_db_user,
        password=settings.app_db_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def obtener_conexion():
    """Dependencia de FastAPI: una conexion por peticion, siempre cerrada al final."""
    conn = conectar()
    try:
        yield conn
    finally:
        conn.close()


def consultar_uno(conn, sql: str, params: tuple = ()) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def consultar(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def ejecutar(conn, sql: str, params: tuple = ()):
    """Ejecuta INSERT/UPDATE y devuelve el cursor (lastrowid, rowcount)."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur


def llamar_sp(conn, nombre: str, args: list):
    """Llama un procedimiento cuyo ULTIMO parametro es OUT y devuelve ese valor.

    `nombre` siempre es una constante del codigo, nunca un dato del usuario.
    """
    marcadores = ", ".join(["%s"] * len(args) + ["@salida"])
    with conn.cursor() as cur:
        cur.execute(f"CALL {nombre}({marcadores})", args)
        cur.execute("SELECT @salida AS salida")
        return cur.fetchone()["salida"]


@contextmanager
def transaccion(conn):
    """Agrupa varias sentencias en una transaccion ACID: o todas o ninguna."""
    conn.begin()
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def leer_config(conn, clave: str, tipo=int):
    fila = consultar_uno(conn, "SELECT valor FROM configuracion WHERE clave = %s", (clave,))
    return tipo(fila["valor"])
