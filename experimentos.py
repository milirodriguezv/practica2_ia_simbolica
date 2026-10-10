"""Experimentos E1-E6: tablas CSV y gráficas (propuesta v2, secc. 9.2).

Responsable: Eloísa (E4: Milagros).

Uso: python experimentos.py E1 [E2 ...]
Los CSV van a resultados/ y las gráficas a figuras/.
"""

import sys

DIR_RESULTADOS = "resultados"
DIR_FIGURAS = "figuras"
SEMILLA = 0


def factor_ramificacion_efectivo(nodos, profundidad):
    """b* tal que nodos + 1 = 1 + b* + b*^2 + ... + b*^profundidad."""
    raise NotImplementedError


def e1():
    """¿Qué heurística es mejor? A* con h0, hprec, hmax, hadd y voraz con hadd en I1-I3."""
    raise NotImplementedError


def e2():
    """¿Cómo escala? G(n) con n creciente y límite de tiempo."""
    raise NotImplementedError


def e3():
    """¿Cuánto aporta la agregación? Bloques individuales frente a contadores."""
    raise NotImplementedError


def e4():
    """¿Qué pasa con los fallos? Fallos aleatorios durante la ejecución en I2/I3."""
    raise NotImplementedError


def e5():
    """(Opcional) ¿Dónde está lo difícil? Variar el margen de generación en G(n)."""
    raise NotImplementedError


def e6():
    """(Opcional) ¿El plan con menos maniobras es el más rápido? Programar I2/I3."""
    raise NotImplementedError


EXPERIMENTOS = {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6}

if __name__ == "__main__":
    for nombre in sys.argv[1:] or ["E1", "E2", "E3"]:
        EXPERIMENTOS[nombre.upper()]()
