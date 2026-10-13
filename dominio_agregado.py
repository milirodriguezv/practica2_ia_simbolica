"""Dominio de reposición de la red eléctrica (versión agregada).

Idea: en la versión individual cada bloque tiene nombre (bH1_1, bH1_2...) y
el planificador distingue "B1 usa bH1_1" de "B1 usa bH1_2", aunque para el
plan dan igual: son estados distintos pero equivalentes. Aquí no se dice
qué bloque está libre, solo cuántos hay libres en cada zona:

    - Libres(z,n): la zona z tiene n bloques libres (la zona de un bloque es
      la de su central).
    - Activados(c,m): la central c tiene m bloques activados.
    - Usa(k,z): la carga k usa un bloque de la zona z (hace falta recordar la
      zona para devolver el bloque al deslastrar).
    - Auxiliar(c,z): la térmica c arrancó con un bloque de la zona z.

Muchos estados de la versión individual que solo se diferencian en el nombre
de los bloques pasan a ser uno solo, así que el espacio de estados es mucho
más pequeño y la búsqueda expande menos nodos.

Cómo se cuenta sin números: el valor forma parte del átomo. Para pasar de 2
a 3 bloques libres la acción borra Libres(N,2) y añade Libres(N,3). Que 3
sigue a 2 sería el hecho estático Sig(2,3); como los demás estáticos, se
resuelve al instanciar: hay una copia de cada acción por cada valor del
contador, y Sig no aparece nunca en los estados.

Límites de los contadores:
    - Libres(z,n): de 0 al total de bloques de las centrales de la zona z.
    - Activados(c,m): de 0 a n_bloques de c.

En todo estado alcanzable hay exactamente un átomo Libres(z,·) por zona y un
Activados(c,·) por central: el estado inicial pone uno de cada, y toda
acción que borra uno añade otro del mismo contador.

La semántica es la misma que la de dominio.py, regla por regla. Las acciones que no
tocan bloques (ArrancarAutonomo, EnergizarCorta, EnergizarLarga y
ExtenderAlcance) son idénticas y se importan de dominio.py.
"""

from dominio import (
    COSTE_MANIOBRA,
    Accion,
    arrancar_autonomo,
    atomo,
    energizar_corta,
    energizar_larga,
    estado_inicial,
    extender_alcance,
    objetivo,
)
from funciones_auxiliares import bloques_de_zona, zona_de_central


def maximo_libres(red, zona):
    """Devuelve el tope del contador Libres de una zona.

    Args:
        red (Red): Descripción de la red.
        zona (str): Nombre de la zona.

    Returns:
        int: Número total de bloques de las centrales de la zona.
    """
    return len(bloques_de_zona(red, zona))


def estado_inicial_agregado(red):
    """Construye el estado inicial de la versión agregada.

    Es el de la versión individual (dominio.estado_inicial) más Libres(z,0)
    para cada zona y Activados(c,0) para cada central.

    Args:
        red (Red): Descripción de la red.

    Returns:
        frozenset[str]: Átomos ciertos al inicio.
    """
    estado = set(estado_inicial(red))

    for zona in red.zonas:
        estado.add(atomo("Libres", zona, 0))

    for central in red.centrales:
        estado.add(atomo("Activados", central, 0))

    return frozenset(estado)


def activar_bloque_agregado(red):
    """Instancia ActivarBloque(c, z, m, n): por central y valores de contador.

    Activa un bloque más de la central c, que queda libre en su zona z.

    PRECOND: EnMarcha(c), Activados(c,m), Libres(z,n), con m < n_bloques(c).
    EFECTO: Activados(c,m+1), Libres(z,n+1), no Activados(c,m),
        no Libres(z,n).
    Estáticos resueltos aquí: Zona(c,z), Sig(m,m+1), Sig(n,n+1).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for central, (subestacion, tipo, n_bloques) in red.centrales.items():
        zona = zona_de_central(red, central)
        # n < máximo de la zona: si m < n_bloques, el bloque que se activa
        # todavía no está contado, así que n nunca llega al máximo.
        for m in range(n_bloques):
            for n in range(maximo_libres(red, zona)):
                acciones.append(
                    Accion(
                        nombre=atomo("ActivarBloque", central, zona, m, n),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("EnMarcha", central),
                                atomo("Activados", central, m),
                                atomo("Libres", zona, n),
                            }
                        ),
                        pre_neg=frozenset(),
                        add=frozenset(
                            {
                                atomo("Activados", central, m + 1),
                                atomo("Libres", zona, n + 1),
                            }
                        ),
                        dele=frozenset(
                            {
                                atomo("Activados", central, m),
                                atomo("Libres", zona, n),
                            }
                        ),
                    )
                )
    return acciones


def arrancar_termica_agregado(red):
    """Instancia ArrancarTermica(c, s, zb, zs, n), por térmica, zona y valor.

    Gasta un bloque libre de la zona zb en los servicios auxiliares de c.

    En la versión individual no se puede usar un bloque de la propia térmica.
    Aquí no hace falta excluirlo a mano: los bloques de c solo se activan con
    EnMarcha(c), y esta acción exige no EnMarcha(c). Por tanto, mientras c
    está parada, ninguno de sus bloques está contado en Libres(zb,n) y todos
    los bloques libres de zb son de otras centrales.

    PRECOND: Operativa(c), ConTension(s), Libres(zb,n) con n >= 1,
        Alcanza(zb,zs), no EnMarcha(c).
    EFECTO: EnMarcha(c), Auxiliar(c,zb), Libres(zb,n-1), no Libres(zb,n).
    Estáticos resueltos aquí: Termica(c), Conecta(c,s), Zona(s,zs),
        Sig(n-1,n).

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

        for zb in red.zonas:
            for n in range(1, maximo_libres(red, zb) + 1):
                acciones.append(
                    Accion(
                        nombre=atomo(
                            "ArrancarTermica", central, subestacion, zb, zs, n
                        ),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("Operativa", central),
                                atomo("ConTension", subestacion),
                                atomo("Libres", zb, n),
                                atomo("Alcanza", zb, zs),
                            }
                        ),
                        pre_neg=frozenset({atomo("EnMarcha", central)}),
                        add=frozenset(
                            {
                                atomo("EnMarcha", central),
                                atomo("Auxiliar", central, zb),
                                atomo("Libres", zb, n - 1),
                            }
                        ),
                        dele=frozenset({atomo("Libres", zb, n)}),
                    )
                )
    return acciones


def _conectar(red, esquema, carga, subestacion, extra_pre):
    """Crea las acciones de conectar una carga, por zona del bloque y valor.

    Código común de ConectarPrioritaria y ConectarCarga, que solo se
    diferencian en el nombre y en las precondiciones extra.

    Args:
        red (Red): Descripción de la red.
        esquema (str): 'ConectarPrioritaria' o 'ConectarCarga'.
        carga (str): Carga que se conecta.
        subestacion (str): Subestación de la carga.
        extra_pre (list[str]): Precondiciones positivas añadidas.

    Returns:
        list[Accion]: Acciones instanciadas para esa carga.
    """
    acciones = []
    zs = red.subestaciones[subestacion]
    for zb in red.zonas:
        for n in range(1, maximo_libres(red, zb) + 1):
            acciones.append(
                Accion(
                    nombre=atomo(esquema, carga, subestacion, zb, zs, n),
                    coste=COSTE_MANIOBRA,
                    pre_pos=frozenset(
                        {
                            atomo("ConTension", subestacion),
                            atomo("Libres", zb, n),
                            atomo("Alcanza", zb, zs),
                            *extra_pre,
                        }
                    ),
                    pre_neg=frozenset({atomo("Suministrada", carga)}),
                    add=frozenset(
                        {
                            atomo("Suministrada", carga),
                            atomo("Usa", carga, zb),
                            atomo("Libres", zb, n - 1),
                        }
                    ),
                    dele=frozenset({atomo("Libres", zb, n)}),
                )
            )
    return acciones


def conectar_prioritaria_agregado(red):
    """Instancia ConectarPrioritaria(k, s, zb, zs, n), por prioritaria, zona y valor.

    PRECOND: ConTension(s), Libres(zb,n) con n >= 1, Alcanza(zb,zs),
        no Suministrada(k).
    EFECTO: Suministrada(k), Usa(k,zb), Libres(zb,n-1),
        no Libres(zb,n).
    Estáticos resueltos aquí: Prioritaria(k), CargaEn(k,s), Zona(s,zs),
        Sig(n-1,n).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for carga, (subestacion, tipo) in red.cargas.items():
        if tipo != "prioritaria":
            continue
        acciones += _conectar(red, "ConectarPrioritaria", carga, subestacion, [])
    return acciones


def conectar_carga_agregado(red):
    """Instancia ConectarCarga(k, s, zb, zs, n), por carga normal, zona y valor.

    PrioridadCubierta(s) se expande al instanciar, como en la versión
    individual: se exige Suministrada(p) para cada prioritaria p de s.

    PRECOND: ConTension(s), Libres(zb,n) con n >= 1, Alcanza(zb,zs),
        Suministrada(p) de cada prioritaria de s, no Suministrada(k).
    EFECTO: Suministrada(k), Usa(k,zb), Libres(zb,n-1),
        no Libres(zb,n).
    Estáticos resueltos aquí: Normal(k), CargaEn(k,s), Zona(s,zs),
        Sig(n-1,n).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for carga, (subestacion, tipo) in red.cargas.items():
        if tipo != "normal":
            continue
        prioritarias = [
            atomo("Suministrada", p)
            for p, (s, t) in red.cargas.items()
            if s == subestacion and t == "prioritaria"
        ]
        acciones += _conectar(red, "ConectarCarga", carga, subestacion, prioritarias)
    return acciones


def deslastrar_agregado(red):
    """Instancia Deslastrar(k, z, n), por carga normal, zona y valor.

    Desconecta la carga y su bloque vuelve a estar libre en la zona z de la
    que salió. Las prioritarias nunca se deslastran.

    PRECOND: Usa(k,z), Libres(z,n) con n < máximo de la zona.
    EFECTO: Libres(z,n+1), no Libres(z,n), no Usa(k,z), no Suministrada(k).
    Estáticos resueltos aquí: Normal(k), Sig(n,n+1).

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Acciones instanciadas del esquema.
    """
    acciones = []
    for carga, (subestacion, tipo) in red.cargas.items():
        if tipo != "normal":
            continue
        for zona in red.zonas:
            for n in range(maximo_libres(red, zona)):
                acciones.append(
                    Accion(
                        nombre=atomo("Deslastrar", carga, zona, n),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {atomo("Usa", carga, zona), atomo("Libres", zona, n)}
                        ),
                        pre_neg=frozenset(),
                        add=frozenset({atomo("Libres", zona, n + 1)}),
                        dele=frozenset(
                            {
                                atomo("Usa", carga, zona),
                                atomo("Suministrada", carga),
                                atomo("Libres", zona, n),
                            }
                        ),
                    )
                )
    return acciones


def acoplar_zonas_agregado(red):
    """Instancia AcoplarZonas(z1, z2, s1, s2, n1, n2), por interconexión y valores.

    Cada zona necesita al menos un bloque libre como margen, pero los
    bloques no se gastan: los contadores no cambian.

    PRECOND: ConTension(s1), ConTension(s2), Libres(z1,n1) con n1 >= 1,
        Libres(z2,n2) con n2 >= 1, no Alcanza(z1,z2).
    EFECTO: Alcanza(z1,z2), Alcanza(z2,z1).
    Estáticos resueltos aquí: Interconexion(s1,s2), Zona(s1,z1), Zona(s2,z2).

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
        for n1 in range(1, maximo_libres(red, z1) + 1):
            for n2 in range(1, maximo_libres(red, z2) + 1):
                acciones.append(
                    Accion(
                        nombre=atomo("AcoplarZonas", z1, z2, s1, s2, n1, n2),
                        coste=COSTE_MANIOBRA,
                        pre_pos=frozenset(
                            {
                                atomo("ConTension", s1),
                                atomo("ConTension", s2),
                                atomo("Libres", z1, n1),
                                atomo("Libres", z2, n2),
                            }
                        ),
                        pre_neg=frozenset({atomo("Alcanza", z1, z2)}),
                        add=frozenset(
                            {atomo("Alcanza", z1, z2), atomo("Alcanza", z2, z1)}
                        ),
                        dele=frozenset(),
                    )
                )
    return acciones


def instanciar_agregado(red):
    """Instancia todos los esquemas de la versión agregada sobre una red.

    ArrancarAutonomo, EnergizarCorta, EnergizarLarga y ExtenderAlcance no
    tocan bloques y son las mismas que en dominio.py.

    Args:
        red (Red): Descripción de la red.

    Returns:
        list[Accion]: Todas las acciones concretas del problema.
    """
    return (
        arrancar_autonomo(red)
        + activar_bloque_agregado(red)
        + energizar_corta(red)
        + energizar_larga(red)
        + arrancar_termica_agregado(red)
        + conectar_prioritaria_agregado(red)
        + conectar_carga_agregado(red)
        + deslastrar_agregado(red)
        + acoplar_zonas_agregado(red)
        + extender_alcance(red)
    )


def problema_agregado(red):
    """Construye el problema de planificación en versión agregada.

    El objetivo es el mismo que en la versión individual.

    Args:
        red (Red): Descripción de la red.

    Returns:
        tuple: (acciones, estado_inicial, objetivo).
    """
    return instanciar_agregado(red), estado_inicial_agregado(red), objetivo(red)
