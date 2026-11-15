"""BARRIDO: busca patrones de fraude en TODO el historial.

El motor en tiempo real solo ve la operacion que esta ocurriendo. El barrido
recorre el grafo completo y encuentra fraudes que ya pasaron (por ejemplo,
antes de que existieran las reglas). Solo CREA ALERTAS: la decision de
congelar una cuenta siempre la toma un analista.

Patrones:
  1. DISPOSITIVO_COMPARTIDO  (Neo4j)  un dispositivo usado por N+ clientes
  2. CICLO_DINERO            (Neo4j)  el dinero da la vuelta en 3 o 4 saltos, rapido y con montos parecidos
  3. CUENTA_MULA             (Neo4j + MySQL)  cuenta nueva que recibe de N+ personas en 24 h
                             Y ademas se vacia rapido (o el motor ya la habia frenado)
  4. VELOCIDAD (rafaga)      (MySQL)  mas de N transferencias en 10 min hacia una misma cuenta
"""
from collections import defaultdict
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

# Una mula saca el dinero enseguida; un negocio legitimo lo deja en su cuenta.
VACIADO_MINIMO = 0.7      # saco al menos el 70% de lo recibido...
HORAS_VACIADO = 48        # ...en las 48 horas siguientes a la ventana

from decimal import Decimal

from ..config import settings
from ..db.mysql import consultar, consultar_uno
from ..servicios import banco, grafo
from .motor import cargar_reglas


def _ya_alertada(conn, cuenta_id: int, codigo: str) -> bool:
    """Evita duplicados: si la cuenta ya tuvo una alerta por este patron, no se repite."""
    return consultar_uno(
        conn,
        "SELECT 1 FROM alertas_fraude WHERE cuenta_id = %s "
        "AND JSON_SEARCH(motivos, 'one', %s, NULL, '$[*].codigo') IS NOT NULL LIMIT 1",
        (cuenta_id, codigo),
    ) is not None


def _consulta_ciclo(saltos: int) -> str:
    """Patron de longitud FIJA (no variable): Neo4j aplica los filtros de tiempo
    y monto en cada salto y descarta caminos temprano. Con longitud variable
    tendria que explorar millones de caminos antes de filtrar.

    Para 4 saltos genera:
      (n0)-[t0]->(n1)-[t1]->(n2)-[t2]->(n3)-[t3]->(n0)
      donde cada t es posterior al anterior y con monto parecido (+-10%),
      y todo ocurre en menos de 48 horas.
    """
    nodos = [f"n{i}" for i in range(saltos)]
    patron = "".join(f"({n}:Cuenta)-[t{i}:TRANSFIERE]->" for i, n in enumerate(nodos)) + "(n0)"
    condiciones = []
    for i in range(saltos - 1):
        condiciones += [f"t{i}.fecha < t{i + 1}.fecha",
                        f"t{i + 1}.monto >= t{i}.monto * 0.9",
                        f"t{i + 1}.monto <= t{i}.monto * 1.1"]
    distintos = [f"{a} <> {b}" for i, a in enumerate(nodos) for b in nodos[i + 1:]]
    return f"""
        MATCH {patron}
        WHERE {' AND '.join(condiciones + distintos)}
          AND duration.inSeconds(t0.fecha, t{saltos - 1}.fecha).seconds < 172800
        RETURN [{', '.join(n + '.id' for n in nodos)}] AS cuentas,
               [{', '.join(n + '.numero' for n in nodos)}] AS numeros,
               t0.monto AS monto
    """


def barrer(conn, solo_detectar: bool = False) -> dict:
    """Recorre el historial. Con solo_detectar=True no escribe alertas:
    devuelve que cuentas marcaria (sirve para probar un cambio de reglas)."""
    reglas = cargar_reglas(conn)
    creadas: dict[str, int] = defaultdict(int)
    encontrados: dict[str, int] = defaultdict(int)
    descartadas: dict[str, int] = defaultdict(int)
    detectadas: dict[str, set] = defaultdict(set)

    def alertar(cuenta_id: int, codigo: str, detalle: str) -> None:
        detectadas[codigo].add(cuenta_id)
        if solo_detectar or _ya_alertada(conn, cuenta_id, codigo):
            return
        peso = int(reglas[codigo]["peso"])
        banco.registrar_alerta(conn, cuenta_id, peso, [{"codigo": codigo, "peso": peso,
                                                        "detalle": detalle, "fuente": "barrido"}])
        creadas[codigo] += 1

    # ---------------------------------------------- 1. dispositivo compartido
    if "DISPOSITIVO_COMPARTIDO" in reglas:
        minimo = int(reglas["DISPOSITIVO_COMPARTIDO"]["umbral"])
        filas = grafo.consultar_grafo(
            """
            MATCH (d:Dispositivo)<-[:USA]-(c:Cliente)
            WITH d, collect(DISTINCT c) AS clientes
            WHERE size(clientes) >= $minimo
            UNWIND clientes AS c
            MATCH (c)-[:TITULAR_DE]->(a:Cuenta)
            RETURN d.huella AS huella, size(clientes) AS total, collect(a.id) AS cuentas
            """, minimo=minimo)
        for f in filas:
            encontrados["DISPOSITIVO_COMPARTIDO"] += 1
            for cuenta_id in f["cuentas"]:
                alertar(cuenta_id, "DISPOSITIVO_COMPARTIDO",
                        f"Su titular comparte un mismo dispositivo con otros {f['total'] - 1} clientes")

    # ------------------------------------------------------------ 2. ciclos
    if "CICLO_DINERO" in reglas:
        maximo = max(3, int(reglas["CICLO_DINERO"]["umbral"]))
        filas = []
        for saltos in range(3, maximo + 1):
            filas += grafo.consultar_grafo(_consulta_ciclo(saltos))
        vistos = set()
        for f in filas:
            clave = frozenset(f["cuentas"])
            if clave in vistos:
                continue
            vistos.add(clave)
            encontrados["CICLO_DINERO"] += 1
            camino = " -> ".join("****" + n[-4:] for n in f["numeros"] + [f["numeros"][0]])
            for cuenta_id in f["cuentas"]:
                alertar(cuenta_id, "CICLO_DINERO",
                        f"Participa en un circulo de dinero ({camino}) por cerca de ${int(f['monto']):,}".replace(",", "."))

    # ------------------------------------------------------------- 3. mulas
    if "CUENTA_MULA" in reglas:
        minimo = int(reglas["CUENTA_MULA"]["umbral"])
        candidatas = grafo.consultar_grafo(
            """
            MATCH (o:Cuenta)-[t:TRANSFIERE]->(m:Cuenta)
            WITH m, t ORDER BY t.fecha
            WITH m, collect(t) AS ts
            WHERE size(ts) >= $minimo
            UNWIND ts AS t0
            UNWIND [x IN ts WHERE t0.fecha <= x.fecha < t0.fecha + duration('PT24H')] AS x
            WITH m, t0, count(DISTINCT startNode(x)) AS origenes
            WHERE origenes >= $minimo
            RETURN m.id AS cuenta, min(t0.fecha) AS desde, max(origenes) AS origenes
            """, minimo=minimo)
        zona = ZoneInfo(settings.tz)
        for f in candidatas:
            cuenta = consultar_uno(conn, "SELECT creada_en FROM cuentas WHERE id = %s", (f["cuenta"],))
            desde_utc = f["desde"].to_native()
            creada = cuenta["creada_en"].replace(tzinfo=zona).astimezone(timezone.utc)
            edad = (desde_utc - creada).days
            if edad >= 30:   # un comerciante antiguo que recibe de muchos NO es una mula
                continue

            # Condicion 2: una mula SACA el dinero enseguida. Se compara lo que
            # entro en la ventana de 24 h con lo que salio hasta 48 h despues.
            # (MySQL guarda hora local, Neo4j guarda UTC: se convierte.)
            desde = desde_utc.astimezone(zona).replace(tzinfo=None)
            hasta = desde + timedelta(hours=24)
            limite_salida = hasta + timedelta(hours=HORAS_VACIADO)
            mov = consultar_uno(
                conn,
                """
                SELECT
                  (SELECT IFNULL(SUM(monto), 0) FROM transacciones
                    WHERE cuenta_destino_id = %s AND tipo = 'transferencia' AND estado = 'aprobada'
                      AND creada_en >= %s AND creada_en < %s) AS entro,
                  (SELECT IFNULL(SUM(monto), 0) FROM transacciones
                    WHERE cuenta_origen_id = %s AND estado = 'aprobada'
                      AND creada_en >= %s AND creada_en < %s) AS salio,
                  (SELECT COUNT(*) FROM transacciones
                    WHERE cuenta_destino_id = %s AND estado IN ('retenida', 'bloqueada')
                      AND creada_en >= %s AND creada_en < %s) AS frenadas
                """,
                (f["cuenta"], desde, hasta, f["cuenta"], desde, limite_salida, f["cuenta"], desde, hasta),
            )
            vaciada = mov["entro"] > 0 and mov["salio"] >= mov["entro"] * Decimal(str(VACIADO_MINIMO))
            # Si el motor en tiempo real ya freno transferencias hacia ella, no
            # pudo vaciarse... justamente porque la detectamos a tiempo.
            if not (vaciada or mov["frenadas"]):
                descartadas["CUENTA_MULA"] += 1
                continue

            encontrados["CUENTA_MULA"] += 1
            if vaciada:
                porcentaje = int(100 * mov["salio"] / mov["entro"])
                razon = f"y saco el {min(porcentaje, 100)}% en las {HORAS_VACIADO} h siguientes"
            else:
                razon = f"y el motor ya freno {mov['frenadas']} transferencia(s) hacia ella"
            alertar(f["cuenta"], "CUENTA_MULA",
                    f"Con {edad} dia(s) de creada recibio dinero de {f['origenes']} personas distintas en 24 h {razon}")

    # ---------------------------------------------------- 4. rafagas (robo)
    if "VELOCIDAD" in reglas:
        maximo = int(reglas["VELOCIDAD"]["umbral"])
        filas = consultar(
            conn,
            """
            SELECT DISTINCT r.origen, r.destino, r.n, r.inicio
            FROM (
                SELECT t1.cuenta_origen_id AS origen, t1.cuenta_destino_id AS destino, t1.creada_en AS inicio,
                       (SELECT COUNT(*) FROM transacciones t2
                        WHERE t2.tipo = 'transferencia'
                          AND t2.cuenta_origen_id = t1.cuenta_origen_id
                          AND t2.cuenta_destino_id = t1.cuenta_destino_id
                          AND t2.creada_en BETWEEN t1.creada_en AND t1.creada_en + INTERVAL 10 MINUTE) AS n
                FROM transacciones t1
                WHERE t1.tipo = 'transferencia'
            ) r
            WHERE r.n > %s
            """,
            (maximo,),
        )
        rafagas = {}
        for f in filas:
            rafagas.setdefault((f["origen"], f["destino"]), f)
        for (origen, destino), f in rafagas.items():
            encontrados["VELOCIDAD"] += 1
            cuenta_destino = consultar_uno(conn, "SELECT numero FROM cuentas WHERE id = %s", (destino,))["numero"]
            alertar(origen, "VELOCIDAD",
                    f"Posible robo: {f['n']} transferencias en 10 minutos hacia ****{cuenta_destino[-4:]} "
                    f"({f['inicio']:%Y-%m-%d %H:%M})")
            alertar(destino, "VELOCIDAD",
                    f"Recibio una rafaga de {f['n']} transferencias en 10 minutos desde una misma cuenta")

    resultado = {"patrones_encontrados": dict(encontrados),
                 "descartados_por_parecer_legitimos": dict(descartadas),
                 "alertas_nuevas": dict(creadas),
                 "total_alertas_nuevas": sum(creadas.values())}
    if solo_detectar:
        resultado["cuentas_detectadas"] = {k: sorted(v) for k, v in detectadas.items()}
    return resultado
