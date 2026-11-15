import argparse

from .carga import cargar
from .vivo import FRAUDES, en_vivo, lanzar, reporte


def main() -> None:
    parser = argparse.ArgumentParser(prog="docker compose run --rm simulador",
                                     description="Simulador de datos de Banco Rosberg")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_carga = sub.add_parser("cargar", help="Carga inicial: clientes, historial y fraudes plantados")
    p_carga.add_argument("--clientes", type=int, default=500)
    p_carga.add_argument("--dias", type=int, default=90)
    p_carga.add_argument("--semilla", type=int, default=42, help="Misma semilla = mismo banco")

    p_vivo = sub.add_parser("en-vivo", help="Trafico normal continuo por la API (Ctrl + C para detener)")
    p_vivo.add_argument("--intervalo", type=float, default=2.0, help="Segundos entre operaciones")

    p_lanzar = sub.add_parser("lanzar", help="Lanzar un fraude ahora mismo")
    p_lanzar.add_argument("tipo", choices=sorted(FRAUDES))

    sub.add_parser("reporte", help="Hoja de respuestas: casos de fraude plantados")
    sub.add_parser("evaluar", help="Metricas del motor antifraude contra la hoja de respuestas")

    args = parser.parse_args()
    if args.comando == "cargar":
        cargar(args.clientes, args.dias, args.semilla)
    elif args.comando == "en-vivo":
        en_vivo(args.intervalo)
    elif args.comando == "lanzar":
        lanzar(args.tipo)
    elif args.comando == "evaluar":
        from .evaluar import evaluar
        evaluar()
    else:
        reporte()


if __name__ == "__main__":
    main()
