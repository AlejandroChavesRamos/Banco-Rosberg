"""Configuracion de la aplicacion, leida desde variables de entorno (.env via docker-compose).

Ninguna contrasena ni clave esta escrita en el codigo.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    nombre_banco: str = "Banco Rosberg"

    # MySQL: la app se conecta con el usuario de PRIVILEGIOS MINIMOS, nunca con root
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str
    app_db_user: str
    app_db_password: str

    # Neo4j: bolt:// = conexion directa (sin enrutamiento) por la red interna de Docker
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str
    scripts_neo4j: str = "/scripts/neo4j"

    # Claves criptograficas (base64 de 32 bytes cada una)
    jwt_secreto: str
    clave_cifrado: str   # AES-256-GCM para cedula y telefono
    clave_indices: str   # HMAC para "indices ciegos" y codigos de retiro

    access_minutos: int = 15
    refresh_dias: int = 7
    cookie_segura: bool = False  # True cuando haya HTTPS (Fase 6)

    tz: str = "UTC"
    origenes_cors: list[str] = ["http://localhost:5173"]  # frontend de la Fase 5

    # Solo desarrollo: usar la IP de X-Forwarded-For (ver docker-compose.yml)
    confiar_x_forwarded_for: bool = False
    # Produccion: nombre del proxy (nginx) del que SI se acepta la cabecera X-Real-IP
    proxy_confiable: str = ""
    # Produccion: oculta /docs y otros detalles internos
    produccion: bool = False

    # Correo saliente (en desarrollo, Mailpit: un buzon de prueba)
    smtp_host: str = "mailpit"
    smtp_puerto: int = 1025
    correo_remitente: str = "Banco Rosberg <no-responder@rosberg.co>"

    # Simulador (Fase 3)
    api_url: str = "http://backend:8000"
    sim_password_clientes: str = ""


settings = Settings()
