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
from .rutas import admin, analista, auth, cajero, cliente, tablero
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origenes_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Dispositivo"],
)


@app.exception_handler(ErrorNegocio)
async def _error_negocio(request: Request, exc: ErrorNegocio):
    return JSONResponse(status_code=exc.codigo_http, content={"detail": exc.mensaje})


@app.exception_handler(pymysql.err.MySQLError)
async def _error_mysql(request: Request, exc: pymysql.err.MySQLError):
    codigo = exc.args[0] if exc.args else None
    if codigo == 1644:
        # SIGNAL SQLSTATE '45000' de un procedimiento: es una regla de negocio
        # (saldo insuficiente, cuenta congelada...). Su mensaje es seguro de mostrar.
        return JSONResponse(status_code=400, content={"detail": exc.args[1]})
    # Cualquier otro error de BD: se registra completo en el log del servidor,
    # pero al cliente NO se le muestran detalles internos (tablas, consultas).
    log.error("Error de MySQL en %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno. Intente de nuevo."})


app.include_router(auth.router)
app.include_router(cliente.router)
app.include_router(cajero.router)
app.include_router(analista.router)
app.include_router(admin.router)
app.include_router(tablero.router)


@app.get("/salud", tags=["0. Sistema"], summary="Estado de las bases de datos")
def salud():
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
    return estado
