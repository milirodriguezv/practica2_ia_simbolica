"""Dominio de reposición de la red eléctrica (bloques individuales).

Convenciones:
    - Un estado es un frozenset de cadenas, p. ej. 'ConTension(S1)'.
    - Una acción es una tupla (nombre, coste, pre_pos, pre_neg, add, dele);
      dele es la lista de eliminación (del es palabra reservada de Python).
    - Resultado(s, a) = (s - dele) | add.
    - Los predicados estáticos (Termica, Conecta, Linea, Zona, CargaEn...) se
      comprueban al instanciar y no aparecen ni en los estados ni en las
      precondiciones.
"""

from collections import namedtuple

from funciones_auxiliares import bloques_de_central, bloques_de_zona, zona_de_central

Accion = namedtuple("Accion", "nombre coste pre_pos pre_neg add dele")

COSTE_MANIOBRA = 1
COSTE_DERIVADA = 0  # ExtenderAlcance


def atomo(predicado, *args):
    """Construye un átomo como cadena.

    Args:
        predicado (str): Nombre del predicado.
        *args: Objetos a los que se aplica.

    Returns:
        str: El átomo, p. ej. atomo('Zona', 'S1', 'N') -> 'Zona(S1,N)'.
    """
    return f"{predicado}({','.join(map(str, args))})"


def aplicable(estado, accion):
    """Comprueba si una acción se puede aplicar en un estado.

    Args:
        estado (frozenset[str]): Átomos ciertos en el estado.
        accion (Accion): Acción instanciada.

    Returns:
        bool: True si el estado contiene todas las precondiciones positivas
        y ninguna de las negadas.
    """
    return accion.pre_pos <= estado and not (accion.pre_neg & estado)


def resultado(estado, accion):
    """Aplica una acción: Resultado(s, a) = (s - Del(a)) | Add(a).

    No comprueba la aplicabilidad; ver aplicable().

    Args:
        estado (frozenset[str]): Estado de partida.
        accion (Accion): Acción instanciada.

    Returns:
        frozenset[str]: El estado resultante.
    """
    return (estado - accion.dele) | accion.add


class Red:
    """Objetos y hechos estáticos de una red; entrada de la instanciación.

    Attributes:
        zonas (list[str]): Zonas eléctricas, que se reponen como islas.
        subestaciones (dict[str, str]): Subestación -> zona.
        lineas (dict[str, tuple]): Línea -> (s1, s2, 'corta' | 'larga'), entre
            dos subestaciones de la misma zona.
        centrales (dict[str, tuple]): Central -> (subestación,
            'autonomo' | 'termica', número de bloques). Las autónomas
            (hidráulicas) arrancan solas; las térmicas necesitan un bloque.
        cargas (dict[str, tuple]): Carga -> (subestación,
            'prioritaria' | 'normal').
        interconexiones (list[tuple]): Pares (s1, s2) de subestaciones de zonas
            distintas donde se pueden acoplar.
    """

    def __init__(self):
        self.zonas = []  # [z]
        self.subestaciones = {}  # s -> z
        self.lineas = {}  # l -> (s1, s2, 'corta' | 'larga')
        self.centrales = {}  # c -> (s, 'autonomo' | 'termica', n_bloques)
        self.cargas = {}  # k -> (s, 'prioritaria' | 'normal')
        self.interconexiones = []  # [(s1, s2)] entre zonas distintas


def estado_inicial(red):
    """Construye el estado inicial: apagón total, sin averías.

    Contiene Operativa(x) para cada central y línea y Alcanza(z,z) para cada
    zona. Nada tiene tensión.

    Args:
        red (Red): Descripción de la red.

    Returns:
        frozenset[str]: Átomos ciertos al inicio.
    """
    estado_inicial = set()

    for central in red.centrales:
        estado_inicial.add(atomo("Operativa", central))

    for linea in red.lineas:
        estado_inicial.add(atomo("Operativa", linea))

    for zona in red.zonas:
        estado_inicial.add(atomo("Alcanza", zona, zona))

    return frozenset(estado_inicial)


def objetivo(red):
    """Construye el objetivo: todo suministrado y las zonas acopladas.

    Contiene Suministrada(k) para cada carga y Alcanza(z1,z2) para cada par de
    zonas con interconexión directa, en un solo sentido (z1 < z2) para que
    ninguna acción consiga más de un átomo del objetivo.

    Args:
        red (Red): Descripción de la red.

    Returns:
        frozenset[str]: Átomos que deben ser ciertos al final.
    """
    objetivo = set()

    for carga in red.cargas:
        objetivo.add(atomo("Suministrada", carga))

    for s1, s2 in red.interconexiones:
        z1, z2 = sorted([red.subestaciones[s1], red.subestaciones[s2]])
        objetivo.add(atomo("Alcanza", z1, z2))

    return frozenset(objetivo)


def arrancar_autonomo(red):
    """Instancia ArrancarAutonomo(c, s): una acción por central autónoma.

    PRECOND: Operativa(c), no EnMarcha(c).
    EFECTO: EnMarcha(c), ConTension(s).
    Estáticos resueltos aquí: ArranqueAutonomo(c), Conecta(c,s).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for central, (subestacion, tipo, n_bloques) in red.centrales.items():
        if tipo != "autonomo":
            continue
        acciones.append(
            Accion(
                nombre=atomo("ArrancarAutonomo", central, subestacion),
                coste=COSTE_MANIOBRA,
                pre_pos=frozenset({atomo("Operativa", central)}),
                pre_neg=frozenset({atomo("EnMarcha", central)}),
                add=frozenset(
                    {atomo("EnMarcha", central), atomo("ConTension", subestacion)}
                ),
                dele=frozenset(),
            )
        )
    return acciones


def activar_bloque(red):
    """Instancia ActivarBloque(b, c): una acción por bloque de cada central.

    PRECOND: EnMarcha(c), no Activado(b).
    EFECTO: Activado(b), Libre(b).
    Estáticos resueltos aquí: BloqueDe(b,c).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for central in red.centrales:
        for bloque in bloques_de_central(red, central):
            acciones.append(
                Accion(
                    nombre=atomo("ActivarBloque", bloque, central),
                    coste=COSTE_MANIOBRA,
                    pre_pos=frozenset({atomo("EnMarcha", central)}),
                    pre_neg=frozenset({atomo("Activado", bloque)}),
                    add=frozenset({atomo("Activado", bloque), atomo("Libre", bloque)}),
                    dele=frozenset(),
                )
            )
    return acciones


def energizar_corta(red):
    """Instancia EnergizarCorta(l, origen, destino, z): dos por línea corta.

    Una acción por cada sentido de la línea; z es la zona de ambas subestaciones.

    PRECOND: Operativa(l), ConTension(origen), no ConTension(destino).
    EFECTO: ConTension(destino).
    Estáticos resueltos aquí: Linea(l,s1,s2) en ambos sentidos, Corta(l),
        Zona(s1,z), Zona(s2,z).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for linea, (s1, s2, tipo) in red.lineas.items():
        if tipo != "corta" or red.subestaciones[s1] != red.subestaciones[s2]:
            continue
        for origen, destino in [(s1, s2), (s2, s1)]:
            acciones.append(
                Accion(
                    nombre=atomo(
                        "EnergizarCorta",
                        linea,
                        origen,
                        destino,
                        red.subestaciones[origen],
                    ),
                    coste=COSTE_MANIOBRA,
                    pre_pos=frozenset(
                        {
                            atomo("ConTension", origen),
                            atomo("Operativa", linea),
                        }
                    ),
                    pre_neg=frozenset({atomo("ConTension", destino)}),
                    add=frozenset(
                        {
                            atomo("ConTension", destino),
                        }
                    ),
                    dele=frozenset(),
                )
            )
    return acciones


def energizar_larga(red):
    """Instancia EnergizarLarga(l, origen, destino, z, k): dos por línea larga.

    Como EnergizarCorta, pero el origen debe tener carga conectada para evitar
    la sobretensión de una línea larga en vacío (efecto Ferranti).

    PRECOND: Operativa(l), ConTension(origen), Suministrada(k),
        no ConTension(destino).
    EFECTO: ConTension(destino).
    Estáticos resueltos aquí: Linea(l,s1,s2) en ambos sentidos, Larga(l),
        Zona(s1,z), Zona(s2,z).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for linea, (s1, s2, tipo) in red.lineas.items():
        if tipo != "larga" or red.subestaciones[s1] != red.subestaciones[s2]:
            continue
        for origen, destino in [(s1, s2), (s2, s1)]:
            for carga, (subestacion, _) in red.cargas.items():
                if subestacion != origen:
                    continue
                acciones.append(
                    Accion(
                        nombre=atomo(
                            "EnergizarLarga",
                            linea,
                            origen,
                            destino,
                            red.subestaciones[origen],
                            carga,
                        ),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("ConTension", origen),
                                atomo("Operativa", linea),
                                atomo("Suministrada", carga),
                            }
                        ),
                        pre_neg=frozenset({atomo("ConTension", destino)}),
                        add=frozenset(
                            {
                                atomo("ConTension", destino),
                            }
                        ),
                        dele=frozenset(),
                    )
                )
    return acciones


def arrancar_termica(red):
    """Instancia ArrancarTermica(c, s, b, zb, zs), por térmica y bloque ajeno.

    El bloque b alimenta los servicios auxiliares y deja de estar libre. Los
    bloques de la propia térmica se excluyen: no pueden estar libres antes de
    arrancarla.

    PRECOND: Operativa(c), ConTension(s), Libre(b), Alcanza(zb,zs),
        no EnMarcha(c).
    EFECTO: EnMarcha(c), Auxiliar(b,c), no Libre(b).
    Estáticos resueltos aquí: Termica(c), Conecta(c,s), Zona(b,zb), Zona(s,zs).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for central, (subestacion, tipo, n_bloques) in red.centrales.items():
        if tipo != "termica":
            continue
        zs = red.subestaciones[subestacion]

        for otra in red.centrales:
            if otra == central:
                continue
            zb = zona_de_central(red, otra)

            for bloque in bloques_de_central(red, otra):
                acciones.append(
                    Accion(
                        nombre=atomo(
                            "ArrancarTermica", central, subestacion, bloque, zb, zs
                        ),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("Operativa", central),
                                atomo("ConTension", subestacion),
                                atomo("Libre", bloque),
                                atomo("Alcanza", zb, zs),
                            }
                        ),
                        pre_neg=frozenset({atomo("EnMarcha", central)}),
                        add=frozenset(
                            {
                                atomo("EnMarcha", central),
                                atomo("Auxiliar", bloque, central),
                            }
                        ),
                        dele=frozenset({atomo("Libre", bloque)}),
                    )
                )
    return acciones


def conectar_prioritaria(red):
    """Instancia ConectarPrioritaria(k, s, b, zb, zs), por prioritaria y bloque.

    PRECOND: ConTension(s), Libre(b), Alcanza(zb,zs), no Suministrada(k).
    EFECTO: Suministrada(k), Usa(k,b), no Libre(b).
    Estáticos resueltos aquí: Prioritaria(k), CargaEn(k,s), Zona(b,zb),
        Zona(s,zs).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for carga, (subestacion, tipo) in red.cargas.items():
        if tipo != "prioritaria":
            continue
        zs = red.subestaciones[subestacion]

        for central in red.centrales:
            zb = zona_de_central(red, central)

            for bloque in bloques_de_central(red, central):
                acciones.append(
                    Accion(
                        nombre=atomo(
                            "ConectarPrioritaria", carga, subestacion, bloque, zb, zs
                        ),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("ConTension", subestacion),
                                atomo("Libre", bloque),
                                atomo("Alcanza", zb, zs),
                            }
                        ),
                        pre_neg=frozenset({atomo("Suministrada", carga)}),
                        add=frozenset(
                            {
                                atomo("Suministrada", carga),
                                atomo("Usa", carga, bloque),
                            }
                        ),
                        dele=frozenset({atomo("Libre", bloque)}),
                    )
                )
    return acciones


def conectar_carga(red):
    """Instancia ConectarCarga(k, s, b, zb, zs), por carga normal y bloque.

    PrioridadCubierta(s) se expande al instanciar: se exige Suministrada(p)
    para cada carga prioritaria p de la subestación.

    PRECOND: ConTension(s), Libre(b), Alcanza(zb,zs), Suministrada(p) de cada
        prioritaria de s, no Suministrada(k).
    EFECTO: Suministrada(k), Usa(k,b), no Libre(b).
    Estáticos resueltos aquí: Normal(k), CargaEn(k,s), Zona(b,zb), Zona(s,zs).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for carga, (subestacion, tipo) in red.cargas.items():
        if tipo != "normal":
            continue
        zs = red.subestaciones[subestacion]
        prioritarias = [
            atomo("Suministrada", p)
            for p, (s, t) in red.cargas.items()
            if s == subestacion and t == "prioritaria"
        ]

        for central in red.centrales:
            zb = zona_de_central(red, central)

            for bloque in bloques_de_central(red, central):
                acciones.append(
                    Accion(
                        nombre=atomo(
                            "ConectarCarga", carga, subestacion, bloque, zb, zs
                        ),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("ConTension", subestacion),
                                atomo("Libre", bloque),
                                atomo("Alcanza", zb, zs),
                                *prioritarias,
                            }
                        ),
                        pre_neg=frozenset({atomo("Suministrada", carga)}),
                        add=frozenset(
                            {
                                atomo("Suministrada", carga),
                                atomo("Usa", carga, bloque),
                            }
                        ),
                        dele=frozenset({atomo("Libre", bloque)}),
                    )
                )
    return acciones


def deslastrar(red):
    """Instancia Deslastrar(k, b): una acción por carga normal y bloque.

    Desconecta la carga para recuperar su bloque. Las cargas prioritarias
    nunca se deslastran.

    PRECOND: Usa(k,b).
    EFECTO: Libre(b), no Usa(k,b), no Suministrada(k).
    Estáticos resueltos aquí: Normal(k).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for carga, (subestacion, tipo) in red.cargas.items():
        if tipo != "normal":
            continue
        for central in red.centrales:
            for bloque in bloques_de_central(red, central):
                acciones.append(
                    Accion(
                        nombre=atomo("Deslastrar", carga, bloque),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset({atomo("Usa", carga, bloque)}),
                        pre_neg=frozenset(),
                        add=frozenset({atomo("Libre", bloque)}),
                        dele=frozenset(
                            {
                                atomo("Usa", carga, bloque),
                                atomo("Suministrada", carga),
                            }
                        ),
                    )
                )
    return acciones


def acoplar_zonas(red):
    """Instancia AcoplarZonas(z1, z2, s1, s2, b1, b2), por interconexión y bloques.

    Se toma un bloque de cada zona: cada una necesita un bloque libre como
    margen, pero los bloques no se gastan.

    PRECOND: ConTension(s1), ConTension(s2), Libre(b1), Libre(b2),
        no Alcanza(z1,z2).
    EFECTO: Alcanza(z1,z2), Alcanza(z2,z1).
    Estáticos resueltos aquí: Interconexion(s1,s2), Zona(s1,z1), Zona(s2,z2),
        Zona(b1,z1), Zona(b2,z2).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for s1, s2 in red.interconexiones:
        z1, z2 = red.subestaciones[s1], red.subestaciones[s2]
        if z1 == z2:
            continue
        for bloque1 in bloques_de_zona(red, z1):
            for bloque2 in bloques_de_zona(red, z2):
                acciones.append(
                    Accion(
                        nombre=atomo("AcoplarZonas", z1, z2, s1, s2, bloque1, bloque2),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("ConTension", s1),
                                atomo("ConTension", s2),
                                atomo("Libre", bloque1),
                                atomo("Libre", bloque2),
                            }
                        ),
                        pre_neg=frozenset(
                            {
                                atomo("Alcanza", z1, z2),
                            }
                        ),
                        add=frozenset(
                            {
                                atomo("Alcanza", z1, z2),
                                atomo("Alcanza", z2, z1),
                            }
                        ),
                        dele=frozenset(),
                    )
                )
    return acciones


def extender_alcance(red):
    """Instancia ExtenderAlcance(z1, z2, z3), de coste 0, por terna de zonas.

    Regla de instanciación: solo pares (z1, z3) sin interconexión directa, para
    que ningún átomo del objetivo se consiga con coste 0 y h_prec siga siendo
    admisible.

    PRECOND: Alcanza(z1,z2), Alcanza(z2,z3), no Alcanza(z1,z3).
    EFECTO: Alcanza(z1,z3), Alcanza(z3,z1).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    conectadas = set()
    for s1, s2 in red.interconexiones:
        za, zb = red.subestaciones[s1], red.subestaciones[s2]
        conectadas.add((za, zb))
        conectadas.add((zb, za))

    for z1 in red.zonas:
        for z2 in red.zonas:
            if z1 == z2:
                continue
            for z3 in red.zonas:
                if z3 == z1 or z3 == z2:
                    continue
                if (z1, z3) in conectadas:
                    continue
                acciones.append(
                    Accion(
                        nombre=atomo("ExtenderAlcance", z1, z2, z3),
                        coste=COSTE_DERIVADA,
                        pre_pos=frozenset(
                            {atomo("Alcanza", z1, z2), atomo("Alcanza", z2, z3)}
                        ),
                        pre_neg=frozenset({atomo("Alcanza", z1, z3)}),
                        add=frozenset(
                            {atomo("Alcanza", z1, z3), atomo("Alcanza", z3, z1)}
                        ),
                        dele=frozenset(),
                    )
                )
    return acciones


def instanciar(red):
    """Instancia todos los esquemas de acciones sobre una red.

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Todas las acciones concretas del problema.
    """
    return (
        arrancar_autonomo(red)
        + activar_bloque(red)
        + energizar_corta(red)
        + energizar_larga(red)
        + arrancar_termica(red)
        + conectar_prioritaria(red)
        + conectar_carga(red)
        + deslastrar(red)
        + acoplar_zonas(red)
        + extender_alcance(red)
    )


def problema(red):
    """Construye el problema de planificación con bloques individuales.

    Args:
        red (Red): Descripción de la red.

    Returns:
        tuple: (acciones, estado_inicial, objetivo).
    """
    return instanciar(red), estado_inicial(red), objetivo(red)
