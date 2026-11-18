-- =====================================================================
-- Migracion: mensaje en las transferencias (estilo Nequi), para una base
-- que YA existe. En una instalacion nueva no hace falta: ya esta en init/.
--
-- Se aplica asi (en PowerShell, desde la carpeta del proyecto):
--   Get-Content db/mysql/migraciones/2026-11-17_mensaje_transferencias.sql | docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" banco'
--   docker compose exec mysql bash /docker-entrypoint-initdb.d/03_usuarios.sh   (vuelve a dar EXECUTE sobre sp_transferir)
--   docker compose exec mysql bash /docker-entrypoint-initdb.d/08_mensajeria.sh (tablas del chat)
--
-- Al borrar y recrear un procedimiento, MySQL borra tambien sus permisos:
-- por eso hay que volver a correr 03_usuarios.sh.
-- =====================================================================

-- Agregar la columna solo si no existe (MySQL no tiene ADD COLUMN IF NOT EXISTS)
SET @existe = (SELECT COUNT(*) FROM information_schema.columns
               WHERE table_schema = DATABASE() AND table_name = 'transacciones' AND column_name = 'mensaje');
SET @sql = IF(@existe = 0,
              'ALTER TABLE transacciones ADD COLUMN mensaje VARCHAR(140) NULL AFTER clave_idempotencia',
              'SELECT ''la columna mensaje ya existia''');
PREPARE paso FROM @sql;
EXECUTE paso;
DEALLOCATE PREPARE paso;

DROP TRIGGER IF EXISTS trg_tx_campos_inmutables;
DROP PROCEDURE IF EXISTS sp_transferir;

DELIMITER $$
CREATE TRIGGER trg_tx_campos_inmutables
BEFORE UPDATE ON transacciones
FOR EACH ROW
BEGIN
    IF NEW.monto <> OLD.monto
       OR NOT (NEW.tipo <=> OLD.tipo)
       OR NOT (NEW.cuenta_origen_id  <=> OLD.cuenta_origen_id)
       OR NOT (NEW.cuenta_destino_id <=> OLD.cuenta_destino_id)
       OR NEW.creada_en <> OLD.creada_en
       OR NOT (NEW.mensaje <=> OLD.mensaje) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Monto, tipo, cuentas, fecha y mensaje de una transaccion son inmutables';
    END IF;
END$$

CREATE PROCEDURE sp_transferir(
    IN  p_origen      BIGINT UNSIGNED,
    IN  p_destino     BIGINT UNSIGNED,
    IN  p_monto       DECIMAL(15,2),
    IN  p_estado      VARCHAR(20),
    IN  p_puntaje     TINYINT UNSIGNED,
    IN  p_ip          VARCHAR(45),
    IN  p_dispositivo BIGINT UNSIGNED,
    IN  p_idem        VARCHAR(64),
    IN  p_mensaje     VARCHAR(140),
    OUT p_tx_id       BIGINT UNSIGNED
)
BEGIN
    DECLARE v_saldo DECIMAL(15,2);
    DECLARE v_estado_origen, v_estado_destino VARCHAR(20);
    DECLARE v_bloqueadas INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    -- Idempotencia: si ya existe una transaccion con esa clave, devolverla
    SET p_tx_id = (SELECT id FROM transacciones WHERE clave_idempotencia = p_idem);
    IF p_tx_id IS NULL THEN

        IF p_monto IS NULL OR p_monto <= 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El monto debe ser mayor que cero';
        END IF;
        IF p_origen = p_destino THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cuenta origen y destino no pueden ser la misma';
        END IF;
        IF p_estado NOT IN ('aprobada','retenida','bloqueada') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Estado inicial invalido';
        END IF;

        START TRANSACTION;

        -- Bloquear AMBAS filas (InnoDB las recorre en orden de id, lo que
        -- evita deadlocks) para impedir condiciones de carrera
        -- como dos retiros simultaneos sobre el mismo saldo
        SELECT COUNT(*) INTO v_bloqueadas FROM cuentas
        WHERE id IN (p_origen, p_destino)
        FOR UPDATE;

        SELECT saldo, estado INTO v_saldo, v_estado_origen
        FROM cuentas WHERE id = p_origen;
        SELECT estado INTO v_estado_destino
        FROM cuentas WHERE id = p_destino;

        IF v_estado_origen IS NULL OR v_estado_destino IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cuenta inexistente';
        END IF;
        IF v_estado_origen <> 'activa' OR v_estado_destino <> 'activa' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Alguna de las cuentas no esta activa';
        END IF;

        IF p_estado = 'aprobada' THEN
            IF v_saldo < p_monto THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Saldo insuficiente';
            END IF;
            UPDATE cuentas SET saldo = saldo - p_monto WHERE id = p_origen;
            UPDATE cuentas SET saldo = saldo + p_monto WHERE id = p_destino;
        END IF;

        INSERT INTO transacciones
            (tipo, cuenta_origen_id, cuenta_destino_id, monto, estado,
             puntaje_riesgo, ip, dispositivo_id, clave_idempotencia, mensaje)
        VALUES
            ('transferencia', p_origen, p_destino, p_monto, p_estado,
             p_puntaje, p_ip, p_dispositivo, p_idem, NULLIF(TRIM(p_mensaje), ''));
        SET p_tx_id = LAST_INSERT_ID();

        COMMIT;
    END IF;
END$$
DELIMITER ;
