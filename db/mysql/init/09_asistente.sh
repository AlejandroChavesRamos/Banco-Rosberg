#!/bin/bash
# =====================================================================
# 09_asistente.sh  -  Contestador automatico ("Asistente Rosberg")
#
#   respuestas_automaticas   lo que el asistente sabe responder
#   palabras_respuesta       palabras clave de cada respuesta (una por fila)
#   respuestas_relacionadas  "temas relacionados": botones de sugerencia y
#                            contexto de la conversacion
#   sinonimos                palabras que significan lo mismo ("clave" = "contrasena")
#   consultas_asistente      cada pregunta que recibio y que hizo con ella:
#                            de aqui aprende el admin (lo que no entendio)
#   tiquetes                 + asistente_activo, asistente_fallos, asistente_desde,
#                              asistente_ultima_respuesta (de que se esta hablando)
#   mensajes_tiquete         + automatico, + opciones (botones de respuesta rapida)
#
# El CONOCIMIENTO inicial (respuestas, palabras, sinonimos) no esta aqui: lo
# carga el backend al arrancar desde app/servicios/conocimiento.py, y solo
# agrega lo que falta (nunca pisa lo que el admin haya editado).
#
# Es idempotente: se puede volver a correr. En una base que ya existia
# (despues de 08_mensajeria.sh) se aplica a mano con:
#   docker compose exec mysql bash /docker-entrypoint-initdb.d/09_asistente.sh
# =====================================================================
set -e

mysql --default-character-set=utf8mb4 -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<'EOSQL'
-- MySQL no tiene "ADD COLUMN IF NOT EXISTS": este procedimiento temporal
-- ejecuta un cambio solo si la columna (o restriccion) aun no existe.
DROP PROCEDURE IF EXISTS tmp_si_falta;
DELIMITER $$
CREATE PROCEDURE tmp_si_falta(IN p_tabla VARCHAR(64), IN p_nombre VARCHAR(64), IN p_sql TEXT)
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = DATABASE() AND table_name = p_tabla AND column_name = p_nombre)
       AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                       WHERE table_schema = DATABASE() AND table_name = p_tabla AND constraint_name = p_nombre) THEN
        SET @sql = p_sql;
        PREPARE paso FROM @sql;
        EXECUTE paso;
        DEALLOCATE PREPARE paso;
    END IF;
END$$
DELIMITER ;

-- ---------------------------------------------------------------------
-- Lo que sabe responder. El admin las crea, edita y DESACTIVA (nunca se
-- borran), igual que las reglas antifraude.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS respuestas_automaticas (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    titulo          VARCHAR(80)   NOT NULL,          -- para reconocerla en la Intranet
    respuesta       VARCHAR(1000) NOT NULL,          -- puede usar {RETIRO_MAXIMO} y otras claves de configuracion
    prioridad       TINYINT UNSIGNED NOT NULL DEFAULT 5,  -- si coinciden varias, gana la mayor
    activa          BOOLEAN NOT NULL DEFAULT TRUE,
    usos            INT UNSIGNED NOT NULL DEFAULT 0,
    creada_en       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    actualizada_en  DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_resp_prioridad CHECK (prioridad BETWEEN 1 AND 10)
) ENGINE=InnoDB;

-- Identificador estable de las respuestas que trae el banco (para cargar
-- solo las que falten); las que crea el admin no lo necesitan.
CALL tmp_si_falta('respuestas_automaticas', 'clave',
    'ALTER TABLE respuestas_automaticas ADD COLUMN clave VARCHAR(40) NULL UNIQUE AFTER id');
-- Como aparece en un boton de sugerencia: "¿Como retiro sin tarjeta?"
CALL tmp_si_falta('respuestas_automaticas', 'pregunta',
    'ALTER TABLE respuestas_automaticas ADD COLUMN pregunta VARCHAR(120) NULL AFTER titulo');
-- Si ademas consulta los DATOS del cliente (solo lectura). Lista cerrada:
-- cada valor corresponde a una consulta fija del backend.
CALL tmp_si_falta('respuestas_automaticas', 'accion',
    'ALTER TABLE respuestas_automaticas ADD COLUMN accion ENUM(''envios'',''cuentas'',''saldo'',''codigos_retiro'',''llaves'',''seguridad'') NULL AFTER respuesta');
-- "¿Te sirvio?": votos de los clientes
CALL tmp_si_falta('respuestas_automaticas', 'util_si',
    'ALTER TABLE respuestas_automaticas ADD COLUMN util_si INT UNSIGNED NOT NULL DEFAULT 0 AFTER usos');
CALL tmp_si_falta('respuestas_automaticas', 'util_no',
    'ALTER TABLE respuestas_automaticas ADD COLUMN util_no INT UNSIGNED NOT NULL DEFAULT 0 AFTER util_si');

-- Una fila por palabra clave (en minusculas y sin tildes: "contrasena").
-- Puede ser una frase corta: "no me llego".
CREATE TABLE IF NOT EXISTS palabras_respuesta (
    respuesta_id  BIGINT UNSIGNED NOT NULL,
    palabra       VARCHAR(40) NOT NULL,
    PRIMARY KEY (respuesta_id, palabra),
    CONSTRAINT fk_palabra_respuesta FOREIGN KEY (respuesta_id) REFERENCES respuestas_automaticas(id),
    INDEX idx_palabra (palabra)
) ENGINE=InnoDB;

-- Temas relacionados (relacion muchos a muchos de la tabla consigo misma)
CREATE TABLE IF NOT EXISTS respuestas_relacionadas (
    respuesta_id    BIGINT UNSIGNED NOT NULL,
    relacionada_id  BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (respuesta_id, relacionada_id),
    CONSTRAINT fk_rel_respuesta   FOREIGN KEY (respuesta_id)   REFERENCES respuestas_automaticas(id),
    CONSTRAINT fk_rel_relacionada FOREIGN KEY (relacionada_id) REFERENCES respuestas_automaticas(id),
    CONSTRAINT ck_rel_distinta CHECK (respuesta_id <> relacionada_id)
) ENGINE=InnoDB;

-- Sinonimos: antes de comparar, cada palabra se cambia por su equivalente
CREATE TABLE IF NOT EXISTS sinonimos (
    palabra   VARCHAR(40) NOT NULL PRIMARY KEY,   -- "clave"
    equivale  VARCHAR(40) NOT NULL,               -- "contrasena"
    CONSTRAINT ck_sinonimo_distinto CHECK (palabra <> equivale)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Tiquetes y mensajes
-- ---------------------------------------------------------------------
CALL tmp_si_falta('tiquetes', 'asistente_activo',
    'ALTER TABLE tiquetes ADD COLUMN asistente_activo BOOLEAN NOT NULL DEFAULT FALSE AFTER calificacion');
CALL tmp_si_falta('tiquetes', 'asistente_fallos',
    'ALTER TABLE tiquetes ADD COLUMN asistente_fallos TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER asistente_activo');
-- NULL = nunca se ha activado. La activacion automatica solo ocurre una vez.
CALL tmp_si_falta('tiquetes', 'asistente_desde',
    'ALTER TABLE tiquetes ADD COLUMN asistente_desde DATETIME(6) NULL AFTER asistente_fallos');
-- De que se esta hablando: la ultima respuesta que dio (contexto)
CALL tmp_si_falta('tiquetes', 'asistente_ultima_respuesta',
    'ALTER TABLE tiquetes ADD COLUMN asistente_ultima_respuesta BIGINT UNSIGNED NULL AFTER asistente_desde');
CALL tmp_si_falta('tiquetes', 'fk_tiq_ultima_resp',
    'ALTER TABLE tiquetes ADD CONSTRAINT fk_tiq_ultima_resp FOREIGN KEY (asistente_ultima_respuesta) REFERENCES respuestas_automaticas(id)');

-- Mensajes del asistente: sin autor (no los escribe ninguna persona)
CALL tmp_si_falta('mensajes_tiquete', 'automatico',
    'ALTER TABLE mensajes_tiquete ADD COLUMN automatico BOOLEAN NOT NULL DEFAULT FALSE AFTER autor_id');
ALTER TABLE mensajes_tiquete MODIFY autor_id BIGINT UNSIGNED NULL;
CALL tmp_si_falta('mensajes_tiquete', 'ck_msj_autor',
    'ALTER TABLE mensajes_tiquete ADD CONSTRAINT ck_msj_autor CHECK ((automatico AND autor_id IS NULL) OR (NOT automatico AND autor_id IS NOT NULL))');
-- Botones de respuesta rapida que acompanan un mensaje del asistente
CALL tmp_si_falta('mensajes_tiquete', 'opciones',
    'ALTER TABLE mensajes_tiquete ADD COLUMN opciones JSON NULL AFTER texto');

-- ---------------------------------------------------------------------
-- Registro de cada pregunta: el admin revisa las que no entendio y se las
-- "ensena" con un clic (las convierte en palabras clave de una respuesta).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consultas_asistente (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tiquete_id    BIGINT UNSIGNED NOT NULL,
    texto         VARCHAR(1000) NOT NULL,
    resultado     ENUM('respondio','no_entendio','derivo') NOT NULL,
    respuesta_id  BIGINT UNSIGNED NULL,           -- la que uso, si respondio
    revisada      BOOLEAN NOT NULL DEFAULT FALSE, -- el admin ya la atendio
    creada_en     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_cons_tiquete   FOREIGN KEY (tiquete_id)   REFERENCES tiquetes(id),
    CONSTRAINT fk_cons_respuesta FOREIGN KEY (respuesta_id) REFERENCES respuestas_automaticas(id),
    INDEX idx_cons_pendientes (resultado, revisada, creada_en)
) ENGINE=InnoDB;

DROP PROCEDURE tmp_si_falta;

-- Interruptor: activar el asistente solo si nadie atiende un tiquete nuevo
INSERT IGNORE INTO configuracion (clave, valor, descripcion) VALUES
('ASISTENTE_AUTOMATICO', '0', 'Activar el asistente en tiquetes nuevos que nadie atiende'),
('MINUTOS_ASISTENTE',    '5', 'Minutos de espera antes de que el asistente tome un tiquete nuevo'),
('CONOCIMIENTO_VERSION', '0', 'Version del conocimiento inicial ya cargada por el backend (no editar)');

-- Bases creadas con la primera version de este script: sus respuestas
-- iniciales no tenian "clave". Se les pone para no duplicarlas.
UPDATE respuestas_automaticas SET clave = CASE titulo
    WHEN 'Registrar una llave'        THEN 'llaves'
    WHEN 'Transferencia en revision'  THEN 'envio_revision'
    WHEN 'Retiro sin tarjeta'         THEN 'retiro'
    WHEN 'Usuario bloqueado'          THEN 'usuario_bloqueado'
    WHEN 'Olvide mi contrasena'       THEN 'contrasena'
    WHEN 'Verificacion en dos pasos'  THEN 'dos_pasos'
    WHEN 'Cuenta congelada'           THEN 'cuenta_congelada'
    WHEN 'Abrir otra cuenta'          THEN 'abrir_cuenta'
    WHEN 'Saludo'                     THEN 'saludo'
    WHEN 'Agradecimiento'             THEN 'gracias'
END
WHERE clave IS NULL AND titulo IN ('Registrar una llave','Transferencia en revision','Retiro sin tarjeta',
      'Usuario bloqueado','Olvide mi contrasena','Verificacion en dos pasos','Cuenta congelada',
      'Abrir otra cuenta','Saludo','Agradecimiento');
EOSQL

# Permisos (aqui SI se expanden las variables del .env, por eso va aparte)
mysql --default-character-set=utf8mb4 -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<EOSQL
GRANT UPDATE (estado, asesor_id, calificacion, visto_cliente_id, visto_asesor_id,
              actualizado_en, cerrado_en, cerrado_por,
              asistente_activo, asistente_fallos, asistente_desde, asistente_ultima_respuesta)
      ON ${MYSQL_DATABASE}.tiquetes TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.respuestas_automaticas TO '${APP_DB_USER}'@'%';
-- Se pueden editar y desactivar, nunca borrar
GRANT UPDATE (titulo, pregunta, respuesta, accion, prioridad, activa, usos, util_si, util_no)
      ON ${MYSQL_DATABASE}.respuestas_automaticas TO '${APP_DB_USER}'@'%';
-- Palabras, relacionadas y sinonimos si se reemplazan (son configuracion, no historia)
GRANT SELECT, INSERT, DELETE ON ${MYSQL_DATABASE}.palabras_respuesta      TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, DELETE ON ${MYSQL_DATABASE}.respuestas_relacionadas TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, DELETE ON ${MYSQL_DATABASE}.sinonimos               TO '${APP_DB_USER}'@'%';
-- Consultas: se registran y el admin solo puede marcarlas como revisadas
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.consultas_asistente TO '${APP_DB_USER}'@'%';
GRANT UPDATE (revisada) ON ${MYSQL_DATABASE}.consultas_asistente TO '${APP_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.respuestas_automaticas TO '${REPORT_DB_USER}'@'%';
FLUSH PRIVILEGES;
EOSQL

echo ">> Asistente automatico listo"
