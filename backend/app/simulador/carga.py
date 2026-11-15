"""Carga inicial: N clientes con D dias de historia y casos de fraude plantados.

Como funciona:
1. Crea clientes con un perfil (estudiante, asalariado, comerciante), una
   "comunidad" (barrio o grupo social) y contactos frecuentes.
2. Programa eventos dia por dia (salarios, arriendos, pagos, retiros...).
3. Planta los casos de fraude dentro de esa misma linea de tiempo.
4. Ejecuta todos los eventos en orden cronologico con sp_cargar_historico,
   que mueve los saldos igual que una operacion real.
5. Reconstruye el grafo de Neo4j y guarda la "hoja de respuestas" en banco_sim.
"""
import json
import random
import sys
import time as reloj
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable

from ..config import settings
from ..db.mysql import conectar, consultar, consultar_uno, ejecutar, llamar_sp
from ..seguridad import cifrado, contrasenas
from ..servicios import auditoria, banco, grafo
from . import datos

CAJERO_SIM = "cajero.sim@rosberg.co"
MINIMO = Decimal(5000)


@dataclass(eq=False)
class Cliente:
    usuario_id: int
    cuenta_id: int
    numero: str
    nombre: str
    email: str
    cedula: str
    perfil: str
    comunidad: int
    dispositivo: str
    dispositivo_id: int
    ip: str
    saldo: Decimal = Decimal(0)
    contactos: list = field(default_factory=list)
    familia: "Cliente | None" = None
    arrendador: "Cliente | None" = None
    salario: Decimal = Decimal(0)
    arriendo: Decimal = Decimal(0)
    dia_arriendo: int = 1


@dataclass(order=True)
class Evento:
    fecha: datetime
    orden: int
    tipo: str = field(compare=False)
    origen: Cliente | None = field(compare=False)
    destino: Cliente | None = field(compare=False)
    monto: Callable[[Decimal], Decimal | None] = field(compare=False)
    ip: str | None = field(compare=False, default=None)
    dispositivo_id: int | None = field(compare=False, default=None)


# ----------------------------------------------------------- montos
def fijo(valor: float):
    return lambda saldo: datos.pesos(valor)


def rango(minimo: float, maximo: float, max_saldo: float = 0.8):
    """Monto al azar, pero nunca mas que cierto porcentaje del saldo."""
    def _f(saldo: Decimal):
        monto = min(datos.pesos(random.uniform(minimo, maximo)), datos.pesos(float(saldo) * max_saldo))
        return monto if monto >= MINIMO else None
    return _f


def porcentaje(p: float):
    def _f(saldo: Decimal):
        monto = datos.pesos(float(saldo) * p)
        return monto if monto >= MINIMO else None
    return _f


def hasta_si_alcanza(valor: Decimal):
    """Pago fijo (como el arriendo): se hace completo o no se hace."""
    return lambda saldo: valor if saldo >= valor else None


def a_la_hora(dia: date, desde: int = 7, hasta: int = 22) -> datetime:
    return datetime.combine(dia, time(random.randint(desde, hasta - 1), random.randint(0, 59), random.randint(0, 59)))


def ultimo_dia_mes(dia: date) -> bool:
    return (dia + timedelta(days=1)).month != dia.month


# ------------------------------------------------------------- carga
class Carga:
    def __init__(self, n_clientes: int, dias: int, semilla: int):
        self.n_clientes = n_clientes
        self.dias = dias
        self.semilla = semilla
        self.conn = conectar()
        self.ahora = datetime.now().replace(microsecond=0)
        self.eventos: dict[date, list[Evento]] = defaultdict(list)
        self.orden = 0
        self.normales: list[Cliente] = []
        self.fraudulentos: list[Cliente] = []
        self.emails = {f["email"] for f in consultar(self.conn, "SELECT email FROM usuarios")}
        self.cedulas: set[str] = set()
        self.celulares: set[str] = set()
        self.hash_demo = ""
        self.stats = defaultdict(int)
        self.casos: list[str] = []

    # ---------------------------------------------------------- helpers BD
    def registrar_dispositivo(self, usuario_id: int, identificador: str, fecha: datetime,
                              confiable: bool = True, agente: str | None = None) -> int:
        cur = ejecutar(
            self.conn,
            "INSERT INTO dispositivos (usuario_id, huella, descripcion, confiable, primera_vez, ultima_vez) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (usuario_id, datos.huella(identificador), agente or datos.agente(), confiable, fecha, fecha),
        )
        return cur.lastrowid

    def registrar_login(self, usuario_id: int, email: str, ip: str, dispositivo_id: int | None,
                        fecha: datetime, exito: bool = True) -> None:
        ejecutar(
            self.conn,
            "INSERT INTO eventos_login (usuario_id, email_intentado, ip, dispositivo_id, exito, fecha) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (usuario_id, email, ip, dispositivo_id, exito, fecha),
        )

    def crear_cliente(self, perfil: str, creado: datetime, comunidad: int,
                      dispositivo: str | None = None, ip: str | None = None) -> Cliente:
        nombre = datos.nombre()
        email = datos.email(nombre, self.emails)
        while True:
            cedula = datos.cedula(self.cedulas)
            if not consultar_uno(self.conn, "SELECT 1 FROM usuarios WHERE documento_hash = %s",
                                 (cifrado.indice_ciego(cedula, "cedula"),)):
                break
        celular = datos.celular(self.celulares)

        cur = ejecutar(
            self.conn,
            "INSERT INTO usuarios (email, password_hash, rol, nombre, documento_cifrado, documento_hash, "
            "telefono_cifrado, creado_en) VALUES (%s, %s, 'cliente', %s, %s, %s, %s, %s)",
            (email, self.hash_demo, nombre, cifrado.cifrar(cedula), cifrado.indice_ciego(cedula, "cedula"),
             cifrado.cifrar(celular), creado),
        )
        usuario_id = cur.lastrowid
        numero = banco.generar_numero_cuenta(self.conn)
        cur = ejecutar(self.conn, "INSERT INTO cuentas (numero, usuario_id, tipo, creada_en) VALUES (%s, %s, %s, %s)",
                       (numero, usuario_id, "corriente" if perfil == "comerciante" else "ahorros", creado))
        cuenta_id = cur.lastrowid

        dispositivo = dispositivo or datos.dispositivo()
        ip = ip or datos.ip_colombia()
        dispositivo_id = self.registrar_dispositivo(usuario_id, dispositivo, creado)
        self.registrar_login(usuario_id, email, ip, dispositivo_id, creado + timedelta(minutes=3))
        # Algunos inicios de sesion mas a lo largo del tiempo (alimentan el grafo de IPs)
        for _ in range(random.randint(1, 3)):
            segundos = int((self.ahora - creado).total_seconds())
            if segundos > 3600:
                fecha = creado + timedelta(seconds=random.randint(3600, segundos - 60))
                self.registrar_login(usuario_id, email, ip, dispositivo_id, fecha)

        if perfil != "fraude":
            if random.random() < 0.6:
                ejecutar(self.conn, "INSERT INTO llaves (cuenta_id, tipo, valor) VALUES (%s, 'celular', %s)",
                         (cuenta_id, celular))
            if random.random() < 0.3:
                ejecutar(self.conn, "INSERT INTO llaves (cuenta_id, tipo, valor) VALUES (%s, 'correo', %s)",
                         (cuenta_id, email))

        ejecutar(
            self.conn,
            "INSERT INTO banco_sim.perfiles (usuario_id, cuenta_id, email, cedula, perfil, comunidad, dispositivo, ip) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (usuario_id, cuenta_id, email, cedula, perfil, comunidad, dispositivo, ip),
        )
        cliente = Cliente(usuario_id=usuario_id, cuenta_id=cuenta_id, numero=numero, nombre=nombre,
                          email=email, cedula=cedula, perfil=perfil, comunidad=comunidad,
                          dispositivo=dispositivo, dispositivo_id=dispositivo_id, ip=ip)
        (self.fraudulentos if perfil == "fraude" else self.normales).append(cliente)
        return cliente

    def programar(self, fecha: datetime, tipo: str, origen: Cliente | None, destino: Cliente | None,
                  monto, ip: str | None = None, dispositivo_id: int | None = None) -> None:
        self.orden += 1
        self.eventos[fecha.date()].append(
            Evento(fecha, self.orden, tipo, origen, destino, monto, ip, dispositivo_id))

    def registrar_caso(self, tipo: str, descripcion: str, fraudulentas: list[Cliente],
                       victimas: list[Cliente] | None = None) -> None:
        cur = ejecutar(self.conn, "INSERT INTO banco_sim.casos (tipo, origen, descripcion) VALUES (%s, 'historico', %s)",
                       (tipo, descripcion))
        for c in fraudulentas:
            ejecutar(self.conn, "INSERT INTO banco_sim.casos_cuentas VALUES (%s, %s, 'fraudulenta')", (cur.lastrowid, c.cuenta_id))
        for c in victimas or []:
            ejecutar(self.conn, "INSERT IGNORE INTO banco_sim.casos_cuentas VALUES (%s, %s, 'victima')", (cur.lastrowid, c.cuenta_id))
        self.casos.append(f"{tipo}: {descripcion}")

    # ---------------------------------------------------- clientes normales
    def crear_clientes_normales(self) -> None:
        n_comunidades = max(1, self.n_clientes // 20)
        perfiles = random.choices(["estudiante", "asalariado", "comerciante"], weights=[30, 50, 20], k=self.n_clientes)
        for i, perfil in enumerate(perfiles, 1):
            creado = self.ahora - timedelta(days=random.randint(self.dias + 5, 400), hours=random.randint(0, 23))
            c = self.crear_cliente(perfil, creado, comunidad=random.randint(1, n_comunidades))
            if perfil == "asalariado":
                c.salario = datos.pesos(random.uniform(1_600_000, 7_000_000))
                c.dia_arriendo = random.randint(1, 5)
            if i % 100 == 0:
                print(f"   {i} clientes creados...")

        por_comunidad: dict[int, list[Cliente]] = defaultdict(list)
        for c in self.normales:
            por_comunidad[c.comunidad].append(c)

        # Contactos: 80% de su comunidad, 20% de cualquier parte
        for c in self.normales:
            vecinos = [v for v in por_comunidad[c.comunidad] if v is not c]
            k = random.randint(3, 8)
            cercanos = random.sample(vecinos, min(len(vecinos), max(1, int(k * 0.8))))
            externos = random.sample([x for x in self.normales if x is not c and x not in cercanos], k - len(cercanos))
            c.contactos = [(v, "comunidad") for v in cercanos] + [(v, "externo") for v in externos]

            if c.perfil == "asalariado" and vecinos:
                candidatos = [v for v in vecinos if v.perfil == "comerciante"] or vecinos
                c.arrendador = random.choice(candidatos)
                c.arriendo = datos.pesos(min(float(c.salario) * random.uniform(0.25, 0.4), 2_500_000))
                c.contactos.append((c.arrendador, "arrendador"))
            if c.perfil == "estudiante":
                padres = [v for v in vecinos if v.perfil == "asalariado"]
                if padres:
                    c.familia = random.choice(padres)
                    c.contactos.append((c.familia, "familia"))

            vistos = set()
            for contacto, relacion in c.contactos:
                if contacto.cuenta_id not in vistos:
                    vistos.add(contacto.cuenta_id)
                    ejecutar(self.conn, "INSERT IGNORE INTO banco_sim.contactos VALUES (%s, %s, %s)",
                             (c.cuenta_id, contacto.cuenta_id, relacion))
        self.por_comunidad = por_comunidad

    def programar_vida_normal(self) -> None:
        inicio = (self.ahora - timedelta(days=self.dias)).date()
        for c in self.normales:
            apertura = {"estudiante": (100_000, 500_000), "asalariado": (500_000, 3_000_000),
                        "comerciante": (2_000_000, 8_000_000)}[c.perfil]
            self.programar(a_la_hora(inicio, 8, 10), "deposito", None, c, fijo(random.uniform(*apertura)))

        for desfase in range(self.dias, 0, -1):
            dia = (self.ahora - timedelta(days=desfase)).date()
            for c in self.normales:
                if c.perfil == "asalariado":
                    if dia.day == 15 or ultimo_dia_mes(dia):
                        self.programar(a_la_hora(dia, 6, 9), "deposito", None, c, fijo(float(c.salario)))
                    if dia.day == c.dia_arriendo and c.arrendador:
                        self.programar(a_la_hora(dia, 8, 20), "transferencia", c, c.arrendador,
                                       hasta_si_alcanza(c.arriendo))
                    probabilidad, montos = 0.12, (30_000, 400_000)
                elif c.perfil == "estudiante":
                    if dia.day == 1:
                        if c.familia:
                            self.programar(a_la_hora(dia, 7, 21), "transferencia", c.familia, c,
                                           rango(300_000, 900_000, 0.4))
                        else:
                            self.programar(a_la_hora(dia, 9, 17), "deposito", None, c, fijo(random.uniform(300_000, 800_000)))
                    probabilidad, montos = 0.10, (10_000, 80_000)
                else:  # comerciante
                    if random.random() < 0.5:
                        clientes_del_dia = [v for v in self.por_comunidad[c.comunidad] if v is not c]
                        for comprador in random.sample(clientes_del_dia, min(len(clientes_del_dia), random.randint(1, 2))):
                            self.programar(a_la_hora(dia, 8, 21), "transferencia", comprador, c,
                                           rango(15_000, 250_000, 0.3))
                    if dia.weekday() == 5:
                        self.programar(a_la_hora(dia, 17, 19), "deposito", None, c, fijo(random.uniform(500_000, 3_000_000)))
                    probabilidad, montos = 0.15, (100_000, 1_500_000)

                if random.random() < probabilidad and c.contactos:
                    contacto, _ = random.choice(c.contactos)
                    self.programar(a_la_hora(dia), "transferencia", c, contacto, rango(*montos))
                if random.random() < 0.02:
                    self.programar(a_la_hora(dia, 8, 20), "retiro", c, None, rango(50_000, 600_000, 0.5))

    # ------------------------------------------------------ fraudes plantados
    def nuevo_fraudulento(self, creado: datetime, dispositivo: str | None = None) -> Cliente:
        return self.crear_cliente("fraude", creado, comunidad=0, dispositivo=dispositivo)

    def plantar_dispositivo_compartido(self) -> None:
        """5 cuentas de 'personas distintas' operan desde el MISMO celular y envian todo a una colectora."""
        compartido = datos.dispositivo()
        creado = self.ahora - timedelta(days=random.randint(38, 45), hours=random.randint(0, 23))
        colectora = self.nuevo_fraudulento(creado - timedelta(days=2))
        miembros = [self.nuevo_fraudulento(creado + timedelta(hours=3 * i), dispositivo=compartido) for i in range(5)]
        dia_deposito = (self.ahora - timedelta(days=random.randint(30, 35))).date()
        for m in miembros:
            self.programar(a_la_hora(dia_deposito, 9, 16), "deposito", None, m, fijo(random.uniform(800_000, 2_500_000)))
            dia_envio = dia_deposito + timedelta(days=random.randint(1, 3))
            self.programar(a_la_hora(dia_envio, 10, 22), "transferencia", m, colectora,
                           porcentaje(random.uniform(0.85, 0.95)), dispositivo_id=m.dispositivo_id)
        self.programar(a_la_hora(dia_deposito + timedelta(days=5), 9, 12), "retiro", colectora, None, porcentaje(0.9))
        self.registrar_caso("dispositivo_compartido",
                            "5 cuentas usan el mismo dispositivo y envian casi todo a una cuenta colectora",
                            miembros + [colectora])

    def plantar_ciclo(self) -> None:
        """El dinero da la vuelta A -> B -> C -> D -> A en pocas horas, dos veces."""
        creado = self.ahora - timedelta(days=random.randint(60, 70))
        anillo = [self.nuevo_fraudulento(creado + timedelta(hours=5 * i)) for i in range(4)]
        for desfase in (random.randint(45, 50), random.randint(18, 22)):
            momento = datetime.combine((self.ahora - timedelta(days=desfase)).date(), time(9, random.randint(0, 59)))
            self.programar(momento - timedelta(hours=1), "deposito", None, anillo[0], fijo(random.uniform(4_000_000, 8_000_000)))
            for i in range(4):
                momento += timedelta(minutes=random.randint(30, 120))
                self.programar(momento, "transferencia", anillo[i], anillo[(i + 1) % 4],
                               porcentaje(random.uniform(0.96, 0.99)))
        self.registrar_caso("ciclo_lavado", "4 cuentas se pasan el dinero en circulo (A->B->C->D->A) dos veces",
                            anillo)

    def plantar_mula(self) -> None:
        """Cuenta nueva que recibe de muchas victimas en un dia y retira todo esa noche."""
        mula = self.nuevo_fraudulento(self.ahora - timedelta(days=random.randint(10, 12)))
        dia = (self.ahora - timedelta(days=random.randint(5, 7))).date()
        candidatas = [c for c in self.normales if c.perfil in ("asalariado", "comerciante")]
        victimas = random.sample(candidatas, 9)
        for v in victimas:
            self.programar(a_la_hora(dia, 9, 19), "transferencia", v, mula, rango(150_000, 600_000, 0.5))
        for j in range(4):
            self.programar(datetime.combine(dia, time(21, 10 * j)), "retiro", mula, None,
                           lambda saldo: min(datos.pesos(float(saldo)), Decimal(2_000_000)) if saldo >= MINIMO else None)
        self.registrar_caso("cuenta_mula", "Cuenta nueva recibe de 9 personas en un dia y retira todo esa noche",
                            [mula], victimas)

    def plantar_robo(self, usados: set) -> None:
        """Login de madrugada desde dispositivo e IP nuevos y rafaga de transferencias que vacia la cuenta."""
        victima = random.choice([c for c in self.normales if c.perfil == "asalariado" and c.cuenta_id not in usados])
        usados.add(victima.cuenta_id)
        beneficiario = self.nuevo_fraudulento(self.ahora - timedelta(days=random.randint(3, 4)))
        dia = (self.ahora - timedelta(days=random.randint(1, 2))).date()
        momento = datetime.combine(dia, time(random.randint(2, 3), random.randint(0, 59)))
        ip_ladron = datos.ip_extranjera()
        disp_ladron = self.registrar_dispositivo(victima.usuario_id, datos.dispositivo(), momento, confiable=False,
                                                 agente="Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0")
        self.registrar_login(victima.usuario_id, victima.email, ip_ladron, None, momento - timedelta(minutes=2), exito=False)
        self.registrar_login(victima.usuario_id, victima.email, ip_ladron, disp_ladron, momento)
        for _ in range(6):
            momento += timedelta(seconds=random.randint(40, 100))
            self.programar(momento, "transferencia", victima, beneficiario, porcentaje(0.22),
                           ip=ip_ladron, dispositivo_id=disp_ladron)
        self.programar(momento + timedelta(hours=5), "retiro", beneficiario, None, porcentaje(0.95))
        self.registrar_caso("robo_cuenta",
                            "Acceso de madrugada desde dispositivo e IP extranjera; 6 transferencias seguidas vacian la cuenta",
                            [beneficiario], [victima])

    # --------------------------------------------------------------- ejecutar
    def ejecutar_eventos(self) -> None:
        total = sum(len(v) for v in self.eventos.values())
        hechos = 0
        for dia in sorted(self.eventos):
            for ev in sorted(self.eventos[dia]):
                hechos += 1
                if ev.fecha >= self.ahora:
                    continue
                saldo = ev.origen.saldo if ev.origen else Decimal(0)
                monto = ev.monto(saldo)
                if not monto or monto <= 0 or (ev.origen and monto > ev.origen.saldo):
                    self.stats["omitidos_sin_saldo"] += 1
                    continue
                quien = ev.origen or ev.destino
                dispositivo_id = ev.dispositivo_id
                if dispositivo_id is None and ev.tipo == "transferencia":
                    dispositivo_id = ev.origen.dispositivo_id
                tx = llamar_sp(self.conn, "sp_cargar_historico", [
                    ev.tipo, ev.origen.cuenta_id if ev.origen else None,
                    ev.destino.cuenta_id if ev.destino else None, monto, ev.fecha,
                    ev.ip or quien.ip, dispositivo_id,
                ])
                if tx is None:
                    self.stats["omitidos_sin_saldo"] += 1
                    continue
                if ev.origen:
                    ev.origen.saldo -= monto
                if ev.destino:
                    ev.destino.saldo += monto
                self.stats[ev.tipo] += 1
                if hechos % 2000 == 0:
                    print(f"   {hechos}/{total} movimientos procesados...")

    def crear_cajero_simulador(self) -> None:
        if not consultar_uno(self.conn, "SELECT 1 FROM usuarios WHERE email = %s", (CAJERO_SIM,)):
            ejecutar(self.conn, "INSERT INTO usuarios (email, password_hash, rol, nombre) "
                                "VALUES (%s, %s, 'cajero', 'Cajero Simulador')", (CAJERO_SIM, self.hash_demo))

    def correr(self) -> None:
        if consultar_uno(self.conn, "SELECT 1 FROM banco_sim.ejecuciones WHERE tipo = 'carga' AND fin IS NOT NULL"):
            sys.exit("Ya existe una carga inicial. Para repetirla hay que reiniciar las bases (docker compose down -v).")
        if not settings.sim_password_clientes:
            sys.exit("Falta SIM_PASSWORD_CLIENTES en el .env")
        contrasenas.validar_politica(settings.sim_password_clientes)

        cur = ejecutar(self.conn, "INSERT INTO banco_sim.ejecuciones (tipo, parametros) VALUES ('carga', %s)",
                       (json.dumps({"clientes": self.n_clientes, "dias": self.dias, "semilla": self.semilla}),))
        ejecucion_id = cur.lastrowid
        inicio = reloj.time()
        datos.fijar_semilla(self.semilla)
        # Un solo hash Argon2 para todos: es la misma contrasena de demo y
        # calcular 500 hashes tardaria mucho.
        self.hash_demo = contrasenas.hashear(settings.sim_password_clientes)

        print(f"1/5 Creando {self.n_clientes} clientes...")
        self.crear_clientes_normales()
        print("2/5 Programando 90 dias de vida normal...")
        self.programar_vida_normal()
        print("3/5 Plantando casos de fraude...")
        usados: set = set()
        for _ in range(2):
            self.plantar_dispositivo_compartido()
            self.plantar_ciclo()
            self.plantar_mula()
            self.plantar_robo(usados)
        print(f"4/5 Ejecutando movimientos en orden cronologico...")
        self.ejecutar_eventos()
        self.crear_cajero_simulador()
        print("5/5 Reconstruyendo el grafo en Neo4j...")
        resumen_grafo = grafo.resincronizar(self.conn)

        resumen = {
            "clientes_normales": len(self.normales),
            "cuentas_fraudulentas": len(self.fraudulentos),
            "depositos": self.stats["deposito"],
            "transferencias": self.stats["transferencia"],
            "retiros": self.stats["retiro"],
            "omitidos_sin_saldo": self.stats["omitidos_sin_saldo"],
            "casos": len(self.casos),
            "grafo": resumen_grafo,
            "segundos": round(reloj.time() - inicio),
        }
        ejecutar(self.conn, "UPDATE banco_sim.ejecuciones SET fin = NOW(), resumen = %s WHERE id = %s",
                 (json.dumps(resumen), ejecucion_id))
        auditoria.registrar(self.conn, "CARGA_SIMULACION", "banco_sim", ejecucion_id, detalle=resumen)

        total = resumen["depositos"] + resumen["transferencias"] + resumen["retiros"]
        print("\n================ CARGA TERMINADA ================")
        print(f"Clientes normales:      {resumen['clientes_normales']}")
        print(f"Cuentas fraudulentas:   {resumen['cuentas_fraudulentas']}")
        print(f"Movimientos creados:    {total}  (depositos {resumen['depositos']}, "
              f"transferencias {resumen['transferencias']}, retiros {resumen['retiros']})")
        print(f"Tiempo:                 {resumen['segundos']} s")
        print(f"\nCasos de fraude plantados ({len(self.casos)}):")
        for caso in self.casos:
            print(f"  - {caso}")
        print(f"\nTodos los clientes simulados usan la contrasena SIM_PASSWORD_CLIENTES del .env")
        print(f"Cajero del simulador: {CAJERO_SIM} (misma contrasena)")
        print("Ver el detalle:  docker compose run --rm simulador reporte")
        self.conn.close()
        grafo.cerrar()


def cargar(clientes: int, dias: int, semilla: int) -> None:
    Carga(clientes, dias, semilla).correr()
