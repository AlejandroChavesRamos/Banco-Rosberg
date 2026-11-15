"""Mide que tan bien detecta el motor antifraude.

Compara las ALERTAS que genero el banco (tabla banco.alertas_fraude) con la
HOJA DE RESPUESTAS del simulador (banco_sim). Solo el simulador puede hacerlo:
la app del banco no tiene acceso a banco_sim, igual que un banco real no sabe
de antemano quien es un estafador.

Metricas:
  - Cobertura de casos: de los casos de fraude reales, cuantos generaron al menos una alerta.
  - Cobertura de cuentas fraudulentas: de las cuentas fraudulentas, cuantas fueron alertadas.
  - Precision: de las cuentas alertadas, cuantas eran parte de un caso real.
    Las que no, son FALSAS ALARMAS (clientes inocentes molestados).
"""
import json
from collections import defaultdict

from ..db.mysql import conectar, consultar


def _codigos(motivos_json) -> set[str]:
    motivos = json.loads(motivos_json) if isinstance(motivos_json, str) else motivos_json
    return {m["codigo"] if isinstance(m, dict) else m for m in motivos}


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def evaluar() -> None:
    conn = conectar()
    try:
        alertas = consultar(conn, "SELECT cuenta_id, motivos, estado FROM alertas_fraude")
        alertadas: dict[int, set[str]] = defaultdict(set)
        pendientes: set[int] = set()   # cuentas con alguna alerta que el analista NO ha descartado
        for a in alertas:
            alertadas[a["cuenta_id"]] |= _codigos(a["motivos"])
            if a["estado"] != "descartada":
                pendientes.add(a["cuenta_id"])

        casos = consultar(conn, "SELECT id, tipo, origen FROM banco_sim.casos ORDER BY id")
        cuentas_caso = consultar(conn, "SELECT caso_id, cuenta_id, rol FROM banco_sim.casos_cuentas")
        por_caso: dict[int, list[dict]] = defaultdict(list)
        for f in cuentas_caso:
            por_caso[f["caso_id"]].append(f)
        en_algun_caso = {f["cuenta_id"] for f in cuentas_caso}
        fraudulentas = {f["cuenta_id"] for f in cuentas_caso if f["rol"] == "fraudulenta"}

        print("================ EVALUACION DEL MOTOR ANTIFRAUDE ================\n")
        print(f"{'Caso':<5}{'Origen':<11}{'Tipo':<24}{'Detectado':<11}Reglas que lo detectaron")
        resumen: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for caso in casos:
            codigos = set()
            for c in por_caso[caso["id"]]:
                codigos |= alertadas.get(c["cuenta_id"], set())
            detectado = bool(codigos)
            resumen[caso["tipo"]][1] += 1
            resumen[caso["tipo"]][0] += detectado
            print(f"#{caso['id']:<4}{caso['origen']:<11}{caso['tipo']:<24}{'SI' if detectado else 'NO':<11}"
                  f"{', '.join(sorted(codigos)) or '-'}")

        print("\nCobertura por tipo de fraude:")
        total_det = total = 0
        for tipo, (det, tot) in sorted(resumen.items()):
            print(f"   {tipo:<24} {_pct(det, tot)}")
            total_det += det
            total += tot

        verdaderas = [c for c in alertadas if c in en_algun_caso]
        falsas = [c for c in alertadas if c not in en_algun_caso]
        fraud_alertadas = [c for c in fraudulentas if c in alertadas]

        print("\n------------------------------ RESUMEN ------------------------------")
        print(f"Casos detectados (cobertura):            {_pct(total_det, total)}")
        print(f"Cuentas fraudulentas alertadas:          {_pct(len(fraud_alertadas), len(fraudulentas))}")
        print(f"Precision (alertas que eran fraude real): {_pct(len(verdaderas), len(alertadas))}")
        ya_descartadas = [c for c in falsas if c not in pendientes]
        print(f"Falsas alarmas (inocentes alertados):    {len(falsas)}"
              + (f"  ({len(ya_descartadas)} ya descartada(s) por el analista)" if ya_descartadas else ""))
        if falsas:
            marcadores = ", ".join(["%s"] * len(falsas))
            for f in consultar(conn, f"SELECT c.id, c.numero, u.nombre, p.perfil FROM cuentas c "
                                     f"JOIN usuarios u ON u.id = c.usuario_id "
                                     f"LEFT JOIN banco_sim.perfiles p ON p.cuenta_id = c.id "
                                     f"WHERE c.id IN ({marcadores})", tuple(falsas)):
                estado = "descartada" if f["id"] not in pendientes else "PENDIENTE"
                print(f"   - {f['numero']} {f['nombre'][:30]:<30} ({f['perfil'] or 'usuario real'}) "
                      f"por {', '.join(sorted(alertadas[f['id']]))}  [{estado}]")
    finally:
        conn.close()
