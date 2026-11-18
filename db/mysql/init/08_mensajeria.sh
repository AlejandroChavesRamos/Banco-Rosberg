#!/bin/bash
# =====================================================================
# 08_mensajeria.sh  -  Chat de ayuda (tiquetes) y respuestas a solicitudes
#
#   tiquetes             un caso de ayuda de un CLIENTE, atendido por un empleado
#   mensajes_tiquete     la conversacion de cada tiquete (tipo messenger)
#   respuestas_solicitud lo que un empleado responde a una solicitud publica;
#                        se envia al correo del visitante (Mailpit en desarrollo)
#
# Es .sh para dar permisos al usuario de la app, cuyo nombre viene del .env.
# Es idempotente: se puede volver a correr sin danar nada. En una base que
# ya existia se aplica a mano con:
#   docker compose exec mysql bash /docker-entrypoint-initdb.d/08_mensajeria.sh
# =====================================================================
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<EOSQL
-- ---------------------------------------------------------------------
-- Tiquetes de ayuda. Estados:  nuevo -> en_atencion -> cerrado
--   nuevo:       nadie lo ha tomado; lo ven todos los empleados
--   en_atencion: un empleado pulso "Atender" y queda a su cargo
--   cerrado:     ya no admite mensajes; el cliente puede calificar (1 a 5)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tiquetes (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cliente_id       BIGINT UNSIGNED NOT NULL,
    tema             ENUM('cuentas','transferencias','retiros','seguridad','otro') NOT NULL,
    asunto           VARCHAR(120) NOT NULL,
    estado           ENUM('nuevo','en_atencion','cerrado') NOT NULL DEFAULT 'nuevo',
    asesor_id        BIGINT UNSIGNED NULL,              -- el empleado a cargo
    calificacion     TINYINT UNSIGNED NULL,
    -- Ultimo mensaje que cada lado ya vio: con esto se cuentan los "no leidos"
    visto_cliente_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
    visto_asesor_id  BIGINT UNSIGNED NOT NULL DEFAULT 0,
    creado_en        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    actualizado_en   DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),  -- ultimo mensaje
    cerrado_en       DATETIME(6) NULL,
    cerrado_por      BIGINT UNSIGNED NULL,
    CONSTRAINT fk_tiq_cliente FOREIGN KEY (cliente_id)  REFERENCES usuarios(id),
    CONSTRAINT fk_tiq_asesor  FOREIGN KEY (asesor_id)   REFERENCES usuarios(id),
    CONSTRAINT fk_tiq_cerro   FOREIGN KEY (cerrado_por) REFERENCES usuarios(id),
    CONSTRAINT ck_tiq_calificacion CHECK (calificacion IS NULL OR calificacion BETWEEN 1 AND 5),
    INDEX idx_tiq_cliente (cliente_id, actualizado_en),
    INDEX idx_tiq_cola    (estado, actualizado_en),
    INDEX idx_tiq_asesor  (asesor_id, estado)
) ENGINE=InnoDB;

-- Mensajes: solo se insertan. Nadie (ni la app) puede editarlos ni borrarlos:
-- son la evidencia de lo que el banco le dijo al cliente.
CREATE TABLE IF NOT EXISTS mensajes_tiquete (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tiquete_id  BIGINT UNSIGNED NOT NULL,
    autor_id    BIGINT UNSIGNED NOT NULL,
    texto       VARCHAR(1000) NOT NULL,
    creado_en   DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_msj_tiquete FOREIGN KEY (tiquete_id) REFERENCES tiquetes(id),
    CONSTRAINT fk_msj_autor   FOREIGN KEY (autor_id)   REFERENCES usuarios(id),
    INDEX idx_msj_tiquete (tiquete_id, id),
    INDEX idx_msj_autor_fecha (autor_id, creado_en)
) ENGINE=InnoDB;

-- Respuestas a las solicitudes publicas. El visitante no tiene cuenta, asi
-- que la respuesta le llega por correo; aqui queda si se pudo enviar.
CREATE TABLE IF NOT EXISTS respuestas_solicitud (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    solicitud_id  BIGINT UNSIGNED NOT NULL,
    autor_id      BIGINT UNSIGNED NOT NULL,
    texto         VARCHAR(2000) NOT NULL,
    estado_envio  ENUM('pendiente','enviado','fallido') NOT NULL DEFAULT 'pendiente',
    error_envio   VARCHAR(255) NULL,
    creado_en     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    enviado_en    DATETIME(6) NULL,
    CONSTRAINT fk_resp_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes_publicas(id),
    CONSTRAINT fk_resp_autor     FOREIGN KEY (autor_id)     REFERENCES usuarios(id),
    INDEX idx_resp_solicitud (solicitud_id, id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Permisos minimos de la app
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.tiquetes TO '${APP_DB_USER}'@'%';
-- No puede cambiar de quien es el tiquete, ni su tema o asunto
GRANT UPDATE (estado, asesor_id, calificacion, visto_cliente_id, visto_asesor_id,
              actualizado_en, cerrado_en, cerrado_por)
      ON ${MYSQL_DATABASE}.tiquetes TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.mensajes_tiquete TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.respuestas_solicitud TO '${APP_DB_USER}'@'%';
-- Solo el resultado del envio del correo; el texto ya enviado no se puede cambiar
GRANT UPDATE (estado_envio, error_envio, enviado_en)
      ON ${MYSQL_DATABASE}.respuestas_solicitud TO '${APP_DB_USER}'@'%';

-- Reportes: puede medir la atencion, pero no leer las conversaciones
GRANT SELECT (id, tema, estado, asesor_id, calificacion, creado_en, actualizado_en, cerrado_en)
      ON ${MYSQL_DATABASE}.tiquetes TO '${REPORT_DB_USER}'@'%';

FLUSH PRIVILEGES;
EOSQL

echo ">> Tablas de mensajeria listas"
