"""Punto de entrada: reposición de la red eléctrica tras un apagón total.

Construye la red pedida (I1-I3, I2-reserva o una G(n) generada), la
instancia en la versión agregada (por defecto) o individual, busca un plan
con el algoritmo y la heurística elegidos y lo muestra validado junto con
las estadísticas de la búsqueda. Opcionalmente guarda un fotograma por paso
del plan (--figuras) o simula fallos con replanificación (--fallo,
--prob-fallo).

Ejemplos:
    python3 main.py --instancia I1 --algoritmo astar --heuristica hmax --individual
    python3 main.py --instancia I3 --algoritmo ucs --heuristica h0 --limite 120
    python3 main.py --generada 4 --margen 1.5 --semilla 3 --heuristica hprec
    python3 main.py --instancia I1 --individual --figuras i1
    python3 main.py --instancia I1 --heuristica hadd --fallo central:T1@11
    python3 main.py --instancia I2-reserva --heuristica hprec --prob-fallo 0.05 \\
        --semilla 8 --tipos-fallo central
"""

import argparse
import sys

import dominio
import dominio_agregado
import instancias
import planificador
import replanificacion
from heuristicas import HEURISTICAS

# Instancias que se pueden elegir con --instancia. I2-reserva solo existe
# para el experimento E4, por eso no está en instancias.REDES.
REDES_MAIN = dict(instancias.REDES, **{"I2-reserva": instancias.red_i2_reserva})

EJEMPLOS = """ejemplos:
  python3 main.py --instancia I1 --algoritmo astar --heuristica hmax --individual
  python3 main.py --instancia I3 --algoritmo ucs --heuristica h0 --limite 120
  python3 main.py --generada 4 --margen 1.5 --semilla 3 --heuristica hprec
  python3 main.py --instancia I1 --individual --figuras i1
  python3 main.py --instancia I1 --heuristica hadd --fallo central:T1@11
  python3 main.py --instancia I2-reserva --heuristica hprec --prob-fallo 0.05 \\
      --semilla 8 --tipos-fallo central
"""

MOTIVOS = {
    "sin_solucion": "El problema no tiene solución: la búsqueda agotó todos "
    "los estados alcanzables sin llegar al objetivo.",
    "limite_tiempo": "Se alcanzó el límite de tiempo antes de encontrar un "
    "plan; no se sabe si hay solución. Prueba a subir --limite.",
    "limite_nodos": "Se alcanzó el límite de nodos expandidos antes de "
    "encontrar un plan; no se sabe si hay solución. Prueba a subir --nodos.",
}


def _leer_fallo(texto):
    """Convierte 'TIPO:ELEMENTO@PASO' en (paso, (tipo, elemento)).

    Args:
        texto (str): Valor de --fallo, p. ej. 'central:T1@11'.

    Returns:
        tuple: (paso, (tipo, elemento)).

    Raises:
        argparse.ArgumentTypeError: Si el formato no es válido.
    """
    try:
        tipo_elemento, paso = texto.rsplit("@", 1)
        tipo, elemento = tipo_elemento.split(":", 1)
        paso = int(paso)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{texto}' no tiene el formato TIPO:ELEMENTO@PASO "
            "(p. ej. central:T1@11)"
        )
    if tipo not in replanificacion.TIPOS_FALLO:
        raise argparse.ArgumentTypeError(
            f"tipo '{tipo}' no válido: usa {' o '.join(replanificacion.TIPOS_FALLO)}"
        )
    if not elemento or paso < 0:
        raise argparse.ArgumentTypeError(
            f"'{texto}': falta el elemento o el paso es negativo"
        )
    return paso, (tipo, elemento)


def _argumentos():
    """Define y lee los argumentos de la línea de órdenes.

    Returns:
        tuple: (parser, args), el parser para poder lanzar errores después.
    """
    p = argparse.ArgumentParser(
        description="Reposición de la red eléctrica tras un apagón total",
        epilog=EJEMPLOS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--instancia", choices=sorted(REDES_MAIN), default="I1")
    p.add_argument("--generada", type=int, metavar="N",
                   help="usa la red aleatoria G(N) en vez de --instancia")
    p.add_argument("--margen", type=float, default=1.0,
                   help="margen oferta/demanda de G(N) (por defecto 1.0)")
    p.add_argument("--semilla", type=int, default=0,
                   help="semilla de G(N) y de los fallos aleatorios (por defecto 0)")
    p.add_argument("--algoritmo", choices=planificador.MODOS, default="astar")
    p.add_argument("--heuristica", choices=sorted(HEURISTICAS), default="hmax")
    p.add_argument("--individual", action="store_true",
                   help="bloques individuales en vez de la versión agregada")
    p.add_argument("--limite", type=float, default=60,
                   help="límite de tiempo por búsqueda en segundos (por defecto 60)")
    p.add_argument("--nodos", type=int, default=500_000,
                   help="límite de nodos expandidos por búsqueda (por defecto 500000)")
    p.add_argument("--figuras", metavar="PREFIJO",
                   help="guarda en figuras/ un fotograma por paso del plan")
    p.add_argument("--fallo", type=_leer_fallo, action="append", default=[],
                   metavar="TIPO:ELEMENTO@PASO",
                   help="fallo programado (repetible); TIPO es linea o central. "
                   "PASO es el número de acciones ya ejecutadas: @0 ocurre antes "
                   "de la primera acción y @11 entre la acción 11 y la 12")
    p.add_argument("--prob-fallo", type=float, default=0.0, metavar="P",
                   help="probabilidad de un fallo aleatorio antes de cada paso "
                   "(usa --semilla)")
    p.add_argument("--tipos-fallo", nargs="+", choices=replanificacion.TIPOS_FALLO,
                   default=list(replanificacion.TIPOS_FALLO), metavar="TIPO",
                   help="tipos de fallo aleatorio: linea y/o central (por "
                   "defecto ambos; E4 usa uno solo cada vez)")
    return p, p.parse_args()


def _construir_red(args):
    """Construye la red pedida: G(N) si se dio --generada, si no --instancia.

    Args:
        args (argparse.Namespace): Argumentos leídos.

    Returns:
        tuple: (red, nombre) con el dominio.Red y un nombre para mostrar.
    """
    if args.generada is not None:
        red = instancias.red_generada(args.generada, args.margen, args.semilla)
        return red, f"G({args.generada}), margen {args.margen}, semilla {args.semilla}"
    return REDES_MAIN[args.instancia](), args.instancia


def _imprimir_plan(plan, inicial, objetivo):
    """Muestra el plan numerado y el resultado de validarlo.

    Args:
        plan (list[Accion]): Acciones del plan, en orden.
        inicial (frozenset[str]): Estado inicial.
        objetivo (frozenset[str]): Átomos que deben cumplirse al final.
    """
    print(f"Plan ({len(plan)} acciones):")
    for i, accion in enumerate(plan, 1):
        print(f"  {i:3d}. {accion.nombre}  [coste {accion.coste}]")
    valido, coste = planificador.validar_plan(plan, inicial, objetivo)
    print(f"Validación: {'plan válido' if valido else 'PLAN NO VÁLIDO'} | coste {coste}")


def _imprimir_estadisticas(estadisticas):
    """Muestra las estadísticas de la búsqueda, una por línea.

    Args:
        estadisticas (dict): Estadísticas devueltas por planificador.buscar.
    """
    print("Estadísticas:")
    print(f"  Nodos expandidos: {estadisticas['expandidos']}")
    print(f"  Nodos generados:  {estadisticas['generados']}")
    print(f"  Tiempo:           {estadisticas['tiempo']:.2f} s")
    print(f"  Longitud:         {estadisticas['longitud']}")
    print(f"  Coste:            {estadisticas['coste']}")
    print(f"  Resultado:        {estadisticas['resultado']}")


def _ejecutar_fallos(args, red, acciones, inicial, objetivo):
    """Ejecuta el plan con fallos y replanificación, y muestra el resumen.

    Args:
        args (argparse.Namespace): Argumentos leídos.
        red (dominio.Red): Red del problema (versión individual).
        acciones (list[Accion]): Acciones instanciadas.
        inicial (frozenset[str]): Estado inicial.
        objetivo (frozenset[str]): Átomos que deben cumplirse al final.

    Returns:
        bool: True si el estado real llegó al objetivo.
    """
    r = replanificacion.ejecutar_con_fallos(
        red, acciones, inicial, objetivo, HEURISTICAS[args.heuristica],
        args.algoritmo, prob_fallo=args.prob_fallo, semilla=args.semilla,
        limite_tiempo=args.limite, limite_nodos=args.nodos,
        tipos_fallo=tuple(args.tipos_fallo), eventos_programados=dict(args.fallo),
    )
    perdidas = ", ".join(r["lista_cargas_perdidas"]) or "ninguna"
    extra = "-" if r["maniobras_extra"] is None else r["maniobras_extra"]
    print("Ejecución con fallos y replanificación:")
    print(f"  Resuelto:                {'sí' if r['resuelto'] else 'no'} ({r['motivo']})")
    if r["motivo"] == "sin_solucion" and r["coste_plan_original"] is not None:
        print("  Tras los fallos, desde el estado real ya no hay solución.")
    elif not r["resuelto"]:
        print(f"  {MOTIVOS.get(r['motivo'], '')}")
    print(f"  Coste del plan original: {r['coste_plan_original']}")
    print(f"  Coste ejecutado:         {r['coste']} ({r['maniobras']} maniobras)")
    print(f"  Maniobras extra:         {extra}")
    print(f"  Cargas perdidas:         {r['cargas_perdidas']} ({perdidas})")
    print(f"  Replanificaciones:       {r['replanificaciones']} "
          f"({r['tiempo_replanificacion']:.2f} s)")
    print("  Eventos:")
    for evento in r["eventos"] or ["ninguno"]:
        print(f"    - {evento}")
    return r["resuelto"]


def main():
    """Lee los argumentos, construye el problema y lanza la búsqueda."""
    p, args = _argumentos()
    if not 0 <= args.prob_fallo <= 1:
        p.error("--prob-fallo debe estar entre 0 y 1")
    red, nombre = _construir_red(args)
    for _, (tipo, elemento) in args.fallo:
        existentes = red.lineas if tipo == "linea" else red.centrales
        if elemento not in existentes:
            p.error(f"--fallo: la {tipo} '{elemento}' no existe en {nombre}")

    con_fallos = bool(args.fallo) or args.prob_fallo > 0
    if con_fallos and not args.individual:
        print("Aviso: la replanificación usa la versión individual, porque al "
              "disparar una central hay que saber qué cargas usaban sus bloques.")
        args.individual = True

    if args.individual:
        acciones, inicial, objetivo = dominio.problema(red)
    else:
        acciones, inicial, objetivo = dominio_agregado.problema_agregado(red)
    heuristica = HEURISTICAS[args.heuristica]

    print(f"Instancia:  {nombre} ({'individual' if args.individual else 'agregada'})")
    print(f"Acciones:   {len(acciones)}")
    print(f"Búsqueda:   {args.algoritmo} + {args.heuristica} "
          f"(límites: {args.limite} s, {args.nodos} nodos)")
    print(f"h(inicial): {heuristica(inicial, objetivo, acciones)}")
    print()

    if con_fallos:
        if args.figuras:
            print("Aviso: --figuras se ignora al simular fallos.")
        sys.exit(0 if _ejecutar_fallos(args, red, acciones, inicial, objetivo) else 1)

    plan, estadisticas = planificador.buscar(
        acciones, inicial, objetivo, heuristica, args.algoritmo,
        limite_tiempo=args.limite, limite_nodos=args.nodos,
    )
    if plan is None:
        print(f"No se encontró plan ({estadisticas['resultado']}).")
        print(MOTIVOS.get(estadisticas["resultado"], ""))
        print()
        _imprimir_estadisticas(estadisticas)
        sys.exit(1)

    _imprimir_plan(plan, inicial, objetivo)
    print()
    _imprimir_estadisticas(estadisticas)

    if args.figuras:
        import visualizacion  # aquí, para no cargar matplotlib si no hace falta

        rutas = visualizacion.fotogramas(red, plan, inicial, args.figuras)
        print()
        print(f"Guardadas {len(rutas)} imágenes: {rutas[0]} ... {rutas[-1]}")


if __name__ == "__main__":
    main()
