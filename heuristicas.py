"""Heurísticas independientes del dominio.

Todas tienen la misma firma, h(estado, objetivo, acciones) -> número, y
estiman el coste que falta para alcanzar el objetivo desde el estado.

    - h0: siempre 0. Admisible.
    - hprec: ignora las precondiciones. Admisible en nuestro dominio.
    - hmax: ignora las listas de eliminación; subobjetivo más caro. Admisible.
    - hadd: ignora las listas de eliminación; suma de subobjetivos. No admisible.

hmax y hadd trabajan sobre el problema relajado: las acciones no borran nada
(se ignora dele) y solo cuentan las precondiciones positivas (se ignora
pre_neg).
"""

import math


def h0(estado, objetivo, acciones):
    """Heurística nula: convierte A* en búsqueda de coste uniforme.

    Admisible. Sirve de línea base para comparar las demás.

    Args:
        estado (frozenset[str]): Átomos ciertos en el estado.
        objetivo (frozenset[str]): Átomos que deben cumplirse.
        acciones (list[Accion]): Acciones instanciadas del problema.

    Returns:
        int: Siempre 0.
    """
    return 0


def hprec(estado, objetivo, acciones):
    """Heurística que ignora las precondiciones.

    Cuenta los átomos del objetivo que faltan en el estado. Sin
    precondiciones, cada uno se conseguiría aplicando directamente una acción.

    Admisible en nuestro dominio: ninguna acción añade más de un átomo del
    objetivo y ninguno se consigue con una acción de coste 0, así que hacen
    falta al menos tantas acciones de coste 1 como átomos faltan.

    Args:
        estado (frozenset[str]): Átomos ciertos en el estado.
        objetivo (frozenset[str]): Átomos que deben cumplirse.
        acciones (list[Accion]): Acciones instanciadas del problema (no se usan).

    Returns:
        int: Número de átomos del objetivo que no están en el estado.
    """
    return len(objetivo - estado)


def hmax(estado, objetivo, acciones):
    """Heurística h_max: coste del subobjetivo más caro, ignorando DEL.

    Calcula por rondas, hasta que nada cambia, el coste de alcanzar cada átomo
    en el problema relajado: 0 si ya está en el estado; si no, el coste de la
    acción más barata que lo añade, donde una acción cuesta su coste más el de
    su precondición más cara.

    Admisible: supone que, al conseguir lo más caro, lo demás ya está hecho.

    Args:
        estado (frozenset[str]): Átomos ciertos en el estado.
        objetivo (frozenset[str]): Átomos que deben cumplirse.
        acciones (list[Accion]): Acciones instanciadas del problema.

    Returns:
        float: Máximo de los costes de los átomos del objetivo, o math.inf si
        alguno no es alcanzable ni en el problema relajado.
    """
    costes = {atomo: 0 for atomo in estado}
    cambio = True
    while cambio:
        cambio = False
        for accion in acciones:
            if not all(pre in costes for pre in accion.pre_pos):
                continue
            valor = accion.coste + max(
                (costes[pre] for pre in accion.pre_pos), default=0
            )
            for atomo in accion.add:
                if atomo not in costes or valor < costes[atomo]:
                    costes[atomo] = valor
                    cambio = True

    for meta in objetivo:
        if meta not in costes:
            return math.inf

    return max(costes[meta] for meta in objetivo)


def hadd(estado, objetivo, acciones):
    """Heurística h_add: suma de los costes de los subobjetivos, ignorando DEL.

    Mismo cálculo que hmax, pero una acción cuesta su coste más la suma de los
    costes de sus precondiciones, y el resultado es la suma sobre el objetivo.

    No admisible: supone que los subobjetivos son independientes, así que
    cuenta varias veces las acciones que comparten.

    Args:
        estado (frozenset[str]): Átomos ciertos en el estado.
        objetivo (frozenset[str]): Átomos que deben cumplirse.
        acciones (list[Accion]): Acciones instanciadas del problema.

    Returns:
        float: Suma de los costes de los átomos del objetivo, o math.inf si
        alguno no es alcanzable ni en el problema relajado.
    """
    costes = {atomo: 0 for atomo in estado}
    cambio = True
    while cambio:
        cambio = False
        for accion in acciones:
            if not all(pre in costes for pre in accion.pre_pos):
                continue
            valor = accion.coste + sum(costes[pre] for pre in accion.pre_pos)
            for atomo in accion.add:
                if atomo not in costes or valor < costes[atomo]:
                    costes[atomo] = valor
                    cambio = True

    for meta in objetivo:
        if meta not in costes:
            return math.inf

    return sum(costes[meta] for meta in objetivo)


HEURISTICAS = {"h0": h0, "hprec": hprec, "hmax": hmax, "hadd": hadd}
