"""Sincronizacion MySQL -> Neo4j.

MySQL es la fuente de verdad. Despues de que una operacion se confirma en
MySQL, se refleja en el grafo. Si Neo4j falla, la operacion de dinero NO se
revierte: se registra el error y luego se puede reconstruir el grafo completo
con `python -m app.cli resincronizar-grafo`.

Modelo:
  (:Cliente)-[:TITULAR_DE]->(:Cuenta)
  (:Cliente)-[:USA]->(:Dispositivo)
  (:Cliente)-[:CONECTA_DESDE]->(:IP)
  (:Cuenta)-[:TRANSFIERE {tx_id, monto, fecha, estado}]->(:Cuenta)
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from neo4j import GraphDatabase

from ..config import settings
from ..db.mysql import consultar

log = logging.getLogger("banco.grafo")
_driver = None


def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(settings.neo4j_uri,
                                       auth=(settings.neo4j_user, settings.neo4j_password))
    return _driver


def cerrar() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def consultar_grafo(cypher: str, **params) -> list[dict]:
    """Lectura del grafo (la usara el motor antifraude en la Fase 4)."""
    registros, _, _ = driver().execute_query(cypher, params, database_="neo4j")
    return [r.data() for r in registros]


def _escribir(cypher: str, **params) -> None:
    try:
        driver().execute_query(cypher, params, database_="neo4j")
    except Exception:
        log.exception("No se pudo sincronizar con Neo4j (MySQL sigue siendo la fuente de verdad)")


def _fecha(valor: datetime) -> datetime:
    """MySQL devuelve fechas sin zona horaria (hora local del banco).

    Se interpretan en la zona del banco y se convierten a UTC. Se envian en UTC
    (desfase fijo) porque el driver de Neo4j se cae al serializar fechas con
    zonas ZoneInfo como America/Bogota.
    """
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=ZoneInfo(settings.tz))
    return valor.astimezone(timezone.utc)


def inicializar() -> None:
    """Crea restricciones e indices (todas usan IF NOT EXISTS: es seguro repetirlo)."""
    archivo = Path(settings.scripts_neo4j) / "01_restricciones.cypher"
    if not archivo.exists():
        log.warning("No se encontro %s", archivo)
        return
    lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines()
              if not l.strip().startswith("//")]
    for sentencia in "\n".join(lineas).split(";"):
        if sentencia.strip():
            _escribir(sentencia)
    log.info("Restricciones de Neo4j verificadas")


# ------------------------------------------------------------------ escrituras
def sincronizar_cliente(usuario_id: int, nombre: str) -> None:
    _escribir("MERGE (c:Cliente {id: $id}) SET c.nombre = $nombre", id=usuario_id, nombre=nombre)


def sincronizar_cuenta(cuenta_id: int, numero: str, usuario_id: int, estado: str = "activa") -> None:
    _escribir(
        """
        MERGE (a:Cuenta {id: $id}) SET a.numero = $numero, a.estado = $estado
        MERGE (c:Cliente {id: $uid})
        MERGE (c)-[:TITULAR_DE]->(a)
        """,
        id=cuenta_id, numero=numero, estado=estado, uid=usuario_id,
    )


def actualizar_estado_cuenta(cuenta_id: int, estado: str) -> None:
    _escribir("MATCH (a:Cuenta {id: $id}) SET a.estado = $estado", id=cuenta_id, estado=estado)


def sincronizar_conexion(usuario_id: int, huella: str, ip: str) -> None:
    """Registra que el cliente uso un dispositivo y una IP."""
    _escribir(
        """
        MERGE (c:Cliente {id: $uid})
        MERGE (d:Dispositivo {huella: $huella})
        MERGE (c)-[u:USA]->(d)
          ON CREATE SET u.desde = datetime()
        SET u.ultima_vez = datetime()
        MERGE (i:IP {direccion: $ip})
        MERGE (c)-[r:CONECTA_DESDE]->(i)
          ON CREATE SET r.desde = datetime()
        SET r.ultima_vez = datetime()
        """,
        uid=usuario_id, huella=huella, ip=ip,
    )


def sincronizar_transferencia(tx_id: int, origen_id: int, destino_id: int,
                              monto, fecha: datetime, estado: str) -> None:
    _escribir(
        """
        MATCH (o:Cuenta {id: $origen}), (d:Cuenta {id: $destino})
        MERGE (o)-[t:TRANSFIERE {tx_id: $tx}]->(d)
        SET t.monto = $monto, t.fecha = $fecha, t.estado = $estado
        """,
        tx=tx_id, origen=origen_id, destino=destino_id,
        monto=float(monto), fecha=_fecha(fecha), estado=estado,
    )


def actualizar_estado_transferencia(tx_id: int, estado: str) -> None:
    _escribir("MATCH ()-[t:TRANSFIERE {tx_id: $tx}]->() SET t.estado = $estado", tx=tx_id, estado=estado)


# ------------------------------------------------------------- vecindario
def vecindario(cuenta_id: int, limite: int = 20) -> dict:
    """Subgrafo alrededor de una cuenta, listo para dibujar en el panel del analista.

    Incluye: las cuentas con las que mas dinero mueve (1er salto), algunas de
    las suyas (2do salto), los titulares, y los dispositivos e IPs del titular
    junto con OTROS clientes que los comparten.
    """
    nodos: dict[str, dict] = {}
    aristas: list[dict] = []

    def nodo(clave: str, tipo: str, etiqueta: str, **extra) -> None:
        nodos.setdefault(clave, {"id": clave, "tipo": tipo, "etiqueta": etiqueta, **extra})

    # 1er salto: las cuentas con las que mas dinero intercambia
    primer = consultar_grafo(
        """
        MATCH (a:Cuenta {id: $id})-[t:TRANSFIERE]-(v:Cuenta)
        WITH v, sum(t.monto) AS total ORDER BY total DESC LIMIT $limite
        RETURN v.id AS id
        """, id=cuenta_id, limite=limite)
    ids_1 = [f["id"] for f in primer]

    # 2do salto: hasta 3 contactos fuertes de cada vecino
    segundo = consultar_grafo(
        """
        UNWIND $vecinos AS vid
        MATCH (v:Cuenta {id: vid})-[t:TRANSFIERE]-(w:Cuenta)
        WHERE w.id <> $id AND NOT w.id IN $vecinos
        WITH v, w, sum(t.monto) AS total ORDER BY total DESC
        WITH v, collect(w.id)[0..3] AS fuertes
        UNWIND fuertes AS wid
        RETURN DISTINCT wid AS id
        """, id=cuenta_id, vecinos=ids_1)
    ids = [cuenta_id] + ids_1 + [f["id"] for f in segundo]

    # Cuentas, titulares y transferencias entre ellas (agrupadas por par)
    for f in consultar_grafo(
            "MATCH (c:Cliente)-[:TITULAR_DE]->(a:Cuenta) WHERE a.id IN $ids "
            "RETURN a.id AS id, a.numero AS numero, a.estado AS estado, c.id AS cliente, c.nombre AS nombre",
            ids=ids):
        nodo(f"cuenta-{f['id']}", "cuenta", "****" + f["numero"][-4:], numero=f["numero"],
             estado=f["estado"], central=f["id"] == cuenta_id)
        nodo(f"cliente-{f['cliente']}", "cliente", f["nombre"])
        aristas.append({"origen": f"cliente-{f['cliente']}", "destino": f"cuenta-{f['id']}", "tipo": "TITULAR_DE"})

    for f in consultar_grafo(
            """
            MATCH (x:Cuenta)-[t:TRANSFIERE]->(y:Cuenta) WHERE x.id IN $ids AND y.id IN $ids
            RETURN x.id AS origen, y.id AS destino, count(t) AS cantidad, sum(t.monto) AS monto,
                   collect(DISTINCT t.estado) AS estados, max(t.fecha) AS ultima
            """, ids=ids):
        aristas.append({"origen": f"cuenta-{f['origen']}", "destino": f"cuenta-{f['destino']}",
                        "tipo": "TRANSFIERE", "cantidad": f["cantidad"], "monto": f["monto"],
                        "estados": f["estados"], "ultima": f["ultima"].iso_format()})

    # Dispositivos e IPs del titular, y quien mas los usa
    for f in consultar_grafo(
            """
            MATCH (c:Cliente)-[:TITULAR_DE]->(:Cuenta {id: $id})
            MATCH (c)-[r:USA|CONECTA_DESDE]->(x)
            OPTIONAL MATCH (x)<-[r2:USA|CONECTA_DESDE]-(otro:Cliente) WHERE otro <> c
            OPTIONAL MATCH (otro)-[:TITULAR_DE]->(oa:Cuenta)
            RETURN c.id AS cliente, type(r) AS relacion, labels(x)[0] AS tipo,
                   coalesce(x.huella, x.direccion) AS valor,
                   collect(DISTINCT {id: otro.id, nombre: otro.nombre, cuenta: oa.id, numero: oa.numero,
                                     estado: oa.estado}) AS otros
            """, id=cuenta_id):
        clave = f"{f['tipo'].lower()}-{f['valor'][:16]}"
        etiqueta = "Dispositivo " + f["valor"][:6] if f["tipo"] == "Dispositivo" else f["valor"]
        compartido = len([o for o in f["otros"] if o["id"] is not None])
        nodo(clave, f["tipo"].lower(), etiqueta, compartido_con=compartido)
        aristas.append({"origen": f"cliente-{f['cliente']}", "destino": clave, "tipo": f["relacion"]})
        for o in f["otros"]:
            if o["id"] is None:
                continue
            nodo(f"cliente-{o['id']}", "cliente", o["nombre"])
            aristas.append({"origen": f"cliente-{o['id']}", "destino": clave, "tipo": f["relacion"]})
            if o["cuenta"] is not None:
                nodo(f"cuenta-{o['cuenta']}", "cuenta", "****" + o["numero"][-4:], numero=o["numero"],
                     estado=o["estado"], central=False)
                aristas.append({"origen": f"cliente-{o['id']}", "destino": f"cuenta-{o['cuenta']}",
                                "tipo": "TITULAR_DE"})

    # Quitar aristas TITULAR_DE repetidas
    unicas, vistas = [], set()
    for a in aristas:
        clave = (a["origen"], a["destino"], a["tipo"])
        if a["tipo"] == "TRANSFIERE" or clave not in vistas:
            vistas.add(clave)
            unicas.append(a)
    return {"nodos": list(nodos.values()), "aristas": unicas}


# ---------------------------------------------------------- reconstruccion
def resincronizar(conn) -> dict:
    """Reconstruye todo el grafo a partir de MySQL (por lotes con UNWIND)."""
    clientes = consultar(conn, "SELECT id, nombre FROM usuarios WHERE rol = 'cliente'")
    cuentas = consultar(conn, "SELECT id, numero, usuario_id, estado FROM cuentas")
    # Solo clientes: los empleados no forman parte del grafo de fraude
    dispositivos = consultar(conn, "SELECT d.usuario_id, d.huella FROM dispositivos d "
                                   "JOIN usuarios u ON u.id = d.usuario_id WHERE u.rol = 'cliente'")
    ips = consultar(conn, "SELECT DISTINCT e.usuario_id, e.ip FROM eventos_login e "
                          "JOIN usuarios u ON u.id = e.usuario_id WHERE e.exito AND u.rol = 'cliente'")
    transferencias = consultar(
        conn,
        "SELECT id, cuenta_origen_id, cuenta_destino_id, monto, estado, creada_en "
        "FROM transacciones WHERE tipo = 'transferencia'",
    )

    driver().execute_query(
        "UNWIND $filas AS f MERGE (c:Cliente {id: f.id}) SET c.nombre = f.nombre",
        {"filas": clientes}, database_="neo4j")
    driver().execute_query(
        """UNWIND $filas AS f
           MERGE (a:Cuenta {id: f.id}) SET a.numero = f.numero, a.estado = f.estado
           MERGE (c:Cliente {id: f.usuario_id}) MERGE (c)-[:TITULAR_DE]->(a)""",
        {"filas": cuentas}, database_="neo4j")
    driver().execute_query(
        """UNWIND $filas AS f
           MERGE (c:Cliente {id: f.usuario_id}) MERGE (d:Dispositivo {huella: f.huella})
           MERGE (c)-[:USA]->(d)""",
        {"filas": dispositivos}, database_="neo4j")
    driver().execute_query(
        """UNWIND $filas AS f
           MERGE (c:Cliente {id: f.usuario_id}) MERGE (i:IP {direccion: f.ip})
           MERGE (c)-[:CONECTA_DESDE]->(i)""",
        {"filas": ips}, database_="neo4j")
    driver().execute_query(
        """UNWIND $filas AS f
           MATCH (o:Cuenta {id: f.origen}), (d:Cuenta {id: f.destino})
           MERGE (o)-[t:TRANSFIERE {tx_id: f.id}]->(d)
           SET t.monto = f.monto, t.fecha = f.fecha, t.estado = f.estado""",
        {"filas": [{"id": t["id"], "origen": t["cuenta_origen_id"], "destino": t["cuenta_destino_id"],
                    "monto": float(t["monto"]), "fecha": _fecha(t["creada_en"]), "estado": t["estado"]}
                   for t in transferencias]},
        database_="neo4j")

    return {"clientes": len(clientes), "cuentas": len(cuentas), "dispositivos": len(dispositivos),
            "ips": len(ips), "transferencias": len(transferencias)}
