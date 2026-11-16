"""Administracion: empleados, reglas antifraude, auditoria y grafo."""
import json

import pymysql
from fastapi import APIRouter, Depends, Query, Request

from ..db.mysql import consultar, consultar_uno, ejecutar, llamar_sp, obtener_conexion
from ..errores import ErrorNegocio
from ..esquemas import CambioConfiguracion, EmpleadoEntrada, EstadoEmpleado, ReglaCambio
from ..seguridad import contrasenas
from ..seguridad.dependencias import UsuarioActual, requiere_rol
from ..servicios import auditoria, grafo
from ..utilidades import ip_cliente

router = APIRouter(prefix="/admin", tags=["5. Administrador"])
admin = requiere_rol("admin")


@router.get("/empleados", summary="Listar empleados")
def empleados(u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    return consultar(conn, "SELECT id, nombre, email, rol, activo, creado_en FROM usuarios "
                           "WHERE rol <> 'cliente' ORDER BY id")


@router.post("/empleados", status_code=201, summary="Crear empleado (cajero, analista o admin)")
def crear_empleado(datos: EmpleadoEntrada, request: Request,
                   u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    temporal = contrasenas.generar_temporal()
    try:
        cur = ejecutar(conn, "INSERT INTO usuarios (email, password_hash, rol, nombre, debe_cambiar_password) "
                             "VALUES (%s, %s, %s, %s, TRUE)",
                       (datos.email.lower(), contrasenas.hashear(temporal), datos.rol, datos.nombre.strip()))
    except pymysql.err.IntegrityError:
        raise ErrorNegocio(409, "Ya existe un usuario con ese correo")
    auditoria.registrar(conn, "CREAR_EMPLEADO", "usuarios", cur.lastrowid, usuario_id=u.id,
                        detalle={"rol": datos.rol}, ip=ip_cliente(request))
    return {"id": cur.lastrowid, "email": datos.email.lower(), "rol": datos.rol,
            "password_temporal": temporal,
            "mensaje": "Entregue la contrasena temporal al empleado. No se volvera a mostrar."}


@router.patch("/empleados/{empleado_id}", summary="Activar o desactivar un empleado")
def cambiar_estado_empleado(empleado_id: int, datos: EstadoEmpleado, request: Request,
                            u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    if empleado_id == u.id:
        raise ErrorNegocio(400, "No puede desactivarse a si mismo")
    empleado = consultar_uno(conn, "SELECT id, rol FROM usuarios WHERE id = %s AND rol <> 'cliente'", (empleado_id,))
    if not empleado:
        raise ErrorNegocio(404, "Empleado no encontrado")
    ejecutar(conn, "UPDATE usuarios SET activo = %s WHERE id = %s", (datos.activo, empleado_id))
    if not datos.activo:
        # Sale de inmediato: se cierran sus sesiones abiertas
        ejecutar(conn, "UPDATE sesiones SET revocada = TRUE WHERE usuario_id = %s", (empleado_id,))
    auditoria.registrar(conn, "ACTIVAR_EMPLEADO" if datos.activo else "DESACTIVAR_EMPLEADO", "usuarios",
                        empleado_id, usuario_id=u.id, ip=ip_cliente(request))
    return {"id": empleado_id, "activo": datos.activo}


@router.get("/reglas", summary="Reglas del motor antifraude")
def reglas(u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    return {
        "reglas": consultar(conn, "SELECT * FROM reglas_fraude ORDER BY motor, codigo"),
        "configuracion": consultar(conn, "SELECT * FROM configuracion ORDER BY clave"),
    }


@router.patch("/reglas/{codigo}", summary="Ajustar peso, umbral o activar/desactivar una regla")
def cambiar_regla(codigo: str, datos: ReglaCambio, request: Request,
                  u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    anterior = consultar_uno(conn, "SELECT * FROM reglas_fraude WHERE codigo = %s", (codigo,))
    if not anterior:
        raise ErrorNegocio(404, "Regla no encontrada")
    cambios = datos.model_dump(exclude_none=True)
    if not cambios:
        raise ErrorNegocio(400, "No envio ningun cambio")
    # Los nombres de columna salen de una lista fija (el modelo), nunca del usuario
    columnas = ", ".join(f"{c} = %s" for c in cambios)
    ejecutar(conn, f"UPDATE reglas_fraude SET {columnas} WHERE codigo = %s", (*cambios.values(), codigo))
    auditoria.registrar(conn, "CAMBIAR_REGLA", "reglas_fraude", None, usuario_id=u.id,
                        detalle={"codigo": codigo, "antes": {k: anterior[k] for k in cambios}, "despues": cambios},
                        ip=ip_cliente(request))
    return consultar_uno(conn, "SELECT * FROM reglas_fraude WHERE codigo = %s", (codigo,))


# Solo estas claves se pueden cambiar desde la Intranet (lista blanca)
_CONFIG_EDITABLE = {
    "2FA_EMPLEADOS": "interruptor",
    "2FA_CLIENTES": "interruptor",
    "2FA_TRANSFERENCIAS": "interruptor",
    "MONTO_2FA": "numero",
}


@router.patch("/configuracion/{clave}", summary="Cambiar un interruptor o valor de seguridad")
def cambiar_configuracion(clave: str, datos: CambioConfiguracion, request: Request,
                          u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    tipo = _CONFIG_EDITABLE.get(clave)
    if not tipo:
        raise ErrorNegocio(404, "Esa configuracion no se puede cambiar desde aqui")
    if tipo == "interruptor" and datos.valor not in ("0", "1"):
        raise ErrorNegocio(400, "Un interruptor solo puede valer 0 (apagado) o 1 (encendido)")
    if tipo == "numero" and (not datos.valor.isdigit() or int(datos.valor) < 1000):
        raise ErrorNegocio(400, "Debe ser un monto entero de al menos 1000")
    anterior = consultar_uno(conn, "SELECT valor FROM configuracion WHERE clave = %s", (clave,))
    ejecutar(conn, "UPDATE configuracion SET valor = %s WHERE clave = %s", (datos.valor, clave))
    auditoria.registrar(conn, "CAMBIAR_CONFIGURACION", "configuracion", None, usuario_id=u.id,
                        detalle={"clave": clave, "antes": anterior["valor"] if anterior else None,
                                 "despues": datos.valor}, ip=ip_cliente(request))
    return {"clave": clave, "valor": datos.valor}


@router.get("/auditoria", summary="Ultimos registros de auditoria")
def ver_auditoria(limite: int = Query(50, ge=1, le=500),
                  u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    filas = consultar(conn, "SELECT id, usuario_id, accion, entidad, entidad_id, detalle, ip, fecha, hash "
                            "FROM auditoria ORDER BY id DESC LIMIT %s", (limite,))
    for f in filas:
        f["detalle"] = json.loads(f["detalle"]) if f["detalle"] else None
    return filas


@router.get("/auditoria/verificar", summary="Verificar que nadie altero la auditoria")
def verificar_auditoria(u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    alterado = llamar_sp(conn, "sp_verificar_auditoria", [])
    total = consultar_uno(conn, "SELECT COUNT(*) AS n FROM auditoria")["n"]
    if alterado is None:
        return {"integra": True, "registros_verificados": total}
    return {"integra": False, "primer_registro_alterado": alterado,
            "mensaje": "La cadena de hashes esta rota: alguien modifico la auditoria"}


@router.post("/grafo/resincronizar", summary="Reconstruir el grafo de Neo4j desde MySQL")
def resincronizar(request: Request, u: UsuarioActual = Depends(admin), conn=Depends(obtener_conexion)):
    resultado = grafo.resincronizar(conn)
    auditoria.registrar(conn, "RESINCRONIZAR_GRAFO", "grafo", None, usuario_id=u.id,
                        detalle=resultado, ip=ip_cliente(request))
    return resultado
