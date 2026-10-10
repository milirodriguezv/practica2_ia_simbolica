"""Planificador de búsqueda hacia delante (propuesta v2, secc. 8.1).

Responsable: Milagros.

Búsqueda en grafo con conjunto de cerrados: coste uniforme, A* y voraz.

Contrato de interfaz (secc. 10):
  buscar(acciones, inicial, objetivo, heuristica, modo) -> (plan, estadisticas)
  validar_plan(plan, inicial, objetivo) -> (valido, coste)
"""

import heapq
import time

MODOS = ("ucs", "astar", "voraz")  # f = g, f = g + h, f = h


def buscar(acciones, inicial, objetivo, heuristica, modo="astar", limite_tiempo=None):
    """Devuelve (plan, estadisticas).

    plan: lista de acciones, o None si no hay solución o se agota el tiempo.
    estadisticas: dict con 'expandidos', 'generados', 'tiempo', 'coste'.
    """
    raise NotImplementedError


def validar_plan(plan, inicial, objetivo):
    """Aplica el plan acción a acción comprobando precondiciones y objetivo.

    Devuelve (valido, coste).
    """
    raise NotImplementedError
