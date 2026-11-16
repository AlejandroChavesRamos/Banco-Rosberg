"""Verificacion en dos pasos (2FA) con codigos TOTP, compatibles con
Google Authenticator, Microsoft Authenticator, Authy, etc.

Como funciona TOTP: el banco y la app del celular comparten un SECRETO. Cada
30 segundos ambos calculan un codigo de 6 digitos a partir del secreto y la
hora actual. Si coinciden, el usuario tiene el celular en la mano.

Medidas de seguridad:
  - El secreto se guarda CIFRADO (AES-GCM), igual que la cedula.
  - Un codigo ya usado no se acepta otra vez (columna totp_ultimo_paso):
    si alguien lo ve por encima del hombro, no le sirve.
  - Se acepta un margen de +-30 s por si el reloj del celular no esta exacto.
"""
import hmac
import io
import time

import pyotp
import qrcode
import qrcode.image.svg

from ..db.mysql import consultar_uno, ejecutar, leer_config
from . import cifrado

EMISOR = "Banco Rosberg"


def nuevo_secreto() -> str:
    return pyotp.random_base32()


def uri_configuracion(secreto: str, email: str) -> str:
    """Enlace otpauth:// que la app del celular lee desde el codigo QR."""
    return pyotp.TOTP(secreto).provisioning_uri(name=email, issuer_name=EMISOR)


def qr_svg(texto: str) -> str:
    imagen = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    salida = io.BytesIO()
    imagen.save(salida)
    return salida.getvalue().decode("utf-8")


def verificar_secreto(secreto: str, codigo: str) -> bool:
    """Para el paso de configuracion (todavia no hay nada guardado como activo)."""
    return pyotp.TOTP(secreto).verify(codigo, valid_window=1)


def verificar_codigo(conn, usuario_id: int, codigo: str) -> bool:
    """Verifica el codigo de un usuario con 2FA activo y lo marca como usado."""
    fila = consultar_uno(conn, "SELECT totp_secreto_cifrado, totp_activo, totp_ultimo_paso "
                               "FROM usuarios WHERE id = %s", (usuario_id,))
    if not fila or not fila["totp_activo"] or not fila["totp_secreto_cifrado"]:
        return False
    totp = pyotp.TOTP(cifrado.descifrar(fila["totp_secreto_cifrado"]))
    paso_actual = int(time.time()) // 30
    for paso in (paso_actual - 1, paso_actual, paso_actual + 1):
        if hmac.compare_digest(totp.at(paso * 30), codigo):
            if fila["totp_ultimo_paso"] is not None and paso <= fila["totp_ultimo_paso"]:
                return False   # codigo reutilizado
            ejecutar(conn, "UPDATE usuarios SET totp_ultimo_paso = %s WHERE id = %s", (paso, usuario_id))
            return True
    return False


# ------------------------------------------------- interruptores del admin
def interruptor(conn, clave: str) -> bool:
    return leer_config(conn, clave, str) == "1"


def debe_configurar(conn, rol: str, totp_activo: bool) -> bool:
    """Empleado sin 2FA cuando el admin lo hizo obligatorio."""
    return rol != "cliente" and not totp_activo and interruptor(conn, "2FA_EMPLEADOS")
