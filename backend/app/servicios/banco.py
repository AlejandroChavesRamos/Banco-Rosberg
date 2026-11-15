"""Logica del banco reutilizada por varias rutas."""
import json
import re
import secrets

import pymysql

from ..db.mysql import consultar_uno, ejecutar, transaccion
from ..errores import ErrorNegocio
from ..seguridad import cifrado
from . import grafo

_SELECT_CUENTA = (
    "SELECT c.id, c.numero, c.usuario_id, c.tipo, c.saldo, c.estado, c.creada_en, "
    "u.nombre AS titular "
    "FROM cuentas c JOIN usuarios u ON u.id = c.usuario_id "
)


def generar_numero_cuenta(conn) -> str:
    """Numero de 12 digitos que empieza por 71 (prefijo inventado de Banco Rosberg)."""
    for _ in range(20):
        numero = "71" + "".join(str(secrets.randbelow(10)) for _ in range(10))
        if not consultar_uno(conn, "SELECT 1 FROM cuentas WHERE numero = %s", (numero,)):
            return numero
    raise RuntimeError("No se pudo generar un numero de cuenta unico")


def cuenta_por_numero(conn, numero: str) -> dict | None:
    return consultar_uno(conn, _SELECT_CUENTA + "WHERE c.numero = %s", (numero,))


def cuenta_propia(conn, numero: str, usuario_id: int) -> dict:
    """Devuelve la cuenta solo si pertenece al usuario.

    Si no es suya responde 404 (no 403): asi no revela que la cuenta existe.
    Esto protege contra IDOR (cambiar el numero en la peticion para ver
    cuentas ajenas).
    """
    cuenta = cuenta_por_numero(conn, numero)
    if not cuenta or cuenta["usuario_id"] != usuario_id:
        raise ErrorNegocio(404, "Cuenta no encontrada")
    return cuenta


def exigir_activa(cuenta: dict) -> None:
    if cuenta["estado"] != "activa":
        raise ErrorNegocio(409, f"La cuenta esta {cuenta['estado']}")


def resolver_destino(conn, valor: str) -> dict:
    """Encuentra la cuenta destino por numero de cuenta, celular o correo (llave)."""
    valor = valor.strip().lower()
    if re.fullmatch(r"\d{12}", valor):
        cuenta = cuenta_por_numero(conn, valor)
    else:
        if re.fullmatch(r"3\d{9}", valor):
            tipo = "celular"
        elif "@" in valor:
            tipo = "correo"
        else:
            raise ErrorNegocio(400, "Escriba un numero de cuenta, un celular o un correo")
        cuenta = consultar_uno(
            conn,
            _SELECT_CUENTA + "JOIN llaves l ON l.cuenta_id = c.id "
            "WHERE l.tipo = %s AND l.valor = %s AND l.activa",
            (tipo, valor),
        )
    if not cuenta:
        raise ErrorNegocio(404, "No encontramos una cuenta o llave con ese dato")
    return cuenta


def registrar_dispositivo(conn, usuario_id: int, huella: str, descripcion: str) -> tuple[int, bool]:
    """Devuelve (id del dispositivo, es_nuevo)."""
    cur = ejecutar(
        conn,
        "INSERT INTO dispositivos (usuario_id, huella, descripcion) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE ultima_vez = NOW(), id = LAST_INSERT_ID(id)",
        (usuario_id, huella, descripcion),
    )
    return cur.lastrowid, cur.rowcount == 1   # 1 = insertado, 2 = ya existia


def registrar_alerta(conn, cuenta_id: int, puntaje: int, motivos: list[str],
                     transaccion_id: int | None = None) -> int:
    cur = ejecutar(
        conn,
        "INSERT INTO alertas_fraude (transaccion_id, cuenta_id, puntaje, motivos) "
        "VALUES (%s, %s, %s, %s)",
        (transaccion_id, cuenta_id, puntaje, json.dumps(motivos)),
    )
    return cur.lastrowid


def crear_cliente(conn, *, nombre: str, email: str, cedula: str, celular: str,
                  password_hash: str, debe_cambiar: bool, tipo_cuenta: str = "ahorros") -> dict:
    """Crea el usuario y su primera cuenta en UNA transaccion."""
    documento_hash = cifrado.indice_ciego(cedula, "cedula")
    try:
        with transaccion(conn):
            cur = ejecutar(
                conn,
                "INSERT INTO usuarios (email, password_hash, rol, nombre, documento_cifrado, "
                "documento_hash, telefono_cifrado, debe_cambiar_password) "
                "VALUES (%s, %s, 'cliente', %s, %s, %s, %s, %s)",
                (email.lower(), password_hash, nombre.strip(), cifrado.cifrar(cedula),
                 documento_hash, cifrado.cifrar(celular), debe_cambiar),
            )
            usuario_id = cur.lastrowid
            numero = generar_numero_cuenta(conn)
            cur = ejecutar(conn, "INSERT INTO cuentas (numero, usuario_id, tipo) VALUES (%s, %s, %s)",
                           (numero, usuario_id, tipo_cuenta))
            cuenta_id = cur.lastrowid
    except pymysql.err.IntegrityError:
        # Email o cedula repetidos. Mensaje generico: no revelamos cual dato existe.
        raise ErrorNegocio(409, "No fue posible completar el registro con esos datos")

    grafo.sincronizar_cliente(usuario_id, nombre.strip())
    grafo.sincronizar_cuenta(cuenta_id, numero, usuario_id)
    return {"usuario_id": usuario_id, "cuenta_id": cuenta_id, "numero": numero}


def cambiar_estado_cuenta(conn, cuenta: dict, nuevo_estado: str) -> None:
    ejecutar(conn, "UPDATE cuentas SET estado = %s WHERE id = %s", (nuevo_estado, cuenta["id"]))
    if nuevo_estado != "activa":
        # Un codigo de retiro pendiente no debe poder canjearse en una cuenta congelada
        ejecutar(conn, "UPDATE codigos_retiro SET estado = 'cancelado' "
                       "WHERE cuenta_id = %s AND estado = 'activo'", (cuenta["id"],))
    grafo.actualizar_estado_cuenta(cuenta["id"], nuevo_estado)
