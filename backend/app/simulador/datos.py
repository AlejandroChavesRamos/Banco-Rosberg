"""Generadores de datos ficticios colombianos (nombres, cedulas, celulares, IPs).

Todo usa `random` con semilla fija: la misma semilla produce el mismo banco,
lo que permite repetir la demo con los mismos resultados.
"""
import hashlib
import random
import unicodedata
from decimal import Decimal

from faker import Faker

_fake = Faker("es_CO")

DOMINIOS = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "gmail.com", "gmail.com"]
PREFIJOS_CELULAR = ["300", "301", "302", "304", "305", "310", "311", "312", "313", "314",
                    "315", "316", "317", "318", "319", "320", "321", "323", "350", "351"]
AGENTES = [
    "Mozilla/5.0 (Linux; Android 14; SM-A546E) RosbergApp/1.0",
    "Mozilla/5.0 (Linux; Android 13; moto g54) RosbergApp/1.0",
    "Mozilla/5.0 (Linux; Android 14; Redmi Note 13) RosbergApp/1.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) RosbergApp/1.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Safari/605.1.15",
]


def fijar_semilla(semilla: int) -> None:
    random.seed(semilla)
    Faker.seed(semilla)


def nombre() -> str:
    return f"{_fake.first_name()} {_fake.last_name()} {_fake.last_name()}"


def _ascii(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sin_tildes.lower() if c.isalnum() or c == " ")


def email(nombre_completo: str, usados: set[str]) -> str:
    partes = _ascii(nombre_completo).split()
    while True:
        base = f"{partes[0]}.{partes[1]}" if random.random() < 0.6 else f"{partes[0][0]}{partes[1]}"
        correo = f"{base}{random.randint(1, 999)}@{random.choice(DOMINIOS)}"
        if correo not in usados:
            usados.add(correo)
            return correo


def cedula(usadas: set[str]) -> str:
    while True:
        if random.random() < 0.7:
            valor = str(random.randint(1_000_000_000, 1_199_999_999))   # cedulas recientes (10 digitos)
        else:
            valor = str(random.randint(10_000_000, 99_999_999))         # cedulas antiguas (8 digitos)
        if valor not in usadas:
            usadas.add(valor)
            return valor


def celular(usados: set[str]) -> str:
    while True:
        valor = random.choice(PREFIJOS_CELULAR) + f"{random.randint(0, 9_999_999):07d}"
        if valor not in usados:
            usados.add(valor)
            return valor


def ip_colombia() -> str:
    return f"{random.choice([181, 186, 190, 191])}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def ip_extranjera() -> str:
    return f"{random.choice([45, 103, 185, 196])}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def dispositivo() -> str:
    """Identificador persistente del navegador o celular (lo que se envia como X-Dispositivo)."""
    return f"sim-{random.getrandbits(64):016x}"


def huella(identificador: str) -> str:
    """Igual que la API: se guarda el SHA-256 del identificador."""
    return hashlib.sha256(identificador.encode("utf-8")).hexdigest()


def agente() -> str:
    return random.choice(AGENTES)


def pesos(valor: float) -> Decimal:
    """Redondea a miles de pesos (los montos reales casi nunca tienen centavos)."""
    return Decimal(int(valor) // 1000 * 1000)


def cop(valor) -> str:
    return "$" + f"{int(valor):,}".replace(",", ".")
