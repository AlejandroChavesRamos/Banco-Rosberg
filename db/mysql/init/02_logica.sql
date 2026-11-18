-- =====================================================================
-- 02_logica.sql  -  Triggers, funciones, procedimientos y vistas
-- =====================================================================

SET NAMES utf8mb4;

DELIMITER $$

-- =====================================================================
-- TRIGGERS DE AUDITORIA (hash encadenado + inmutabilidad)
-- =====================================================================
CREATE TRIGGER trg_auditoria_hash
BEFORE INSERT ON auditoria
FOR EACH ROW
BEGIN
    DECLARE v_prev CHAR(64);
    SET v_prev = (SELECT hash FROM auditoria ORDER BY id DESC LIMIT 1);
    IF v_prev IS NULL THEN
        SET v_prev = REPEAT('0', 64);                    -- bloque "genesis"
    END IF;
    IF NEW.fecha IS NULL THEN
        SET NEW.fecha = NOW(6);
    END IF;
    SET NEW.hash_anterior = v_prev;
    SET NEW.hash = SHA2(CONCAT_WS('|',
        v_prev,
        IFNULL(NEW.usuario_id, ''),
        NEW.accion,
        NEW.entidad,
        IFNULL(NEW.entidad_id, ''),
        IFNULL(CAST(NEW.detalle AS CHAR), ''),
        IFNULL(NEW.ip, ''),
        DATE_FORMAT(NEW.fecha, '%Y-%m-%d %H:%i:%s.%f')
    ), 256);
END$$

CREATE TRIGGER trg_auditoria_no_update
BEFORE UPDATE ON auditoria
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La auditoria es inmutable: UPDATE no permitido';
END$$

CREATE TRIGGER trg_auditoria_no_delete
BEFORE DELETE ON auditoria
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La auditoria es inmutable: DELETE no permitido';
END$$

-- =====================================================================
-- TRIGGERS DE TRANSACCIONES (no se borran ni se alteran sus datos base)
-- =====================================================================
CREATE TRIGGER trg_tx_no_delete
BEFORE DELETE ON transacciones
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Las transacciones no se pueden eliminar';
END$$

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

-- =====================================================================
-- FUNCIONES PARA LAS REGLAS ANTIFRAUDE QUE SE EVALUAN EN MYSQL
-- =====================================================================

-- Regla VELOCIDAD: cuantas transacciones salieron de la cuenta en los ultimos N minutos
CREATE FUNCTION fn_tx_recientes(p_cuenta BIGINT UNSIGNED, p_minutos INT)
RETURNS INT
READS SQL DATA
BEGIN
    RETURN (
        SELECT COUNT(*) FROM transacciones
        WHERE cuenta_origen_id = p_cuenta
          AND creada_en >= NOW(6) - INTERVAL p_minutos MINUTE
    );
END$$

-- Regla MONTO_INUSUAL: promedio historico de las transacciones aprobadas de la cuenta
CREATE FUNCTION fn_promedio_salidas(p_cuenta BIGINT UNSIGNED)
RETURNS DECIMAL(15,2)
READS SQL DATA
BEGIN
    RETURN (
        SELECT IFNULL(AVG(monto), 0) FROM transacciones
        WHERE cuenta_origen_id = p_cuenta AND estado = 'aprobada'
    );
END$$

-- Regla CUENTA_DESTINO_NUEVA: dias de antiguedad de una cuenta
CREATE FUNCTION fn_dias_antiguedad(p_cuenta BIGINT UNSIGNED)
RETURNS INT
READS SQL DATA
BEGIN
    RETURN (SELECT DATEDIFF(NOW(), creada_en) FROM cuentas WHERE id = p_cuenta);
END$$

-- =====================================================================
-- PROCEDIMIENTOS DE DINERO
-- Son la UNICA forma de mover saldo: el usuario de la app no tiene
-- permiso para hacer UPDATE sobre cuentas.saldo (ver 03_usuarios.sh).
-- Llamarlos con autocommit activo: manejan su propia transaccion.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Transferencia entre cuentas
-- p_estado lo decide el motor antifraude del backend:
--   'aprobada'  -> mueve el dinero
--   'retenida'  -> queda registrada, el dinero NO se mueve hasta que un analista apruebe
--   'bloqueada' -> queda registrada, no se mueve nada
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- Deposito (lo hace un cajero en ventanilla)
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_depositar(
    IN  p_cuenta  BIGINT UNSIGNED,
    IN  p_monto   DECIMAL(15,2),
    IN  p_cajero  BIGINT UNSIGNED,
    IN  p_idem    VARCHAR(64),
    OUT p_tx_id   BIGINT UNSIGNED
)
BEGIN
    DECLARE v_estado VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_tx_id = (SELECT id FROM transacciones WHERE clave_idempotencia = p_idem);
    IF p_tx_id IS NULL THEN
        IF p_monto IS NULL OR p_monto <= 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El monto debe ser mayor que cero';
        END IF;

        START TRANSACTION;
        SELECT estado INTO v_estado FROM cuentas WHERE id = p_cuenta FOR UPDATE;
        IF v_estado IS NULL OR v_estado <> 'activa' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cuenta no existe o no esta activa';
        END IF;

        UPDATE cuentas SET saldo = saldo + p_monto WHERE id = p_cuenta;
        INSERT INTO transacciones
            (tipo, cuenta_destino_id, monto, estado, ejecutada_por, clave_idempotencia)
        VALUES
            ('deposito', p_cuenta, p_monto, 'aprobada', p_cajero, p_idem);
        SET p_tx_id = LAST_INSERT_ID();
        COMMIT;
    END IF;
END$$

-- ---------------------------------------------------------------------
-- Retiro (cajero automatico o ventanilla). Tambien pasa por el motor antifraude.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_retirar(
    IN  p_cuenta      BIGINT UNSIGNED,
    IN  p_monto       DECIMAL(15,2),
    IN  p_estado      VARCHAR(20),
    IN  p_puntaje     TINYINT UNSIGNED,
    IN  p_ip          VARCHAR(45),
    IN  p_dispositivo BIGINT UNSIGNED,
    IN  p_ejecutor    BIGINT UNSIGNED,
    IN  p_idem        VARCHAR(64),
    OUT p_tx_id       BIGINT UNSIGNED
)
BEGIN
    DECLARE v_saldo DECIMAL(15,2);
    DECLARE v_estado VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_tx_id = (SELECT id FROM transacciones WHERE clave_idempotencia = p_idem);
    IF p_tx_id IS NULL THEN
        IF p_monto IS NULL OR p_monto <= 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El monto debe ser mayor que cero';
        END IF;
        IF p_estado NOT IN ('aprobada','retenida','bloqueada') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Estado inicial invalido';
        END IF;

        START TRANSACTION;
        SELECT saldo, estado INTO v_saldo, v_estado
        FROM cuentas WHERE id = p_cuenta FOR UPDATE;

        IF v_estado IS NULL OR v_estado <> 'activa' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cuenta no existe o no esta activa';
        END IF;

        IF p_estado = 'aprobada' THEN
            IF v_saldo < p_monto THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Saldo insuficiente';
            END IF;
            UPDATE cuentas SET saldo = saldo - p_monto WHERE id = p_cuenta;
        END IF;

        INSERT INTO transacciones
            (tipo, cuenta_origen_id, monto, estado, puntaje_riesgo,
             ip, dispositivo_id, ejecutada_por, clave_idempotencia)
        VALUES
            ('retiro', p_cuenta, p_monto, p_estado, p_puntaje,
             p_ip, p_dispositivo, p_ejecutor, p_idem);
        SET p_tx_id = LAST_INSERT_ID();
        COMMIT;
    END IF;
END$$

-- ---------------------------------------------------------------------
-- El analista aprueba o rechaza una transaccion retenida
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_resolver_retenida(
    IN p_tx_id     BIGINT UNSIGNED,
    IN p_analista  BIGINT UNSIGNED,
    IN p_aprobar   BOOLEAN
)
BEGIN
    DECLARE v_tipo VARCHAR(20);
    DECLARE v_estado VARCHAR(20);
    DECLARE v_origen, v_destino BIGINT UNSIGNED;
    DECLARE v_monto, v_saldo DECIMAL(15,2);
    DECLARE v_bloqueadas INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT tipo, estado, cuenta_origen_id, cuenta_destino_id, monto
      INTO v_tipo, v_estado, v_origen, v_destino, v_monto
    FROM transacciones WHERE id = p_tx_id FOR UPDATE;

    IF v_estado IS NULL OR v_estado <> 'retenida' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La transaccion no existe o no esta retenida';
    END IF;

    IF p_aprobar THEN
        SELECT COUNT(*) INTO v_bloqueadas FROM cuentas
        WHERE id IN (v_origen, IFNULL(v_destino, v_origen))
        FOR UPDATE;

        SELECT saldo INTO v_saldo FROM cuentas WHERE id = v_origen;
        IF v_saldo < v_monto THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Saldo insuficiente para aprobar';
        END IF;

        UPDATE cuentas SET saldo = saldo - v_monto WHERE id = v_origen;
        IF v_tipo = 'transferencia' THEN
            UPDATE cuentas SET saldo = saldo + v_monto WHERE id = v_destino;
        END IF;
        UPDATE transacciones
           SET estado = 'aprobada', resuelta_en = NOW(6), resuelta_por = p_analista
         WHERE id = p_tx_id;
    ELSE
        UPDATE transacciones
           SET estado = 'rechazada', resuelta_en = NOW(6), resuelta_por = p_analista
         WHERE id = p_tx_id;
    END IF;

    COMMIT;
END$$

-- ---------------------------------------------------------------------
-- Verifica la cadena de hashes de la auditoria.
-- Devuelve el primer id alterado, o NULL si todo esta integro.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_verificar_auditoria(OUT p_primer_id_alterado BIGINT UNSIGNED)
BEGIN
    DECLARE v_fin BOOLEAN DEFAULT FALSE;
    DECLARE v_id BIGINT UNSIGNED;
    DECLARE v_usuario BIGINT UNSIGNED;
    DECLARE v_accion VARCHAR(60);
    DECLARE v_entidad VARCHAR(40);
    DECLARE v_entidad_id BIGINT UNSIGNED;
    DECLARE v_detalle JSON;
    DECLARE v_ip VARCHAR(45);
    DECLARE v_fecha DATETIME(6);
    DECLARE v_hash_ant, v_hash, v_esperado CHAR(64);
    DECLARE v_prev CHAR(64) DEFAULT REPEAT('0', 64);

    DECLARE cur CURSOR FOR
        SELECT id, usuario_id, accion, entidad, entidad_id, detalle, ip, fecha, hash_anterior, hash
        FROM auditoria ORDER BY id;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_fin = TRUE;

    SET p_primer_id_alterado = NULL;
    OPEN cur;
    recorrer: LOOP
        FETCH cur INTO v_id, v_usuario, v_accion, v_entidad, v_entidad_id,
                       v_detalle, v_ip, v_fecha, v_hash_ant, v_hash;
        IF v_fin THEN LEAVE recorrer; END IF;

        SET v_esperado = SHA2(CONCAT_WS('|',
            v_prev,
            IFNULL(v_usuario, ''),
            v_accion,
            v_entidad,
            IFNULL(v_entidad_id, ''),
            IFNULL(CAST(v_detalle AS CHAR), ''),
            IFNULL(v_ip, ''),
            DATE_FORMAT(v_fecha, '%Y-%m-%d %H:%i:%s.%f')
        ), 256);

        IF v_hash_ant <> v_prev OR v_hash <> v_esperado THEN
            SET p_primer_id_alterado = v_id;
            LEAVE recorrer;
        END IF;
        SET v_prev = v_hash;
    END LOOP;
    CLOSE cur;
END$$

DELIMITER ;

-- =====================================================================
-- VISTAS
-- =====================================================================

-- Cola de trabajo del analista de fraude
CREATE VIEW v_alertas_pendientes AS
SELECT a.id            AS alerta_id,
       a.puntaje,
       a.motivos,
       a.estado,
       a.creada_en,
       c.numero        AS cuenta,
       u.nombre        AS titular,
       t.id            AS transaccion_id,
       t.tipo,
       t.monto,
       t.estado        AS estado_transaccion
FROM alertas_fraude a
JOIN cuentas c       ON c.id = a.cuenta_id
JOIN usuarios u      ON u.id = c.usuario_id
LEFT JOIN transacciones t ON t.id = a.transaccion_id
WHERE a.estado IN ('abierta','en_revision');

-- Resumen por cuenta (sin datos sensibles del titular)
CREATE VIEW v_resumen_cuentas AS
SELECT c.id,
       c.numero,
       c.tipo,
       c.estado,
       c.saldo,
       u.nombre AS titular,
       (SELECT COUNT(*) FROM transacciones t
         WHERE t.cuenta_origen_id = c.id OR t.cuenta_destino_id = c.id) AS total_movimientos,
       (SELECT COUNT(*) FROM alertas_fraude a WHERE a.cuenta_id = c.id) AS total_alertas
FROM cuentas c
JOIN usuarios u ON u.id = c.usuario_id;
