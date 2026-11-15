-- =====================================================================
-- 05_simulador.sql  -  Soporte para el simulador de datos (Fase 3)
--
-- 1) Esquema aparte "banco_sim": la "hoja de respuestas" de la simulacion
--    (perfiles, contactos y casos de fraude plantados). Un banco real no
--    sabe esto, por eso NO se mezcla con las tablas del banco.
-- 2) sp_cargar_historico: unico camino para crear movimientos con fecha
--    pasada. Solo lo puede ejecutar el usuario banco_simulador.
-- =====================================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS banco_sim CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Perfil de comportamiento de cada cliente simulado
CREATE TABLE IF NOT EXISTS banco_sim.perfiles (
    usuario_id   BIGINT UNSIGNED PRIMARY KEY,
    cuenta_id    BIGINT UNSIGNED NOT NULL,
    email        VARCHAR(120) NOT NULL,
    cedula       VARCHAR(10)  NOT NULL,             -- dato ficticio, solo para canjear retiros en la demo
    perfil       ENUM('estudiante','asalariado','comerciante','fraude') NOT NULL,
    comunidad    SMALLINT UNSIGNED NOT NULL,        -- "barrio" o grupo social
    dispositivo  VARCHAR(64)  NOT NULL,             -- identificador que envia como X-Dispositivo
    ip           VARCHAR(45)  NOT NULL,
    INDEX idx_perfiles_perfil (perfil)
) ENGINE=InnoDB;

-- Con quien suele transferir cada cliente (familia, amigos, arrendador...)
CREATE TABLE IF NOT EXISTS banco_sim.contactos (
    cuenta_id          BIGINT UNSIGNED NOT NULL,
    contacto_cuenta_id BIGINT UNSIGNED NOT NULL,
    relacion           ENUM('comunidad','externo','familia','arrendador') NOT NULL,
    PRIMARY KEY (cuenta_id, contacto_cuenta_id)
) ENGINE=InnoDB;

-- Casos de fraude plantados (la "verdad" contra la que se mide el motor)
CREATE TABLE IF NOT EXISTS banco_sim.casos (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tipo        ENUM('dispositivo_compartido','ciclo_lavado','cuenta_mula','robo_cuenta') NOT NULL,
    origen      ENUM('historico','en_vivo') NOT NULL,
    descripcion VARCHAR(255) NOT NULL,
    creado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS banco_sim.casos_cuentas (
    caso_id   BIGINT UNSIGNED NOT NULL,
    cuenta_id BIGINT UNSIGNED NOT NULL,
    rol       ENUM('fraudulenta','victima') NOT NULL,
    PRIMARY KEY (caso_id, cuenta_id, rol),
    CONSTRAINT fk_cc_caso FOREIGN KEY (caso_id) REFERENCES banco_sim.casos(id)
) ENGINE=InnoDB;

-- Registro de cada ejecucion del simulador
CREATE TABLE IF NOT EXISTS banco_sim.ejecuciones (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tipo        VARCHAR(20) NOT NULL,
    parametros  JSON        NULL,
    inicio      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fin         DATETIME    NULL,
    resumen     JSON        NULL
) ENGINE=InnoDB;

DROP PROCEDURE IF EXISTS sp_cargar_historico;

DELIMITER $$

-- ---------------------------------------------------------------------
-- Carga un movimiento HISTORICO (fecha pasada), moviendo el saldo igual
-- que los procedimientos normales. Si no hay saldo, no hace nada y
-- devuelve NULL (en lugar de error) para que la carga masiva continue.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_cargar_historico(
    IN  p_tipo        VARCHAR(20),
    IN  p_origen      BIGINT UNSIGNED,
    IN  p_destino     BIGINT UNSIGNED,
    IN  p_monto       DECIMAL(15,2),
    IN  p_fecha       DATETIME(6),
    IN  p_ip          VARCHAR(45),
    IN  p_dispositivo BIGINT UNSIGNED,
    OUT p_tx_id       BIGINT UNSIGNED
)
proc: BEGIN
    DECLARE v_saldo DECIMAL(15,2);
    DECLARE v_bloqueadas INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_tx_id = NULL;

    IF p_fecha IS NULL OR p_fecha >= NOW(6) OR p_fecha < NOW(6) - INTERVAL 400 DAY THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo se pueden cargar movimientos del ultimo ano (fechas pasadas)';
    END IF;
    IF p_monto IS NULL OR p_monto <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El monto debe ser mayor que cero';
    END IF;
    IF NOT (
           (p_tipo = 'deposito'      AND p_origen IS NULL     AND p_destino IS NOT NULL)
        OR (p_tipo = 'retiro'        AND p_origen IS NOT NULL AND p_destino IS NULL)
        OR (p_tipo = 'transferencia' AND p_origen IS NOT NULL AND p_destino IS NOT NULL AND p_origen <> p_destino)
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Combinacion de tipo y cuentas invalida';
    END IF;

    START TRANSACTION;

    SELECT COUNT(*) INTO v_bloqueadas FROM cuentas
    WHERE id IN (IFNULL(p_origen, 0), IFNULL(p_destino, 0))
    FOR UPDATE;

    IF p_origen IS NOT NULL THEN
        SELECT saldo INTO v_saldo FROM cuentas WHERE id = p_origen;
        IF v_saldo IS NULL OR v_saldo < p_monto THEN
            ROLLBACK;
            LEAVE proc;
        END IF;
        UPDATE cuentas SET saldo = saldo - p_monto WHERE id = p_origen;
    END IF;

    IF p_destino IS NOT NULL THEN
        UPDATE cuentas SET saldo = saldo + p_monto WHERE id = p_destino;
    END IF;

    INSERT INTO transacciones
        (tipo, cuenta_origen_id, cuenta_destino_id, monto, estado, puntaje_riesgo,
         ip, dispositivo_id, creada_en)
    VALUES
        (p_tipo, p_origen, p_destino, p_monto, 'aprobada', 0,
         p_ip, p_dispositivo, p_fecha);
    SET p_tx_id = LAST_INSERT_ID();

    COMMIT;
END$$

DELIMITER ;
