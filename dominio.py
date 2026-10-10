"""Dominio de reposición de la red eléctrica (propuesta v2, secc. 5).

Responsable: Eloísa.

Esquemas de acciones con coste e instanciación (grounding), en dos versiones:
bloques individuales (Libre(b)) y agregada (contadores Libres(z,n), secc. 7.4).

Contrato de interfaz (secc. 10):
  - Un estado es un frozenset de cadenas, p. ej. 'ConTension(S1)'.
  - Una acción es una tupla (nombre, coste, pre_pos, pre_neg, add, del).
  - Resultado(s, a) = (s - del) | add.
"""

from collections import namedtuple

# Sigue siendo una tupla (nombre, coste, pre_pos, pre_neg, add, del);
# el último campo se llama 'dele' porque 'del' es palabra reservada.
Accion = namedtuple("Accion", "nombre coste pre_pos pre_neg add dele")

COSTE_MANIOBRA = 1
COSTE_DERIVADA = 0  # ExtenderAlcance


def atomo(predicado, *args):
    """Construye un átomo como cadena: atomo('Zona', 'S1', 'N') -> 'Zona(S1,N)'."""
    return f"{predicado}({','.join(map(str, args))})"


def aplicable(estado, accion):
    """Cierto si el estado cumple las precondiciones positivas y negadas."""
    return accion.pre_pos <= estado and not (accion.pre_neg & estado)


def resultado(estado, accion):
    """Resultado(s, a) = (s - Del(a)) | Add(a)."""
    return (estado - accion.dele) | accion.add


# ---------------------------------------------------------------------------
# Descripción de una red (la rellenan las instancias)
# ---------------------------------------------------------------------------

class Red:
    """Objetos y hechos estáticos de una red; entrada de la instanciación."""

    def __init__(self):
        self.zonas = []              # [z]
        self.subestaciones = {}      # s -> z
        self.lineas = {}             # l -> (s1, s2, 'corta' | 'larga')
        self.centrales = {}          # c -> (s, 'autonomo' | 'termica', n_bloques)
        self.cargas = {}             # k -> (s, 'prioritaria' | 'normal')
        self.interconexiones = []    # [(s1, s2)] entre zonas distintas


# ---------------------------------------------------------------------------
# Versión con bloques individuales (secc. 5.3)
# ---------------------------------------------------------------------------

def estado_inicial(red):
    """Hechos estáticos + Operativa(x) + Alcanza(z,z) + PrioridadCubierta(s)."""
    raise NotImplementedError


def objetivo(red):
    """Suministrada(k) para toda carga + Alcanza(z1,z2), un solo sentido (z1<z2)."""
    raise NotImplementedError


def arrancar_autonomo(red):
    raise NotImplementedError


def activar_bloque(red):
    raise NotImplementedError


def energizar_corta(red):
    raise NotImplementedError


def energizar_larga(red):
    raise NotImplementedError


def arrancar_termica(red):
    raise NotImplementedError


def conectar_prioritaria(red):
    raise NotImplementedError


def conectar_carga(red):
    raise NotImplementedError


def deslastrar(red):
    raise NotImplementedError


def acoplar_zonas(red):
    raise NotImplementedError


def extender_alcance(red):
    """Coste 0. Regla de instanciación: solo pares (z1, z3) sin interconexión
    directa, para que h_prec siga siendo admisible (secc. 8.2)."""
    raise NotImplementedError


def instanciar(red):
    """Devuelve la lista de acciones concretas de los 9 esquemas."""
    raise NotImplementedError


def problema(red):
    """Devuelve (acciones, estado_inicial, objetivo) con bloques individuales."""
    return instanciar(red), estado_inicial(red), objetivo(red)


# ---------------------------------------------------------------------------
# Versión agregada (secc. 7.4): Libres(z,n), Sig(n,n+1), Pendientes(c,n)
# ---------------------------------------------------------------------------

def problema_agregado(red):
    """Devuelve (acciones, estado_inicial, objetivo) con contadores por zona."""
    raise NotImplementedError
