import argparse

import instancias
import planificador
from heuristicas import HEURISTICAS


def main():
    p = argparse.ArgumentParser(
        description="Reposición de la red eléctrica tras un apagón total"
    )
    p.add_argument("--instancia", choices=sorted(instancias.REDES), default="I1")
    p.add_argument("--algoritmo", choices=planificador.MODOS, default="astar")
    p.add_argument("--heuristica", choices=sorted(HEURISTICAS), default="hmax")
    p.add_argument(
        "--individual",
        action="store_true",
        help="bloques individuales en vez de la versión agregada",
    )
    p.add_argument(
        "--limite", type=float, default=None, help="límite de tiempo en segundos"
    )
    args = p.parse_args()

    acciones, inicial, objetivo = instancias.cargar(
        args.instancia, agregada=not args.individual
    )
    plan, estadisticas = planificador.buscar(
        acciones,
        inicial,
        objetivo,
        HEURISTICAS[args.heuristica],
        args.algoritmo,
        limite_tiempo=args.limite,
    )

    if plan is None:
        print("Sin solución.")
    else:
        valido, coste = planificador.validar_plan(plan, inicial, objetivo)
        for i, accion in enumerate(plan, 1):
            print(f"{i:3d}. {accion.nombre}")
        print(f"Plan válido: {valido} | coste: {coste}")
    print(estadisticas)


if __name__ == "__main__":
    main()
