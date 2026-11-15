"""Funciones auxiliares sobre la peticion HTTP."""
import hashlib

from fastapi import Request

from .config import settings


def ip_cliente(request: Request) -> str:
    # X-Forwarded-For la puede escribir cualquiera, por eso solo se usa si se
    # activo a proposito (desarrollo/simulador). En la Fase 6 solo se confiara
    # en la que agregue nginx.
    if settings.confiar_x_forwarded_for:
        reenviada = request.headers.get("x-forwarded-for")
        if reenviada:
            return reenviada.split(",")[0].strip()[:45]
    return request.client.host if request.client else "desconocida"


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
