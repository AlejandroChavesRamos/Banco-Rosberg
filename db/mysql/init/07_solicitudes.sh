#!/bin/bash
# =====================================================================
# 07_solicitudes.sh  -  Solicitudes hechas desde la pagina publica
#
# Guarda los correos que dejan los visitantes en la pantalla de login:
#   - 'tarjeta':  piden la tarjeta debito fisica
#   - 'contacto': piden que el banco les escriba
#   - 'empleo':   dejan su correo en "Trabaja con nosotros"
# El banco no envia correos reales (proyecto academico): la solicitud
# queda aqui para que un empleado la atienda.
#
# Es .sh para poder dar permisos al usuario de la app, cuyo nombre viene
# del .env. Si la base ya existia, se aplica a mano con:
#   docker compose exec mysql bash /docker-entrypoint-initdb.d/07_solicitudes.sh
# =====================================================================
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<EOSQL
CREATE TABLE IF NOT EXISTS solicitudes_publicas (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tipo       ENUM('tarjeta','contacto','empleo') NOT NULL,
    email      VARCHAR(254) NOT NULL,
    mensaje    VARCHAR(500) NULL,
    ip         VARCHAR(45)  NULL,
    atendida   BOOLEAN      NOT NULL DEFAULT FALSE,
    creada_en  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_solicitudes_ip (ip, creada_en),
    INDEX idx_solicitudes_pendientes (atendida, creada_en)
) ENGINE=InnoDB;

-- Por si la tabla ya existia con menos tipos
ALTER TABLE solicitudes_publicas MODIFY tipo ENUM('tarjeta','contacto','empleo') NOT NULL;

-- La app puede crear solicitudes, leerlas (limite por IP y bandeja de la
-- Intranet) y marcar si ya se atendieron. No puede cambiar su contenido ni borrarlas.
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.solicitudes_publicas TO '${APP_DB_USER}'@'%';
GRANT UPDATE (atendida) ON ${MYSQL_DATABASE}.solicitudes_publicas TO '${APP_DB_USER}'@'%';

-- Reportes: lectura, para atender las solicitudes desde Workbench
GRANT SELECT ON ${MYSQL_DATABASE}.solicitudes_publicas TO '${REPORT_DB_USER}'@'%';

FLUSH PRIVILEGES;
EOSQL

echo ">> Tabla 'solicitudes_publicas' lista"
