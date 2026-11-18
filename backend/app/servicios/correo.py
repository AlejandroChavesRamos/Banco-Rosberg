"""Envio de correos del banco.

En desarrollo el servidor es Mailpit (contenedor `mailpit`): recibe el correo
por SMTP y lo muestra en http://localhost:8025 sin enviarlo a nadie real.
Para usar un servidor real bastaria cambiar SMTP_HOST y SMTP_PUERTO.

Seguridad:
  - El texto lo escribe un empleado: va como texto plano y, en la version
    HTML, ESCAPADO (html.escape), asi un "<script>" se ve como texto.
  - El destinatario sale de la base (validado como correo al guardarse) y el
    asunto es fijo: no hay forma de inyectar cabeceras.
  - Tiempo de espera corto: si el servidor de correo no responde, la
    peticion no se queda colgada; la respuesta queda como "fallida".
"""
import html
import logging
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

from ..config import settings

log = logging.getLogger(__name__)

ASUNTOS = {
    "tarjeta": "Tu solicitud de tarjeta física",
    "contacto": "Respuesta a tu mensaje",
    "empleo": "Tu postulación en Banco Rosberg",
}


class CorreoNoEnviado(Exception):
    """El servidor de correo no acepto o no recibio el mensaje."""


def _html(saludo: str, texto: str, cierre: str) -> str:
    parrafos = "".join(
        f'<p style="margin:0 0 14px">{html.escape(p).replace(chr(10), "<br>")}</p>'
        for p in texto.split("\n\n") if p.strip()
    )
    return f"""<!doctype html>
<html lang="es"><body style="margin:0;background:#F4F9F1;font-family:Arial,Helvetica,sans-serif;color:#0C2B26">
  <div style="max-width:560px;margin:0 auto;padding:32px 16px">
    <div style="background:#164A41;color:#fff;border-radius:16px 16px 0 0;padding:20px 28px;font-size:20px;font-weight:bold">
      Banco Rosberg
    </div>
    <div style="background:#fff;border-radius:0 0 16px 16px;padding:28px;line-height:1.55;font-size:15px">
      <p style="margin:0 0 14px">{html.escape(saludo)}</p>
      {parrafos}
      <p style="margin:24px 0 0;color:#4D774E;font-size:13px">{html.escape(cierre)}</p>
    </div>
    <p style="text-align:center;color:#74A06E;font-size:12px;margin-top:16px">
      Banco Rosberg es un banco simulado con fines académicos.
    </p>
  </div>
</body></html>"""


def enviar_respuesta_solicitud(destinatario: str, tipo: str, texto: str) -> None:
    """Envia la respuesta de un empleado al visitante que dejo una solicitud."""
    saludo = "Hola,"
    cierre = ("Este correo no recibe respuestas. Si necesitas algo más, déjanos otra solicitud "
              "en la página del banco o abre tu cuenta en minutos.")
    msg = EmailMessage()
    msg["Subject"] = ASUNTOS.get(tipo, "Respuesta de Banco Rosberg")
    msg["From"] = settings.correo_remitente
    msg["To"] = destinatario
    msg["Message-ID"] = make_msgid(domain="rosberg.co")
    msg.set_content(f"{saludo}\n\n{texto}\n\n--\n{cierre}\n")
    msg.add_alternative(_html(saludo, texto, cierre), subtype="html")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_puerto, timeout=5) as smtp:
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        log.warning("No se pudo enviar el correo: %s", e)
        raise CorreoNoEnviado("El servidor de correo no está disponible") from e
