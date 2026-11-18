"""Modelos de entrada/salida (Pydantic).

FastAPI valida automaticamente cada peticion contra estos modelos: si un
campo no cumple (monto negativo, cedula con letras...), responde 422 sin
que el dato llegue a la base de datos.
"""
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from .seguridad.contrasenas import validar_politica

Monto = Annotated[Decimal, Field(gt=0, max_digits=15, decimal_places=2,
                                 description="Monto en pesos colombianos")]
Cedula = Annotated[str, Field(pattern=r"^\d{6,10}$", examples=["1020304050"])]
Celular = Annotated[str, Field(pattern=r"^3\d{9}$", examples=["3001234567"])]
NumeroCuenta = Annotated[str, Field(pattern=r"^\d{12}$", examples=["710000000001"])]
Nombre = Annotated[str, Field(min_length=3, max_length=120)]
TipoCuenta = Literal["ahorros", "corriente"]


def _texto_limpio(v: str | None, obligatorio: bool = True) -> str | None:
    """Quita espacios sobrantes y caracteres de control (salvo saltos de linea)."""
    if v is None:
        return None
    v = "".join(c for c in v if c == "\n" or c.isprintable()).strip()
    if obligatorio and not v:
        raise ValueError("No puede estar vacio")
    return v or None


# ---------------------------- Autenticacion ----------------------------
class RegistroEntrada(BaseModel):
    nombre: Nombre
    email: EmailStr
    cedula: Cedula
    celular: Celular
    password: str

    @field_validator("password")
    @classmethod
    def _politica(cls, v: str) -> str:
        return validar_politica(v)


# ------------------------------ Publico --------------------------------
class SolicitudPublica(BaseModel):
    email: EmailStr
    tipo: Literal["tarjeta", "contacto", "empleo"]
    mensaje: str | None = Field(default=None, max_length=500)


class EstadoSolicitud(BaseModel):
    atendida: bool


Portal = Literal["app", "intranet"]


class LoginEntrada(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    portal: Portal = Field(description="'app' para clientes, 'intranet' para empleados")


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_segundos: int
    rol: str
    nombre: str
    debe_cambiar_password: bool
    debe_configurar_2fa: bool = False
    tiene_2fa: bool = False


CodigoTotp = Annotated[str, Field(pattern=r"^\d{6}$", description="Codigo de 6 digitos de la app autenticadora")]


class Verificar2FA(BaseModel):
    token_2fa: str
    codigo: CodigoTotp


class CodigoEntrada(BaseModel):
    codigo: CodigoTotp


class Desactivar2FA(BaseModel):
    password: str = Field(max_length=128)
    codigo: CodigoTotp


class CambioConfiguracion(BaseModel):
    valor: str = Field(min_length=1, max_length=20)


class CambioPassword(BaseModel):
    actual: str = Field(max_length=128)
    nueva: str

    @field_validator("nueva")
    @classmethod
    def _politica(cls, v: str) -> str:
        return validar_politica(v)


class RecuperarPassword(BaseModel):
    """El cliente demuestra quien es con los datos que dio al abrir la cuenta."""
    email: EmailStr
    cedula: Cedula
    celular: Celular
    nueva: str

    @field_validator("nueva")
    @classmethod
    def _politica(cls, v: str) -> str:
        return validar_politica(v)


# ------------------------------ Cliente --------------------------------
class NuevaCuenta(BaseModel):
    tipo: TipoCuenta = "ahorros"


class NuevaLlave(BaseModel):
    tipo: Literal["celular", "correo"]
    cuenta: NumeroCuenta


class TransferenciaEntrada(BaseModel):
    cuenta_origen: NumeroCuenta
    destino: str = Field(min_length=3, max_length=120,
                         description="Numero de cuenta (12 digitos), celular o correo registrado como llave")
    monto: Monto
    codigo_2fa: str | None = Field(default=None, pattern=r"^\d{6}$",
                                   description="Solo si el banco lo exige para montos grandes")
    mensaje: str | None = Field(default=None, max_length=140,
                                description="Nota para quien recibe, como en Nequi (\"Para el almuerzo\")")

    @field_validator("mensaje")
    @classmethod
    def _mensaje(cls, v):
        return _texto_limpio(v, obligatorio=False)


class CerrarCuentaEntrada(BaseModel):
    password: str = Field(max_length=128, description="Contrasena actual, para confirmar")
    destino: NumeroCuenta | None = Field(default=None,
                                         description="Cuenta propia que recibe el saldo (obligatoria si hay saldo)")


class MetaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    objetivo: Monto
    cuenta: NumeroCuenta


class MovimientoMeta(BaseModel):
    monto: Monto


class CodigoRetiroEntrada(BaseModel):
    cuenta: NumeroCuenta
    monto: Monto


# ------------------------------- Cajero --------------------------------
class ClienteVentanilla(BaseModel):
    nombre: Nombre
    email: EmailStr
    cedula: Cedula
    celular: Celular
    tipo_cuenta: TipoCuenta = "ahorros"


class CuentaVentanilla(BaseModel):
    cedula: Cedula
    tipo: TipoCuenta = "ahorros"


class DepositoEntrada(BaseModel):
    cuenta: NumeroCuenta
    monto: Monto


class CanjeRetiro(BaseModel):
    cuenta: NumeroCuenta
    cedula: Cedula
    codigo: str = Field(pattern=r"^\d{6}$")


# ------------------------------ Analista -------------------------------
class ResolverAlerta(BaseModel):
    confirmar_fraude: bool = Field(description="true = es fraude (se rechaza y se congela la cuenta); "
                                               "false = falsa alarma (se aprueba)")
    nota: str = Field(default="", max_length=1000)


class MotivoCongelar(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


# -------------------------------- Admin --------------------------------
class EmpleadoEntrada(BaseModel):
    nombre: Nombre
    email: EmailStr
    rol: Literal["cajero", "analista", "admin"]


class EstadoEmpleado(BaseModel):
    activo: bool


class ReglaCambio(BaseModel):
    peso: int | None = Field(default=None, ge=0, le=100)
    umbral: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    activa: bool | None = None


# ------------------------------ Mensajeria -----------------------------
TemaTiquete = Literal["cuentas", "transferencias", "retiros", "seguridad", "otro"]


class NuevoTiquete(BaseModel):
    tema: TemaTiquete
    asunto: str = Field(min_length=3, max_length=120)
    mensaje: str = Field(min_length=1, max_length=1000)

    @field_validator("asunto", "mensaje")
    @classmethod
    def _limpio(cls, v):
        return _texto_limpio(v)


class MensajeEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)

    @field_validator("texto")
    @classmethod
    def _limpio(cls, v):
        return _texto_limpio(v)


class CierreTiquete(BaseModel):
    calificacion: int | None = Field(default=None, ge=1, le=5, description="Solo el cliente califica")


class Calificacion(BaseModel):
    calificacion: int = Field(ge=1, le=5)


class Reasignacion(BaseModel):
    asesor_id: int


class RespuestaSolicitud(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)

    @field_validator("texto")
    @classmethod
    def _limpio(cls, v):
        return _texto_limpio(v)


# ------------------------------ Asistente ------------------------------
class AsistenteEstado(BaseModel):
    activo: bool


PalabrasClave = Annotated[list[Annotated[str, Field(min_length=2, max_length=40)]],
                          Field(min_length=1, max_length=20,
                                description="Palabras o frases cortas que activan la respuesta")]


AccionAsistente = Literal["envios", "cuentas", "saldo", "codigos_retiro", "llaves", "seguridad"]


class NuevaRespuestaAutomatica(BaseModel):
    titulo: str = Field(min_length=3, max_length=80)
    pregunta: str | None = Field(default=None, max_length=120,
                                 description="Como aparece en un boton de sugerencia")
    respuesta: str = Field(min_length=5, max_length=1000)
    accion: AccionAsistente | None = Field(default=None, description="Ademas, mostrar estos datos del cliente")
    palabras: PalabrasClave
    relacionadas: list[int] = Field(default_factory=list, max_length=6)
    prioridad: int = Field(default=5, ge=1, le=10)

    @field_validator("titulo", "respuesta")
    @classmethod
    def _limpio(cls, v):
        return _texto_limpio(v)

    @field_validator("pregunta")
    @classmethod
    def _pregunta(cls, v):
        return _texto_limpio(v, obligatorio=False)


class CambioRespuestaAutomatica(BaseModel):
    """Solo se cambia lo que se envia. pregunta = "" o accion = "ninguna" las quitan."""
    titulo: str | None = Field(default=None, min_length=3, max_length=80)
    pregunta: str | None = Field(default=None, max_length=120)
    respuesta: str | None = Field(default=None, min_length=5, max_length=1000)
    accion: AccionAsistente | Literal["ninguna"] | None = None
    palabras: PalabrasClave | None = None
    relacionadas: list[int] | None = Field(default=None, max_length=6)
    prioridad: int | None = Field(default=None, ge=1, le=10)
    activa: bool | None = None

    @field_validator("titulo", "respuesta", "pregunta")
    @classmethod
    def _limpio(cls, v):
        return _texto_limpio(v, obligatorio=False) if v is not None else None


class Ensenanza(BaseModel):
    respuesta_id: int
    palabras: PalabrasClave


class NuevoSinonimo(BaseModel):
    palabra: str = Field(min_length=2, max_length=40)
    equivale: str = Field(min_length=2, max_length=40)
