"""Modo en vivo: trafico normal continuo y fraudes lanzados a pedido.

Todo pasa por la API (login, roles, motor antifraude, auditoria), igual que
un cliente real usando la app.
"""
import random
import time
from datetime import datetime
from decimal import Decimal

from ..config import settings
from ..db.mysql import conectar, consultar, consultar_uno, ejecutar
from . import datos
from .api import ErrorAPI, SesionAPI, registrar_cliente
from .carga import CAJERO_SIM

_sesiones: dict[str, SesionAPI] = {}


def _hora() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _sesion(perfil: dict, dispositivo: str | None = None, ip: str | None = None) -> SesionAPI:
    clave = f"{perfil['email']}|{dispositivo or perfil['dispositivo']}"
    if clave not in _sesiones:
        _sesiones[clave] = SesionAPI(perfil["email"], settings.sim_password_clientes,
                                     dispositivo or perfil["dispositivo"], ip or perfil["ip"])
    return _sesiones[clave]


def _cajero() -> SesionAPI:
    clave = f"{CAJERO_SIM}|ventanilla"
    if clave not in _sesiones:
        _sesiones[clave] = SesionAPI(CAJERO_SIM, settings.sim_password_clientes,
                                     "sim-cajero-ventanilla-01", "10.20.0.15", portal="intranet")
    return _sesiones[clave]


def _perfiles_normales(conn) -> list[dict]:
    return consultar(
        conn,
        "SELECT p.*, c.numero, c.saldo, u.nombre FROM banco_sim.perfiles p "
        "JOIN cuentas c ON c.id = p.cuenta_id JOIN usuarios u ON u.id = p.usuario_id "
        "WHERE p.perfil <> 'fraude' AND c.estado = 'activa'",
    )


def _saldo(conn, numero: str) -> Decimal:
    return consultar_uno(conn, "SELECT saldo FROM cuentas WHERE numero = %s", (numero,))["saldo"]


def _exigir_carga(conn) -> None:
    if not consultar_uno(conn, "SELECT 1 FROM banco_sim.ejecuciones WHERE tipo = 'carga' AND fin IS NOT NULL"):
        raise SystemExit("Primero ejecuta la carga inicial: docker compose run --rm simulador cargar")


# ================================================================ en vivo
def en_vivo(intervalo: float) -> None:
    conn = conectar()
    _exigir_carga(conn)
    perfiles = _perfiles_normales(conn)
    contactos: dict[int, list[str]] = {}
    for fila in consultar(conn, "SELECT co.cuenta_id, c.numero FROM banco_sim.contactos co "
                                "JOIN cuentas c ON c.id = co.contacto_cuenta_id"):
        contactos.setdefault(fila["cuenta_id"], []).append(fila["numero"])

    print(f"Simulacion en vivo de Banco Rosberg: una operacion cada {intervalo} s. Ctrl + C para detener.")
    print("Para lanzar un fraude, abre OTRA terminal y ejecuta:")
    print("   docker compose run --rm simulador lanzar ciclo|dispositivo|mula|robo\n")
    ciclo = 0
    try:
        while True:
            ciclo += 1
            try:
                if ciclo % 12 == 0:
                    p = random.choice([x for x in perfiles if x["perfil"] == "asalariado"])
                    monto = datos.pesos(random.uniform(1_600_000, 5_000_000))
                    estado, r = _cajero().llamar("POST", "/cajero/depositos", {"cuenta": p["numero"], "monto": int(monto)})
                    print(f"[{_hora()}] DEPOSITO      ventanilla -> {p['nombre'][:28]:<28} {datos.cop(monto):>13}  {estado}")
                else:
                    p = random.choice(perfiles)
                    destinos = contactos.get(p["cuenta_id"])
                    saldo = _saldo(conn, p["numero"])
                    if not destinos or saldo < 20_000:
                        continue
                    tope = {"estudiante": 80_000, "asalariado": 400_000, "comerciante": 1_500_000}[p["perfil"]]
                    monto = min(datos.pesos(random.uniform(10_000, tope)), datos.pesos(float(saldo) * 0.5))
                    if monto < 5000:
                        continue
                    destino = random.choice(destinos)
                    estado, r = _sesion(p).transferir(p["numero"], destino, monto)
                    resultado = r.get("estado", r.get("detail")) if isinstance(r, dict) else r
                    print(f"[{_hora()}] TRANSFERENCIA {p['nombre'][:28]:<28} -> ****{destino[-4:]} "
                          f"{datos.cop(monto):>13}  {resultado}")
            except ErrorAPI as e:
                print(f"[{_hora()}] (error) {e}")
            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\nSimulacion detenida.")
    finally:
        conn.close()


# ======================================================== fraudes a pedido
def _nuevo_cliente_api(conn, dispositivo: str | None = None, ip: str | None = None) -> dict:
    """Registra un cliente nuevo por la API (como haria un defraudador real)."""
    emails = {f["email"] for f in consultar(conn, "SELECT email FROM usuarios")}
    nombre = datos.nombre()
    email = datos.email(nombre, emails)
    cedula = datos.cedula(set())
    celular = datos.celular(set())
    dispositivo = dispositivo or datos.dispositivo()
    ip = ip or datos.ip_colombia()
    numero = registrar_cliente(nombre, email, cedula, celular, settings.sim_password_clientes, dispositivo, ip)
    cuenta = consultar_uno(conn, "SELECT id, usuario_id FROM cuentas WHERE numero = %s", (numero,))
    ejecutar(conn, "INSERT INTO banco_sim.perfiles VALUES (%s, %s, %s, %s, 'fraude', 0, %s, %s)",
             (cuenta["usuario_id"], cuenta["id"], email, cedula, dispositivo, ip))
    print(f"   + cliente nuevo: {nombre} (cuenta ****{numero[-4:]})")
    return {"email": email, "nombre": nombre, "cedula": cedula, "numero": numero, "cuenta_id": cuenta["id"],
            "dispositivo": dispositivo, "ip": ip}


def _registrar_caso(conn, tipo: str, descripcion: str, fraudulentas: list[dict], victimas: list[dict] = ()) -> None:
    cur = ejecutar(conn, "INSERT INTO banco_sim.casos (tipo, origen, descripcion) VALUES (%s, 'en_vivo', %s)",
                   (tipo, descripcion))
    for c in fraudulentas:
        ejecutar(conn, "INSERT INTO banco_sim.casos_cuentas VALUES (%s, %s, 'fraudulenta')", (cur.lastrowid, c["cuenta_id"]))
    for c in victimas:
        ejecutar(conn, "INSERT IGNORE INTO banco_sim.casos_cuentas VALUES (%s, %s, 'victima')", (cur.lastrowid, c["cuenta_id"]))
    print(f"\nCaso registrado en la hoja de respuestas (banco_sim.casos #{cur.lastrowid}).")


def _mostrar(estado: int, r, texto: str) -> None:
    resultado = (r.get("estado") or r.get("mensaje") or r.get("detail")) if isinstance(r, dict) else r
    print(f"[{_hora()}] {texto}  -> {estado} {resultado}")


def lanzar_ciclo(conn) -> None:
    print("CICLO DE LAVADO: 4 cuentas nuevas se pasan el dinero en circulo.")
    anillo = [_nuevo_cliente_api(conn) for _ in range(4)]
    monto = datos.pesos(random.uniform(4_000_000, 8_000_000))
    estado, r = _cajero().llamar("POST", "/cajero/depositos", {"cuenta": anillo[0]["numero"], "monto": int(monto)})
    _mostrar(estado, r, f"Deposito de {datos.cop(monto)} en la cuenta A")
    letras = "ABCD"
    for i in range(4):
        time.sleep(2)
        origen, destino = anillo[i], anillo[(i + 1) % 4]
        monto = datos.pesos(float(_saldo(conn, origen["numero"])) * random.uniform(0.96, 0.99))
        estado, r = _sesion(origen).transferir(origen["numero"], destino["numero"], monto)
        _mostrar(estado, r, f"{letras[i]} -> {letras[(i + 1) % 4]}  {datos.cop(monto)}")
    _registrar_caso(conn, "ciclo_lavado", "En vivo: 4 cuentas nuevas se pasan el dinero en circulo", anillo)


def lanzar_dispositivo(conn) -> None:
    print("DISPOSITIVO COMPARTIDO: 5 'personas distintas' operan desde el mismo celular.")
    compartido = datos.dispositivo()
    colectora = _nuevo_cliente_api(conn)
    miembros = [_nuevo_cliente_api(conn, dispositivo=compartido) for _ in range(5)]
    for m in miembros:
        monto = datos.pesos(random.uniform(800_000, 2_000_000))
        estado, r = _cajero().llamar("POST", "/cajero/depositos", {"cuenta": m["numero"], "monto": int(monto)})
        _mostrar(estado, r, f"Deposito de {datos.cop(monto)} a ****{m['numero'][-4:]}")
    for m in miembros:
        time.sleep(1)
        monto = datos.pesos(float(_saldo(conn, m["numero"])) * random.uniform(0.85, 0.95))
        estado, r = _sesion(m).transferir(m["numero"], colectora["numero"], monto)
        _mostrar(estado, r, f"****{m['numero'][-4:]} -> colectora  {datos.cop(monto)}")
    _registrar_caso(conn, "dispositivo_compartido",
                    "En vivo: 5 cuentas con el mismo dispositivo envian todo a una colectora", miembros + [colectora])


def lanzar_mula(conn) -> None:
    print("CUENTA MULA: una cuenta nueva recibe de muchas victimas y retira todo.")
    mula = _nuevo_cliente_api(conn)
    victimas = random.sample([p for p in _perfiles_normales(conn) if p["saldo"] > 400_000], 8)
    for v in victimas:
        time.sleep(1)
        monto = datos.pesos(random.uniform(100_000, 400_000))
        estado, r = _sesion(v).transferir(v["numero"], mula["numero"], monto)
        _mostrar(estado, r, f"{v['nombre'][:24]} -> mula  {datos.cop(monto)}")
    # Retirar todo con codigos de retiro sin tarjeta (maximo 2.000.000 cada uno)
    sesion_mula = _sesion(mula)
    while (saldo := _saldo(conn, mula["numero"])) >= 10_000:
        monto = min(datos.pesos(float(saldo)), Decimal(2_000_000))
        estado, r = sesion_mula.llamar("POST", "/retiros/codigo", {"cuenta": mula["numero"], "monto": int(monto)})
        if estado != 201:
            _mostrar(estado, r, "Generar codigo de retiro")
            break
        estado, r = _cajero().llamar("POST", "/cajero/retiros/canjear",
                                     {"cuenta": mula["numero"], "cedula": mula["cedula"], "codigo": r["codigo"]})
        _mostrar(estado, r, f"Retiro en ventanilla de {datos.cop(monto)}")
        if estado != 200:
            break
    victimas_ids = [{"cuenta_id": v["cuenta_id"]} for v in victimas]
    _registrar_caso(conn, "cuenta_mula", "En vivo: cuenta nueva recibe de 8 personas y retira todo", [mula], victimas_ids)


def lanzar_robo(conn) -> None:
    print("ROBO DE CUENTA: alguien entra desde un dispositivo e IP extranjera y vacia la cuenta.")
    candidatas = [p for p in _perfiles_normales(conn) if p["perfil"] == "asalariado" and p["saldo"] > 800_000]
    victima = random.choice(candidatas)
    print(f"   victima: {victima['nombre']} (saldo {datos.cop(victima['saldo'])})")
    beneficiario = _nuevo_cliente_api(conn)
    ladron = _sesion(victima, dispositivo=datos.dispositivo(), ip=datos.ip_extranjera())
    print(f"   el ladron entra desde la IP {ladron.ip} con un dispositivo nunca visto")
    for i in range(6):
        time.sleep(1)
        monto = datos.pesos(float(_saldo(conn, victima["numero"])) * 0.22)
        if monto < 5000:
            break
        estado, r = ladron.transferir(victima["numero"], beneficiario["numero"], monto)
        _mostrar(estado, r, f"Transferencia {i + 1}/6  {datos.cop(monto)}")
    _registrar_caso(conn, "robo_cuenta", "En vivo: acceso desde dispositivo e IP extranjera vacia la cuenta",
                    [beneficiario], [{"cuenta_id": victima["cuenta_id"]}])


FRAUDES = {"ciclo": lanzar_ciclo, "dispositivo": lanzar_dispositivo, "mula": lanzar_mula, "robo": lanzar_robo}


def lanzar(tipo: str) -> None:
    conn = conectar()
    try:
        _exigir_carga(conn)
        FRAUDES[tipo](conn)
    except ErrorAPI as e:
        print(f"Error de la API: {e}")
    finally:
        conn.close()


# ================================================================ reporte
def reporte() -> None:
    conn = conectar()
    try:
        ejec = consultar_uno(conn, "SELECT resumen FROM banco_sim.ejecuciones WHERE tipo = 'carga' AND fin IS NOT NULL")
        if not ejec:
            raise SystemExit("Todavia no hay carga inicial.")
        casos = consultar(conn, "SELECT id, tipo, origen, descripcion, creado_en FROM banco_sim.casos ORDER BY id")
        print("=========== HOJA DE RESPUESTAS DEL SIMULADOR ===========")
        for caso in casos:
            print(f"\n#{caso['id']} [{caso['origen']}] {caso['tipo']}: {caso['descripcion']}")
            filas = consultar(
                conn,
                "SELECT cc.rol, c.numero, u.nombre, c.saldo, c.estado FROM banco_sim.casos_cuentas cc "
                "JOIN cuentas c ON c.id = cc.cuenta_id JOIN usuarios u ON u.id = c.usuario_id "
                "WHERE cc.caso_id = %s ORDER BY cc.rol, c.numero",
                (caso["id"],),
            )
            for f in filas:
                print(f"    {f['rol']:<11} {f['numero']}  {f['nombre'][:32]:<32} saldo {datos.cop(f['saldo']):>13}  {f['estado']}")
    finally:
        conn.close()
