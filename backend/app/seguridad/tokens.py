"""Tokens JWT.

- access: dura 15 minutos y viaja en la cabecera Authorization.
- refresh: dura 7 dias, viaja en una cookie HttpOnly (JavaScript no la puede
  leer, asi un ataque XSS no puede robarla) y esta registrado en la tabla
  `sesiones`, por lo que se puede revocar.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from ..config import settings

_ALGORITMO = "HS256"


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def crear_access(usuario_id: int, rol: str) -> str:
    ahora = _ahora()
    datos = {
        "sub": str(usuario_id),
        "rol": rol,
        "tipo": "access",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.access_minutos),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(datos, settings.jwt_secreto, algorithm=_ALGORITMO)


def crear_refresh(usuario_id: int, jti: str) -> str:
    ahora = _ahora()
    datos = {
        "sub": str(usuario_id),
        "tipo": "refresh",
        "iat": ahora,
        "exp": ahora + timedelta(days=settings.refresh_dias),
        "jti": jti,
    }
    return jwt.encode(datos, settings.jwt_secreto, algorithm=_ALGORITMO)


def crear_paso_2fa(usuario_id: int, portal: str) -> str:
    """Token de 5 minutos que solo sirve para el segundo paso del login
    (la contrasena ya fue correcta, falta el codigo del celular)."""
    ahora = _ahora()
    datos = {
        "sub": str(usuario_id),
        "tipo": "2fa",
        "portal": portal,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=5),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(datos, settings.jwt_secreto, algorithm=_ALGORITMO)


def decodificar(token: str, tipo_esperado: str) -> dict:
    """Valida firma, vencimiento y tipo.

    `algorithms` es una lista fija: impide el ataque clasico de enviar un
    token con "alg": "none" (sin firma).
    """
    try:
        datos = jwt.decode(
            token,
            settings.jwt_secreto,
            algorithms=[_ALGORITMO],
            options={"require": ["exp", "sub", "tipo", "jti"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido o vencido",
                            headers={"WWW-Authenticate": "Bearer"})
    if datos.get("tipo") != tipo_esperado:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tipo de token incorrecto",
                            headers={"WWW-Authenticate": "Bearer"})
    return datos
