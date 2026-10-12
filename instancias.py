"""Instancias I1-I3, generador G(n) y comprobación de redes.

Cada función red_*() devuelve un dominio.Red (solo hechos estáticos).
cargar() la convierte en el problema (acciones, estado_inicial, objetivo)
con las funciones de dominio.py. validar() revisa que una red tenga sentido
antes de buscar un plan.
"""

import math
import random
from collections import deque

import dominio
import dominio_agregado
from heuristicas import hmax


def _referencias(red):
    """Comprueba que todo lo que se nombra en la red existe.

    Args:
        red (dominio.Red): Red a revisar.

    Returns:
        list[str]: Problemas encontrados (vacía si todo existe).
    """
    problemas = []
    for s, z in red.subestaciones.items():
        if z not in red.zonas:
            problemas.append(f"La subestación {s} está en la zona {z}, que no existe.")
    for l, (s1, s2, tipo) in red.lineas.items():
        for s in (s1, s2):
            if s not in red.subestaciones:
                problemas.append(f"La línea {l} usa la subestación {s}, que no existe.")
        if tipo not in ("corta", "larga"):
            problemas.append(f"La línea {l} tiene un tipo desconocido: {tipo}.")
    for c, (s, tipo, n) in red.centrales.items():
        if s not in red.subestaciones:
            problemas.append(f"La central {c} está en {s}, que no existe.")
        if tipo not in ("autonomo", "termica"):
            problemas.append(f"La central {c} tiene un tipo desconocido: {tipo}.")
    for k, (s, tipo) in red.cargas.items():
        if s not in red.subestaciones:
            problemas.append(f"La carga {k} está en {s}, que no existe.")
        if tipo not in ("prioritaria", "normal"):
            problemas.append(f"La carga {k} tiene un tipo desconocido: {tipo}.")
    for s1, s2 in red.interconexiones:
        for s in (s1, s2):
            if s not in red.subestaciones:
                problemas.append(f"La interconexión ({s1}, {s2}) usa {s}, que no existe.")
    return problemas


def _subestaciones_con_tension(red):
    """Calcula qué subestaciones pueden llegar a tener tensión.

    Búsqueda en anchura (BFS) desde las subestaciones con central autónoma.
    Una línea corta se puede cruzar siempre; una larga, solo desde una
    subestación con alguna carga (regla de sobretensión). Las líneas entre
    zonas distintas no cuentan, porque dominio.py no las instancia.

    Args:
        red (dominio.Red): Red a revisar.

    Returns:
        set[str]: Subestaciones alcanzables.
    """
    con_carga = {s for s, _ in red.cargas.values()}
    alcanzadas = {s for s, tipo, _ in red.centrales.values() if tipo == "autonomo"}
    cola = deque(alcanzadas)
    while cola:
        origen = cola.popleft()
        for s1, s2, tipo in red.lineas.values():
            if red.subestaciones[s1] != red.subestaciones[s2]:
                continue
            if origen == s1:
                destino = s2
            elif origen == s2:
                destino = s1
            else:
                continue
            if tipo == "larga" and origen not in con_carga:
                continue
            if destino not in alcanzadas:
                alcanzadas.add(destino)
                cola.append(destino)
    return alcanzadas


def validar(red):
    """Revisa que una red esté bien construida y pueda tener solución.

    Son condiciones necesarias, no una prueba de que exista plan (eso lo
    confirma el planificador):
        a. Cada zona tiene al menos una central autónoma.
        b. Cada línea une dos subestaciones de la misma zona.
        c. Todas las subestaciones pueden recibir tensión (ver
           _subestaciones_con_tension).
        d. Cada interconexión une subestaciones de zonas distintas.
        e. Hay bloques suficientes: uno por carga y uno por térmica.
        f. Red de seguridad: hmax del estado inicial no es infinita, es decir,
           el objetivo se alcanza al menos en el problema relajado.

    Args:
        red (dominio.Red): Red a revisar.

    Returns:
        list[str]: Mensajes con los problemas encontrados; vacía si está bien.
    """
    # Si algo apunta a un objeto que no existe, el resto fallaría.
    problemas = _referencias(red)
    if problemas:
        return problemas

    # a. Arranque autónomo en cada zona.
    for zona in red.zonas:
        autonomas = [
            c
            for c, (s, tipo, _) in red.centrales.items()
            if tipo == "autonomo" and red.subestaciones[s] == zona
        ]
        if not autonomas:
            problemas.append(f"La zona {zona} no tiene ninguna central autónoma.")

    # b. Líneas dentro de una misma zona.
    for l, (s1, s2, _) in red.lineas.items():
        if red.subestaciones[s1] != red.subestaciones[s2]:
            problemas.append(
                f"La línea {l} une {s1} y {s2}, que son de zonas distintas "
                "(dominio.py la ignoraría)."
            )

    # c. Todas las subestaciones pueden tener tensión.
    alcanzadas = _subestaciones_con_tension(red)
    for s in red.subestaciones:
        if s not in alcanzadas:
            problemas.append(f"La subestación {s} nunca puede recibir tensión.")

    # d. Interconexiones entre zonas distintas.
    for s1, s2 in red.interconexiones:
        if red.subestaciones[s1] == red.subestaciones[s2]:
            problemas.append(
                f"La interconexión ({s1}, {s2}) une subestaciones de la misma zona."
            )

    # e. Oferta suficiente: un bloque por carga y otro por cada térmica.
    oferta = sum(n for _, _, n in red.centrales.values())
    termicas = sum(1 for _, tipo, _ in red.centrales.values() if tipo == "termica")
    demanda = len(red.cargas) + termicas
    if oferta < demanda:
        problemas.append(
            f"Faltan bloques: hay {oferta} y hacen falta {demanda} "
            f"({len(red.cargas)} cargas + {termicas} térmicas)."
        )

    # f. Red de seguridad con el problema relajado.
    if not problemas:
        acciones, inicial, objetivo = dominio.problema(red)
        if hmax(inicial, objetivo, acciones) == math.inf:
            problemas.append(
                "El objetivo no se alcanza ni en el problema relajado (hmax = inf)."
            )

    return problemas


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
    """Construye I2, la red Norte/Sur (secc. 7.2).

    Dos zonas, N y S, de tres subestaciones cada una, unidas por la
    interconexión S3-S5. Cada zona tiene una hidráulica (2 bloques), una
    térmica (2 bloques), una línea larga y hospitales (P1 en N; P2 y P3 en
    S). Demanda: 6 cargas + 2 bloques de auxiliares = 8; oferta:
    2 + 2 + 2 + 2 = 8 (justa). Por zonas, N tiene un bloque de sobra
    (oferta 4, demanda 3) y a S le falta uno (oferta 4, demanda 5), así que
    hay que acoplar las zonas y pasar un bloque de N a S.

    Tamaño elegido para que todas las búsquedas óptimas (UCS y A* con h0,
    hprec y hmax) terminen con bloques individuales (coste óptimo 23) y E1
    compare las heurísticas de forma justa. Una versión anterior con
    térmicas de 3 bloques y dos industrias más no se resolvía de forma
    óptima en 120 s: I3 es la instancia grande que muestra esa explosión.

    Returns:
        dominio.Red: La red Norte/Sur.
    """
    red = dominio.Red()
    red.zonas = ["N", "S"]
    red.subestaciones = {
        "S1": "N",
        "S2": "N",
        "S3": "N",
        "S4": "S",
        "S5": "S",
        "S6": "S",
    }
    red.lineas = {
        "L12": ("S1", "S2", "larga"),
        "L23": ("S2", "S3", "corta"),
        "L45": ("S4", "S5", "corta"),
        "L46": ("S4", "S6", "larga"),
    }
    red.centrales = {
        "H1": ("S1", "autonomo", 2),
        "T1": ("S2", "termica", 2),
        "H2": ("S4", "autonomo", 2),
        "T2": ("S6", "termica", 2),
    }
    red.cargas = {
        "P1": ("S1", "prioritaria"),  # hospital
        "B1": ("S3", "normal"),  # barrio
        "P2": ("S4", "prioritaria"),
        "B2": ("S5", "normal"),
        "B3": ("S5", "normal"),
        "P3": ("S6", "prioritaria"),
    }
    red.interconexiones = [("S3", "S5")]
    return red


def red_i2_reserva():
    """Construye I2 con reserva: I2 más líneas dobles y una térmica de reserva.

    Existe solo para el experimento E4 (fallos y replanificación). I2 tiene
    oferta justa y un único camino a cada subestación, así que casi cualquier
    fallo la deja sin solución y E4 no podría medir recuperaciones. Esta
    variante añade la redundancia mínima para que la haya:
        - Cada línea tiene una gemela en paralelo, del mismo tipo (doble
          circuito): L12b, L23b, L45b y L46b. Si una se avería, la otra
          lleva la tensión por el mismo camino.
        - Una térmica de reserva T3 (2 bloques) en S6, junto a T2. Puede
          sustituir a una térmica que dispare.

    Por qué así y no de otra forma (medido con A* + hprec, bloques
    individuales):
        - Líneas que cierran un anillo (S1-S3, S5-S6) multiplican los órdenes
          posibles de energizar: A* + hprec no terminaba en 1 M de nodos. Una
          línea en paralelo no crea estados nuevos (la subestación destino
          queda con tensión igual), así que la búsqueda no crece.
        - Un bloque de sobra en una hidráulica abarata el plan: compensaría
          no arrancar una térmica (1 maniobra en vez de 3) y el óptimo
          bajaría de 23 a 20. Una térmica de 2 bloques cuesta lo mismo que
          T1 o T2 (arrancar + 2 activaciones para ganar 1 bloque neto), así
          que sin fallos no compensa usarla y el óptimo sigue siendo 23.
        - En S6 (detrás de la línea larga) la búsqueda crece menos que en
          S2, S3 o S5: 166 k nodos expandidos frente a 308-343 k.

    Oferta: 2 + 2 + 2 + 2 + 2 = 10 bloques; demanda sin fallos: 8 (6 cargas
    + 2 bloques de auxiliares). Coste óptimo: 23, igual que I2 (A* + hprec:
    unos 166 k nodos expandidos y 4,6 s).

    No está en REDES: E1-E3 y la línea de órdenes no cambian.

    Returns:
        dominio.Red: La red Norte/Sur con reserva.
    """
    red = red_i2()
    for linea in list(red.lineas):
        s1, s2, tipo = red.lineas[linea]
        red.lineas[linea + "b"] = (s1, s2, tipo)  # segundo circuito
    red.centrales["T3"] = ("S6", "termica", 2)  # térmica de reserva
    return red


def red_i3():
    """Construye I3, la red peninsular simplificada (secc. 7.2).

    Cuatro zonas (NO, NE, C y S), cada una con su hidráulica. NO tiene
    además la única térmica (T1, 3 bloques), que arranca con el bloque de
    H1 y luego alimenta las cargas de la zona. Hay dos líneas largas (en NE
    y en C) y un hospital por zona; en NO1 la carga normal B1 tiene que
    esperar al hospital P1 (regla de prioridad). Las interconexiones forman
    una cadena a través del centro (NO-C, C-NE, C-S), así que pares como
    NO-S o NO-NE no tienen enlace directo y solo se alcanzan con
    ExtenderAlcance.

    Demanda: 7 cargas + 1 bloque de auxiliares = 8; oferta:
    1 + 3 + 2 + 1 + 1 = 8 (justa). Por zonas (oferta/demanda): NO 4/4,
    NE 2/1, C 1/2 y S 1/1. A C le falta un bloque y NE tiene uno de sobra,
    así que hay que acoplar las zonas y pasar un bloque de NE a C.

    La frontera de NE (NE2) está detrás de la línea larga: para llegar hay
    que conectar antes el hospital P2. No hay bloqueo porque NE tiene un
    bloque de sobra, que sirve de margen para acoplar con C (comprobado con
    el planificador).

    Coste óptimo: 26 = 4 arranques autónomos + 8 activaciones + 1 arranque
    de térmica + 7 cargas + 3 líneas + 3 acoplamientos.

    Tamaño elegido para que la versión agregada se resuelva de forma óptima
    en pocos segundos y la de bloques individuales no (UCS y A* con hprec
    agotan el límite de nodos), así I3 muestra lo que gana la agregación
    (E3). La versión anterior (4 zonas de 3 subestaciones, 12 cargas, 2
    térmicas y 14 bloques) no se resolvía de forma óptima ni siquiera con
    la versión agregada.

    Returns:
        dominio.Red: La red peninsular simplificada.
    """
    red = dominio.Red()
    red.zonas = ["NO", "NE", "C", "S"]
    red.subestaciones = {
        "NO1": "NO",
        "NO2": "NO",
        "NE1": "NE",
        "NE2": "NE",
        "C1": "C",
        "C2": "C",
        "S1": "S",
    }
    red.lineas = {
        "LNO12": ("NO1", "NO2", "corta"),  # la térmica se alcanza sin línea larga
        "LNE12": ("NE1", "NE2", "larga"),
        "LC12": ("C1", "C2", "larga"),
    }
    red.centrales = {
        "H1": ("NO1", "autonomo", 1),
        "T1": ("NO2", "termica", 3),
        "H2": ("NE1", "autonomo", 2),
        "H3": ("C1", "autonomo", 1),
        "H4": ("S1", "autonomo", 1),
    }
    red.cargas = {
        "P1": ("NO1", "prioritaria"),  # hospital
        "B1": ("NO1", "normal"),  # barrio, espera a P1
        "I1": ("NO2", "normal"),  # industria
        "P2": ("NE1", "prioritaria"),
        "P3": ("C1", "prioritaria"),
        "B2": ("C2", "normal"),
        "P4": ("S1", "prioritaria"),
    }
    red.interconexiones = [("NO2", "C1"), ("C1", "NE2"), ("C1", "S1")]
    return red


# Constantes del generador G(n). Valores sencillos, elegidos a mano.
SUBESTACIONES_POR_ZONA = 4  # zonas pequeñas, como en I2 e I3 (unas 3-4 subestaciones)
PROB_LARGA = 0.3  # la mayoría de líneas son cortas, pero aparecen varias largas
MAX_CARGAS = 2  # cada subestación tiene entre 0 y 2 cargas aleatorias
PROB_PRIORITARIA = 0.25  # más o menos una de cada cuatro cargas es un hospital
PROB_TERMICA = 0.3  # algunas subestaciones candidatas tienen una térmica


def _nueva_carga(red, subestacion, rng, contadores):
    """Añade una carga aleatoria (hospital o normal) a una subestación.

    Args:
        red (dominio.Red): Red en construcción.
        subestacion (str): Subestación donde se conecta la carga.
        rng (random.Random): Generador de números aleatorios.
        contadores (dict): Último número usado para 'P' (hospitales) y 'B'
            (cargas normales); se actualiza aquí.
    """
    if rng.random() < PROB_PRIORITARIA:
        contadores["P"] += 1
        red.cargas[f"P{contadores['P']}"] = (subestacion, "prioritaria")
    else:
        contadores["B"] += 1
        red.cargas[f"B{contadores['B']}"] = (subestacion, "normal")


def _repartir_bloques(red, total, rng):
    """Reparte los bloques entre las centrales, al menos uno por central.

    Primero da un bloque a cada central y luego asigna los que quedan, de uno
    en uno, a centrales elegidas al azar. Si hay más centrales que bloques,
    gana el mínimo (un bloque por central) y el total real queda por encima
    del pedido.

    Args:
        red (dominio.Red): Red con las centrales ya creadas (con 0 bloques).
        total (int): Número de bloques que se quieren repartir.
        rng (random.Random): Generador de números aleatorios.
    """
    nombres = list(red.centrales)
    bloques = {c: 1 for c in nombres}
    for _ in range(total - len(nombres)):
        bloques[rng.choice(nombres)] += 1
    for c in nombres:
        s, tipo, _ = red.centrales[c]
        red.centrales[c] = (s, tipo, bloques[c])


def red_generada(n, margen=1.0, semilla=0):
    """G(n): red aleatoria de tamaño n con margen oferta/demanda ajustable.

    Pasos:
        1. Zonas de unas SUBESTACIONES_POR_ZONA subestaciones:
           n_zonas = max(1, n // 4). Las n subestaciones se reparten lo más
           igualado posible (cada zona, al menos una).
        2. En cada zona se construye un árbol: la primera subestación (raíz)
           tiene la hidráulica de la zona y un hospital; cada subestación
           siguiente cuelga de una anterior de su zona, elegida al azar, con
           una línea corta o larga (larga con probabilidad PROB_LARGA).
        3. Cargas aleatorias: entre 0 y MAX_CARGAS por subestación, cada una
           hospital con probabilidad PROB_PRIORITARIA. Después, si una línea
           larga sale de una subestación sin carga, se le añade una (regla de
           sobretensión). Así la zona es conexa y toda subestación puede
           recibir tensión por construcción.
        4. Térmicas: cada subestación candidata (ver abajo), salvo la raíz,
           tiene una térmica con probabilidad PROB_TERMICA.
        5. Bloques: total = ceil(margen * (cargas + térmicas)), repartidos
           con al menos un bloque por central (ver _repartir_bloques).
        6. Interconexiones: cadena de zonas Z1-Z2, Z2-Z3, ..., con una
           subestación frontera candidata elegida al azar en cada zona.

    Subestaciones candidatas: las que se alcanzan desde la raíz solo por
    líneas cortas (la raíz siempre lo es). Las térmicas y las fronteras solo
    se ponen ahí, para evitar bloqueos cuando la oferta es justa. Ejemplo
    que se evita: hidráulica de 1 bloque con un hospital en S1 y una térmica
    en S2 tras una línea larga; para llegar a S2 hay que conectar el
    hospital, que gasta el único bloque, y la térmica ya no puede arrancar.
    Con esta regla, en cada zona se puede arrancar la hidráulica, después
    las térmicas y acoplar las zonas sin conectar ninguna carga; con todo
    acoplado, cualquier bloque libre sirve para cualquier carga.

    Por eso, con margen >= 1 la red tiene solución. Con margen < 1 faltan
    bloques a propósito y la red no tiene solución (experimento E5).

    Nombres (únicos, en el estilo de I1-I3):
        - Zonas: Z1, Z2, ...
        - Subestaciones: S1..Sn, numeradas zona a zona.
        - Líneas: L<a>_<b>, entre Sa y Sb (a es el padre en el árbol).
        - Centrales: H<i> la hidráulica (autónoma) de la zona Zi; T1, T2,
          ... las térmicas.
        - Cargas: P1, P2, ... los hospitales; B1, B2, ... las normales.

    Args:
        n (int): Número de subestaciones (n >= 1).
        margen (float): Oferta / demanda deseada. 1.0 = oferta justa.
        semilla (int): Semilla; la misma (n, margen, semilla) da siempre la
            misma red.

    Returns:
        dominio.Red: La red generada.

    Raises:
        ValueError: Si n < 1.
    """
    if n < 1:
        raise ValueError("G(n) necesita al menos una subestación (n >= 1).")

    # Generador propio: no altera el estado global de random.
    rng = random.Random(semilla)
    red = dominio.Red()
    contadores = {"P": 0, "B": 0, "T": 0}  # último número de hospitales, normales y térmicas

    # 1. Zonas y reparto de subestaciones (las primeras zonas, una más).
    n_zonas = max(1, n // SUBESTACIONES_POR_ZONA)
    red.zonas = [f"Z{i}" for i in range(1, n_zonas + 1)]
    tamanos = [n // n_zonas + (1 if i < n % n_zonas else 0) for i in range(n_zonas)]

    numero = 0  # número de la última subestación creada
    fronteras = []  # una subestación frontera por zona
    for i, zona in enumerate(red.zonas):
        # 2. Árbol de la zona. candidatas = alcanzables solo por líneas cortas.
        raiz = f"S{numero + 1}"
        de_la_zona = []
        candidatas = []
        largas = []  # (padre, hijo) de cada línea larga
        for _ in range(tamanos[i]):
            numero += 1
            s = f"S{numero}"
            red.subestaciones[s] = zona
            if s == raiz:
                candidatas.append(s)
            else:
                padre = rng.choice(de_la_zona)
                tipo = "larga" if rng.random() < PROB_LARGA else "corta"
                # Nombre L<a>_<b> con los números de Sa y Sb (quita la 'S').
                red.lineas[f"L{padre[1:]}_{s[1:]}"] = (padre, s, tipo)
                if tipo == "larga":
                    largas.append((padre, s))
                elif padre in candidatas:
                    candidatas.append(s)
            de_la_zona.append(s)

        # La raíz tiene la hidráulica (bloques más tarde) y un hospital.
        red.centrales[f"H{i + 1}"] = (raiz, "autonomo", 0)
        contadores["P"] += 1
        red.cargas[f"P{contadores['P']}"] = (raiz, "prioritaria")

        # 3. Cargas aleatorias y, si hace falta, una carga en el origen de
        # cada línea larga.
        for s in de_la_zona:
            for _ in range(rng.randint(0, MAX_CARGAS)):
                _nueva_carga(red, s, rng, contadores)
        con_carga = {s for s, _ in red.cargas.values()}
        for padre, _ in largas:
            if padre not in con_carga:
                _nueva_carga(red, padre, rng, contadores)
                con_carga.add(padre)

        # 4. Térmicas en candidatas distintas de la raíz.
        for s in candidatas[1:]:
            if rng.random() < PROB_TERMICA:
                contadores["T"] += 1
                red.centrales[f"T{contadores['T']}"] = (s, "termica", 0)

        fronteras.append(rng.choice(candidatas))

    # 5. Bloques: demanda = cargas + térmicas (un bloque de auxiliares cada una).
    # round evita errores de coma flotante (1.1 * 50 = 55.00000000000001).
    total = math.ceil(round(margen * (len(red.cargas) + contadores["T"]), 6))
    _repartir_bloques(red, total, rng)

    # 6. Interconexiones en cadena entre zonas consecutivas.
    for i in range(n_zonas - 1):
        red.interconexiones.append((fronteras[i], fronteras[i + 1]))

    return red


REDES = {"I1": red_i1, "I2": red_i2, "I3": red_i3}


def cargar(nombre, agregada=True):
    """Devuelve (acciones, estado_inicial, objetivo) de la instancia pedida."""
    red = REDES[nombre]()
    return dominio_agregado.problema_agregado(red) if agregada else dominio.problema(red)
