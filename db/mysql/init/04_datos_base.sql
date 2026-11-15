-- =====================================================================
-- 04_datos_base.sql  -  Reglas antifraude y configuracion inicial
-- Los usuarios (con contrasenas hasheadas) los crea el backend/simulador,
-- no este script, para no dejar hashes ni contrasenas en el repositorio.
-- =====================================================================

INSERT INTO reglas_fraude (codigo, descripcion, motor, peso, umbral) VALUES
-- Reglas simples (MySQL)
('MONTO_INUSUAL',        'Monto N veces mayor al promedio historico de la cuenta',            'mysql', 30, 3.00),
('VELOCIDAD',            'Mas de N transacciones salientes en 10 minutos',                    'mysql', 25, 5.00),
('HORARIO_NOCTURNO',     'Operacion entre las 00:00 y las N horas',                           'mysql', 10, 5.00),
('DISPOSITIVO_NUEVO',    'Primera operacion desde un dispositivo no confiable',               'mysql', 20, NULL),
('CUENTA_DESTINO_NUEVA', 'La cuenta destino tiene menos de N dias de creada',                 'mysql', 15, 2.00),
-- Patrones de grafo (Neo4j)
('DISPOSITIVO_COMPARTIDO','El dispositivo lo usan N o mas clientes distintos',                'neo4j', 35, 3.00),
('CICLO_DINERO',         'El dinero vuelve a la cuenta origen en N saltos o menos (A->B->C->A)','neo4j', 40, 4.00),
('CUENTA_MULA',          'La cuenta destino recibio de N o mas origenes distintos en 24 h',   'neo4j', 35, 5.00),
('CERCANIA_FRAUDE',      'La cuenta destino esta a N saltos o menos de una cuenta congelada', 'neo4j', 30, 2.00);

INSERT INTO configuracion (clave, valor, descripcion) VALUES
('UMBRAL_RETENER',  '40',     'Desde este puntaje la transaccion queda retenida para revision'),
('UMBRAL_BLOQUEAR', '70',     'Desde este puntaje la transaccion se bloquea'),
('MONTO_2FA',       '1000000','Transferencias desde este monto exigen codigo 2FA'),
('MAX_INTENTOS_LOGIN','5',    'Intentos fallidos antes de bloquear la cuenta de usuario'),
('MINUTOS_BLOQUEO_LOGIN','15','Minutos de bloqueo tras superar los intentos'),
('RETIRO_MAXIMO',   '2000000','Monto maximo de un codigo de retiro (COP)'),
('VIGENCIA_CODIGO_RETIRO','30','Minutos de validez de un codigo de retiro'),
('INTENTOS_CODIGO_RETIRO','3','Intentos fallidos antes de bloquear un codigo de retiro'),
('MAX_CUENTAS_CLIENTE','3',  'Cuentas maximas por cliente');
