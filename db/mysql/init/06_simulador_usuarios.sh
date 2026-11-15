#!/bin/bash
# =====================================================================
# 06_simulador_usuarios.sh  -  Usuario de MySQL exclusivo del simulador
#
# Separacion de funciones: la app (banco_app) NO puede fechar movimientos
# en el pasado; el simulador (banco_simulador) SI puede, pero solo a traves
# de sp_cargar_historico, y no puede modificar saldos ni borrar nada.
# =====================================================================
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<EOSQL
CREATE USER IF NOT EXISTS '${SIM_DB_USER}'@'%' IDENTIFIED BY '${SIM_DB_PASSWORD}';

-- Lectura del banco
GRANT SELECT ON ${MYSQL_DATABASE}.* TO '${SIM_DB_USER}'@'%';

-- Crear clientes, dispositivos, inicios de sesion y llaves con fechas pasadas
GRANT INSERT ON ${MYSQL_DATABASE}.usuarios      TO '${SIM_DB_USER}'@'%';
GRANT INSERT ON ${MYSQL_DATABASE}.dispositivos  TO '${SIM_DB_USER}'@'%';
GRANT INSERT ON ${MYSQL_DATABASE}.eventos_login TO '${SIM_DB_USER}'@'%';
GRANT INSERT ON ${MYSQL_DATABASE}.llaves        TO '${SIM_DB_USER}'@'%';
GRANT INSERT ON ${MYSQL_DATABASE}.auditoria     TO '${SIM_DB_USER}'@'%';

-- Cuentas: puede crearlas con fecha pasada, pero nunca elegir el saldo
GRANT INSERT (numero, usuario_id, tipo, creada_en) ON ${MYSQL_DATABASE}.cuentas TO '${SIM_DB_USER}'@'%';

-- Unico procedimiento que puede ejecutar
GRANT EXECUTE ON PROCEDURE ${MYSQL_DATABASE}.sp_cargar_historico TO '${SIM_DB_USER}'@'%';

-- Esquema propio de la simulacion
GRANT ALL PRIVILEGES ON banco_sim.* TO '${SIM_DB_USER}'@'%';

FLUSH PRIVILEGES;
EOSQL

echo ">> Usuario '${SIM_DB_USER}' creado para el simulador"
