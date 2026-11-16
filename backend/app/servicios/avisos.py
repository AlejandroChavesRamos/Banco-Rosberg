"""Avisos de inicio de sesion sospechoso para el cliente.

Cuando alguien entra a una cuenta desde un DISPOSITIVO nunca visto o una IP
que el cliente nunca habia usado, el cliente ve un aviso en su App y puede
responder "fui yo" (el dispositivo queda como confiable) o "no fui yo" (se
cierran todas las sesiones y debe cambiar la contrasena).
"""
from ..db.mysql import consultar_uno, ejecutar


def revisar_inicio_sesion(conn, usuario_id: int, dispositivo_id: int, es_nuevo: bool, ip: str) -> None:
    # Si es su primer inicio de sesion no hay con que comparar
    anteriores = consultar_uno(conn, "SELECT COUNT(*) AS n FROM eventos_login WHERE usuario_id = %s AND exito",
                               (usuario_id,))["n"]
    if anteriores == 0:
        return

    motivos = []
    dispositivo = consultar_uno(conn, "SELECT confiable, descripcion FROM dispositivos WHERE id = %s", (dispositivo_id,))
    if es_nuevo and not dispositivo["confiable"]:
        motivos.append("dispositivo nuevo")
    ip_conocida = consultar_uno(conn, "SELECT 1 FROM eventos_login WHERE usuario_id = %s AND exito AND ip = %s LIMIT 1",
                                (usuario_id, ip))
    if not ip_conocida:
        motivos.append(f"ubicacion nueva (IP {ip})")
    if not motivos:
        return

    descripcion = (dispositivo["descripcion"] or "")[:80]
    ejecutar(conn, "INSERT INTO avisos_login (usuario_id, dispositivo_id, ip, motivo) VALUES (%s, %s, %s, %s)",
             (usuario_id, dispositivo_id, ip, f"Inicio de sesion desde {' y '.join(motivos)}. {descripcion}".strip()))
