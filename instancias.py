"""Instancias I1-I3 y generador G(n) (propuesta v2, secc. 9.1).

Responsable: Milagros.

Contrato: cada función devuelve (acciones, estado_inicial, objetivo) usando
las funciones de dominio.py.
"""

import random

import dominio


def red_i1():
    """I1 - Juguete (secc. 7.2): una zona, S1-S2 por línea larga, H1 (2 bloques)
    en S1, T1 (4 bloques) en S2; 1 prioritaria + 2 barrio en S1, 2 industria en S2."""
    raise NotImplementedError


def red_i2():
    """I2 - Norte/Sur: 2 zonas, ~6 subestaciones, 2-3 cargas prioritarias."""
    raise NotImplementedError


def red_i3():
    """I3 - Peninsular simplificada: 3-4 zonas, ~12 subestaciones; al menos un
    par de zonas sin interconexión directa (para ExtenderAlcance)."""
    raise NotImplementedError


def red_generada(n, margen=1.0, semilla=0):
    """G(n): red aleatoria de tamaño n con margen oferta/demanda ajustable.

    Garantiza solución: cada zona tiene arranque autónomo, su red es conexa y
    la oferta cubre la demanda más los auxiliares de las térmicas.
    """
    rng = random.Random(semilla)
    raise NotImplementedError


REDES = {"I1": red_i1, "I2": red_i2, "I3": red_i3}


def cargar(nombre, agregada=True):
    """Devuelve (acciones, estado_inicial, objetivo) de la instancia pedida."""
    red = REDES[nombre]()
    return dominio.problema_agregado(red) if agregada else dominio.problema(red)
