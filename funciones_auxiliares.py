"""Consultas sobre una Red que usa la instanciación del dominio."""


def bloques_de_central(red, central):
    """Genera los nombres de los bloques de una central.

    Args:
        red (Red): Descripción de la red.
        central (str): Nombre de la central.

    Returns:
        list[str]: Nombres de sus bloques, p. ej. ['bH1_1', 'bH1_2'].
    """
    n = red.centrales[central][2]
    return [f"b{central}_{i}" for i in range(1, n + 1)]


def zona_de_central(red, central):
    """Devuelve la zona de una central, que es también la de sus bloques.

    Args:
        red (Red): Descripción de la red.
        central (str): Nombre de la central.

    Returns:
        str: Zona de la subestación a la que está conectada.
    """
    subestacion = red.centrales[central][0]
    return red.subestaciones[subestacion]


def bloques_de_zona(red, zona):
    """Reúne los bloques de todas las centrales de una zona.

    Args:
        red (Red): Descripción de la red.
        zona (str): Nombre de la zona.

    Returns:
        list[str]: Nombres de los bloques de la zona.
    """
    centrales = [c for c in red.centrales if zona_de_central(red, c) == zona]
    bloques = []
    for c in centrales:
        bloques.extend(bloques_de_central(red, c))
    return bloques
