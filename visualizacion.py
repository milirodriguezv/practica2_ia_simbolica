"""Dibujo de la red paso a paso (fotogramas para las diapositivas).

Responsable: Milagros.

Usa matplotlib y networkx.
"""

DIR_FIGURAS = "figuras"


def dibujar_red(red, estado, ax=None, titulo=None):
    """Dibuja la red coloreando subestaciones con tensión, centrales en marcha
    y cargas suministradas según el estado."""
    raise NotImplementedError


def fotogramas(red, plan, inicial, prefijo):
    """Guarda en figuras/ una imagen por cada paso del plan."""
    raise NotImplementedError
