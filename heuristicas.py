"""Heurísticas independientes del dominio.

Una heurística es una función h(estado, objetivo, acciones) -> número.
"""

import math


def h0(estado, objetivo, acciones):
    """Siempre 0 (coste uniforme). Admisible."""
    return 0


def hprec(estado, objetivo, acciones):
    """Ignora precondiciones: átomos del objetivo no cumplidos.

    Admisible en nuestro dominio: ninguna acción añade más de un átomo del
    objetivo y ninguno se consigue con coste 0.

    Si ninguna acción tuviera precondiciones, podrías aplicar directamente
    una acción que consiga cada átomo que falta del objetivo
    (está en el estado pero no en el objetivo).
    Como en el dominio cada acción consigue como mucho un átomo del objetivo
    y ninguno se consigue con coste 0, harían falta exactamente tantas
    acciones de coste 1 como átomos faltan.
    """
    return len(objetivo - estado)


def hmax(estado, objetivo, acciones):
    """Ignora DEL: coste del subobjetivo más caro. Admisible."""
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
    """Ignora DEL: suma de costes de los subobjetivos. No admisible."""
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


def hff(estado, objetivo, acciones):
    """(Opcional) Ignora DEL: longitud de un plan relajado. No admisible."""
    raise NotImplementedError


HEURISTICAS = {"h0": h0, "hprec": hprec, "hmax": hmax, "hadd": hadd}
