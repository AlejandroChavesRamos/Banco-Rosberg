"""Funciones auxiliares sobre la peticion HTTP."""
import hashlib
import socket
import time

from fastapi import Request

from .config import settings

_ip_proxy = {"ip": None, "revisado": 0.0}


def _es_proxy_confiable(ip: str) -> bool:
    """La peticion viene de nginx? (se resuelve su IP en la red de Docker)."""
    if not settings.proxy_confiable:
        return False
    if time.time() - _ip_proxy["revisado"] > 60:   # se vuelve a resolver cada minuto
        try:
            _ip_proxy["ip"] = socket.gethostbyname(settings.proxy_confiable)
        except OSError:
            _ip_proxy["ip"] = None
        _ip_proxy["revisado"] = time.time()
    return ip == _ip_proxy["ip"]


def ip_cliente(request: Request) -> str:
    """IP real del cliente.

    Las cabeceras X-Forwarded-For / X-Real-IP las puede escribir CUALQUIERA,
    asi que solo se creen en dos casos:
      - Produccion: si la peticion viene de nginx (que pone X-Real-IP con la IP real).
      - Desarrollo: si se activo CONFIAR_X_FORWARDED_FOR (lo usa el simulador).
    """
    directa = request.client.host if request.client else "desconocida"
    if _es_proxy_confiable(directa):
        return (request.headers.get("x-real-ip") or directa)[:45]
    if settings.confiar_x_forwarded_for:
        reenviada = request.headers.get("x-forwarded-for")
        if reenviada:
            return reenviada.split(",")[0].strip()[:45]
    return directa


def huella_dispositivo(request: Request) -> tuple[str, str]:
    """Identifica el dispositivo del usuario.

    El frontend enviara la cabecera X-Dispositivo con un identificador
    persistente del navegador. Si no llega (por ejemplo, desde /docs), se usa
    el User-Agent. Se guarda solo su hash SHA-256.
    """
    agente = request.headers.get("user-agent", "sin-agente")
    base = request.headers.get("x-dispositivo") or agente
    return hashlib.sha256(base.encode("utf-8")).hexdigest(), agente[:255]


def enmascarar_nombre(nombre: str) -> str:
    """'Juan Perez Gomez' -> 'Juan P**** G****'."""
    partes = nombre.split()
    return " ".join(p if i == 0 else p[0] + "*" * (len(p) - 1) for i, p in enumerate(partes))


def enmascarar_numero(numero: str) -> str:
    return "****" + numero[-4:]
