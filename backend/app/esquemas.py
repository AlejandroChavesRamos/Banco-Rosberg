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
