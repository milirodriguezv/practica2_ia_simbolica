"""Heurísticas independientes del dominio (propuesta v2, secc. 8.2).

Responsable: Eloísa.

Contrato: una heurística es una función h(estado, objetivo, acciones) -> número.
"""


def h0(estado, objetivo, acciones):
    """Siempre 0 (coste uniforme). Admisible."""
    return 0


def hprec(estado, objetivo, acciones):
    """Ignora precondiciones: átomos del objetivo no cumplidos.

    Admisible en nuestro dominio: ninguna acción añade más de un átomo del
    objetivo y ninguno se consigue con coste 0.
    """
    raise NotImplementedError


def hmax(estado, objetivo, acciones):
    """Ignora DEL: coste del subobjetivo más caro. Admisible."""
    raise NotImplementedError


def hadd(estado, objetivo, acciones):
    """Ignora DEL: suma de costes de los subobjetivos. No admisible."""
    raise NotImplementedError


def hff(estado, objetivo, acciones):
    """(Opcional) Ignora DEL: longitud de un plan relajado. No admisible."""
    raise NotImplementedError


HEURISTICAS = {"h0": h0, "hprec": hprec, "hmax": hmax, "hadd": hadd, "hff": hff}
