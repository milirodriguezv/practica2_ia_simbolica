"""Experimentos E1-E6: tablas CSV y gráficas (propuesta v2, secc. 9.2).

Responsable: Eloísa (E4: Milagros).

Uso: python experimentos.py E1 [E2 ...]
Los CSV van a resultados/ y las gráficas a figuras/.
"""

import csv
import os
import statistics
import sys
import time

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo se guarda la imagen
import matplotlib.pyplot as plt

import dominio
import instancias
from heuristicas import hprec
from replanificacion import ejecutar_con_fallos

DIR_RESULTADOS = "resultados"
DIR_FIGURAS = "figuras"
SEMILLA = 0


def factor_ramificacion_efectivo(nodos, profundidad):
    """b* tal que nodos + 1 = 1 + b* + b*^2 + ... + b*^profundidad."""
    raise NotImplementedError


def e1():
    """¿Qué heurística es mejor? A* con h0, hprec, hmax, hadd y voraz con hadd en I1-I3."""
    raise NotImplementedError


def e2():
    """¿Cómo escala? G(n) con n creciente y límite de tiempo."""
    raise NotImplementedError


def e3():
    """¿Cuánto aporta la agregación? Bloques individuales frente a contadores."""
    raise NotImplementedError


# Parámetros de E4 (Milagros). Elegidos para que todo E4 tarde unos 10 min.
E4_PROBABILIDADES = (0.05, 0.1, 0.2)  # probabilidad de fallo antes de cada paso
E4_SEMILLAS = 15  # ejecuciones por configuración: semillas SEMILLA .. SEMILLA + 14
E4_TIPOS = ("linea", "central")  # averías de línea frente a disparos de central
E4_LIMITE_TIEMPO = 60  # segundos por búsqueda (plan inicial o replanificación)
E4_LIMITE_NODOS = 300_000  # nodos expandidos por búsqueda

E4_COLUMNAS = [
    "instancia", "tipo_fallo", "prob_fallo", "semilla", "resuelto", "motivo",
    "coste", "coste_plan_original", "maniobras_extra", "cargas_perdidas",
    "replanificaciones", "tiempo_replanificacion", "n_eventos", "eventos",
]
E4_COLUMNAS_RESUMEN = [
    "instancia", "tipo_fallo", "prob_fallo", "ejecuciones", "eventos_medios",
    "pct_resueltas", "pct_sin_solucion", "pct_limite", "maniobras_extra_media",
    "cargas_perdidas_media", "replanificaciones_media",
    "tiempo_replanificacion_medio",
]


def _e4_guardar_csv(ruta, filas, columnas):
    """Guarda una lista de diccionarios como CSV.

    Args:
        ruta (str): Fichero de salida.
        filas (list[dict]): Una fila por diccionario.
        columnas (list[str]): Columnas, en orden.
    """
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def _e4_fila(nombre, tipo, prob, semilla, r):
    """Convierte el resultado de ejecutar_con_fallos en una fila del CSV.

    Args:
        nombre (str): Nombre de la instancia.
        tipo (str): "linea" o "central".
        prob (float): Probabilidad de fallo.
        semilla (int): Semilla de la ejecución.
        r (dict): Resumen devuelto por ejecutar_con_fallos.

    Returns:
        dict: Fila con las columnas de E4_COLUMNAS.
    """
    return {
        "instancia": nombre,
        "tipo_fallo": tipo,
        "prob_fallo": prob,
        "semilla": semilla,
        "resuelto": r["resuelto"],
        "motivo": r["motivo"],
        "coste": r["coste"],
        "coste_plan_original": r["coste_plan_original"],
        "maniobras_extra": r["maniobras_extra"],  # None (celda vacía) si no se resolvió
        "cargas_perdidas": r["cargas_perdidas"],
        "replanificaciones": r["replanificaciones"],
        "tiempo_replanificacion": round(r["tiempo_replanificacion"], 3),
        "n_eventos": len(r["eventos"]),
        "eventos": " | ".join(r["eventos"]),
    }


def _e4_media(valores):
    """Media redondeada a 2 decimales, o None si no hay valores.

    Args:
        valores (list[float]): Números a promediar.

    Returns:
        float | None: La media, o None si la lista está vacía.
    """
    if not valores:
        return None
    return round(statistics.mean(valores), 2)


def _e4_resumen(filas):
    """Agrupa las ejecuciones por instancia, tipo de fallo y probabilidad.

    Las maniobras extra se promedian solo sobre las ejecuciones resueltas
    (en las demás no tienen sentido); el resto, sobre todas.

    Args:
        filas (list[dict]): Filas de _e4_fila.

    Returns:
        list[dict]: Una fila por grupo, con las columnas de E4_COLUMNAS_RESUMEN.
    """
    grupos = {}  # (instancia, tipo, prob) -> filas, en el orden de ejecución
    for f in filas:
        clave = (f["instancia"], f["tipo_fallo"], f["prob_fallo"])
        grupos.setdefault(clave, []).append(f)

    resumen = []
    for (nombre, tipo, prob), grupo in grupos.items():
        n = len(grupo)
        resueltas = [f for f in grupo if f["resuelto"]]
        sin_solucion = [f for f in grupo if f["motivo"] == "sin_solucion"]
        limite = [f for f in grupo if f["motivo"].startswith("limite")]
        resumen.append({
            "instancia": nombre,
            "tipo_fallo": tipo,
            "prob_fallo": prob,
            "ejecuciones": n,
            "eventos_medios": _e4_media([f["n_eventos"] for f in grupo]),
            "pct_resueltas": round(100 * len(resueltas) / n, 1),
            "pct_sin_solucion": round(100 * len(sin_solucion) / n, 1),
            "pct_limite": round(100 * len(limite) / n, 1),
            "maniobras_extra_media": _e4_media([f["maniobras_extra"] for f in resueltas]),
            "cargas_perdidas_media": _e4_media([f["cargas_perdidas"] for f in grupo]),
            "replanificaciones_media": _e4_media([f["replanificaciones"] for f in grupo]),
            "tiempo_replanificacion_medio": _e4_media(
                [f["tiempo_replanificacion"] for f in grupo]
            ),
        })
    return resumen


def _e4_figura(resumen, ruta):
    """Dibuja E4: tres paneles frente a la probabilidad de fallo.

    Paneles: % de ejecuciones resueltas, maniobras extra medias (solo
    resueltas) y cargas perdidas medias. El color distingue el tipo de fallo
    (lo que compara la hipótesis) y el trazo, la instancia.

    Args:
        resumen (list[dict]): Filas de _e4_resumen.
        ruta (str): Fichero PNG de salida.
    """
    colores = {"linea": "#2a78d6", "central": "#eb6834"}
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
            for tipo in E4_TIPOS:
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
                    color=colores[tipo], label=f"{nombre}: {nombres_tipo[tipo]}",
                )
        eje.set_title(titulo)
        eje.set_xlabel("Probabilidad de fallo antes de cada paso")
        eje.set_xticks(E4_PROBABILIDADES)
        eje.grid(alpha=0.3)
    ejes[0].set_ylim(-5, 105)
    # Una sola leyenda, debajo de los paneles, para que no tape los datos.
    lineas, etiquetas = ejes[0].get_legend_handles_labels()
    fig.legend(lineas, etiquetas, loc="lower center", ncol=4, fontsize=10)
    fig.suptitle(
        f"E4: fallos durante la ejecución (A* + hprec, {E4_SEMILLAS} semillas por punto)"
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))  # deja sitio abajo para la leyenda
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def _e4_imprimir(resumen):
    """Imprime la tabla resumen de E4 en la terminal.

    Args:
        resumen (list[dict]): Filas de _e4_resumen.
    """
    print()
    print(f"{'instancia':<11} {'fallo':<8} {'p':>5} {'ev.':>5} {'%res':>6} "
          f"{'%sin':>6} {'%lim':>5} {'extra':>6} {'perd.':>6} {'repl.':>6} {'t_repl':>7}")
    for f in resumen:
        extra = "-" if f["maniobras_extra_media"] is None else f["maniobras_extra_media"]
        print(f"{f['instancia']:<11} {f['tipo_fallo']:<8} {f['prob_fallo']:>5} "
              f"{f['eventos_medios']:>5} {f['pct_resueltas']:>6} "
              f"{f['pct_sin_solucion']:>6} {f['pct_limite']:>5} {extra:>6} "
              f"{f['cargas_perdidas_media']:>6} {f['replanificaciones_media']:>6} "
              f"{f['tiempo_replanificacion_medio']:>7}")


def e4():
    """¿Qué pasa con los fallos? Fallos aleatorios durante la ejecución.

    Hipótesis de la propuesta: los disparos de térmicas cuestan más que las
    averías de líneas.

    Diseño:
        - Instancias: I2 y I2-reserva (instancias.red_i2_reserva). I2 tiene
          oferta justa y un solo camino a cada subestación, así que casi
          todo fallo es definitivo; I2-reserva añade líneas dobles y una
          térmica de reserva para que se puedan medir recuperaciones. I3 se
          deja fuera: con bloques individuales solo A* + hadd la resuelve,
          en unos 97 s por búsqueda, demasiado para repetirla con muchas
          semillas (PLAN secc. 9.6). I1 tampoco aporta: es de juguete y sin
          redundancia, como I2.
        - Factores: tipo de fallo (solo líneas o solo centrales, para
          compararlos por separado) y probabilidad de fallo antes de cada
          paso (E4_PROBABILIDADES).
        - Semillas SEMILLA, SEMILLA + 1, ... Con la misma semilla y la misma
          probabilidad, los fallos caen en los mismos pasos para los dos
          tipos (el dado se tira igual), así la comparación es pareada.
        - Planificador: A* con hprec. Es admisible, así que el plan inicial
          y cada replanificación son óptimos y las maniobras extra se miden
          contra el mínimo; y es la configuración óptima más rápida con
          bloques individuales en I2 (PLAN secc. 2).
        - Versión individual (dominio.problema): al disparar una central hay
          que saber qué cargas usaban sus bloques.
        - Límites por búsqueda: E4_LIMITE_TIEMPO s y E4_LIMITE_NODOS nodos.

    Salidas: resultados/e4.csv (una fila por ejecución),
    resultados/e4_resumen.csv (una fila por instancia, tipo y probabilidad)
    y figuras/e4.png.
    """
    os.makedirs(DIR_RESULTADOS, exist_ok=True)
    os.makedirs(DIR_FIGURAS, exist_ok=True)
    redes = {"I2": instancias.red_i2(), "I2-reserva": instancias.red_i2_reserva()}

    filas = []
    inicio = time.perf_counter()
    for nombre, red in redes.items():
        acciones, inicial, objetivo = dominio.problema(red)
        for tipo in E4_TIPOS:
            for prob in E4_PROBABILIDADES:
                t0 = time.perf_counter()
                resueltas = 0
                for i in range(E4_SEMILLAS):
                    semilla = SEMILLA + i
                    r = ejecutar_con_fallos(
                        red, acciones, inicial, objetivo, hprec, "astar",
                        prob_fallo=prob, semilla=semilla,
                        limite_tiempo=E4_LIMITE_TIEMPO,
                        limite_nodos=E4_LIMITE_NODOS,
                        tipos_fallo=(tipo,),
                    )
                    filas.append(_e4_fila(nombre, tipo, prob, semilla, r))
                    resueltas += r["resuelto"]
                print(f"E4 {nombre}, fallos de {tipo}, p = {prob}: "
                      f"{resueltas}/{E4_SEMILLAS} resueltas "
                      f"({time.perf_counter() - t0:.0f} s)", flush=True)

    _e4_guardar_csv(os.path.join(DIR_RESULTADOS, "e4.csv"), filas, E4_COLUMNAS)
    resumen = _e4_resumen(filas)
    _e4_guardar_csv(
        os.path.join(DIR_RESULTADOS, "e4_resumen.csv"), resumen, E4_COLUMNAS_RESUMEN
    )
    _e4_figura(resumen, os.path.join(DIR_FIGURAS, "e4.png"))
    _e4_imprimir(resumen)
    print(f"\nE4 terminado en {time.perf_counter() - inicio:.0f} s.")


def e5():
    """(Opcional) ¿Dónde está lo difícil? Variar el margen de generación en G(n)."""
    raise NotImplementedError


def e6():
    """(Opcional) ¿El plan con menos maniobras es el más rápido? Programar I2/I3."""
    raise NotImplementedError


EXPERIMENTOS = {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6}

if __name__ == "__main__":
    for nombre in sys.argv[1:] or ["E1", "E2", "E3"]:
        EXPERIMENTOS[nombre.upper()]()
