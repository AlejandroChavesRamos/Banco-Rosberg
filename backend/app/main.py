"""Punto de entrada de la API de Banco Rosberg."""
import logging
from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db.mysql import conectar
from .errores import ErrorNegocio
from .rutas import admin, analista, auth, ayuda, cajero, cliente, publico, seguridad, tablero
from .servicios import grafo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("banco")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    try:
        grafo.inicializar()
    except Exception:
        log.exception("Neo4j no disponible al iniciar")
    yield
    grafo.cerrar()


app = FastAPI(
    title=f"{settings.nombre_banco} · API",
    version="0.2.0",
    description=(
        "Banco simulado con detector de fraude (proyecto de Bases de Datos).\n\n"
        "**Como probar:** 1) `POST /auth/login` 2) copie el `access_token` "
        "3) pulse **Authorize** arriba a la derecha y peguelo."
    ),
    lifespan=ciclo_de_vida,
    # En produccion no se publica la documentacion interactiva: le daria a un
    # atacante el mapa completo de la API.
    docs_url=None if settings.produccion else "/docs",
    redoc_url=None,
    openapi_url=None if settings.produccion else "/openapi.json",
)

if not settings.produccion:
    # En produccion las pantallas y la API comparten dominio (via nginx): no hace falta CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origenes_cors,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Dispositivo"],
    )


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    # Los datos bancarios no se guardan en cache (ni del navegador ni de proxies)
    respuesta.headers["Cache-Control"] = "no-store"
    # El navegador no debe "adivinar" el tipo de contenido
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    # Las respuestas de la API no se pueden incrustar en otra pagina (clickjacking)
    respuesta.headers["X-Frame-Options"] = "DENY"
    return respuesta


@app.exception_handler(ErrorNegocio)
async def _error_negocio(request: Request, exc: ErrorNegocio):
    return JSONResponse(status_code=exc.codigo_http, content={"detail": exc.mensaje})


# Codigos de PyMySQL que significan "no hay conexion con el servidor MySQL"
# (contenedor apagado, reiniciandose o red caida)
_SIN_CONEXION_MYSQL = {2002, 2003, 2006, 2013, 2055}


@app.exception_handler(pymysql.err.MySQLError)
async def _error_mysql(request: Request, exc: pymysql.err.MySQLError):
    codigo = exc.args[0] if exc.args else None
    if codigo == 1644:
        # SIGNAL SQLSTATE '45000' de un procedimiento: es una regla de negocio
        # (saldo insuficiente, cuenta congelada...). Su mensaje es seguro de mostrar.
        return JSONResponse(status_code=400, content={"detail": exc.args[1]})
    if codigo in _SIN_CONEXION_MYSQL:
        # 503 = "servicio no disponible por ahora": la app sigue viva y se
        # recuperara sola cuando el contenedor de MySQL vuelva.
        log.warning("MySQL no disponible en %s %s", request.method, request.url.path)
        return JSONResponse(status_code=503, headers={"Retry-After": "10"},
                            content={"detail": "La base de datos del banco no está disponible en este momento. "
                                               "Intenta de nuevo en unos segundos."})
    # Cualquier otro error de BD: se registra completo en el log del servidor,
    # pero al cliente NO se le muestran detalles internos (tablas, consultas).
    log.error("Error de MySQL en %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno. Intente de nuevo."})


@app.exception_handler(grafo.GrafoNoDisponible)
async def _grafo_no_disponible(request: Request, exc: grafo.GrafoNoDisponible):
    # Solo afecta lo que NECESITA el grafo (por ejemplo, dibujarlo o el barrido).
    # Transferencias, login y saldos siguen funcionando con MySQL.
    return JSONResponse(status_code=503, headers={"Retry-After": "15"},
                        content={"detail": "El grafo de relaciones (Neo4j) no está disponible en este momento. "
                                           "Las demás funciones del banco siguen operando."})


app.include_router(auth.router)
app.include_router(cliente.router)
app.include_router(seguridad.router)
app.include_router(cajero.router)
app.include_router(analista.router)
app.include_router(admin.router)
app.include_router(tablero.router)
app.include_router(publico.router)
app.include_router(ayuda.router_cliente)
app.include_router(ayuda.router_empleado)


@app.get("/salud", tags=["0. Sistema"], summary="Estado de la API y de cada base de datos")
def salud():
    """Siempre responde 200 si la API esta viva (Docker lo usa como healthcheck).
    Dentro indica el estado de cada base: la API puede estar bien aunque una
    base este caida ("degradado")."""
    estado = {"api": "ok"}
    try:
        conn = conectar()
        conn.ping()
        conn.close()
        estado["mysql"] = "ok"
    except Exception:
        estado["mysql"] = "error"
    try:
        grafo.driver().verify_connectivity()
        estado["neo4j"] = "ok"
    except Exception:
        estado["neo4j"] = "error"
    pendiente = grafo.estado()
    if pendiente["pendientes"]:
        estado["grafo_desactualizado"] = f"{pendiente['pendientes']} cambio(s) por sincronizar"
        if estado["neo4j"] == "ok" and estado["mysql"] == "ok":
            grafo._al_recuperarse()   # Neo4j volvio: reconstruir el grafo en segundo plano
    estado["estado"] = "ok" if estado["mysql"] == "ok" and estado["neo4j"] == "ok" else "degradado"
    return estado
