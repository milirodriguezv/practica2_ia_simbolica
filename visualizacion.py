"""Dibujo de la red paso a paso 

Cada fotograma muestra un estado de la red:
    - Subestaciones: gris = sin tensión, amarillo = ConTension(s).
    - Líneas: corta = trazo continuo, larga = discontinuo; en rojo con una
      X si no está Operativa (avería, útil para la replanificación).
    - Interconexiones entre zonas: punteadas en morado; más gruesas cuando
      las dos zonas ya están acopladas (Alcanza).
    - Junto a cada subestación, sus centrales (en marcha, parada o
      averiada) y sus cargas (suministrada o no); los hospitales llevan (H).

Solo se usan átomos que existen en las dos versiones del dominio
(ConTension, EnMarcha, Operativa, Suministrada, Alcanza), así que sirve
tanto para dominio.problema como para dominio_agregado.problema_agregado.

"""

import os

import matplotlib

matplotlib.use("Agg")  
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

from dominio import atomo, resultado

DIR_FIGURAS = "figuras"

# Colores (elegidos para que se distingan bien proyectados).
GRIS = "#bdbdbd"  # subestación sin tensión
AMARILLO = "#ffd43b"  # subestación con tensión
COLOR_LINEA = "#424242"  # línea operativa
ROJO = "#d62728"  # avería
MORADO = "#7b3fa0"  # interconexión entre zonas
VERDE = "#2b8a3e"  # central en marcha / carga suministrada
APAGADO = "#757575"  # central parada / carga sin suministro

SEPARACION_GEMELAS = 0.04  # distancia entre líneas paralelas (en coordenadas del dibujo)
RADIO_ZONA = 0.45  # tamaño de cada zona; los centros de las zonas están a escala 1
DISTANCIA_CERCA = 0.8  # subestaciones más cercanas estorban a los textos


def grafo(red):
    """Construye el grafo de la red con networkx.

    Se usa un MultiGraph porque puede haber líneas gemelas en paralelo entre
    las mismas subestaciones (p. ej. red_i2_reserva): un Graph simple las
    juntaría en una sola arista.

    Args:
        red (dominio.Red): Descripción de la red.

    Returns:
        nx.MultiGraph: Nodos = subestaciones; aristas = líneas (atributo
        'tipo' = 'corta' | 'larga') e interconexiones ('interconexion').
    """
    g = nx.MultiGraph()
    g.add_nodes_from(red.subestaciones)
    for linea, (s1, s2, tipo) in red.lineas.items():
        g.add_edge(s1, s2, key=linea, tipo=tipo)
    for s1, s2 in red.interconexiones:
        g.add_edge(s1, s2, key=f"{s1}-{s2}", tipo="interconexion")
    return g


def posiciones(red):
    """Calcula la posición de cada subestación, una sola vez por red.

    Se reutiliza en todos los fotogramas para que los nodos no se muevan
    entre una imagen y la siguiente. La semilla fija hace que el resultado
    sea siempre el mismo.

    Se hace en dos niveles para que cada zona quede agrupada y separada de
    las demás:
        1. Los centros de las zonas se reparten en un círculo
           (circular_layout), en el orden de red.zonas.
        2. Dentro de cada zona se colocan sus subestaciones (unidas por sus
           líneas) con spring_layout, más pequeño y centrado en la zona.

    Args:
        red (dominio.Red): Descripción de la red.

    Returns:
        dict[str, tuple]: Subestación -> (x, y).
    """
    # 1. Centro de cada zona, repartidos en un círculo (una zona: el centro).
    centros = nx.circular_layout(red.zonas, scale=1.0)

    # 2. Subestaciones de cada zona alrededor de su centro.
    pos = {}
    for zona in red.zonas:
        # Grafo de la zona construido a mano, siempre en el mismo orden.
        # (g.subgraph() recorre los nodos en un orden que cambia de una
        # ejecución a otra, y con él cambiaría el dibujo.)
        g_zona = nx.Graph()
        g_zona.add_nodes_from(s for s, z in red.subestaciones.items() if z == zona)
        for s1, s2, _ in red.lineas.values():
            if s1 in g_zona and s2 in g_zona:
                g_zona.add_edge(s1, s2)
        pos_zona = nx.spring_layout(
            g_zona, seed=0, center=centros[zona], scale=RADIO_ZONA
        )
        pos.update(pos_zona)
    return pos


def _desplazamiento(p1, p2, i, n):
    """Calcula cuánto separar la i-ésima de n líneas paralelas.

    Las n líneas se reparten simétricamente a ambos lados de la recta que
    une las dos subestaciones (con n = 1 no se desplaza).

    Args:
        p1 (tuple): Posición (x, y) de un extremo.
        p2 (tuple): Posición (x, y) del otro extremo.
        i (int): Índice de la línea entre sus gemelas (0..n-1).
        n (int): Número de líneas entre las mismas subestaciones.

    Returns:
        tuple: (dx, dy) que se suma a los dos extremos.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    largo = (dx**2 + dy**2) ** 0.5 or 1.0
    normal = (-dy / largo, dx / largo)  # vector perpendicular de longitud 1
    d = (i - (n - 1) / 2) * SEPARACION_GEMELAS
    return normal[0] * d, normal[1] * d


def _dibujar_lineas(red, estado, ax, pos):
    """Dibuja las líneas de la red (y las gemelas separadas).

    Args:
        red (dominio.Red): Descripción de la red.
        estado (frozenset[str]): Estado que se dibuja.
        ax (matplotlib.axes.Axes): Ejes donde se dibuja.
        pos (dict): Subestación -> (x, y).
    """
    # Agrupa las líneas por par de subestaciones para separar las gemelas.
    por_par = {}
    for linea, (s1, s2, tipo) in red.lineas.items():
        par = tuple(sorted((s1, s2)))
        por_par.setdefault(par, []).append((linea, tipo))

    for (s1, s2), lineas in por_par.items():
        for i, (linea, tipo) in enumerate(lineas):
            dx, dy = _desplazamiento(pos[s1], pos[s2], i, len(lineas))
            xs = [pos[s1][0] + dx, pos[s2][0] + dx]
            ys = [pos[s1][1] + dy, pos[s2][1] + dy]
            averiada = atomo("Operativa", linea) not in estado
            ax.plot(
                xs,
                ys,
                color=ROJO if averiada else COLOR_LINEA,
                linestyle="--" if tipo == "larga" else "-",
                linewidth=2.5,
                zorder=1,
            )
            # Nombre de la línea en el punto medio; una X si está averiada.
            medio = ((xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2)
            if averiada:
                ax.plot(*medio, marker="X", color=ROJO, markersize=14, zorder=3)
            ax.annotate(
                linea,
                medio,
                xytext=(0, 6),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color=ROJO if averiada else APAGADO,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.5),
                zorder=3,
            )


def _dibujar_interconexiones(red, estado, ax, pos):
    """Dibuja las interconexiones entre zonas (punteadas).

    Args:
        red (dominio.Red): Descripción de la red.
        estado (frozenset[str]): Estado que se dibuja.
        ax (matplotlib.axes.Axes): Ejes donde se dibuja.
        pos (dict): Subestación -> (x, y).
    """
    for s1, s2 in red.interconexiones:
        z1, z2 = red.subestaciones[s1], red.subestaciones[s2]
        acopladas = atomo("Alcanza", z1, z2) in estado
        ax.plot(
            [pos[s1][0], pos[s2][0]],
            [pos[s1][1], pos[s2][1]],
            color=MORADO,
            linestyle=":",
            linewidth=4 if acopladas else 2,
            zorder=1,
        )


def _etiquetas(red, estado, s):
    """Prepara el texto que va junto a una subestación.

    Args:
        red (dominio.Red): Descripción de la red.
        estado (frozenset[str]): Estado que se dibuja.
        s (str): Subestación.

    Returns:
        list[tuple]: Pares (texto, color), uno por central y por carga.
    """
    etiquetas = []
    for c, (sub, tipo, _) in red.centrales.items():
        if sub != s:
            continue
        if atomo("Operativa", c) not in estado:
            etiquetas.append((f"{c} averiada", ROJO))
        elif atomo("EnMarcha", c) in estado:
            etiquetas.append((f"{c} ✓ en marcha", VERDE))
        else:
            etiquetas.append((f"{c} ✗ parada", APAGADO))
    for k, (sub, tipo) in red.cargas.items():
        if sub != s:
            continue
        nombre = f"{k} (H)" if tipo == "prioritaria" else k
        if atomo("Suministrada", k) in estado:
            etiquetas.append((f"{nombre} ✓", VERDE))
        else:
            etiquetas.append((f"{nombre} ✗", APAGADO))
    return etiquetas


def _leyenda(red, ax):
    """Añade la leyenda debajo del dibujo.

    Args:
        red (dominio.Red): Descripción de la red (para saber si hay
            interconexiones que explicar).
        ax (matplotlib.axes.Axes): Ejes donde se dibuja.
    """
    elementos = [
        Line2D([], [], marker="o", color="w", markerfacecolor=GRIS,
               markeredgecolor="black", markersize=12, label="Sin tensión"),
        Line2D([], [], marker="o", color="w", markerfacecolor=AMARILLO,
               markeredgecolor="black", markersize=12, label="Con tensión"),
        Line2D([], [], color=COLOR_LINEA, linewidth=2.5, label="Línea corta"),
        Line2D([], [], color=COLOR_LINEA, linewidth=2.5, linestyle="--",
               label="Línea larga"),
        Line2D([], [], color=ROJO, linewidth=2.5, marker="X", markersize=10,
               label="Línea averiada"),
    ]
    if red.interconexiones:  # solo si hay más de una zona que acoplar
        elementos += [
            Line2D([], [], color=MORADO, linewidth=2, linestyle=":",
                   label="Interconexión"),
            Line2D([], [], color=MORADO, linewidth=4, linestyle=":",
                   label="Zonas acopladas"),
        ]
    ax.legend(
        handles=elementos,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=4,
        fontsize=10,
        frameon=False,
    )
    # Clave de las etiquetas de texto, debajo de la leyenda.
    ax.text(
        0.5,
        -0.13,
        "✓ en marcha / suministrada     ✗ parada / sin suministro     "
        "(H) hospital (carga prioritaria)",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=10,
    )


def _lado_libre(s, pos, g):
    """Elige el lado (derecha o izquierda) donde poner los textos de s.

    Obstáculos: las subestaciones unidas a s (por línea o interconexión) y
    las que están cerca (a menos de DISTANCIA_CERCA). Para cada obstáculo se
    mira cuánto apunta hacia la derecha: dx / distancia, entre -1 (justo a
    la izquierda) y 1 (justo a la derecha). Se elige el lado cuyo obstáculo
    más alineado lo está menos. Si empatan (o no hay obstáculos), se pone
    hacia fuera del dibujo.

    Args:
        s (str): Subestación.
        pos (dict): Subestación -> (x, y).
        g (nx.MultiGraph): Grafo de la red (ver grafo()).

    Returns:
        str: 'derecha' o 'izquierda'.
    """
    x, y = pos[s]
    peor_derecha, peor_izquierda = -1.0, -1.0
    for v in pos:
        if v == s:
            continue
        dx, dy = pos[v][0] - x, pos[v][1] - y
        distancia = (dx**2 + dy**2) ** 0.5 or 1e-9
        if g.has_edge(s, v) or distancia < DISTANCIA_CERCA:
            peor_derecha = max(peor_derecha, dx / distancia)
            peor_izquierda = max(peor_izquierda, -dx / distancia)
    if peor_derecha < peor_izquierda:
        return "derecha"
    if peor_izquierda < peor_derecha:
        return "izquierda"
    centro_x = sum(p[0] for p in pos.values()) / len(pos)
    return "izquierda" if x < centro_x else "derecha"


def dibujar_red(red, estado, ax=None, titulo=None, pos=None):
    """Dibuja la red coloreando subestaciones con tensión, centrales en marcha
    y cargas suministradas según el estado.

    Args:
        red (dominio.Red): Descripción de la red.
        estado (frozenset[str]): Estado que se dibuja (de la versión
            individual o de la agregada).
        ax (matplotlib.axes.Axes, optional): Ejes donde dibujar; si no se
            da, se crea una figura nueva.
        titulo (str, optional): Título del dibujo.
        pos (dict, optional): Posiciones de las subestaciones; si no se dan,
            se calculan con posiciones(red). Para varios fotogramas conviene
            pasar siempre las mismas.

    Returns:
        matplotlib.axes.Axes: Los ejes con el dibujo.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 8))
    if pos is None:
        pos = posiciones(red)

    _dibujar_interconexiones(red, estado, ax, pos)
    _dibujar_lineas(red, estado, ax, pos)

    # Subestaciones: círculo con su nombre dentro.
    nodos = list(red.subestaciones)
    colores = [
        AMARILLO if atomo("ConTension", s) in estado else GRIS for s in nodos
    ]
    g = grafo(red)
    nx.draw_networkx_nodes(
        g, pos, nodelist=nodos, node_color=colores, node_size=1100,
        edgecolors="black", linewidths=1.5, ax=ax,
    )
    nx.draw_networkx_labels(
        g, pos, labels={s: s for s in nodos}, font_size=10,
        font_weight="bold", ax=ax,
    )

    # Al lado de cada subestación, una línea de texto por central y por carga,
    # en el lado (derecha o izquierda) más despejado.
    for s in nodos:
        etiquetas = _etiquetas(red, estado, s)
        if _lado_libre(s, pos, g) == "derecha":
            dx, alineacion = 24, "left"
        else:
            dx, alineacion = -24, "right"
        for i, (texto, color) in enumerate(etiquetas):
            # Bloque centrado en vertical respecto a la subestación.
            dy = 7 * (len(etiquetas) - 1) - 14 * i
            ax.annotate(
                texto,
                pos[s],
                xytext=(dx, dy),
                textcoords="offset points",
                ha=alineacion,
                va="center",
                fontsize=10,
                color=color,
                fontweight="bold" if color == VERDE else "normal",
                # Fondo blanco para que el texto se lea aunque pase una línea.
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1),
                zorder=4,
            )

    # Nombre de cada zona encima de sus subestaciones (si hay más de una).
    if len(red.zonas) > 1:
        for z in red.zonas:
            puntos = [pos[s] for s, zona in red.subestaciones.items() if zona == z]
            x = sum(p[0] for p in puntos) / len(puntos)
            y = max(p[1] for p in puntos)
            ax.annotate(
                f"Zona {z}", (x, y), xytext=(0, 26), textcoords="offset points",
                ha="center", fontsize=12, color=MORADO, fontweight="bold",
            )

    # Margen alrededor de los nodos para que quepan los textos.
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    ancho = max(max(xs) - min(xs), 0.5)
    alto = max(max(ys) - min(ys), 0.5)
    ax.set_xlim(min(xs) - 0.35 * ancho, max(xs) + 0.35 * ancho)
    ax.set_ylim(min(ys) - 0.15 * alto, max(ys) + 0.2 * alto)
    ax.axis("off")

    _leyenda(red, ax)
    if titulo:
        ax.set_title(titulo, fontsize=14)
    return ax


def fotogramas(red, plan, inicial, prefijo):
    """Guarda en figuras/ una imagen por cada paso del plan.

    La imagen 00 es el estado inicial y la i-ésima, el estado tras aplicar
    la acción i con dominio.resultado().

    Args:
        red (dominio.Red): Descripción de la red.
        plan (list[Accion]): Acciones del plan, en orden.
        inicial (frozenset[str]): Estado inicial.
        prefijo (str): Comienzo del nombre de los ficheros.

    Returns:
        list[str]: Rutas de las imágenes guardadas, en orden.
    """
    os.makedirs(DIR_FIGURAS, exist_ok=True)
    pos = posiciones(red)  # una sola vez: los nodos no se mueven
    rutas = []
    estado = inicial
    pasos = [None] + list(plan)  # el paso 0 es el estado inicial
    for i, accion in enumerate(pasos):
        if accion is None:
            titulo = "Paso 0: estado inicial"
        else:
            estado = resultado(estado, accion)
            titulo = f"Paso {i}: {accion.nombre}"
        fig, ax = plt.subplots(figsize=(12, 8))
        dibujar_red(red, estado, ax=ax, titulo=titulo, pos=pos)
        ruta = os.path.join(DIR_FIGURAS, f"{prefijo}_{i:02d}.png")
        fig.savefig(ruta, dpi=100, bbox_inches="tight")
        plt.close(fig)  # libera la memoria de la figura
        rutas.append(ruta)
    return rutas


if __name__ == "__main__":
    # Fotogramas del plan óptimo de I1 (A* + hmax, versión individual: los
    # títulos nombran el bloque que se usa, p. ej. ActivarBloque(bT1_1,T1)).
    import instancias
    from heuristicas import hmax
    from planificador import buscar

    red_i1 = instancias.red_i1()
    acciones, inicial, objetivo = instancias.cargar("I1", agregada=False)
    plan, estadisticas = buscar(
        acciones, inicial, objetivo, hmax, "astar",
        limite_tiempo=60, limite_nodos=300_000,
    )
    print(estadisticas)
    if plan is not None:
        for ruta in fotogramas(red_i1, plan, inicial, "i1"):
            print(ruta)
