#!/bin/bash
# =====================================================================
# 03_usuarios.sh  -  Usuarios de MySQL con PRIVILEGIOS MINIMOS
# Es .sh (y no .sql) para poder leer las contrasenas desde el .env
# =====================================================================
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<EOSQL
-- ---------------------------------------------------------------
-- Usuario de la APLICACION (el backend se conecta con este)
-- ---------------------------------------------------------------
CREATE USER IF NOT EXISTS '${APP_DB_USER}'@'%' IDENTIFIED BY '${APP_DB_PASSWORD}';

-- Usuarios: puede crearlos, pero solo puede ACTUALIZAR columnas de seguridad.
-- No puede cambiar el rol, el email ni la cedula de nadie (evita escalar privilegios).
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.usuarios TO '${APP_DB_USER}'@'%';
GRANT UPDATE (password_hash, intentos_fallidos, bloqueado_hasta, debe_cambiar_password,
              activo, totp_secreto_cifrado, totp_activo, totp_ultimo_paso)
      ON ${MYSQL_DATABASE}.usuarios TO '${APP_DB_USER}'@'%';

-- Dispositivos, sesiones, llaves y codigos de retiro: leer, crear y actualizar (nunca borrar)
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.dispositivos   TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.sesiones       TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.avisos_login   TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.llaves         TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.codigos_retiro TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.alertas_fraude TO '${APP_DB_USER}'@'%';
GRANT SELECT, INSERT         ON ${MYSQL_DATABASE}.eventos_login TO '${APP_DB_USER}'@'%';

-- Cuentas: privilegios POR COLUMNA.
-- Puede crear cuentas (sin elegir el saldo) y cambiar su estado,
-- pero NO puede tocar el saldo directamente.
GRANT SELECT                          ON ${MYSQL_DATABASE}.cuentas TO '${APP_DB_USER}'@'%';
GRANT INSERT (numero, usuario_id, tipo) ON ${MYSQL_DATABASE}.cuentas TO '${APP_DB_USER}'@'%';
GRANT UPDATE (estado)                 ON ${MYSQL_DATABASE}.cuentas TO '${APP_DB_USER}'@'%';

-- Transacciones: solo lectura. Se crean exclusivamente con los procedimientos.
GRANT SELECT ON ${MYSQL_DATABASE}.transacciones TO '${APP_DB_USER}'@'%';

-- Auditoria: solo insertar y leer (los triggers impiden UPDATE/DELETE igualmente)
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.auditoria TO '${APP_DB_USER}'@'%';

-- Reglas y configuracion: el admin puede ajustar pesos y umbrales
GRANT SELECT, UPDATE ON ${MYSQL_DATABASE}.reglas_fraude TO '${APP_DB_USER}'@'%';
GRANT SELECT, UPDATE ON ${MYSQL_DATABASE}.configuracion TO '${APP_DB_USER}'@'%';

-- Vistas, funciones y procedimientos
GRANT SELECT ON ${MYSQL_DATABASE}.v_alertas_pendientes TO '${APP_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.v_resumen_cuentas    TO '${APP_DB_USER}'@'%';
# EXECUTE procedimiento por procedimiento (no "ON banco.*"): asi la app
# NO puede ejecutar sp_cargar_historico, que es exclusivo del simulador.
GRANT EXECUTE ON PROCEDURE ${MYSQL_DATABASE}.sp_transferir          TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON PROCEDURE ${MYSQL_DATABASE}.sp_depositar           TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON PROCEDURE ${MYSQL_DATABASE}.sp_retirar             TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON PROCEDURE ${MYSQL_DATABASE}.sp_resolver_retenida   TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON PROCEDURE ${MYSQL_DATABASE}.sp_verificar_auditoria TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON FUNCTION  ${MYSQL_DATABASE}.fn_tx_recientes        TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON FUNCTION  ${MYSQL_DATABASE}.fn_promedio_salidas    TO '${APP_DB_USER}'@'%';
GRANT EXECUTE ON FUNCTION  ${MYSQL_DATABASE}.fn_dias_antiguedad     TO '${APP_DB_USER}'@'%';

-- ---------------------------------------------------------------
-- Usuario de REPORTES (solo lectura, para Workbench / analistas)
-- No ve la tabla usuarios (datos personales y hashes de contrasena)
-- ---------------------------------------------------------------
CREATE USER IF NOT EXISTS '${REPORT_DB_USER}'@'%' IDENTIFIED BY '${REPORT_DB_PASSWORD}';
GRANT SELECT ON ${MYSQL_DATABASE}.v_alertas_pendientes TO '${REPORT_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.v_resumen_cuentas    TO '${REPORT_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.transacciones        TO '${REPORT_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.alertas_fraude       TO '${REPORT_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.reglas_fraude        TO '${REPORT_DB_USER}'@'%';
GRANT SELECT ON ${MYSQL_DATABASE}.auditoria            TO '${REPORT_DB_USER}'@'%';

FLUSH PRIVILEGES;
EOSQL

echo ">> Usuarios '${APP_DB_USER}' y '${REPORT_DB_USER}' creados con privilegios minimos"
