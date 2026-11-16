"""Motor antifraude en TIEMPO REAL.

Se ejecuta antes de cada transferencia y de cada codigo de retiro.
Cada regla activa de la tabla `reglas_fraude` que se cumpla suma su PESO:

    puntaje 0-39  -> aprobada
    puntaje 40-69 -> retenida  (el dinero no se mueve hasta que decida un analista)
    puntaje 70+   -> bloqueada

Reglas en MySQL (comportamiento de la propia cuenta):
    MONTO_INUSUAL, VELOCIDAD, HORARIO_NOCTURNO, DISPOSITIVO_NUEVO, CUENTA_DESTINO_NUEVA
Reglas en Neo4j (relaciones con otras cuentas):
    DISPOSITIVO_COMPARTIDO, CICLO_DINERO, CUENTA_MULA, CERCANIA_FRAUDE

Los pesos y umbrales se leen de la base de datos en cada evaluacion: si el
administrador los cambia, el motor se ajusta sin reiniciar nada.
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from ..db.mysql import consultar, consultar_uno, leer_config
from ..servicios import grafo

log = logging.getLogger("banco.antifraude")


def _cop(valor) -> str:
    return "$" + f"{int(valor):,}".replace(",", ".")


@dataclass
class ContextoOperacion:
    tipo: str                          # 'transferencia' | 'retiro'
    cuenta_origen_id: int
    monto: Decimal
    cuenta_destino_id: int | None = None
    usuario_id: int | None = None
    dispositivo_id: int | None = None
    dispositivo_nuevo: bool = False
    huella: str | None = None
    ip: str | None = None

    @property
    def cuenta_receptora(self) -> int:
        """La cuenta que RECIBE el dinero: el destino en una transferencia;
        en un retiro, la propia cuenta que se esta vaciando."""
        return self.cuenta_destino_id if self.tipo == "transferencia" else self.cuenta_origen_id


@dataclass
class Evaluacion:
    puntaje: int
    decision: str                      # 'aprobada' | 'retenida' | 'bloqueada'
    motivos: list[dict] = field(default_factory=list)


class Acumulador:
    """Va sumando las reglas que se cumplen, con una explicacion para el analista."""

    def __init__(self, reglas: dict[str, dict]):
        self.reglas = reglas
        self.motivos: list[dict] = []

    def activa(self, codigo: str) -> bool:
        return codigo in self.reglas

    def umbral(self, codigo: str) -> float:
        return float(self.reglas[codigo]["umbral"] or 0)

    def sumar(self, codigo: str, detalle: str) -> None:
        self.motivos.append({"codigo": codigo, "peso": int(self.reglas[codigo]["peso"]), "detalle": detalle})

    @property
    def puntaje(self) -> int:
        return min(100, sum(m["peso"] for m in self.motivos))


def cargar_reglas(conn) -> dict[str, dict]:
    return {r["codigo"]: r for r in consultar(conn, "SELECT codigo, peso, umbral FROM reglas_fraude WHERE activa")}


def decidir(conn, puntaje: int) -> str:
    if puntaje >= leer_config(conn, "UMBRAL_BLOQUEAR"):
        return "bloqueada"
    if puntaje >= leer_config(conn, "UMBRAL_RETENER"):
        return "retenida"
    return "aprobada"


# ====================================================== reglas en MySQL
def _reglas_mysql(conn, ctx: ContextoOperacion, acc: Acumulador) -> None:
    if acc.activa("MONTO_INUSUAL"):
        fila = consultar_uno(conn, "SELECT COUNT(*) AS n, IFNULL(AVG(monto), 0) AS promedio FROM transacciones "
                                   "WHERE cuenta_origen_id = %s AND estado = 'aprobada'", (ctx.cuenta_origen_id,))
        veces = acc.umbral("MONTO_INUSUAL")
        # Se necesita algo de historia para saber que es "normal"
        if fila["n"] >= 3 and fila["promedio"] > 0 and ctx.monto > fila["promedio"] * Decimal(str(veces)):
            acc.sumar("MONTO_INUSUAL", f"{_cop(ctx.monto)} es {ctx.monto / fila['promedio']:.1f} veces "
                                       f"su promedio ({_cop(fila['promedio'])})")

    if acc.activa("VELOCIDAD"):
        recientes = consultar_uno(conn, "SELECT fn_tx_recientes(%s, 10) AS n", (ctx.cuenta_origen_id,))["n"]
        if recientes >= acc.umbral("VELOCIDAD"):
            acc.sumar("VELOCIDAD", f"{recientes + 1} operaciones en los ultimos 10 minutos")

    if acc.activa("HORARIO_NOCTURNO"):
        hora = consultar_uno(conn, "SELECT HOUR(NOW()) AS h")["h"]
        if hora < acc.umbral("HORARIO_NOCTURNO"):
            acc.sumar("HORARIO_NOCTURNO", f"Operacion a las {hora}:00 (madrugada)")

    if acc.activa("DISPOSITIVO_NUEVO") and ctx.dispositivo_id and ctx.usuario_id:
        # Nuevo = visto por primera vez hace menos de 24 h, en un cliente que YA
        # tenia otro dispositivo de antes. (El primer celular de un cliente nuevo no cuenta.)
        # Si el cliente ya dijo "fui yo" (dispositivo confiable), no se sospecha de el
        fila = consultar_uno(
            conn,
            "SELECT (d.primera_vez > NOW() - INTERVAL 1 DAY AND NOT d.confiable) AS reciente, "
            "(SELECT COUNT(*) FROM dispositivos o WHERE o.usuario_id = d.usuario_id AND o.id <> d.id "
            " AND o.primera_vez <= NOW() - INTERVAL 1 DAY) AS anteriores "
            "FROM dispositivos d WHERE d.id = %s",
            (ctx.dispositivo_id,),
        )
        if fila and fila["reciente"] and fila["anteriores"] > 0:
            acc.sumar("DISPOSITIVO_NUEVO", "Primera vez que se usa este dispositivo; el cliente "
                                           f"tiene {fila['anteriores']} dispositivo(s) habitual(es)")

    if acc.activa("CUENTA_DESTINO_NUEVA") and ctx.cuenta_receptora:
        dias = consultar_uno(conn, "SELECT fn_dias_antiguedad(%s) AS d", (ctx.cuenta_receptora,))["d"]
        if dias is not None and dias < acc.umbral("CUENTA_DESTINO_NUEVA"):
            quien = "La cuenta destino" if ctx.tipo == "transferencia" else "La cuenta que retira"
            acc.sumar("CUENTA_DESTINO_NUEVA", f"{quien} tiene {dias} dia(s) de creada")


# ====================================================== reglas en Neo4j
def _reglas_grafo(conn, ctx: ContextoOperacion, acc: Acumulador) -> None:
    if acc.activa("DISPOSITIVO_COMPARTIDO") and ctx.huella:
        n = grafo.consultar_grafo(
            "MATCH (d:Dispositivo {huella: $huella})<-[:USA]-(c:Cliente) RETURN count(DISTINCT c) AS n",
            huella=ctx.huella)[0]["n"]
        if n >= acc.umbral("DISPOSITIVO_COMPARTIDO"):
            acc.sumar("DISPOSITIVO_COMPARTIDO", f"Este dispositivo lo usan {n} clientes distintos")

    if acc.activa("CICLO_DINERO") and ctx.tipo == "transferencia":
        # La flecha nueva todavia no existe: buscamos si YA hay un camino
        # destino -> ... -> origen. Si existe, esta transferencia cerraria el circulo.
        # Solo cuenta si es reciente (48 h) y con montos parecidos (+-20%).
        saltos = max(2, int(acc.umbral("CICLO_DINERO")) - 1)
        filas = grafo.consultar_grafo(
            f"""
            MATCH p = (d:Cuenta {{id: $destino}})-[:TRANSFIERE*2..{saltos}]->(o:Cuenta {{id: $origen}})
            WHERE all(t IN relationships(p) WHERE t.fecha > datetime() - duration('PT48H')
                      AND t.monto >= $monto * 0.8 AND t.monto <= $monto * 1.25)
            RETURN [n IN nodes(p) | n.numero] AS camino LIMIT 1
            """,
            destino=ctx.cuenta_destino_id, origen=ctx.cuenta_origen_id, monto=float(ctx.monto))
        if filas:
            camino = " -> ".join("****" + n[-4:] for n in filas[0]["camino"])
            acc.sumar("CICLO_DINERO", f"El dinero cerraria un circulo: {camino} -> ****{filas[0]['camino'][0][-4:]}")

    if acc.activa("CUENTA_MULA") and ctx.cuenta_receptora:
        n = grafo.consultar_grafo(
            "MATCH (o:Cuenta)-[t:TRANSFIERE]->(m:Cuenta {id: $cuenta}) "
            "WHERE t.fecha > datetime() - duration('PT24H') AND o.id <> $excluir "
            "RETURN count(DISTINCT o) AS n",
            cuenta=ctx.cuenta_receptora, excluir=ctx.cuenta_origen_id)[0]["n"]
        if ctx.tipo == "transferencia":
            n += 1   # el remitente actual tambien cuenta
        dias = consultar_uno(conn, "SELECT fn_dias_antiguedad(%s) AS d", (ctx.cuenta_receptora,))["d"]
        # Solo es sospechoso en cuentas NUEVAS: un comerciante antiguo recibe de muchos y es normal
        if n >= acc.umbral("CUENTA_MULA") and dias is not None and dias < 30:
            acc.sumar("CUENTA_MULA", f"Cuenta de {dias} dia(s) que recibio de {n} personas distintas en 24 h")

    if acc.activa("CERCANIA_FRAUDE") and ctx.tipo == "transferencia":
        saltos = max(1, int(acc.umbral("CERCANIA_FRAUDE")))
        cerca = grafo.consultar_grafo(
            f"""
            MATCH (d:Cuenta {{id: $destino}})
            RETURN EXISTS {{
                MATCH (d)-[:TRANSFIERE*1..{saltos}]-(f:Cuenta) WHERE f.estado = 'congelada' AND f <> d
            }} AS cerca
            """,
            destino=ctx.cuenta_destino_id)[0]["cerca"]
        if cerca:
            acc.sumar("CERCANIA_FRAUDE", f"La cuenta destino esta a {saltos} salto(s) o menos de una cuenta congelada")


def evaluar(conn, ctx: ContextoOperacion) -> Evaluacion:
    acc = Acumulador(cargar_reglas(conn))
    _reglas_mysql(conn, ctx, acc)
    try:
        _reglas_grafo(conn, ctx, acc)
    except grafo.GrafoNoDisponible:
        # Si el contenedor de Neo4j esta apagado, el banco sigue operando solo con
        # las reglas de MySQL (se prefiere no detener los pagos de todos los clientes).
        log.warning("Neo4j no disponible: operacion evaluada solo con las reglas de MySQL")
    except Exception:
        log.exception("Error en las reglas de grafo; se evalua solo con MySQL")
    puntaje = acc.puntaje
    return Evaluacion(puntaje=puntaje, decision=decidir(conn, puntaje), motivos=acc.motivos)
