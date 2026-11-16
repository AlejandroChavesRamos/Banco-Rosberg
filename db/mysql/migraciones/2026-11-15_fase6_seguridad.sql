-- =====================================================================
-- Migracion Fase 6 (seguridad) para una base que YA existe.
--
-- Los scripts de db/mysql/init/ solo corren cuando la base esta vacia.
-- Para no borrar los datos, estos cambios se aplicaron a mano asi:
--   docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" banco' < db/mysql/migraciones/2026-11-15_fase6_seguridad.sql
--   docker compose exec mysql bash /docker-entrypoint-initdb.d/03_usuarios.sh   (vuelve a dar los permisos)
-- En una instalacion nueva no hace falta: ya esta incluido en init/.
-- =====================================================================

ALTER TABLE usuarios
    ADD COLUMN totp_ultimo_paso BIGINT NULL AFTER totp_activo;

CREATE TABLE IF NOT EXISTS avisos_login (
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

INSERT IGNORE INTO configuracion (clave, valor, descripcion) VALUES
('2FA_EMPLEADOS',      '0', 'Exigir verificacion en dos pasos a todos los empleados'),
('2FA_CLIENTES',       '0', 'Permitir que los clientes activen la verificacion en dos pasos'),
('2FA_TRANSFERENCIAS', '0', 'Exigir el codigo 2FA en transferencias desde MONTO_2FA');
