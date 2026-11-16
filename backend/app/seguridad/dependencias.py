"""Autenticacion y autorizacion por roles (RBAC) como dependencias de FastAPI.

Uso en una ruta:
    def mi_ruta(u: UsuarioActual = Depends(requiere_rol("cajero", "admin"))):

El rol se lee de la BASE DE DATOS en cada peticion (no solo del token):
si un admin desactiva a un empleado, pierde el acceso de inmediato.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..db.mysql import consultar_uno, obtener_conexion
from . import doble_factor
from .tokens import decodificar

_bearer = HTTPBearer(auto_error=False, description="Pega aqui el access_token del login")


class UsuarioActual(BaseModel):
    id: int
    rol: str
    nombre: str
    email: str
    debe_cambiar_password: bool
    tiene_2fa: bool = False
    debe_configurar_2fa: bool = False


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    conn=Depends(obtener_conexion),
) -> UsuarioActual:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debe iniciar sesion",
                            headers={"WWW-Authenticate": "Bearer"})
    datos = decodificar(cred.credentials, "access")
    fila = consultar_uno(
        conn,
        "SELECT id, rol, nombre, email, activo, debe_cambiar_password, totp_activo "
        "FROM usuarios WHERE id = %s",
        (int(datos["sub"]),),
    )
    if not fila or not fila["activo"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo o inexistente",
                            headers={"WWW-Authenticate": "Bearer"})
    return UsuarioActual(
        id=fila["id"], rol=fila["rol"], nombre=fila["nombre"], email=fila["email"],
        debe_cambiar_password=bool(fila["debe_cambiar_password"]),
        tiene_2fa=bool(fila["totp_activo"]),
        debe_configurar_2fa=doble_factor.debe_configurar(conn, fila["rol"], bool(fila["totp_activo"])),
    )


def requiere_rol(*roles: str):
    def _verificar(u: UsuarioActual = Depends(usuario_actual)) -> UsuarioActual:
        if u.debe_cambiar_password:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Debe cambiar su contrasena temporal en /auth/cambiar-password")
        if u.debe_configurar_2fa:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "El banco exige verificacion en dos pasos: configurela antes de continuar")
        if u.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permiso para esta operacion")
        return u

    return _verificar
