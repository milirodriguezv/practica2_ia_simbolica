"""Figuras de los experimentos (matplotlib).

Cada figura_eN recibe las filas que calcula experimentos.py y guarda
figuras/eN.png. Las instancias, configuraciones y demás valores de los ejes
se leen de las propias filas, en su orden de aparición.
"""

import os

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo se guarda la imagen
import matplotlib.pyplot as plt

DIR_FIGURAS = "figuras"

# Un color y un marcador fijos por configuración de búsqueda, por versión del
# dominio y por tipo de fallo: los mismos en todas las figuras.
COLORES = {
    "A* + h0": "#2a78d6",
    "A* + hprec": "#eb6834",
    "A* + hmax": "#1baf7a",
    "A* + hadd": "#eda100",
    "voraz + hadd": "#e87ba4",
    "individual": "#eb6834",
    "agregada": "#2a78d6",
    "linea": "#2a78d6",
    "central": "#eb6834",
}
MARCADORES = {
    "A* + h0": "o",
    "A* + hprec": "s",
    "A* + hmax": "^",
    "A* + hadd": "D",
    "voraz + hadd": "v",
}
# Familias de redes de E5: colores distintos de los de las configuraciones.
COLORES_FAMILIA = ("#008300", "#6250d6", "#e34948")
MARCADORES_FAMILIA = ("o", "s", "^")
GRIS = "#52514e"


def _valores(filas, columna):
    """Devuelve los valores distintos de una columna, en orden de aparición.

    Args:
        filas (list[dict]): Filas de una tabla.
        columna (str): Nombre de la columna.

    Returns:
        list: Valores sin repetir.
    """
    return list(dict.fromkeys(f[columna] for f in filas))


def guardar_figura(fig, nombre):
    """Guarda la figura en figuras/<nombre>.png y la cierra.

    Args:
        fig (matplotlib.figure.Figure): Figura terminada.
        nombre (str): Nombre del fichero, sin extensión.
    """
    os.makedirs(DIR_FIGURAS, exist_ok=True)
    fig.savefig(os.path.join(DIR_FIGURAS, nombre + ".png"), dpi=150)
    plt.close(fig)


def preparar_eje(eje, titulo, etiqueta_x=None, logaritmico=False):
    """Aplica el estilo común a un panel.

    Args:
        eje (matplotlib.axes.Axes): Panel.
        titulo (str): Título del panel.
        etiqueta_x (str | None): Etiqueta del eje horizontal.
        logaritmico (bool): Si el eje vertical es logarítmico.
    """
    eje.set_title(titulo, fontsize=11)
    if etiqueta_x:
        eje.set_xlabel(etiqueta_x)
    if logaritmico:
        eje.set_yscale("log")
    eje.grid(alpha=0.3, axis="y")
    eje.set_axisbelow(True)
    eje.spines[["top", "right"]].set_visible(False)


def _barras_e1(eje, busquedas, columna, titulo, con_etiquetas):
    """Dibuja un panel de barras por instancia y configuración.

    Las barras rayadas son búsquedas que no terminaron en el límite de
    tiempo. Con con_etiquetas, encima de cada barra resuelta se escriben las
    maniobras de más sobre el óptimo, si las hay.

    Args:
        eje (matplotlib.axes.Axes): Panel.
        busquedas (list[dict]): Filas de búsqueda de E1.
        columna (str): 'expandidos' o 'tiempo'.
        titulo (str): Título del panel.
        con_etiquetas (bool): Si se anotan las maniobras de más.
    """
    instancias = _valores(busquedas, "instancia")
    ancho = 0.16
    minimo = 1 if columna == "expandidos" else 0.001
    for j, configuracion in enumerate(_valores(busquedas, "configuracion")):
        for i, nombre in enumerate(instancias):
            r = next(f for f in busquedas if f["instancia"] == nombre
                     and f["configuracion"] == configuracion)
            x = i + (j - 2) * ancho
            valor = max(minimo, r[columna])
            resuelto = r["resultado"] == "resuelto"
            eje.bar(
                x, valor, ancho * 0.88,
                color=COLORES[configuracion] if resuelto else "none",
                edgecolor=COLORES[configuracion], linewidth=1.2,
                hatch=None if resuelto else "///",
                label=configuracion if i == 0 else None,
            )
            if not resuelto:
                texto = "sin\nresolver"
            elif con_etiquetas and r["maniobras_de_mas"]:
                texto = f"+{r['maniobras_de_mas']}"
            else:
                texto = ""
            if texto:
                eje.text(x, valor * 1.15, texto, ha="center", va="bottom",
                         fontsize=7.5, color=GRIS)
    optimos = {f["instancia"]: f["optimo"] for f in busquedas}
    eje.set_xticks(range(len(instancias)))
    eje.set_xticklabels([f"{n}\nóptimo: {optimos[n]}" for n in instancias])
    preparar_eje(eje, titulo, logaritmico=True)
    eje.margins(y=0.25)


def figura_e1(busquedas, precision):
    """Dibuja E1: esfuerzo de búsqueda y precisión de las heurísticas.

    Paneles: nodos expandidos y tiempo por instancia y configuración (escala
    logarítmica), y precisión h / h* de cada heurística, en todos los
    estados y solo en los estados trampa, en la mayor instancia cuyo espacio
    de estados cabe entero.

    Args:
        busquedas (list[dict]): Filas de búsqueda de E1.
        precision (list[dict]): Filas de precisión de E1.
    """
    fig, (eje_nodos, eje_tiempo, eje_precision) = plt.subplots(
        1, 3, figsize=(17, 5.4), gridspec_kw={"width_ratios": [1.25, 1.25, 1]}
    )
    _barras_e1(eje_nodos, busquedas, "expandidos",
               "Nodos expandidos (escala logarítmica)", con_etiquetas=True)
    _barras_e1(eje_tiempo, busquedas, "tiempo",
               "Tiempo de búsqueda (s; escala logarítmica)", con_etiquetas=False)

    nombre = precision[-1]["instancia"]
    filas = [f for f in precision if f["instancia"] == nombre]
    series = [
        ("precision_media", "todos los estados", "#2a78d6"),
        ("precision_en_trampas", "solo estados trampa", "#eb6834"),
    ]
    for j, (columna, etiqueta, color) in enumerate(series):
        for i, f in enumerate(filas):
            if f[columna] is None:
                continue
            x = i + (j - 0.5) * 0.36
            eje_precision.bar(x, f[columna], 0.33, color=color,
                              label=etiqueta if i == 0 else None)
            eje_precision.text(x, f[columna] + 0.02, f"{f[columna]:.2f}",
                               ha="center", va="bottom", fontsize=9, color=GRIS)
    eje_precision.axhline(1, color=GRIS, linewidth=1, linestyle="--")
    eje_precision.text(-0.45, 1.02, "h = coste real", ha="left",
                       va="bottom", fontsize=8.5, color=GRIS)
    eje_precision.set_xticks(range(len(filas)))
    eje_precision.set_xticklabels([f["heuristica"] for f in filas])
    eje_precision.set_ylim(0, 1.4)
    preparar_eje(
        eje_precision,
        f"Precisión h / h* en {nombre} ({filas[0]['estados']} estados, "
        f"{filas[0]['estados_trampa']} trampa)",
    )
    eje_precision.legend(loc="upper left", fontsize=9, frameon=False)

    lineas, nombres = eje_nodos.get_legend_handles_labels()
    fig.legend(lineas, nombres, loc="lower center", ncol=5, fontsize=10, frameon=False)
    fig.suptitle("E1: heurísticas en un dominio con recursos que se gastan "
                 "(versión agregada; +n = maniobras de más sobre el óptimo)")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    guardar_figura(fig, "e1")


def figura_e2(resumen, limite_tiempo, margen):
    """Dibuja E2: redes resueltas y tiempo frente al tamaño.

    Args:
        resumen (list[dict]): Filas del resumen de E2.
        limite_tiempo (float): Segundos de límite por búsqueda.
        margen (float): Margen oferta / demanda de las redes.
    """
    tamanos = _valores(resumen, "subestaciones")
    fig, (eje_resueltas, eje_tiempo) = plt.subplots(1, 2, figsize=(13, 5))
    for configuracion in _valores(resumen, "configuracion"):
        filas = [f for f in resumen if f["configuracion"] == configuracion]
        estilo = {"color": COLORES[configuracion], "marker": MARCADORES[configuracion],
                  "markersize": 7, "linewidth": 2, "label": configuracion}
        eje_resueltas.plot([f["subestaciones"] for f in filas],
                           [f["pct_resueltas"] for f in filas], **estilo)
        con_tiempo = [f for f in filas if f["tiempo_mediana"] is not None]
        eje_tiempo.plot([f["subestaciones"] for f in con_tiempo],
                        [max(f["tiempo_mediana"], 0.001) for f in con_tiempo], **estilo)

    eje_resueltas.set_ylim(-5, 105)
    eje_tiempo.axhline(limite_tiempo, color=GRIS, linewidth=1, linestyle="--")
    eje_tiempo.text(tamanos[0], limite_tiempo * 1.15, "límite de tiempo",
                    fontsize=8.5, color=GRIS)
    etiquetas = []
    for n in tamanos:
        zonas = next(f["zonas"] for f in resumen if f["subestaciones"] == n)
        etiquetas.append(f"{n}\n{zonas} zona{'s' if zonas > 1 else ''}")
    for eje in (eje_resueltas, eje_tiempo):
        eje.set_xticks(tamanos)
        eje.set_xticklabels(etiquetas)
    preparar_eje(eje_resueltas, f"Redes resueltas en {limite_tiempo} s (%)",
                 etiqueta_x="Subestaciones de la red")
    preparar_eje(eje_tiempo, "Tiempo de las resueltas (mediana, s; escala logarítmica)",
                 etiqueta_x="Subestaciones de la red", logaritmico=True)
    lineas, nombres = eje_resueltas.get_legend_handles_labels()
    fig.legend(lineas, nombres, loc="lower center", ncol=5, fontsize=10, frameon=False)
    fig.suptitle(f"E2: escalabilidad en redes G(n) (versión agregada, margen "
                 f"{margen}, {resumen[0]['redes']} redes por tamaño)")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    guardar_figura(fig, "e2")


def _barras_e3(eje, filas, columna, titulo, tope_estados):
    """Dibuja un panel de barras individual frente a agregada por instancia.

    Encima de cada pareja se escribe cuántas veces se reduce. Una barra
    rayada indica que no se llegó al final (tope de estados o de tiempo).

    Args:
        eje (matplotlib.axes.Axes): Panel.
        filas (list[dict]): Filas por instancia de E3.
        columna (str): 'estados_alcanzables' o 'expandidos'.
        titulo (str): Título del panel.
        tope_estados (int): Tope con el que se contaron los estados.
    """
    instancias = _valores(filas, "instancia")
    for i, nombre in enumerate(instancias):
        valores = {}
        for j, version in enumerate(_valores(filas, "version")):
            f = next(f for f in filas
                     if f["instancia"] == nombre and f["version"] == version)
            if columna == "estados_alcanzables":
                completo = f[columna] is not None
                valor = f[columna] if completo else tope_estados
            else:
                completo = f["resultado"] == "resuelto"
                valor = f[columna]
            x = i + (j - 0.5) * 0.36
            eje.bar(x, valor, 0.33,
                    color=COLORES[version] if completo else "none",
                    edgecolor=COLORES[version], linewidth=1.2,
                    hatch=None if completo else "///",
                    label=version if i == 0 else None)
            valores[version] = valor if completo else None
            if not completo:
                texto = "más de\n" if columna == "estados_alcanzables" else "sin resolver\n"
                eje.text(x, valor * 1.15, f"{texto}{valor:,}".replace(",", " "),
                         ha="center", va="bottom", fontsize=7.5, color=GRIS)
        if valores["individual"] and valores["agregada"]:
            factor = valores["individual"] / valores["agregada"]
            eje.text(i, max(valores.values()) * 1.3, f"÷ {factor:.0f}",
                     ha="center", va="bottom", fontsize=10, fontweight="bold")
    eje.set_xticks(range(len(instancias)))
    eje.set_xticklabels(instancias)
    preparar_eje(eje, titulo, logaritmico=True)
    eje.margins(y=0.3)


def figura_e3(filas, familia, configuracion, limite_tiempo, tope_estados):
    """Dibuja E3: tres paneles en escala logarítmica.

    Paneles: estados alcanzables por instancia, nodos expandidos por la
    búsqueda, y estados alcanzables de la familia del juguete según el
    número de bloques de la térmica.

    Args:
        filas (list[dict]): Filas por instancia de E3.
        familia (list[dict]): Filas de la familia del juguete.
        configuracion (str): Configuración de búsqueda usada.
        limite_tiempo (float): Segundos de límite por búsqueda.
        tope_estados (int): Tope con el que se contaron los estados.
    """
    fig, (eje_estados, eje_nodos, eje_familia) = plt.subplots(1, 3, figsize=(15, 5))
    _barras_e3(eje_estados, filas, "estados_alcanzables", "Estados alcanzables",
               tope_estados)
    _barras_e3(eje_nodos, filas, "expandidos",
               f"Nodos expandidos ({configuracion}, límite {limite_tiempo} s)",
               tope_estados)
    eje_estados.legend(loc="upper left", fontsize=9, frameon=False)

    for version, columna in (("individual", "estados_individual"),
                             ("agregada", "estados_agregada")):
        puntos = [(f["bloques_termica"], f[columna]) for f in familia if f[columna]]
        eje_familia.plot([x for x, _ in puntos], [y for _, y in puntos],
                         marker="o", markersize=7, linewidth=2,
                         color=COLORES[version], label=version)
    for f in familia:
        if f["factor_reduccion"]:
            eje_familia.annotate(
                f"÷ {f['factor_reduccion']:.{1 if f['factor_reduccion'] < 10 else 0}f}",
                (f["bloques_termica"], f["estados_individual"]),
                textcoords="offset points", xytext=(0, 9), ha="center",
                fontsize=9, color=GRIS,
            )
    eje_familia.set_xticks([f["bloques_termica"] for f in familia])
    eje_familia.margins(y=0.12)  # sitio para la etiqueta del último punto
    preparar_eje(eje_familia, "Juguete con k bloques en la térmica: estados",
                 etiqueta_x="k (bloques intercambiables de la térmica)",
                 logaritmico=True)
    eje_familia.legend(loc="upper left", fontsize=9, frameon=False)

    fig.suptitle("E3: bloques individuales frente a contadores por zona "
                 "(escala logarítmica; ÷ n = veces que se reduce)")
    fig.tight_layout()
    guardar_figura(fig, "e3")


def figura_e4(resumen):
    """Dibuja E4: tres paneles frente a la probabilidad de fallo.

    Paneles: % de ejecuciones resueltas, maniobras extra medias (solo
    resueltas) y cargas perdidas medias. El color distingue el tipo de fallo
    (lo que compara la hipótesis) y el trazo, la instancia.

    Args:
        resumen (list[dict]): Filas del resumen de E4.
    """
    nombres_tipo = {"linea": "avería de línea", "central": "disparo de central"}
    trazos = {"I2": ("--", "s"), "I2-reserva": ("-", "o")}
    paneles = [
        ("pct_resueltas", "Ejecuciones resueltas (%)"),
        ("maniobras_extra_media", "Maniobras extra (media, resueltas)"),
        ("cargas_perdidas_media", "Cargas perdidas (media)"),
    ]

    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.8))
    for eje, (columna, titulo) in zip(ejes, paneles):
        for nombre, (trazo, marcador) in trazos.items():
            for tipo in _valores(resumen, "tipo_fallo"):
                puntos = [
                    (f["prob_fallo"], f[columna])
                    for f in resumen
                    if f["instancia"] == nombre and f["tipo_fallo"] == tipo
                    and f[columna] is not None
                ]
                if not puntos:
                    continue
                eje.plot(
                    [x for x, _ in puntos], [y for _, y in puntos],
                    linestyle=trazo, marker=marcador, markersize=8, linewidth=2,
                    color=COLORES[tipo], label=f"{nombre}: {nombres_tipo[tipo]}",
                )
        eje.set_xticks(_valores(resumen, "prob_fallo"))
        preparar_eje(eje, titulo,
                     etiqueta_x="Probabilidad de fallo antes de cada paso")
    ejes[0].set_ylim(-5, 105)
    # Una sola leyenda, debajo de los paneles, para que no tape los datos.
    lineas, etiquetas = ejes[0].get_legend_handles_labels()
    fig.legend(lineas, etiquetas, loc="lower center", ncol=4, fontsize=10,
               frameon=False)
    fig.suptitle(f"E4: fallos durante la ejecución (A* + hprec, "
                 f"{resumen[0]['ejecuciones']} semillas por punto)")
    fig.tight_layout(rect=(0, 0.08, 1, 1))  # deja sitio abajo para la leyenda
    guardar_figura(fig, "e4")


def figura_e5(resumen, configuracion_nodos):
    """Dibuja E5: tres paneles frente a los bloques sobrantes.

    Paneles: % de estados trampa del espacio de estados, maniobras que se
    ahorra el plan óptimo respecto a la oferta justa y nodos expandidos por
    configuracion_nodos. Una línea por familia de redes. La holgura -1 solo
    aparece en el panel de nodos: no hay solución, así que no hay ni trampas
    ni plan.

    Args:
        resumen (list[dict]): Filas del resumen de E5.
        configuracion_nodos (str): Configuración del panel de nodos.
    """
    holguras = _valores(resumen, "holgura")
    posiciones = {h: i for i, h in enumerate(holguras)}
    etiquetas = []
    for h in holguras:
        if h < 0:
            etiquetas.append(f"{h}\n(imposible)")
        elif h == 0:
            etiquetas.append("0\n(justa)")
        else:
            etiquetas.append(f"+{h}")
    paneles = [
        ("pct_trampa_medio", "A* + hprec", "Estados trampa: hay que deslastrar (%)", False),
        ("ahorro_medio", "A* + hprec",
         "Maniobras que ahorra el plan óptimo frente a la oferta justa", False),
        ("expandidos_mediana", configuracion_nodos,
         f"Nodos expandidos ({configuracion_nodos}; escala logarítmica)", True),
    ]

    fig, ejes = plt.subplots(1, 3, figsize=(16, 5.4))
    for eje, (columna, configuracion, titulo, con_negativa) in zip(ejes, paneles):
        for i, familia in enumerate(_valores(resumen, "familia")):
            filas = [f for f in resumen if f["familia"] == familia
                     and f["configuracion"] == configuracion]
            puntos = [
                (posiciones[f["holgura"]], f[columna]) for f in filas
                if f[columna] is not None and (con_negativa or f["holgura"] >= 0)
            ]
            redes = filas[0]["redes"]
            medias = f" (media de {redes})" if redes > 1 else ""
            eje.plot([x for x, _ in puntos], [y for _, y in puntos],
                     marker=MARCADORES_FAMILIA[i], markersize=7, linewidth=2,
                     color=COLORES_FAMILIA[i], label=familia + medias)
        eje.set_xticks(range(len(holguras)))
        eje.set_xticklabels(etiquetas)
        eje.set_xlim(-0.4, len(holguras) - 0.6)
        preparar_eje(eje, titulo, etiqueta_x="Bloques sobrantes (oferta − demanda)",
                     logaritmico=con_negativa)
    ejes[0].set_ylim(bottom=0)
    ejes[1].set_ylim(bottom=0)
    lineas, nombres = ejes[0].get_legend_handles_labels()
    fig.legend(lineas, nombres, loc="lower center", ncol=3, fontsize=10, frameon=False)
    fig.suptitle("E5: qué cambia al tener bloques de sobra (versión agregada)")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    guardar_figura(fig, "e5")
