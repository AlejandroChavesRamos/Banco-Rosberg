"""Asistente Rosberg: contestador automatico del chat de ayuda (sin IA externa).

COMO ENTIENDE UN MENSAJE
  1. Normaliza: minusculas, sin tildes ni signos ("¿Olvidé mi CLAVE?" ->
     "olvide mi clave").
  2. Sinonimos: cambia cada palabra por su equivalente (tabla sinonimos):
     "clave" -> "contrasena", "plata" -> "dinero".
  3. Raices: quita terminaciones comunes del espanol para comparar la raiz:
     "retiro", "retirar", "retire" -> "retir"; "bloqueado", "bloquearon" -> "bloque".
  4. Errores de escritura: dos raices largas que difieren en 1 letra (o en 2
     si son muy largas) cuentan como iguales: "trasferencia" = "transferencia".
  5. Una palabra clave de varias palabras ("no me llego") coincide si sus
     palabras aparecen en orden, aunque haya alguna en medio ("no me ha llegado").
  6. Entre las respuestas que coinciden gana la de MAYOR PRIORIDAD (+2 si es un
     tema relacionado con lo que se venia hablando); si empatan, la que tenga
     mas palabras en comun.

CONTEXTO
  - Recuerda la ultima respuesta que dio (tiquetes.asistente_ultima_respuesta):
    los temas relacionados con ella ganan puntos.
  - Si un mensaje corto no coincide con nada ("¿y cuanto tarda?"), lo vuelve a
    intentar junto con el mensaje anterior del cliente.

BOTONES
  Cada respuesta trae botones de respuesta rapida ("Si, me sirvio", "No me
  sirvio" y preguntas de temas relacionados). Al pulsarlos se envia ese texto.

DATOS REALES
  Si la respuesta tiene "accion", ademas consulta (solo lectura) los datos del
  cliente: sus envios, cuentas, saldo, codigos de retiro, llaves o seguridad.
  Siempre los del cliente que abrio el tiquete, con numeros y nombres enmascarados.
  El asistente nunca cambia nada: no mueve dinero ni modifica datos.

APRENDE
  Cada pregunta queda en consultas_asistente. El admin ve las que no entendio
  y con un clic las convierte en palabras clave de una respuesta. Los botones
  "Si/No me sirvio" llevan la cuenta de que respuestas funcionan.

Se apaga (pasa el caso a una persona) si el cliente lo pide, si no entiende
dos veces seguidas o cuando un empleado toma el tiquete.
"""
import json
import logging
import re
import unicodedata
from datetime import datetime

from ..db.mysql import consultar, consultar_uno, ejecutar, leer_config
from ..utilidades import enmascarar_nombre, enmascarar_numero
from . import conocimiento

log = logging.getLogger(__name__)

NOMBRE = "Asistente Rosberg"
ASESOR = "Hablar con un asesor"
OTRA = "Tengo otra pregunta"
SI_SIRVIO = "Sí, me sirvió"
NO_SIRVIO = "No me sirvió"

SALUDO = ("Hola, soy el Asistente Rosberg. Mientras un asesor se desocupa, intento ayudarte. "
          "Puedes escribir tu duda o elegir un tema. Si prefieres a una persona, escribe \"asesor\".")
NO_ENTENDI = ("No estoy seguro de haber entendido. ¿Puedes decirlo con otras palabras? "
              "También puedes elegir uno de estos temas:")
PASO_A_ASESOR = ("Voy a comunicarte con un asesor del banco para que revise tu caso. "
                 "Te responderá por aquí mismo en cuanto se desocupe.")
PIDE_PERSONA = "Listo, le paso tu caso a un asesor. Te responderá por aquí mismo en cuanto se desocupe."

# ------------------------------------------------------------- normalizar
_PIDEN_PERSONA = {"asesor", "asesora", "humano", "persona", "agente", "operador"}
_MENU = {"menu", "temas", "opciones", "ayuda", "que puedes hacer", "en que me ayudas", "tengo otra pregunta"}
_SI = {"si me sirvio", "me sirvio", "si sirvio", "si gracias me sirvio", "si", "funciono", "si funciono"}
_NO = {"no me sirvio", "no sirvio", "no", "no funciono", "no me ayudo", "no era eso"}
# Palabras de pregunta: un mensaje corto con estas probablemente sigue el tema anterior
_SEGUIMIENTO = {"y", "cuanto", "cuando", "como", "donde", "porque", "por", "que", "cual", "eso", "entonces"}
# Terminaciones que se quitan para quedarse con la raiz (de la mas larga a la mas corta)
_SUFIJOS = ("amientos", "imientos", "amiento", "imiento", "aciones", "uciones", "adoras", "adores", "ancias",
            "encias", "acion", "ucion", "adora", "ador", "ancia", "encia", "ieron", "aron", "ando", "iendo",
            "ados", "adas", "idos", "idas", "ado", "ada", "ido", "ida", "ar", "er", "ir", "es", "os", "as",
            "e", "o", "a", "s")


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes ni signos, espacios simples."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                         if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", sin_tildes).split())


def raiz(palabra: str) -> str:
    if len(palabra) <= 4 or palabra.isdigit():
        return palabra
    for s in _SUFIJOS:
        if palabra.endswith(s) and len(palabra) - len(s) >= 4:
            return palabra[: -len(s)]
    return palabra


def _distancia(a: str, b: str, maximo: int) -> int:
    """Distancia de edicion (Levenshtein), cortando apenas supera el maximo."""
    if abs(len(a) - len(b)) > maximo:
        return maximo + 1
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        if min(actual) > maximo:
            return maximo + 1
        previa = actual
    return previa[-1]


def _parecidas(a: str, b: str) -> bool:
    if a == b:
        return True
    corta = min(len(a), len(b))
    if corta < 6:            # palabras cortas: deben ser iguales ("cuenta" no es "cuesta")
        return False
    return _distancia(a, b, 2 if corta >= 9 else 1) <= (2 if corta >= 9 else 1)


def _sinonimos(conn) -> dict:
    return {f["palabra"]: f["equivale"] for f in consultar(conn, "SELECT palabra, equivale FROM sinonimos")}


def _raices(texto: str, sinonimos: dict) -> list[str]:
    salida = []
    for p in normalizar(texto).split():
        salida.extend(sinonimos.get(p, p).split())
    return [raiz(p) for p in salida]


def _coincide(frase: list[str], texto: list[str]) -> bool:
    """Las palabras de la frase aparecen en orden en el texto, con a lo sumo 2 palabras extra en medio."""
    if not frase:
        return False
    for inicio, t in enumerate(texto):
        if not _parecidas(frase[0], t):
            continue
        pos, ok = inicio, True
        for p in frase[1:]:
            ventana = texto[pos + 1: pos + 4]
            siguiente = next((k for k, t2 in enumerate(ventana) if _parecidas(p, t2)), None)
            if siguiente is None:
                ok = False
                break
            pos += 1 + siguiente
        if ok:
            return True
    return False


# ---------------------------------------------------------------- buscar
def buscar_respuesta(conn, texto: str, contexto_id: int | None = None) -> dict | None:
    """La mejor respuesta activa para el texto (o None), con las palabras que coincidieron."""
    sinonimos = _sinonimos(conn)
    t = _raices(texto, sinonimos)
    if not t:
        return None
    normal = normalizar(texto)

    # Si el texto es exactamente la pregunta de una respuesta (boton pulsado), es esa
    for f in consultar(conn, "SELECT id, titulo, respuesta, accion, prioridad, pregunta FROM respuestas_automaticas "
                             "WHERE activa AND pregunta IS NOT NULL"):
        if normalizar(f["pregunta"]) == normal:
            return {**f, "puntos": 99, "coincidencias": ["(botón)"]}

    relacionadas = set()
    if contexto_id:
        relacionadas = {f["relacionada_id"] for f in consultar(
            conn, "SELECT relacionada_id FROM respuestas_relacionadas WHERE respuesta_id = %s", (contexto_id,))}

    filas = consultar(
        conn,
        "SELECT r.id, r.titulo, r.respuesta, r.accion, r.prioridad, r.pregunta, p.palabra "
        "FROM respuestas_automaticas r JOIN palabras_respuesta p ON p.respuesta_id = r.id WHERE r.activa",
    )
    candidatas: dict[int, dict] = {}
    for f in filas:
        frase = _raices(f["palabra"], sinonimos)
        if _coincide(frase, t):
            c = candidatas.setdefault(f["id"], {k: f[k] for k in ("id", "titulo", "respuesta", "accion", "prioridad",
                                                                   "pregunta")} | {"puntos": 0, "coincidencias": []})
            c["puntos"] += len(frase)
            c["coincidencias"].append(f["palabra"])
    if not candidatas:
        return None
    return max(candidatas.values(),
               key=lambda c: (c["prioridad"] + (2 if c["id"] in relacionadas else 0), c["puntos"]))


def pide_persona(texto: str) -> bool:
    n = normalizar(texto)
    return n == normalizar(ASESOR) or any(p in _PIDEN_PERSONA for p in n.split())


# ------------------------------------------------------------- plantillas
_DINERO = {"RETIRO_MAXIMO", "MONTO_2FA"}


def _pesos(valor) -> str:
    return "$" + f"{int(valor):,}".replace(",", ".")


def plantilla(conn, texto: str) -> str:
    """Reemplaza {CLAVE} por el valor actual de la configuracion."""
    def poner(m):
        fila = consultar_uno(conn, "SELECT valor FROM configuracion WHERE clave = %s", (m.group(1),))
        if not fila:
            return m.group(0)
        return _pesos(fila["valor"]) if m.group(1) in _DINERO else fila["valor"]
    return re.sub(r"\{([A-Z0-9_]+)\}", poner, texto)


# ---------------------------------------------------------- datos reales
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _fecha(d: datetime) -> str:
    return f"{d.day} {_MESES[d.month - 1]}"


def _hora(d: datetime) -> str:
    return d.strftime("%I:%M %p").lstrip("0").replace("AM", "a. m.").replace("PM", "p. m.")


_ESTADO_ENVIO = {
    "aprobada": "exitosa",
    "retenida": "en revisión (el dinero sigue en tu cuenta)",
    "bloqueada": "bloqueada por seguridad (el dinero no salió)",
    "rechazada": "rechazada (el dinero no salió)",
}


def _datos_envios(conn, cliente_id: int) -> str:
    enviados = consultar(
        conn,
        "SELECT t.monto, t.estado, t.creada_en, u.nombre AS para FROM transacciones t "
        "JOIN cuentas co ON co.id = t.cuenta_origen_id JOIN cuentas cd ON cd.id = t.cuenta_destino_id "
        "JOIN usuarios u ON u.id = cd.usuario_id "
        "WHERE co.usuario_id = %s AND t.tipo = 'transferencia' AND t.creada_en > NOW() - INTERVAL 30 DAY "
        "ORDER BY t.estado = 'aprobada', t.creada_en DESC LIMIT 4",
        (cliente_id,),
    )
    recibidos = consultar(
        conn,
        "SELECT t.monto, t.creada_en, u.nombre AS de FROM transacciones t "
        "JOIN cuentas cd ON cd.id = t.cuenta_destino_id JOIN cuentas co ON co.id = t.cuenta_origen_id "
        "JOIN usuarios u ON u.id = co.usuario_id "
        "WHERE cd.usuario_id = %s AND t.tipo = 'transferencia' AND t.estado = 'aprobada' "
        "AND t.creada_en > NOW() - INTERVAL 30 DAY ORDER BY t.creada_en DESC LIMIT 3",
        (cliente_id,),
    )
    if not enviados and not recibidos:
        return "Revisé tu cuenta: no tienes transferencias en los últimos 30 días."
    partes = []
    revision = sum(1 for e in enviados if e["estado"] == "retenida")
    if revision:
        partes.append(f"Tienes {revision} envío{'s' if revision > 1 else ''} en revisión.")
    if enviados:
        partes.append("Tus envíos recientes:\n" + "\n".join(
            f"• {_fecha(e['creada_en'])}: {_pesos(e['monto'])} a {enmascarar_nombre(e['para'])}, "
            f"{_ESTADO_ENVIO[e['estado']]}" for e in enviados))
    if recibidos:
        partes.append("Lo último que recibiste:\n" + "\n".join(
            f"• {_fecha(r['creada_en'])}: {_pesos(r['monto'])} de {enmascarar_nombre(r['de'])}" for r in recibidos))
    return "\n\n".join(partes)


def _datos_cuentas(conn, cliente_id: int) -> str:
    cuentas = consultar(conn, "SELECT numero, tipo, estado FROM cuentas WHERE usuario_id = %s ORDER BY id", (cliente_id,))
    if not cuentas:
        return "No encontré cuentas a tu nombre."
    estados = {"activa": "activa ✓", "congelada": "congelada", "cerrada": "cerrada"}
    lineas = [f"• {c['tipo'].capitalize()} {enmascarar_numero(c['numero'])}: {estados[c['estado']]}" for c in cuentas]
    congeladas = sum(c["estado"] == "congelada" for c in cuentas)
    inicio = (f"Revisé tus cuentas: {congeladas} está{'n' if congeladas > 1 else ''} congelada{'s' if congeladas > 1 else ''}."
              if congeladas else "Revisé tus cuentas y ninguna está congelada.")
    return inicio + "\n" + "\n".join(lineas)


def _datos_saldo(conn, cliente_id: int) -> str:
    cuentas = consultar(conn, "SELECT numero, tipo, saldo, estado FROM cuentas WHERE usuario_id = %s "
                              "AND estado <> 'cerrada' ORDER BY id", (cliente_id,))
    if not cuentas:
        return "No encontré cuentas a tu nombre."
    lineas = [f"• {c['tipo'].capitalize()} {enmascarar_numero(c['numero'])}: {_pesos(c['saldo'])}"
              + (" (congelada)" if c["estado"] == "congelada" else "") for c in cuentas]
    if len(cuentas) > 1:
        lineas.append(f"Total: {_pesos(sum(c['saldo'] for c in cuentas))}")
    return "\n".join(lineas)


def _datos_codigos(conn, cliente_id: int) -> str:
    codigos = consultar(
        conn,
        "SELECT r.monto, r.estado, r.creado_en, r.expira_en, (r.expira_en < NOW()) AS vencio "
        "FROM codigos_retiro r JOIN cuentas c ON c.id = r.cuenta_id "
        "WHERE c.usuario_id = %s ORDER BY r.creado_en DESC LIMIT 3",
        (cliente_id,),
    )
    if not codigos:
        return "No has generado códigos de retiro todavía."
    lineas = []
    for c in codigos:
        estado = c["estado"]
        if estado == "activo" and c["vencio"]:
            estado = "vencido"
        texto = {"activo": f"vigente hasta las {_hora(c['expira_en'])}", "usado": "ya se usó",
                 "vencido": "venció (genera uno nuevo)", "bloqueado": "bloqueado por intentos fallidos (genera uno nuevo)",
                 "cancelado": "cancelado"}[estado]
        lineas.append(f"• {_fecha(c['creado_en'])}, {_pesos(c['monto'])}: {texto}")
    return "Tus últimos códigos de retiro:\n" + "\n".join(lineas)


def _ocultar_llave(tipo: str, valor: str) -> str:
    if tipo == "celular":
        return valor[:3] + "****" + valor[-3:]
    usuario, _, dominio = valor.partition("@")
    return usuario[:2] + "***@" + dominio


def _datos_llaves(conn, cliente_id: int) -> str:
    llaves = consultar(conn, "SELECT l.tipo, l.valor, c.numero FROM llaves l JOIN cuentas c ON c.id = l.cuenta_id "
                             "WHERE c.usuario_id = %s AND l.activa ORDER BY l.id", (cliente_id,))
    if not llaves:
        return "Todavía no tienes llaves registradas."
    return "Tus llaves activas:\n" + "\n".join(
        f"• {l['tipo'].capitalize()} {_ocultar_llave(l['tipo'], l['valor'])} → cuenta {enmascarar_numero(l['numero'])}"
        for l in llaves)


def _datos_seguridad(conn, cliente_id: int) -> str:
    u = consultar_uno(conn, "SELECT totp_activo FROM usuarios WHERE id = %s", (cliente_id,))
    avisos = consultar_uno(conn, "SELECT COUNT(*) AS n FROM avisos_login WHERE usuario_id = %s AND estado = 'pendiente'",
                           (cliente_id,))["n"]
    lineas = ["• Verificación en dos pasos: " + ("activa ✓" if u and u["totp_activo"] else "no activada")]
    if avisos:
        lineas.append(f"• Tienes {avisos} aviso{'s' if avisos > 1 else ''} de inicio de sesión sin revisar "
                      "(aparecen arriba en tu pantalla).")
    else:
        lineas.append("• No tienes avisos de inicio de sesión pendientes.")
    return "Revisé tu seguridad:\n" + "\n".join(lineas)


ACCIONES = {
    "envios": _datos_envios, "cuentas": _datos_cuentas, "saldo": _datos_saldo,
    "codigos_retiro": _datos_codigos, "llaves": _datos_llaves, "seguridad": _datos_seguridad,
}


def armar_texto(conn, r: dict, cliente_id: int | None) -> str:
    texto = plantilla(conn, r["respuesta"])
    if r.get("accion") and cliente_id:
        try:
            texto += "\n\n" + ACCIONES[r["accion"]](conn, cliente_id)
        except Exception:  # los datos son un extra: si fallan, se responde igual
            log.exception("No se pudieron consultar los datos (%s)", r["accion"])
    return texto


# --------------------------------------------------------------- botones
def temas_principales(conn, cuantos: int = 4) -> list[str]:
    return [f["pregunta"] for f in consultar(
        conn, "SELECT pregunta FROM respuestas_automaticas WHERE activa AND pregunta IS NOT NULL AND prioridad > 2 "
              "ORDER BY usos DESC, prioridad DESC, id LIMIT %s", (cuantos,))]


def _botones_para(conn, r: dict) -> list[str]:
    if r["prioridad"] <= 2:  # cortesia (saludo, gracias): ofrecer temas
        return temas_principales(conn) + [ASESOR]
    relacionadas = [f["pregunta"] for f in consultar(
        conn, "SELECT a.pregunta FROM respuestas_relacionadas rr JOIN respuestas_automaticas a ON a.id = rr.relacionada_id "
              "WHERE rr.respuesta_id = %s AND a.activa AND a.pregunta IS NOT NULL ORDER BY a.usos DESC LIMIT 2", (r["id"],))]
    return [SI_SIRVIO, NO_SIRVIO] + relacionadas


# ------------------------------------------------------------- conversar
def _decir(conn, tiquete_id: int, texto: str, opciones: list[str] | None = None) -> None:
    ejecutar(conn, "INSERT INTO mensajes_tiquete (tiquete_id, autor_id, automatico, texto, opciones) "
                   "VALUES (%s, NULL, TRUE, %s, %s)",
             (tiquete_id, texto[:1000], json.dumps(opciones, ensure_ascii=False) if opciones else None))
    ejecutar(conn, "UPDATE tiquetes SET actualizado_en = NOW(6) WHERE id = %s", (tiquete_id,))


def _registrar(conn, tiquete_id: int, texto: str, resultado: str, respuesta_id: int | None = None) -> None:
    ejecutar(conn, "INSERT INTO consultas_asistente (tiquete_id, texto, resultado, respuesta_id) VALUES (%s, %s, %s, %s)",
             (tiquete_id, texto[:1000], resultado, respuesta_id))


def _apagar(conn, tiquete_id: int) -> None:
    ejecutar(conn, "UPDATE tiquetes SET asistente_activo = FALSE, asistente_fallos = 0 WHERE id = %s", (tiquete_id,))


def _contestar(conn, t: dict, r: dict) -> None:
    _decir(conn, t["id"], armar_texto(conn, r, t["cliente_id"]), _botones_para(conn, r))
    ejecutar(conn, "UPDATE respuestas_automaticas SET usos = usos + 1 WHERE id = %s", (r["id"],))
    ejecutar(conn, "UPDATE tiquetes SET asistente_fallos = 0, asistente_ultima_respuesta = %s WHERE id = %s",
             (r["id"], t["id"]))


def _mensaje_anterior_del_cliente(conn, t: dict) -> str | None:
    filas = consultar(conn, "SELECT texto FROM mensajes_tiquete WHERE tiquete_id = %s AND autor_id = %s "
                            "ORDER BY id DESC LIMIT 2", (t["id"], t["cliente_id"]))
    return filas[1]["texto"] if len(filas) == 2 else None


def responder(conn, tiquete_id: int, texto_cliente: str) -> str:
    """El cliente escribio en un tiquete con el asistente activo. Devuelve que paso."""
    t = consultar_uno(conn, "SELECT id, cliente_id, asunto, estado, asistente_activo, asistente_fallos, "
                            "asistente_ultima_respuesta FROM tiquetes WHERE id = %s", (tiquete_id,))
    if not t or not t["asistente_activo"] or t["estado"] == "cerrado":
        return "inactivo"
    normal = normalizar(texto_cliente)
    ultima = t["asistente_ultima_respuesta"]

    # 1) Pide una persona
    if pide_persona(texto_cliente):
        _decir(conn, t["id"], PIDE_PERSONA)
        _apagar(conn, t["id"])
        return "derivado"

    # 2) "¿Te sirvio?" (botones)
    if ultima and (normal in _SI or normal in _NO):
        util = normal in _SI
        ejecutar(conn, f"UPDATE respuestas_automaticas SET {'util_si = util_si' if util else 'util_no = util_no'} + 1 "
                       "WHERE id = %s", (ultima,))
        ejecutar(conn, "UPDATE tiquetes SET asistente_ultima_respuesta = NULL WHERE id = %s", (t["id"],))
        if util:
            _decir(conn, t["id"], "¡Qué bien! ¿Te ayudo con algo más? Si ya terminaste, pulsa \"Finalizar\" arriba.",
                   [OTRA, ASESOR])
        else:
            _decir(conn, t["id"], "Lo siento. ¿Quieres que te atienda un asesor o prefieres preguntarlo de otra forma?",
                   [ASESOR, OTRA])
        return "valorado"

    # 3) Pide el menu de temas
    if normal in _MENU:
        _decir(conn, t["id"], "Claro. Escribe tu pregunta o elige uno de estos temas:", temas_principales(conn, 6) + [ASESOR])
        return "menu"

    # 4) Buscar respuesta (con el contexto de lo que se venia hablando)
    r = buscar_respuesta(conn, texto_cliente, ultima)
    if not r and len(normal.split()) <= 6 and set(normal.split()) & _SEGUIMIENTO:
        anterior = _mensaje_anterior_del_cliente(conn, t)
        if anterior:  # "¿y cuanto tarda?" -> se lee junto con el mensaje anterior
            r = buscar_respuesta(conn, f"{anterior} {texto_cliente}", ultima)
    if r:
        _contestar(conn, t, r)
        _registrar(conn, t["id"], texto_cliente, "respondio", r["id"])
        return "respondido"

    # 5) No entendio: una oportunidad mas, luego pasa a una persona
    if t["asistente_fallos"] == 0:
        _decir(conn, t["id"], NO_ENTENDI, temas_principales(conn) + [ASESOR])
        ejecutar(conn, "UPDATE tiquetes SET asistente_fallos = 1 WHERE id = %s", (t["id"],))
        _registrar(conn, t["id"], texto_cliente, "no_entendio")
        return "no_entendio"

    _decir(conn, t["id"], PASO_A_ASESOR)
    _apagar(conn, t["id"])
    _registrar(conn, t["id"], texto_cliente, "derivo")
    return "derivado"


def activar(conn, tiquete_id: int) -> bool:
    """Enciende el asistente y, si el cliente escribio algo sin respuesta, lo contesta ya."""
    cur = ejecutar(conn, "UPDATE tiquetes SET asistente_activo = TRUE, asistente_fallos = 0, "
                         "asistente_desde = IFNULL(asistente_desde, NOW(6)) "
                         "WHERE id = %s AND estado <> 'cerrado' AND NOT asistente_activo", (tiquete_id,))
    if cur.rowcount == 0:
        return False
    _saludar_y_contestar(conn, tiquete_id)
    return True


def _saludar_y_contestar(conn, tiquete_id: int) -> None:
    # Primero se lee lo pendiente (antes del saludo, que seria "el ultimo mensaje")
    t = consultar_uno(conn, "SELECT id, cliente_id, asunto FROM tiquetes WHERE id = %s", (tiquete_id,))
    pendiente = []
    for f in consultar(conn, "SELECT texto, autor_id FROM mensajes_tiquete WHERE tiquete_id = %s ORDER BY id",
                       (tiquete_id,)):
        pendiente = pendiente + [f["texto"]] if f["autor_id"] == t["cliente_id"] else []
    r = buscar_respuesta(conn, " ".join([t["asunto"], *pendiente])) if pendiente else None
    if r and r["prioridad"] > 2:
        _decir(conn, tiquete_id, SALUDO)
        _contestar(conn, t, r)
        _registrar(conn, tiquete_id, " ".join(pendiente), "respondio", r["id"])
    else:
        _decir(conn, tiquete_id, SALUDO, temas_principales(conn) + [ASESOR])


def apagar_por_humano(conn, tiquete_id: int) -> None:
    """Un empleado tomo el tiquete o escribio: el asistente deja de responder."""
    _apagar(conn, tiquete_id)


def revisar_autoactivacion(conn, cliente_id: int) -> None:
    """Activa el asistente en los tiquetes nuevos de este cliente que nadie atendio a tiempo."""
    if leer_config(conn, "ASISTENTE_AUTOMATICO") != 1:
        return
    minutos = leer_config(conn, "MINUTOS_ASISTENTE")
    esperando = consultar(
        conn,
        "SELECT id FROM tiquetes WHERE cliente_id = %s AND estado = 'nuevo' AND NOT asistente_activo "
        "AND asistente_desde IS NULL AND creado_en < NOW(6) - INTERVAL %s MINUTE",
        (cliente_id, minutos),
    )
    for t in esperando:
        # asistente_desde IS NULL en el WHERE: si dos peticiones llegan a la vez, solo una lo activa
        cur = ejecutar(conn, "UPDATE tiquetes SET asistente_activo = TRUE, asistente_fallos = 0, "
                             "asistente_desde = NOW(6) WHERE id = %s AND asistente_desde IS NULL", (t["id"],))
        if cur.rowcount:
            _saludar_y_contestar(conn, t["id"])


# ----------------------------------------------------------- aprender
_VACIAS = {"de", "la", "el", "los", "las", "un", "una", "que", "en", "mi", "me", "y", "a", "por", "para", "con", "no",
           "es", "se", "lo", "le", "al", "del", "como", "pero", "ya", "si", "su", "mis", "tu", "hola", "buenas",
           "buenos", "dias", "tardes", "noches", "quiero", "necesito", "tengo", "puedo", "favor", "porque", "esta",
           "estoy", "hace", "hay", "muy", "mas", "eso", "esto", "ese", "este", "fue", "ser", "sobre", "cuando"}


def sugerir_palabras(texto: str) -> list[str]:
    """Palabras utiles de un mensaje para ensenarselas al asistente."""
    vistas = []
    for p in normalizar(texto).split():
        if len(p) >= 4 and p not in _VACIAS and p not in vistas:
            vistas.append(p)
    return vistas[:6]


# ------------------------------------------------- conocimiento inicial
def sembrar_conocimiento(conn) -> None:
    """Carga el conocimiento de conocimiento.py: solo lo que falta, una vez por version."""
    actual = consultar_uno(conn, "SELECT valor FROM configuracion WHERE clave = 'CONOCIMIENTO_VERSION'")
    if not actual or int(actual["valor"]) >= conocimiento.VERSION:
        return
    ids = {}
    for r in conocimiento.RESPUESTAS:
        fila = consultar_uno(conn, "SELECT id, pregunta, accion FROM respuestas_automaticas WHERE clave = %s",
                             (r["clave"],))
        if fila:
            # Ya existe (quiza editada por el admin): solo completar lo vacio
            if fila["pregunta"] is None and r.get("pregunta"):
                ejecutar(conn, "UPDATE respuestas_automaticas SET pregunta = %s WHERE id = %s", (r["pregunta"], fila["id"]))
            if fila["accion"] is None and r.get("accion"):
                ejecutar(conn, "UPDATE respuestas_automaticas SET accion = %s WHERE id = %s", (r["accion"], fila["id"]))
            # Palabras nuevas de esta version (INSERT IGNORE: no duplica las que ya tiene)
            for p in {normalizar(p) for p in r["palabras"]}:
                ejecutar(conn, "INSERT IGNORE INTO palabras_respuesta (respuesta_id, palabra) VALUES (%s, %s)",
                         (fila["id"], p[:40]))
            ids[r["clave"]] = (fila["id"], False)
        else:
            cur = ejecutar(conn, "INSERT INTO respuestas_automaticas (clave, titulo, pregunta, respuesta, accion, prioridad) "
                                 "VALUES (%s, %s, %s, %s, %s, %s)",
                           (r["clave"], r["titulo"], r.get("pregunta"), r["respuesta"], r.get("accion"), r["prioridad"]))
            ids[r["clave"]] = (cur.lastrowid, True)
            for p in {normalizar(p) for p in r["palabras"]}:
                ejecutar(conn, "INSERT IGNORE INTO palabras_respuesta (respuesta_id, palabra) VALUES (%s, %s)",
                         (cur.lastrowid, p[:40]))
    for r in conocimiento.RESPUESTAS:
        rid, _ = ids[r["clave"]]
        ya = consultar_uno(conn, "SELECT COUNT(*) AS n FROM respuestas_relacionadas WHERE respuesta_id = %s", (rid,))["n"]
        if not ya:
            for clave in r.get("relacionadas", []):
                if clave in ids:
                    ejecutar(conn, "INSERT IGNORE INTO respuestas_relacionadas (respuesta_id, relacionada_id) "
                                   "VALUES (%s, %s)", (rid, ids[clave][0]))
    version_actual = int(actual["valor"])
    for version, clave, columna, valor in conocimiento.AJUSTES:
        if version > version_actual and clave in ids and columna in ("prioridad", "pregunta", "accion"):
            ejecutar(conn, f"UPDATE respuestas_automaticas SET {columna} = %s WHERE id = %s", (valor, ids[clave][0]))
    for version, clave, palabra in conocimiento.QUITAR_PALABRAS:
        if version > version_actual and clave in ids:
            ejecutar(conn, "DELETE FROM palabras_respuesta WHERE respuesta_id = %s AND palabra = %s",
                     (ids[clave][0], palabra))
    for palabra, equivale in conocimiento.SINONIMOS.items():
        ejecutar(conn, "INSERT IGNORE INTO sinonimos (palabra, equivale) VALUES (%s, %s)",
                 (normalizar(palabra), normalizar(equivale)))
    ejecutar(conn, "UPDATE configuracion SET valor = %s WHERE clave = 'CONOCIMIENTO_VERSION'", (str(conocimiento.VERSION),))
    nuevas = sum(1 for _, nueva in ids.values() if nueva)
    log.info("Conocimiento del asistente v%s cargado (%s respuestas nuevas)", conocimiento.VERSION, nuevas)
