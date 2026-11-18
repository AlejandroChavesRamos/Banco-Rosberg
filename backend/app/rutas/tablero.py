"""Tablero: cifras generales para el analista y el administrador."""
from fastapi import APIRouter, Depends

from ..db.mysql import consultar, consultar_uno, obtener_conexion
from ..seguridad.dependencias import UsuarioActual, requiere_rol

router = APIRouter(prefix="/tablero", tags=["6. Tablero"])


@router.get("", summary="Indicadores y graficas del banco")
def tablero(u: UsuarioActual = Depends(requiere_rol("analista", "admin")), conn=Depends(obtener_conexion)):
    indicadores = consultar_uno(
        conn,
        """
        SELECT
          (SELECT COUNT(*) FROM usuarios WHERE rol = 'cliente')                         AS clientes,
          (SELECT COUNT(*) FROM cuentas)                                                AS cuentas,
          (SELECT COUNT(*) FROM cuentas WHERE estado = 'congelada')                     AS cuentas_congeladas,
          (SELECT IFNULL(SUM(saldo), 0) FROM cuentas)                                   AS dinero_total,
          (SELECT COUNT(*) FROM transacciones WHERE creada_en >= NOW() - INTERVAL 1 DAY) AS transacciones_24h,
          (SELECT COUNT(*) FROM alertas_fraude WHERE estado IN ('abierta', 'en_revision')) AS alertas_abiertas,
          (SELECT COUNT(*) FROM transacciones WHERE estado IN ('retenida', 'bloqueada', 'rechazada')) AS operaciones_frenadas,
          (SELECT IFNULL(SUM(monto), 0) FROM transacciones
            WHERE estado IN ('retenida', 'bloqueada', 'rechazada'))                     AS dinero_protegido,
          (SELECT COUNT(*) FROM tiquetes WHERE estado <> 'cerrado')                     AS tiquetes_abiertos,
          (SELECT COUNT(*) FROM tiquetes WHERE estado = 'nuevo')                        AS tiquetes_sin_asignar,
          (SELECT ROUND(AVG(calificacion), 1) FROM tiquetes)                            AS satisfaccion,
          (SELECT COUNT(calificacion) FROM tiquetes)                                    AS calificaciones,
          (SELECT COUNT(*) FROM solicitudes_publicas WHERE NOT atendida)                AS solicitudes_pendientes
        """,
    )

    # Transacciones por hora en las ultimas 24 h (aprobadas vs frenadas por el motor)
    # %% porque PyMySQL usa % para los parametros
    por_hora = consultar(
        conn,
        """
        SELECT DATE_FORMAT(creada_en, '%%H:00') AS hora,
               DATE_FORMAT(creada_en, '%%Y-%%m-%%d %%H') AS orden,
               CAST(SUM(estado = 'aprobada') AS UNSIGNED)  AS aprobadas,
               CAST(SUM(estado <> 'aprobada') AS UNSIGNED) AS frenadas
        FROM transacciones
        WHERE creada_en >= NOW() - INTERVAL 24 HOUR
        GROUP BY orden, hora
        ORDER BY orden
        """,
    )

    # Alertas por regla. Los motivos se guardan como JSON dentro de la alerta;
    # JSON_TABLE los "despliega" en filas para poder agruparlos.
    por_regla = consultar(
        conn,
        """
        SELECT jt.codigo,
               COUNT(*) AS total,
               CAST(SUM(a.estado IN ('abierta', 'en_revision')) AS UNSIGNED) AS abiertas
        FROM alertas_fraude a,
             JSON_TABLE(a.motivos, '$[*]' COLUMNS (codigo VARCHAR(40) PATH '$.codigo')) AS jt
        WHERE jt.codigo IS NOT NULL
        GROUP BY jt.codigo
        ORDER BY total DESC
        """,
    )

    # Decisiones del motor en transferencias de los ultimos 7 dias
    decisiones = consultar(
        conn,
        """
        SELECT estado, COUNT(*) AS total
        FROM transacciones
        WHERE tipo = 'transferencia' AND creada_en >= NOW() - INTERVAL 7 DAY
        GROUP BY estado
        """,
    )

    return {"indicadores": indicadores, "por_hora": por_hora, "por_regla": por_regla, "decisiones": decisiones}
