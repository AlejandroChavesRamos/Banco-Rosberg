"""Cliente HTTP de la API: el modo en vivo usa el banco igual que la app real.

Cada sesion envia su propio X-Dispositivo (identificador del celular) y
X-Forwarded-For (la IP desde la que "se conecta" el cliente simulado).
"""
import json
import secrets
import urllib.error
import urllib.request

from ..config import settings


class ErrorAPI(Exception):
    pass


class SesionAPI:
    def __init__(self, email: str, password: str, dispositivo: str, ip: str, portal: str = "app"):
        self.email = email
        self.password = password
        self.dispositivo = dispositivo
        self.ip = ip
        self.portal = portal          # 'app' para clientes, 'intranet' para empleados
        self.token: str | None = None

    def _peticion(self, metodo: str, ruta: str, cuerpo=None, clave: str | None = None, autenticada: bool = True):
        cabeceras = {
            "Content-Type": "application/json",
            "User-Agent": "RosbergApp/1.0 (simulador)",
            "X-Dispositivo": self.dispositivo,
            "X-Forwarded-For": self.ip,
        }
        if autenticada and self.token:
            cabeceras["Authorization"] = f"Bearer {self.token}"
        if clave:
            cabeceras["Idempotency-Key"] = clave
        datos = json.dumps(cuerpo, default=str).encode() if cuerpo is not None else None
        peticion = urllib.request.Request(settings.api_url + ruta, data=datos, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(peticion, timeout=30) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def login(self) -> None:
        estado, respuesta = self._peticion("POST", "/auth/login",
                                           {"email": self.email, "password": self.password, "portal": self.portal},
                                           autenticada=False)
        if estado != 200:
            raise ErrorAPI(f"No se pudo iniciar sesion como {self.email}: {estado} {respuesta}")
        self.token = respuesta["access_token"]

    def llamar(self, metodo: str, ruta: str, cuerpo=None, idempotente: bool = False):
        if not self.token:
            self.login()
        clave = secrets.token_hex(16) if idempotente else None
        estado, respuesta = self._peticion(metodo, ruta, cuerpo, clave)
        if estado == 401:            # token vencido: entrar de nuevo y reintentar con la MISMA clave
            self.login()
            estado, respuesta = self._peticion(metodo, ruta, cuerpo, clave)
        return estado, respuesta

    def transferir(self, cuenta_origen: str, destino: str, monto) -> tuple[int, dict]:
        return self.llamar("POST", "/transferencias",
                           {"cuenta_origen": cuenta_origen, "destino": destino, "monto": int(monto)},
                           idempotente=True)


def registrar_cliente(nombre: str, email: str, cedula: str, celular: str, password: str,
                      dispositivo: str, ip: str) -> str:
    """Registro en linea por la API. Devuelve el numero de cuenta."""
    anonima = SesionAPI(email, password, dispositivo, ip)
    estado, respuesta = anonima._peticion("POST", "/auth/registro", {
        "nombre": nombre, "email": email, "cedula": cedula, "celular": celular, "password": password,
    }, autenticada=False)
    if estado != 201:
        raise ErrorAPI(f"No se pudo registrar a {email}: {estado} {respuesta}")
    return respuesta["cuenta"]
