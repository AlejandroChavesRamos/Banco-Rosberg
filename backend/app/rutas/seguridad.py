"""Seguridad de la cuenta del cliente: avisos de inicio de sesion sospechoso."""
from fastapi import APIRouter, Depends, Request

from ..db.mysql import consultar, consultar_uno, ejecutar, obtener_conexion
from ..errores import ErrorNegocio
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, banco
from ..utilidades import ip_cliente

router = APIRouter(prefix="/seguridad", tags=["2. Cliente"])
solo_cliente = requiere_rol("cliente")


@router.get("/avisos", summary="Inicios de sesion sospechosos sin revisar")
def avisos_pendientes(u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    return consultar(conn, "SELECT id, ip, motivo, creado_en FROM avisos_login "
                           "WHERE usuario_id = %s AND estado = 'pendiente' ORDER BY id DESC LIMIT 10", (u.id,))


def _aviso_propio(conn, aviso_id: int, usuario_id: int) -> dict:
    aviso = consultar_uno(conn, "SELECT id, dispositivo_id, ip, estado FROM avisos_login "
                                "WHERE id = %s AND usuario_id = %s", (aviso_id, usuario_id))
    if not aviso:
        raise ErrorNegocio(404, "Aviso no encontrado")
    if aviso["estado"] != "pendiente":
        raise ErrorNegocio(409, "Este aviso ya fue respondido")
    return aviso


@router.post("/avisos/{aviso_id}/fui-yo", summary="Reconocer el inicio de sesion")
def fui_yo(aviso_id: int, request: Request, u: UsuarioActual = Depends(solo_cliente), conn=Depends(obtener_conexion)):
    aviso = _aviso_propio(conn, aviso_id, u.id)
    ejecutar(conn, "UPDATE avisos_login SET estado = 'reconocido', resuelto_en = NOW() WHERE id = %s", (aviso_id,))
    if aviso["dispositivo_id"]:
        # El cliente confirma que es suyo: queda como confiable (el motor deja de sospechar de el)
        ejecutar(conn, "UPDATE dispositivos SET confiable = TRUE WHERE id = %s AND usuario_id = %s",
                 (aviso["dispositivo_id"], u.id))
    auditoria.registrar(conn, "AVISO_LOGIN_RECONOCIDO", "avisos_login", aviso_id, usuario_id=u.id, ip=ip_cliente(request))
    return {"mensaje": "Gracias. Marcamos ese dispositivo como de confianza."}


@router.post("/avisos/{aviso_id}/no-fui-yo", summary="Denunciar un inicio de sesion no reconocido")
def no_fui_yo(aviso_id: int, request: Request, u: UsuarioActual = Depends(solo_cliente),
              conn=Depends(obtener_conexion)):
    aviso = _aviso_propio(conn, aviso_id, u.id)
    ejecutar(conn, "UPDATE avisos_login SET estado = 'no_reconocido', resuelto_en = NOW() WHERE id = %s", (aviso_id,))
    # 1) Echar a todos: se cierran TODAS las sesiones (tambien la del intruso)
    ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE usuario_id = %s", (u.id,))
    # 2) Obligar a cambiar la contrasena (el intruso la conoce)
    ejecutar(conn, "UPDATE usuarios SET debe_cambiar_password = TRUE WHERE id = %s", (u.id,))
    # 3) Avisar al area de fraude con una alerta sobre la cuenta principal del cliente
    cuenta = consultar_uno(conn, "SELECT id FROM cuentas WHERE usuario_id = %s ORDER BY id LIMIT 1", (u.id,))
    if cuenta:
        banco.registrar_alerta(conn, cuenta["id"], 50, [{
            "codigo": "ACCESO_NO_RECONOCIDO", "peso": 50,
            "detalle": f"El cliente reporto que no reconoce un inicio de sesion desde la IP {aviso['ip']}"}])
    auditoria.registrar(conn, "AVISO_LOGIN_NO_RECONOCIDO", "avisos_login", aviso_id, usuario_id=u.id,
                        detalle={"ip_intruso": aviso["ip"]}, ip=ip_cliente(request))
    return {"mensaje": "Cerramos todas las sesiones de tu cuenta y avisamos a nuestro equipo de fraude. "
                       "Por seguridad, crea una contrasena nueva."}
