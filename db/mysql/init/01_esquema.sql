-- =====================================================================
-- 01_esquema.sql  -  Tablas del banco simulado
-- MySQL es la FUENTE DE VERDAD: aqui vive el dinero.
-- =====================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- Usuarios del sistema (clientes y empleados)
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email              VARCHAR(120)  NOT NULL,
    password_hash      VARCHAR(255)  NOT NULL,          -- Argon2/bcrypt, generado en el backend
    rol                ENUM('cliente','cajero','analista','admin') NOT NULL DEFAULT 'cliente',
    nombre             VARCHAR(120)  NOT NULL,
    documento_cifrado  VARBINARY(512) NULL,             -- cifrado AES-GCM en el backend
    documento_hash     CHAR(64)      NULL,              -- "indice ciego" (HMAC) para buscar por cedula sin descifrar
    telefono_cifrado   VARBINARY(512) NULL,
    totp_secreto_cifrado VARBINARY(512) NULL,           -- secreto 2FA, tambien cifrado (Fase 6)
    totp_activo        BOOLEAN       NOT NULL DEFAULT FALSE,
    totp_ultimo_paso   BIGINT        NULL,              -- ultimo codigo 2FA usado: impide reutilizarlo
    intentos_fallidos  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    bloqueado_hasta    DATETIME      NULL,
    debe_cambiar_password BOOLEAN    NOT NULL DEFAULT FALSE,  -- clientes creados en ventanilla
    activo             BOOLEAN       NOT NULL DEFAULT TRUE,
    creado_en          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_usuarios_email UNIQUE (email),
    CONSTRAINT uq_usuarios_documento UNIQUE (documento_hash)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Sesiones (tokens de renovacion). Permite cerrar sesion y revocar tokens.
-- ---------------------------------------------------------------------
CREATE TABLE sesiones (
    id             CHAR(36)     PRIMARY KEY,             -- identificador (jti) del token de renovacion
    usuario_id     BIGINT UNSIGNED NOT NULL,
    dispositivo_id BIGINT UNSIGNED NULL,
    ip             VARCHAR(45)  NULL,
    creada_en      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_en      DATETIME     NOT NULL,
    revocada       BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_sesiones_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    INDEX idx_sesiones_usuario (usuario_id, revocada)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Cuentas bancarias
-- ---------------------------------------------------------------------
CREATE TABLE cuentas (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    numero      CHAR(12)      NOT NULL,
    usuario_id  BIGINT UNSIGNED NOT NULL,
    tipo        ENUM('ahorros','corriente') NOT NULL DEFAULT 'ahorros',
    saldo       DECIMAL(15,2) NOT NULL DEFAULT 0.00,     -- DECIMAL, nunca FLOAT
    estado      ENUM('activa','congelada','cerrada') NOT NULL DEFAULT 'activa',
    creada_en   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cuentas_numero UNIQUE (numero),
    CONSTRAINT fk_cuentas_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT ck_cuentas_saldo CHECK (saldo >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Dispositivos desde los que opera cada usuario (huella del navegador)
-- ---------------------------------------------------------------------
CREATE TABLE dispositivos (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id   BIGINT UNSIGNED NOT NULL,
    huella       CHAR(64)     NOT NULL,                  -- hash SHA-256 de la huella
    descripcion  VARCHAR(255) NULL,                      -- user agent resumido
    confiable    BOOLEAN      NOT NULL DEFAULT FALSE,
    primera_vez  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_vez   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dispositivo_usuario UNIQUE (usuario_id, huella),
    CONSTRAINT fk_dispositivos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    INDEX idx_dispositivos_huella (huella)               -- para buscar huellas compartidas
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Avisos de inicio de sesion sospechoso (dispositivo o IP nuevos).
-- El cliente responde "fui yo" o "no fui yo" desde su App.
-- ---------------------------------------------------------------------
CREATE TABLE avisos_login (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id     BIGINT UNSIGNED NOT NULL,
    dispositivo_id BIGINT UNSIGNED NULL,
    ip             VARCHAR(45)  NOT NULL,
    motivo         VARCHAR(255) NOT NULL,
    estado         ENUM('pendiente','reconocido','no_reconocido') NOT NULL DEFAULT 'pendiente',
    creado_en      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resuelto_en    DATETIME     NULL,
    CONSTRAINT fk_aviso_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_aviso_disp    FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id),
    INDEX idx_avisos_usuario (usuario_id, estado)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Intentos de inicio de sesion (exitosos y fallidos)
-- ---------------------------------------------------------------------
CREATE TABLE eventos_login (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id       BIGINT UNSIGNED NULL,
    email_intentado  VARCHAR(120) NOT NULL,
    ip               VARCHAR(45)  NOT NULL,              -- 45 = cabe IPv6
    dispositivo_id   BIGINT UNSIGNED NULL,
    exito            BOOLEAN      NOT NULL,
    fecha            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_login_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_login_dispositivo FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id),
    INDEX idx_login_email_fecha (email_intentado, fecha),
    INDEX idx_login_ip_fecha (ip, fecha)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Transacciones: depositos, retiros y transferencias
-- Solo se insertan a traves de procedimientos almacenados (ver 02_logica.sql)
-- ---------------------------------------------------------------------
CREATE TABLE transacciones (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tipo               ENUM('deposito','retiro','transferencia') NOT NULL,
    cuenta_origen_id   BIGINT UNSIGNED NULL,             -- NULL en depositos
    cuenta_destino_id  BIGINT UNSIGNED NULL,             -- NULL en retiros
    monto              DECIMAL(15,2) NOT NULL,
    estado             ENUM('aprobada','retenida','bloqueada','rechazada') NOT NULL,
    puntaje_riesgo     TINYINT UNSIGNED NOT NULL DEFAULT 0,
    ip                 VARCHAR(45)  NULL,
    dispositivo_id     BIGINT UNSIGNED NULL,
    ejecutada_por      BIGINT UNSIGNED NULL,             -- cajero, si fue en ventanilla
    clave_idempotencia VARCHAR(64)  NULL,                -- evita duplicados por doble clic
    creada_en          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    resuelta_en        DATETIME(6)  NULL,
    resuelta_por       BIGINT UNSIGNED NULL,             -- analista que la resolvio
    CONSTRAINT uq_tx_idempotencia UNIQUE (clave_idempotencia),
    CONSTRAINT fk_tx_origen   FOREIGN KEY (cuenta_origen_id)  REFERENCES cuentas(id),
    CONSTRAINT fk_tx_destino  FOREIGN KEY (cuenta_destino_id) REFERENCES cuentas(id),
    CONSTRAINT fk_tx_disp     FOREIGN KEY (dispositivo_id)    REFERENCES dispositivos(id),
    CONSTRAINT fk_tx_ejecutor FOREIGN KEY (ejecutada_por)     REFERENCES usuarios(id),
    CONSTRAINT fk_tx_resolvio FOREIGN KEY (resuelta_por)      REFERENCES usuarios(id),
    CONSTRAINT ck_tx_monto CHECK (monto > 0),
    CONSTRAINT ck_tx_puntaje CHECK (puntaje_riesgo <= 100),
    INDEX idx_tx_origen_fecha  (cuenta_origen_id, creada_en),
    INDEX idx_tx_destino_fecha (cuenta_destino_id, creada_en),
    INDEX idx_tx_estado (estado)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Llaves: alias para recibir transferencias (celular o correo), estilo Bre-B
-- Una llave ACTIVA es unica en todo el banco. Las desactivadas se conservan
-- como historial y no bloquean que alguien vuelva a registrar ese valor:
-- la columna generada vale 1 si esta activa y NULL si no, y en un indice
-- UNIQUE los NULL nunca chocan entre si.
-- ---------------------------------------------------------------------
CREATE TABLE llaves (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cuenta_id    BIGINT UNSIGNED NOT NULL,
    tipo         ENUM('celular','correo') NOT NULL,
    valor        VARCHAR(120) NOT NULL,
    activa       BOOLEAN      NOT NULL DEFAULT TRUE,
    activa_marca TINYINT      GENERATED ALWAYS AS (IF(activa, 1, NULL)) STORED,
    creada_en    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_llaves_cuenta FOREIGN KEY (cuenta_id) REFERENCES cuentas(id),
    CONSTRAINT uq_llave_activa UNIQUE (tipo, valor, activa_marca)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Codigos de retiro sin tarjeta: el cliente lo genera, el cajero lo canjea.
-- El codigo NUNCA se guarda en texto plano: solo su HMAC.
-- ---------------------------------------------------------------------
CREATE TABLE codigos_retiro (
    id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cuenta_id         BIGINT UNSIGNED NOT NULL,
    codigo_hash       CHAR(64)      NOT NULL,
    monto             DECIMAL(15,2) NOT NULL,
    puntaje_riesgo    TINYINT UNSIGNED NOT NULL DEFAULT 0,
    estado            ENUM('activo','usado','vencido','bloqueado','cancelado') NOT NULL DEFAULT 'activo',
    intentos_fallidos TINYINT UNSIGNED NOT NULL DEFAULT 0,
    creado_en         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_en         DATETIME      NOT NULL,
    usado_en          DATETIME      NULL,
    canjeado_por      BIGINT UNSIGNED NULL,
    transaccion_id    BIGINT UNSIGNED NULL,
    CONSTRAINT fk_codigo_cuenta  FOREIGN KEY (cuenta_id)      REFERENCES cuentas(id),
    CONSTRAINT fk_codigo_cajero  FOREIGN KEY (canjeado_por)   REFERENCES usuarios(id),
    CONSTRAINT fk_codigo_tx      FOREIGN KEY (transaccion_id) REFERENCES transacciones(id),
    CONSTRAINT ck_codigo_monto CHECK (monto > 0),
    INDEX idx_codigos_cuenta_estado (cuenta_id, estado)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Alertas generadas por el motor antifraude
-- ---------------------------------------------------------------------
CREATE TABLE alertas_fraude (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    transaccion_id BIGINT UNSIGNED NULL,
    cuenta_id      BIGINT UNSIGNED NOT NULL,
    puntaje        TINYINT UNSIGNED NOT NULL,
    motivos        JSON         NOT NULL,                -- ["VELOCIDAD","DISPOSITIVO_COMPARTIDO"]
    estado         ENUM('abierta','en_revision','confirmada','descartada') NOT NULL DEFAULT 'abierta',
    analista_id    BIGINT UNSIGNED NULL,
    nota           TEXT         NULL,
    creada_en      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resuelta_en    DATETIME     NULL,
    CONSTRAINT fk_alerta_tx       FOREIGN KEY (transaccion_id) REFERENCES transacciones(id),
    CONSTRAINT fk_alerta_cuenta   FOREIGN KEY (cuenta_id)      REFERENCES cuentas(id),
    CONSTRAINT fk_alerta_analista FOREIGN KEY (analista_id)    REFERENCES usuarios(id),
    INDEX idx_alertas_estado (estado, creada_en)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Reglas del motor antifraude (configurables por el administrador)
-- ---------------------------------------------------------------------
CREATE TABLE reglas_fraude (
    codigo       VARCHAR(40)   PRIMARY KEY,
    descripcion  VARCHAR(255)  NOT NULL,
    motor        ENUM('mysql','neo4j') NOT NULL,         -- donde se evalua
    peso         TINYINT UNSIGNED NOT NULL,              -- puntos que suma al puntaje
    umbral       DECIMAL(10,2) NULL,                     -- parametro de la regla
    activa       BOOLEAN       NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_regla_peso CHECK (peso <= 100)
) ENGINE=InnoDB;

CREATE TABLE configuracion (
    clave  VARCHAR(40)  PRIMARY KEY,
    valor  VARCHAR(100) NOT NULL,
    descripcion VARCHAR(255) NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Auditoria inmutable con hash encadenado (estilo blockchain simple)
-- Cada fila guarda el hash de la anterior: si alguien modifica una fila,
-- la cadena se rompe y sp_verificar_auditoria lo detecta.
-- ---------------------------------------------------------------------
CREATE TABLE auditoria (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id     BIGINT UNSIGNED NULL,
    accion         VARCHAR(60)  NOT NULL,                -- LOGIN, TRANSFERENCIA, CONGELAR_CUENTA...
    entidad        VARCHAR(40)  NOT NULL,
    entidad_id     BIGINT UNSIGNED NULL,
    detalle        JSON         NULL,
    ip             VARCHAR(45)  NULL,
    fecha          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    hash_anterior  CHAR(64)     NOT NULL,
    hash           CHAR(64)     NOT NULL,
    INDEX idx_auditoria_usuario (usuario_id, fecha),
    INDEX idx_auditoria_entidad (entidad, entidad_id)
) ENGINE=InnoDB;
