#!/bin/bash
# =====================================================================
# 10_metas.sh  -  Metas de ahorro ("bolsillos")
#
# El cliente aparta parte del saldo de una cuenta para algo con nombre
# (por ejemplo "Viaje"). El dinero NO sale de la cuenta: solo deja de estar
# disponible para transferir o retirar hasta que el cliente lo libere.
#   disponible = saldo de la cuenta - suma de lo apartado en sus metas activas
#
# Es .sh para dar permisos al usuario de la app, cuyo nombre viene del .env.
# Si la base ya existia, se aplica a mano con:
#   docker compose exec mysql bash /docker-entrypoint-initdb.d/10_metas.sh
# =====================================================================
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<EOSQL
CREATE TABLE IF NOT EXISTS metas_ahorro (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    usuario_id  BIGINT UNSIGNED NOT NULL,
    cuenta_id   BIGINT UNSIGNED NOT NULL,
    nombre      VARCHAR(60)    NOT NULL,
    objetivo    DECIMAL(15,2)  NOT NULL,
    apartado    DECIMAL(15,2)  NOT NULL DEFAULT 0,
    activa      BOOLEAN        NOT NULL DEFAULT TRUE,
    creada_en   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_meta_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_meta_cuenta  FOREIGN KEY (cuenta_id)  REFERENCES cuentas(id),
    CONSTRAINT ck_meta_objetivo CHECK (objetivo > 0),
    CONSTRAINT ck_meta_apartado CHECK (apartado >= 0),
    INDEX idx_metas_usuario (usuario_id, activa),
    INDEX idx_metas_cuenta (cuenta_id, activa)
) ENGINE=InnoDB;

-- La app crea metas y mueve lo apartado; nunca las borra (se desactivan)
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.metas_ahorro TO '${APP_DB_USER}'@'%';
GRANT UPDATE (nombre, apartado, activa) ON ${MYSQL_DATABASE}.metas_ahorro TO '${APP_DB_USER}'@'%';

-- Reportes: lectura
GRANT SELECT ON ${MYSQL_DATABASE}.metas_ahorro TO '${REPORT_DB_USER}'@'%';

FLUSH PRIVILEGES;
EOSQL

echo ">> Tabla 'metas_ahorro' lista"
