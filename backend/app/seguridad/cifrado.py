"""Cifrado de datos sensibles e indices ciegos.

- AES-256-GCM: cifra la cedula y el telefono. Cada valor lleva un "nonce"
  aleatorio, asi dos cedulas iguales producen textos cifrados distintos.
  GCM ademas detecta si alguien altero el dato cifrado.
- Indice ciego (HMAC-SHA256): como el cifrado es aleatorio, no se puede
  buscar "WHERE documento_cifrado = ...". Guardamos tambien un HMAC con una
  clave secreta: permite buscar por cedula exacta sin poder revertirlo.
"""
import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings


def _clave(valor_b64: str, nombre: str) -> bytes:
    clave = base64.b64decode(valor_b64)
    if len(clave) != 32:
        raise ValueError(f"{nombre} debe ser base64 de 32 bytes")
    return clave


_AES = AESGCM(_clave(settings.clave_cifrado, "CLAVE_CIFRADO"))
_CLAVE_INDICES = _clave(settings.clave_indices, "CLAVE_INDICES")


def cifrar(texto: str) -> bytes:
    nonce = os.urandom(12)
    return nonce + _AES.encrypt(nonce, texto.encode("utf-8"), None)


def descifrar(datos: bytes) -> str:
    return _AES.decrypt(datos[:12], datos[12:], None).decode("utf-8")


def indice_ciego(texto: str, contexto: str) -> str:
    """HMAC con contexto: el mismo valor da hashes distintos en cada uso."""
    mensaje = f"{contexto}:{texto}".encode("utf-8")
    return hmac.new(_CLAVE_INDICES, mensaje, hashlib.sha256).hexdigest()


def iguales(a: str, b: str) -> bool:
    """Comparacion en tiempo constante (evita ataques de tiempo)."""
    return hmac.compare_digest(a, b)
