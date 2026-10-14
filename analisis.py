"""Análisis exacto del espacio de estados de un problema.

Cuando el espacio de estados cabe entero en memoria, se puede calcular el
coste óptimo real h* de todos los estados y clasificarlos. Los experimentos
usan dos clases propias de este dominio, que existen porque la generación
es un recurso que se gasta:

    - Estado trampa: el objetivo sigue siendo alcanzable, pero solo
      deshaciendo trabajo (Deslastrar). Es el "callejón sin salida" de la
      propuesta: se gastó un bloque donde no tocaba.
    - Estado sin salida: el objetivo ya no es alcanzable. Ocurre cuando los
      bloques se gastan en cargas prioritarias, que no se pueden deslastrar.
"""

import heapq
import math
from collections import deque

import dominio


def espacio_de_estados(acciones, inicial, tope):
    """Recorre en anchura todos los estados alcanzables.

    Args:
        acciones (list[Accion]): Acciones instanciadas.
        inicial (frozenset[str]): Estado inicial.
        tope (int): Número máximo de estados; si se supera, se abandona.

    Returns:
        tuple: (estados, arcos), o (None, None) si se supera el tope.
            estados (list[frozenset]): Estados alcanzables; el 0 es el inicial.
            arcos (list[tuple]): (origen, destino, coste, nombre de la acción),
            con origen y destino como índices de estados.
    """
    indice = {inicial: 0}
    estados = [inicial]
    arcos = []
    cola = deque([inicial])
    while cola:
        estado = cola.popleft()
        i = indice[estado]
        for accion in acciones:
            if not dominio.aplicable(estado, accion):
                continue
            sucesor = dominio.resultado(estado, accion)
            if sucesor not in indice:
                if len(estados) >= tope:
                    return None, None
                indice[sucesor] = len(estados)
                estados.append(sucesor)
                cola.append(sucesor)
            arcos.append((i, indice[sucesor], accion.coste, accion.nombre))
    return estados, arcos


def coste_real(estados, arcos, objetivo, sin_deslastrar=False):
    """Calcula el coste óptimo real h* desde cada estado.

    Dijkstra hacia atrás desde los estados que cumplen el objetivo.

    Args:
        estados (list[frozenset]): Estados de espacio_de_estados.
        arcos (list[tuple]): Arcos de espacio_de_estados.
        objetivo (frozenset[str]): Átomos del objetivo.
        sin_deslastrar (bool): Si es True, se prohíbe Deslastrar: el coste
            sale infinito en los estados que solo se arreglan deshaciendo.

    Returns:
        list[float]: h* de cada estado; math.inf si no alcanza el objetivo.
    """
    entrantes = [[] for _ in estados]
    for origen, destino, coste, nombre in arcos:
        if sin_deslastrar and nombre.startswith("Deslastrar"):
            continue
        entrantes[destino].append((origen, coste))

    real = [math.inf] * len(estados)
    cola = []
    for i, estado in enumerate(estados):
        if objetivo <= estado:
            real[i] = 0
            cola.append((0, i))
    heapq.heapify(cola)
    while cola:
        coste, j = heapq.heappop(cola)
        if coste > real[j]:
            continue
        for i, paso in entrantes[j]:
            if coste + paso < real[i]:
                real[i] = coste + paso
                heapq.heappush(cola, (real[i], i))
    return real


def clasificar_estados(estados, arcos, objetivo):
    """Separa los estados en trampas, sin salida y normales.

    Args:
        estados (list[frozenset]): Estados de espacio_de_estados.
        arcos (list[tuple]): Arcos de espacio_de_estados.
        objetivo (frozenset[str]): Átomos del objetivo.

    Returns:
        tuple: (real, trampas, sin_salida).
            real (list[float]): h* de cada estado.
            trampas (list[int]): Índices de los estados que alcanzan el
            objetivo, pero solo deslastrando.
            sin_salida (list[int]): Índices de los que ya no lo alcanzan.
    """
    real = coste_real(estados, arcos, objetivo)
    sin_deshacer = coste_real(estados, arcos, objetivo, sin_deslastrar=True)
    trampas = [
        i for i in range(len(estados))
        if real[i] < math.inf and sin_deshacer[i] == math.inf
    ]
    sin_salida = [i for i in range(len(estados)) if real[i] == math.inf]
    return real, trampas, sin_salida
