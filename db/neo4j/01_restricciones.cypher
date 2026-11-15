// =====================================================================
// 01_restricciones.cypher  -  Modelo del grafo antifraude
// Ejecutar una vez (ver GUIA.md, paso 6).
//
// Modelo:
//   (:Cliente)-[:TITULAR_DE]->(:Cuenta)
//   (:Cliente)-[:USA]->(:Dispositivo)
//   (:Cliente)-[:CONECTA_DESDE]->(:IP)
//   (:Cuenta)-[:TRANSFIERE {tx_id, monto, fecha, estado}]->(:Cuenta)
//
// Los ids son los mismos de MySQL, asi se cruzan ambos mundos.
// =====================================================================

CREATE CONSTRAINT cliente_id IF NOT EXISTS
FOR (c:Cliente) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT cuenta_id IF NOT EXISTS
FOR (c:Cuenta) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT dispositivo_huella IF NOT EXISTS
FOR (d:Dispositivo) REQUIRE d.huella IS UNIQUE;

CREATE CONSTRAINT ip_direccion IF NOT EXISTS
FOR (i:IP) REQUIRE i.direccion IS UNIQUE;

// Indice para buscar cuentas congeladas rapido (regla CERCANIA_FRAUDE)
CREATE INDEX cuenta_estado IF NOT EXISTS
FOR (c:Cuenta) ON (c.estado);

// Indice sobre la fecha de las transferencias (regla CUENTA_MULA, ultimas 24 h)
CREATE INDEX transfiere_fecha IF NOT EXISTS
FOR ()-[t:TRANSFIERE]-() ON (t.fecha);
