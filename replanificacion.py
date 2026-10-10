"""Replanificación ante fallos (propuesta v2, secc. 8.3).

Responsable: Milagros.

Ciclo: planificar -> ejecutar acción a acción -> monitorizar -> replanificar.
Los eventos son del entorno, no acciones del agente.
"""

import random


def averia_linea(estado, linea):
    """Borra Operativa(l). Devuelve el nuevo estado."""
    raise NotImplementedError


def disparo_central(estado, central):
    """Borra EnMarcha(c) y Operativa(c); sus bloques dejan de estar libres y
    las cargas que los usaban pierden el suministro. Devuelve el nuevo estado."""
    raise NotImplementedError


def ejecutar_con_fallos(acciones, inicial, objetivo, heuristica, modo="astar",
                        prob_fallo=0.1, semilla=0):
    """Bucle ejecutar-monitorizar-replanificar.

    Devuelve un dict con 'resuelto', 'maniobras', 'maniobras_extra',
    'cargas_perdidas', 'replanificaciones' y 'tiempo_replanificacion'.
    """
    rng = random.Random(semilla)
    raise NotImplementedError
