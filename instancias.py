"""Instancias I1-I3 y generador G(n).

Cada función devuelve (acciones, estado_inicial, objetivo) usando
las funciones de dominio.py.
"""

import random

import dominio


def red_i1():
    """Construye I1, la instancia de juguete (secc. 7.2).

    Una zona; S1 y S2 unidas por una línea larga; hidráulica H1 (2 bloques) en
    S1 y térmica T1 (4 bloques) en S2. Demanda: 5 cargas + 1 bloque de
    auxiliares de T1 = 6; oferta: 2 + 4 = 6 (justa).

    Returns:
        dominio.Red: La red del juguete.
    """
    red = dominio.Red()
    red.zonas = ["N"]
    red.subestaciones = {"S1": "N", "S2": "N"}
    red.lineas = {"L12": ("S1", "S2", "larga")}
    red.centrales = {
        "H1": ("S1", "autonomo", 2),
        "T1": ("S2", "termica", 4),
    }
    red.cargas = {
        "P1": ("S1", "prioritaria"),
        "B1": ("S1", "normal"),  # barrio
        "B2": ("S1", "normal"),
        "I1": ("S2", "normal"),  # industria
        "I2": ("S2", "normal"),
    }
    return red


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
