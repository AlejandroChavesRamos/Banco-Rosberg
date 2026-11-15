"""Comandos de administracion por consola.

Uso (desde la carpeta del proyecto):
    docker compose exec backend python -m app.cli crear-admin --email admin@rosberg.co --nombre "Tu Nombre"
    docker compose exec backend python -m app.cli resincronizar-grafo

El primer administrador se crea asi (y no con un INSERT en los scripts SQL)
para que ninguna contrasena ni hash quede guardado en el repositorio.
"""
import argparse
import getpass
import os
import sys

import pymysql

from .db.mysql import conectar
from .seguridad import contrasenas
from .servicios import auditoria, grafo


def crear_admin(email: str, nombre: str) -> None:
    password = os.environ.get("BANCO_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Contrasena del administrador: ")
        if password != getpass.getpass("Repita la contrasena: "):
            sys.exit("Las contrasenas no coinciden")
    try:
        contrasenas.validar_politica(password)
    except ValueError as e:
        sys.exit(str(e))

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO usuarios (email, password_hash, rol, nombre) VALUES (%s, %s, 'admin', %s)",
                        (email.lower(), contrasenas.hashear(password), nombre))
            nuevo_id = cur.lastrowid
        auditoria.registrar(conn, "CREAR_ADMIN_CONSOLA", "usuarios", nuevo_id, detalle={"email": email.lower()})
    except pymysql.err.IntegrityError:
        sys.exit("Ya existe un usuario con ese correo")
    finally:
        conn.close()
    print(f"Administrador creado: {email.lower()} (id {nuevo_id})")


def resincronizar_grafo() -> None:
    conn = conectar()
    try:
        print(grafo.resincronizar(conn))
    finally:
        conn.close()
        grafo.cerrar()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_admin = sub.add_parser("crear-admin", help="Crear un usuario administrador")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--nombre", required=True)
    sub.add_parser("resincronizar-grafo", help="Reconstruir Neo4j desde MySQL")
    args = parser.parse_args()

    if args.comando == "crear-admin":
        crear_admin(args.email, args.nombre)
    elif args.comando == "resincronizar-grafo":
        resincronizar_grafo()


if __name__ == "__main__":
    main()
