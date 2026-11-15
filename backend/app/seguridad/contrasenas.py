"""Contrasenas: hash con Argon2id (ganador de la Password Hashing Competition).

Argon2 es lento y usa mucha memoria A PROPOSITO: probar millones de
contrasenas contra un hash robado se vuelve muy costoso.
"""
import re
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_ph = PasswordHasher()

# Hash de una contrasena inventada. Si el email no existe, igual verificamos
# contra este hash para que la respuesta tarde lo mismo: asi un atacante no
# puede averiguar que correos estan registrados midiendo el tiempo.
_HASH_FICTICIO = _ph.hash("contrasena-ficticia-para-igualar-tiempos-1")


def hashear(password: str) -> str:
    return _ph.hash(password)


def verificar(hash_guardado: str, password: str) -> bool:
    try:
        return _ph.verify(hash_guardado, password)
    except (VerificationError, InvalidHashError):
        return False


def verificar_ficticio(password: str) -> None:
    verificar(_HASH_FICTICIO, password)


def necesita_rehash(hash_guardado: str) -> bool:
    return _ph.check_needs_rehash(hash_guardado)


def validar_politica(password: str) -> str:
    if len(password) < 10:
        raise ValueError("La contrasena debe tener al menos 10 caracteres")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("La contrasena debe tener letras y numeros")
    if len(password) > 128:
        raise ValueError("La contrasena es demasiado larga")
    return password


def generar_temporal() -> str:
    """Contrasena temporal para clientes y empleados creados por el banco."""
    alfabeto = string.ascii_letters + string.digits
    while True:
        candidata = "".join(secrets.choice(alfabeto) for _ in range(12))
        try:
            return validar_politica(candidata)
        except ValueError:
            continue
