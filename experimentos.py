"""Experimentos E1-E5: ejecutan las búsquedas y guardan las tablas.

Responsable: Eloísa (E4: Milagros).

Uso: python experimentos.py E1 [E2 ...]
Las tablas van a resultados/ (CSV) y las gráficas a figuras/ (las dibuja
figuras.py).

Cada experimento responde a una pregunta sobre este dominio en concreto, no
sobre la búsqueda en general. Lo que lo hace difícil es que la generación es
un recurso que se gasta, así que además de nodos y tiempo se miden los
estados trampa y los estados sin salida (definidos en analisis.py) y los
deslastres del plan: cuántas veces el plan devuelto deshace trabajo.

Tiempos orientativos (portátil): E1, E3 y E5 unos 3 min cada uno, E2 unos
15 min y E4 unos 8 min.
"""

import csv
import math
import os
import statistics
import sys
import time

import dominio
import dominio_agregado
import figuras
import instancias
from analisis import clasificar_estados, espacio_de_estados
from heuristicas import h0, hadd, hmax, hprec
from planificador import buscar, validar_plan
from replanificacion import ejecutar_con_fallos

DIR_RESULTADOS = "resultados"
SEMILLA = 0

# Configuraciones de búsqueda que se comparan: etiqueta -> (modo, heurística).
CONFIGURACIONES = {
    "A* + h0": ("astar", h0),
    "A* + hprec": ("astar", hprec),
    "A* + hmax": ("astar", hmax),
    "A* + hadd": ("astar", hadd),
    "voraz + hadd": ("voraz", hadd),
}
# Las tres primeras usan una heurística admisible: su coste es el óptimo.
ADMISIBLES = ("A* + h0", "A* + hprec", "A* + hmax")


def factor_ramificacion_efectivo(nodos, profundidad):
    """Calcula el factor de ramificación efectivo b*.

    Es el b tal que un árbol uniforme de esa profundidad tendría los mismos
    nodos: nodos + 1 = 1 + b + b^2 + ... + b^profundidad. Se resuelve por
    bisección, porque el lado derecho crece con b.

    Args:
        nodos (int): Nodos generados por la búsqueda.
        profundidad (int): Número de acciones del plan encontrado.

    Returns:
        float | None: b*, o None si no hay plan (profundidad 0).
    """
    if profundidad <= 0 or nodos <= 0:
        return None

    def total(b):
        """Nodos de un árbol uniforme con factor b: 1 + b + ... + b^profundidad."""
        return sum(b**i for i in range(profundidad + 1))

    bajo, alto = 0.0, float(max(2, nodos))
    for _ in range(100):
        medio = (bajo + alto) / 2
        if total(medio) < nodos + 1:
            bajo = medio
        else:
            alto = medio
    return round((bajo + alto) / 2, 3)


def _guardar_csv(nombre, filas):
    """Guarda una lista de diccionarios en resultados/<nombre>.csv.

    Args:
        nombre (str): Nombre del fichero, sin extensión.
        filas (list[dict]): Una fila por diccionario; las columnas son las
            claves del primero.
    """
    os.makedirs(DIR_RESULTADOS, exist_ok=True)
    ruta = os.path.join(DIR_RESULTADOS, nombre + ".csv")
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


def _mediana(valores):
    """Mediana redondeada a 3 decimales, o None si no hay valores.

    Args:
        valores (list[float]): Números.

    Returns:
        float | None: La mediana.
    """
    return round(statistics.median(valores), 3) if valores else None


def _media(valores):
    """Media redondeada a 2 decimales de los valores que no son None.

    Args:
        valores (iterable): Números o None.

    Returns:
        float | None: La media, o None si no queda ningún valor.
    """
    validos = [v for v in valores if v is not None]
    return round(statistics.mean(validos), 2) if validos else None


def _ejecutar(acciones, inicial, objetivo, configuracion, limite_tiempo):
    """Lanza una búsqueda y resume lo que interesa de ella.

    Args:
        acciones (list[Accion]): Acciones instanciadas.
        inicial (frozenset[str]): Estado inicial.
        objetivo (frozenset[str]): Átomos del objetivo.
        configuracion (str): Clave de CONFIGURACIONES.
        limite_tiempo (float): Segundos máximos de búsqueda.

    Returns:
        dict: 'resultado' ("resuelto", "sin_solucion" o "limite_tiempo"),
        'coste', 'longitud', 'deslastres', 'expandidos', 'generados',
        'tiempo' y 'plan_valido'. Sin plan, coste, longitud, deslastres y
        plan_valido valen None.
    """
    modo, heuristica = CONFIGURACIONES[configuracion]
    plan, est = buscar(
        acciones, inicial, objetivo, heuristica, modo, limite_tiempo=limite_tiempo
    )
    resumen = {
        "resultado": est["resultado"],
        "coste": None,
        "longitud": None,
        "deslastres": None,
        "expandidos": est["expandidos"],
        "generados": est["generados"],
        "tiempo": round(est["tiempo"], 3),
        "plan_valido": None,
    }
    if plan is not None:
        valido, coste = validar_plan(plan, inicial, objetivo)
        resumen["coste"] = coste
        resumen["longitud"] = len(plan)
        resumen["deslastres"] = sum(a.nombre.startswith("Deslastrar") for a in plan)
        resumen["plan_valido"] = valido
    return resumen


# ---------------------------------------------------------------------------
# E1: qué heurística guía mejor cuando los recursos se gastan
# ---------------------------------------------------------------------------

E1_INSTANCIAS = ("I1", "I2", "I3")
E1_LIMITE_TIEMPO = 180  # segundos por búsqueda
E1_EXACTAS = ("I1", "I2", "I3")  # su espacio de estados agregado cabe entero
E1_TOPE_ESTADOS = 200_000
E1_HEURISTICAS = {"hprec": hprec, "hmax": hmax, "hadd": hadd}


def _e1_busquedas():
    """Ejecuta cada configuración en cada instancia (versión agregada).

    Returns:
        list[dict]: Una fila por instancia y configuración. Además de lo que
        devuelve _ejecutar: 'optimo' (coste de las configuraciones
        admisibles), 'maniobras_de_mas' respecto al óptimo, 'h_inicial',
        'precision_inicial' (h_inicial / óptimo), 'ms_por_nodo' y
        'ramificacion_efectiva'.
    """
    filas = []
    for nombre in E1_INSTANCIAS:
        acciones, inicial, objetivo = instancias.cargar(nombre, agregada=True)
        grupo = []
        for configuracion in CONFIGURACIONES:
            r = _ejecutar(acciones, inicial, objetivo, configuracion, E1_LIMITE_TIEMPO)
            heuristica = CONFIGURACIONES[configuracion][1]
            r = {"instancia": nombre, "configuracion": configuracion, **r}
            r["h_inicial"] = heuristica(inicial, objetivo, acciones)
            r["ms_por_nodo"] = round(1000 * r["tiempo"] / max(1, r["expandidos"]), 3)
            r["ramificacion_efectiva"] = factor_ramificacion_efectivo(
                r["generados"], r["longitud"] or 0
            )
            grupo.append(r)
            print(f"E1 {nombre}, {configuracion}: {r['resultado']}, coste "
                  f"{r['coste']}, {r['expandidos']} nodos, {r['tiempo']:.1f} s",
                  flush=True)

        costes = [r["coste"] for r in grupo
                  if r["configuracion"] in ADMISIBLES and r["coste"] is not None]
        optimo = min(costes) if costes else None
        for r in grupo:
            r["optimo"] = optimo
            hay = optimo is not None and r["coste"] is not None
            r["maniobras_de_mas"] = r["coste"] - optimo if hay else None
            r["precision_inicial"] = (
                round(r["h_inicial"] / optimo, 2) if optimo else None
            )
        filas += grupo
    return filas


def _e1_precision():
    """Compara cada heurística con el coste real en todos los estados.

    En las instancias de E1_EXACTAS, cuyo espacio de estados agregado cabe
    entero, así que h* se calcula exactamente.

    Returns:
        list[dict]: Una fila por instancia y heurística con:
            - 'precision_media': media de h / h* (1 = exacta) en los estados
              que alcanzan el objetivo.
            - 'pct_sobrestima': % de esos estados con h > h* (si es mayor
              que 0, la heurística no es admisible).
            - 'precision_en_trampas': media de h / h* en los estados trampa.
            - 'pct_sin_salida_detectados': % de estados sin salida en los
              que la heurística vale infinito (los poda).
    """
    filas = []
    for nombre in E1_EXACTAS:
        acciones, inicial, objetivo = instancias.cargar(nombre, agregada=True)
        estados, arcos = espacio_de_estados(acciones, inicial, E1_TOPE_ESTADOS)
        if estados is None:
            print(f"E1 {nombre}: el espacio de estados supera el tope; se omite.")
            continue
        real, trampas, sin_salida = clasificar_estados(estados, arcos, objetivo)
        vivos = [i for i in range(len(estados)) if 0 < real[i] < math.inf]

        for etiqueta, heuristica in E1_HEURISTICAS.items():
            h = [heuristica(estado, objetivo, acciones) for estado in estados]
            fila = {
                "instancia": nombre,
                "heuristica": etiqueta,
                "estados": len(estados),
                "estados_trampa": len(trampas),
                "estados_sin_salida": len(sin_salida),
                "precision_media": round(
                    statistics.mean(h[i] / real[i] for i in vivos), 3
                ),
                "pct_sobrestima": round(
                    100 * sum(h[i] > real[i] for i in vivos) / len(vivos), 1
                ),
                "precision_en_trampas": (
                    round(statistics.mean(h[i] / real[i] for i in trampas), 3)
                    if trampas else None
                ),
                "pct_sin_salida_detectados": (
                    round(100 * sum(h[i] == math.inf for i in sin_salida)
                          / len(sin_salida), 1)
                    if sin_salida else None
                ),
            }
            filas.append(fila)
            print(f"E1 {nombre}, {etiqueta}: h/h* = {fila['precision_media']} "
                  f"(en trampas {fila['precision_en_trampas']}), sobrestima en "
                  f"{fila['pct_sobrestima']} %, detecta "
                  f"{fila['pct_sin_salida_detectados']} % de los sin salida",
                  flush=True)
    return filas


def e1():
    """¿Qué heurística guía mejor cuando los recursos se gastan?

    Hipótesis de la propuesta: las heurísticas admisibles dan el plan óptimo;
    hadd expande muchos menos nodos, pero puede dar planes más largos.

    Diseño, en dos partes:
        1. Búsqueda. A* con h0, hprec, hmax y hadd, y voraz con hadd, en I1,
           I2 e I3 (versión agregada, que es la principal). Además de nodos
           y tiempo, se mide lo que importa en este dominio: maniobras de
           más sobre el óptimo, deslastres del plan (si la búsqueda cayó en
           una trampa y tuvo que deshacer) y milisegundos por nodo (hmax y
           hadd resuelven un problema relajado en cada estado).
        2. Precisión. El espacio de estados agregado de las tres cabe
           entero, así que se calcula el coste real h* de todos los estados y se compara con
           cada heurística: en general, en los estados trampa y en los
           estados sin salida. Explica el porqué de la parte 1: las
           heurísticas que ignoran las listas de eliminación no ven que un
           bloque ya está gastado.

    Salidas: resultados/e1_busqueda.csv, resultados/e1_precision.csv y
    figuras/e1.png.
    """
    inicio = time.perf_counter()
    busquedas = _e1_busquedas()
    _guardar_csv("e1_busqueda", busquedas)
    precision = _e1_precision()
    _guardar_csv("e1_precision", precision)
    figuras.figura_e1(busquedas, precision)
    print(f"\nE1 terminado en {time.perf_counter() - inicio:.0f} s.")


# ---------------------------------------------------------------------------
# E2: hasta qué tamaño de red llega cada configuración
# ---------------------------------------------------------------------------

E2_TAMANOS = (2, 4, 6, 8, 10, 12, 14)  # subestaciones; una zona cada 4
E2_SEMILLAS = 5  # redes por tamaño: semillas SEMILLA .. SEMILLA + 4
E2_MARGEN = 1.2  # oferta / demanda
E2_LIMITE_TIEMPO = 10  # segundos por búsqueda


def _e2_ejecuciones():
    """Resuelve redes G(n) de tamaño creciente con cada configuración.

    Returns:
        list[dict]: Una fila por tamaño, semilla y configuración, con el
        tamaño real de la red (zonas, cargas, bloques, acciones) y el
        resultado de _ejecutar.
    """
    filas = []
    for n in E2_TAMANOS:
        t0 = time.perf_counter()
        for i in range(E2_SEMILLAS):
            semilla = SEMILLA + i
            red = instancias.red_generada(n, margen=E2_MARGEN, semilla=semilla)
            acciones, inicial, objetivo = dominio_agregado.problema_agregado(red)
            for configuracion in CONFIGURACIONES:
                r = _ejecutar(acciones, inicial, objetivo, configuracion,
                              E2_LIMITE_TIEMPO)
                filas.append({
                    "subestaciones": n,
                    "semilla": semilla,
                    "zonas": len(red.zonas),
                    "cargas": len(red.cargas),
                    "bloques": sum(c[2] for c in red.centrales.values()),
                    "acciones": len(acciones),
                    "configuracion": configuracion,
                    **r,
                })
        print(f"E2 n = {n}: {E2_SEMILLAS} redes "
              f"({time.perf_counter() - t0:.0f} s)", flush=True)
    return filas


def _e2_resumen(filas):
    """Agrupa las ejecuciones por tamaño y configuración.

    Las medianas se calculan solo sobre las ejecuciones resueltas. Las
    maniobras de más se miden contra el mejor coste admisible de la misma
    red, cuando alguna configuración admisible la resolvió.

    Args:
        filas (list[dict]): Filas de _e2_ejecuciones.

    Returns:
        list[dict]: Una fila por tamaño y configuración.
    """
    optimo = {}  # (n, semilla) -> coste óptimo, si se conoce
    for f in filas:
        if f["configuracion"] in ADMISIBLES and f["coste"] is not None:
            clave = (f["subestaciones"], f["semilla"])
            optimo[clave] = min(f["coste"], optimo.get(clave, math.inf))

    resumen = []
    for n in E2_TAMANOS:
        for configuracion in CONFIGURACIONES:
            grupo = [f for f in filas if f["subestaciones"] == n
                     and f["configuracion"] == configuracion]
            resueltas = [f for f in grupo if f["resultado"] == "resuelto"]
            de_mas = [
                f["coste"] - optimo[(n, f["semilla"])]
                for f in resueltas if (n, f["semilla"]) in optimo
            ]
            resumen.append({
                "subestaciones": n,
                "zonas": grupo[0]["zonas"],
                "cargas_media": statistics.mean(f["cargas"] for f in grupo),
                "configuracion": configuracion,
                "redes": len(grupo),
                "pct_resueltas": round(100 * len(resueltas) / len(grupo), 1),
                "expandidos_mediana": _mediana([f["expandidos"] for f in resueltas]),
                "tiempo_mediana": _mediana([f["tiempo"] for f in resueltas]),
                "maniobras_de_mas_media": (
                    round(statistics.mean(de_mas), 2) if de_mas else None
                ),
                "redes_con_optimo_conocido": len(de_mas),
            })
    return resumen


def e2():
    """¿Hasta qué tamaño de red llega cada configuración?

    Hipótesis de la propuesta: crecimiento exponencial; h0 y hprec dejan de
    resolver antes.

    Diseño:
        - Redes G(n) del generador, con n subestaciones y una zona cada 4,
          así que al crecer n aparecen las maniobras de acoplamiento.
        - E2_SEMILLAS redes por tamaño y las cinco configuraciones sobre
          cada red (comparación pareada), en la versión agregada.
        - Límite de E2_LIMITE_TIEMPO s por búsqueda: no resolver a tiempo es
          un resultado, no un fallo. Se mide el porcentaje de redes
          resueltas y, de las resueltas, nodos y tiempo.
        - Maniobras de más de las configuraciones no admisibles, en las
          redes donde alguna admisible dio el óptimo.

    Salidas: resultados/e2.csv (una fila por ejecución),
    resultados/e2_resumen.csv y figuras/e2.png.
    """
    inicio = time.perf_counter()
    filas = _e2_ejecuciones()
    _guardar_csv("e2", filas)
    resumen = _e2_resumen(filas)
    _guardar_csv("e2_resumen", resumen)
    figuras.figura_e2(resumen, E2_LIMITE_TIEMPO, E2_MARGEN)

    print()
    for configuracion in CONFIGURACIONES:
        maximo = None  # mayor n con todas las redes resueltas, sin saltos
        for f in resumen:
            if f["configuracion"] != configuracion:
                continue
            if f["pct_resueltas"] < 100:
                break
            maximo = f["subestaciones"]
        print(f"{configuracion:<13} resuelve todas las redes hasta n = "
              f"{maximo if maximo else '-'}")
    print(f"\nE2 terminado en {time.perf_counter() - inicio:.0f} s.")


# ---------------------------------------------------------------------------
# E3: cuánto aporta agregar los bloques indistinguibles
# ---------------------------------------------------------------------------

E3_INSTANCIAS = ("I1", "I2", "I3")
E3_CONFIGURACION = "A* + hadd"  # la que resuelve I3 más rápido
E3_LIMITE_TIEMPO = 120  # segundos por búsqueda
E3_TOPE_ESTADOS = 300_000
E3_BLOQUES = (1, 2, 3, 4, 5, 6)  # bloques de la térmica en la familia del juguete
E3_VERSIONES = {
    "individual": dominio.problema,
    "agregada": dominio_agregado.problema_agregado,
}


def red_juguete(k):
    """Construye la familia del juguete: I1 con k bloques en la térmica.

    Igual que I1 (una zona, S1 y S2 unidas por una línea larga, hidráulica de
    2 bloques en S1 y térmica en S2), pero la térmica tiene k bloques y hay k
    cargas normales, repartidas entre S1 y S2. La oferta sigue justa:
    2 + k bloques para 1 prioritaria + k normales + 1 de auxiliares. Con
    k = 4 es exactamente I1. Lo único que cambia con k es cuántos bloques
    intercambiables hay.

    Args:
        k (int): Bloques de la térmica y número de cargas normales.

    Returns:
        dominio.Red: La red.
    """
    red = dominio.Red()
    red.zonas = ["N"]
    red.subestaciones = {"S1": "N", "S2": "N"}
    red.lineas = {"L12": ("S1", "S2", "larga")}
    red.centrales = {"H1": ("S1", "autonomo", 2), "T1": ("S2", "termica", k)}
    red.cargas = {"P1": ("S1", "prioritaria")}
    for i in range(1, k + 1):
        if i % 2:
            red.cargas[f"B{i}"] = ("S1", "normal")
        else:
            red.cargas[f"I{i}"] = ("S2", "normal")
    return red


def _e3_instancias():
    """Compara las dos versiones del dominio en I1, I2 e I3.

    Returns:
        list[dict]: Una fila por instancia y versión con las acciones
        instanciadas, los estados alcanzables (None si superan
        E3_TOPE_ESTADOS) y el resultado de la búsqueda con E3_CONFIGURACION.
    """
    filas = []
    for nombre in E3_INSTANCIAS:
        red = instancias.REDES[nombre]()
        for version, problema in E3_VERSIONES.items():
            acciones, inicial, objetivo = problema(red)
            estados, _ = espacio_de_estados(acciones, inicial, E3_TOPE_ESTADOS)
            r = _ejecutar(acciones, inicial, objetivo, E3_CONFIGURACION,
                          E3_LIMITE_TIEMPO)
            filas.append({
                "instancia": nombre,
                "version": version,
                "acciones": len(acciones),
                "estados_alcanzables": len(estados) if estados else None,
                **r,
            })
            total = len(estados) if estados else f"más de {E3_TOPE_ESTADOS}"
            print(f"E3 {nombre}, {version}: {total} estados; {r['resultado']}, "
                  f"coste {r['coste']}, {r['expandidos']} nodos, "
                  f"{r['tiempo']:.1f} s", flush=True)
    return filas


def _e3_familia():
    """Mide el espacio de estados de red_juguete(k) en las dos versiones.

    Returns:
        list[dict]: Una fila por k con los estados alcanzables de cada
        versión y el factor de reducción (individual / agregada).
    """
    filas = []
    for k in E3_BLOQUES:
        red = red_juguete(k)
        tamanos = {}
        for version, problema in E3_VERSIONES.items():
            acciones, inicial, _ = problema(red)
            estados, _ = espacio_de_estados(acciones, inicial, E3_TOPE_ESTADOS)
            tamanos[version] = len(estados) if estados else None
        hay = tamanos["individual"] and tamanos["agregada"]
        filas.append({
            "bloques_termica": k,
            "estados_individual": tamanos["individual"],
            "estados_agregada": tamanos["agregada"],
            "factor_reduccion": (
                round(tamanos["individual"] / tamanos["agregada"], 1) if hay else None
            ),
        })
        print(f"E3 juguete con k = {k}: {tamanos['individual']} estados con "
              f"bloques individuales, {tamanos['agregada']} agregados", flush=True)
    return filas


def e3():
    """¿Cuánto aporta agregar los bloques indistinguibles?

    Hipótesis de la propuesta: reducción de órdenes de magnitud.

    Diseño:
        - Instancias I1, I2 e I3 en las dos versiones del dominio. Se mide
          el espacio de estados completo (sin heurística, para aislar el
          efecto de la representación) y la búsqueda con A* + hadd, que es
          la configuración que resuelve I3 más rápido.
        - Familia del juguete (red_juguete): I1 cambiando solo el número k
          de bloques de la térmica. Con bloques individuales, cada reparto
          de k bloques entre k cargas es un estado distinto; con contadores,
          todos son el mismo. Así se ve cómo crece la reducción con el
          número de bloques intercambiables, que es de donde viene la
          simetría.
        - El coste del plan debe coincidir en las dos versiones: la
          agregación cambia la representación, no el problema.

    Salidas: resultados/e3_instancias.csv, resultados/e3_familia.csv y
    figuras/e3.png.
    """
    inicio = time.perf_counter()
    filas = _e3_instancias()
    _guardar_csv("e3_instancias", filas)
    familia = _e3_familia()
    _guardar_csv("e3_familia", familia)
    figuras.figura_e3(filas, familia, E3_CONFIGURACION, E3_LIMITE_TIEMPO,
                      E3_TOPE_ESTADOS)
    print(f"\nE3 terminado en {time.perf_counter() - inicio:.0f} s.")


# Parámetros de E4 (Milagros). Elegidos para que todo E4 tarde unos 8 min.
E4_PROBABILIDADES = (0.05, 0.1, 0.2)  # probabilidad de fallo antes de cada paso
E4_SEMILLAS = 15  # ejecuciones por configuración: semillas SEMILLA .. SEMILLA + 14
E4_TIPOS = ("linea", "central")  # averías de línea frente a disparos de central
E4_LIMITE_TIEMPO = 60  # segundos por búsqueda (plan inicial o replanificación)
E4_LIMITE_NODOS = 300_000  # nodos expandidos por búsqueda


def _e4_fila(nombre, tipo, prob, semilla, r):
    """Convierte el resultado de ejecutar_con_fallos en una fila del CSV.

    Args:
        nombre (str): Nombre de la instancia.
        tipo (str): "linea" o "central".
        prob (float): Probabilidad de fallo.
        semilla (int): Semilla de la ejecución.
        r (dict): Resumen devuelto por ejecutar_con_fallos.

    Returns:
        dict: Fila de resultados/e4.csv.
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


def _e4_resumen(filas):
    """Agrupa las ejecuciones por instancia, tipo de fallo y probabilidad.

    Las maniobras extra se promedian solo sobre las ejecuciones resueltas
    (en las demás no tienen sentido); el resto, sobre todas.

    Args:
        filas (list[dict]): Filas de _e4_fila.

    Returns:
        list[dict]: Una fila por grupo (resultados/e4_resumen.csv).
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
            "eventos_medios": _media([f["n_eventos"] for f in grupo]),
            "pct_resueltas": round(100 * len(resueltas) / n, 1),
            "pct_sin_solucion": round(100 * len(sin_solucion) / n, 1),
            "pct_limite": round(100 * len(limite) / n, 1),
            "maniobras_extra_media": _media([f["maniobras_extra"] for f in resueltas]),
            "cargas_perdidas_media": _media([f["cargas_perdidas"] for f in grupo]),
            "replanificaciones_media": _media([f["replanificaciones"] for f in grupo]),
            "tiempo_replanificacion_medio": _media(
                [f["tiempo_replanificacion"] for f in grupo]
            ),
        })
    return resumen


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
          y tarda más de 80 s por búsqueda, demasiado para repetirla con
          muchas semillas. I1 tampoco aporta: es de juguete y sin
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
          bloques individuales en I2.
        - Versión individual (dominio.problema): al disparar una central hay
          que saber qué cargas usaban sus bloques.
        - Límites por búsqueda: E4_LIMITE_TIEMPO s y E4_LIMITE_NODOS nodos.

    Salidas: resultados/e4.csv (una fila por ejecución),
    resultados/e4_resumen.csv (una fila por instancia, tipo y probabilidad)
    y figuras/e4.png.
    """
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

    _guardar_csv("e4", filas)
    resumen = _e4_resumen(filas)
    _guardar_csv("e4_resumen", resumen)
    figuras.figura_e4(resumen)
    _e4_imprimir(resumen)
    print(f"\nE4 terminado en {time.perf_counter() - inicio:.0f} s.")


# ---------------------------------------------------------------------------
# E5: dónde está lo difícil (bloques sobrantes)
# ---------------------------------------------------------------------------

E5_HOLGURAS = (-1, 0, 1, 2, 3, 4, 6)  # bloques sobrantes: oferta - demanda
E5_SUBESTACIONES = 6  # tamaño de las redes generadas
E5_SEMILLAS = 8  # redes generadas: semillas SEMILLA .. SEMILLA + 7
E5_CONFIGURACIONES = ("A* + hprec", "A* + hadd", "voraz + hadd")
E5_CONFIGURACION_FIGURA = "A* + hadd"
E5_LIMITE_TIEMPO = 20  # segundos por búsqueda
E5_TOPE_ESTADOS = 150_000


def red_con_bloques_extra(nombre, holgura):
    """Devuelve I1 o I2 con bloques de más o de menos.

    I1 e I2 tienen la oferta justa. Los bloques se añaden (o se quitan) de
    uno en uno, recorriendo las centrales por orden alfabético y volviendo a
    empezar, para no favorecer a ninguna.

    Args:
        nombre (str): "I1" o "I2".
        holgura (int): Bloques que se añaden; si es negativo, se quitan.

    Returns:
        dominio.Red: La red modificada.
    """
    red = instancias.REDES[nombre]()
    centrales = sorted(red.centrales)
    paso = 1 if holgura > 0 else -1
    for i in range(abs(holgura)):
        central = centrales[i % len(centrales)]
        subestacion, tipo, n = red.centrales[central]
        red.centrales[central] = (subestacion, tipo, n + paso)
    return red


def red_generada_con_holgura(n, holgura, semilla):
    """Genera una red G(n) con un número exacto de bloques sobrantes.

    El generador no cambia la red al cambiar el margen (solo reparte más o
    menos bloques), así que con la misma semilla sale la misma red con
    distinta holgura.

    Args:
        n (int): Subestaciones.
        holgura (int): Bloques de oferta menos bloques de demanda (cargas
            más un bloque de auxiliares por térmica).
        semilla (int): Semilla del generador.

    Returns:
        dominio.Red: La red.
    """
    base = instancias.red_generada(n, margen=1.0, semilla=semilla)
    termicas = sum(1 for _, tipo, _ in base.centrales.values() if tipo == "termica")
    demanda = len(base.cargas) + termicas
    return instancias.red_generada(
        n, margen=(demanda + holgura) / demanda, semilla=semilla
    )


def _e5_redes(holgura):
    """Construye todas las redes del experimento para una holgura.

    Args:
        holgura (int): Bloques sobrantes.

    Returns:
        list[tuple]: (familia, nombre, red). La familia es "I1", "I2" o
        "G(n)"; en las generadas, el nombre incluye la semilla.
    """
    redes = [(nombre, nombre, red_con_bloques_extra(nombre, holgura))
             for nombre in ("I1", "I2")]
    familia = f"G({E5_SUBESTACIONES})"
    for i in range(E5_SEMILLAS):
        semilla = SEMILLA + i
        red = red_generada_con_holgura(E5_SUBESTACIONES, holgura, semilla)
        redes.append((familia, f"{familia} semilla {semilla}", red))
    return redes


def _e5_ejecuciones():
    """Clasifica el espacio de estados de cada red y la resuelve.

    Returns:
        list[dict]: Una fila por red, holgura y configuración. Las columnas
        'estados', 'pct_trampa' y 'pct_sin_salida' describen el espacio de
        estados de esa red (None si supera E5_TOPE_ESTADOS) y se repiten en
        las filas de sus configuraciones.
    """
    filas = []
    for holgura in E5_HOLGURAS:
        t0 = time.perf_counter()
        for familia, nombre, red in _e5_redes(holgura):
            acciones, inicial, objetivo = dominio_agregado.problema_agregado(red)
            estados, arcos = espacio_de_estados(acciones, inicial, E5_TOPE_ESTADOS)
            espacio = {"estados": None, "pct_trampa": None, "pct_sin_salida": None}
            if estados is not None:
                _, trampas, sin_salida = clasificar_estados(estados, arcos, objetivo)
                espacio = {
                    "estados": len(estados),
                    "pct_trampa": round(100 * len(trampas) / len(estados), 2),
                    "pct_sin_salida": round(100 * len(sin_salida) / len(estados), 2),
                }
            for configuracion in E5_CONFIGURACIONES:
                r = _ejecutar(acciones, inicial, objetivo, configuracion,
                              E5_LIMITE_TIEMPO)
                filas.append({
                    "familia": familia,
                    "red": nombre,
                    "holgura": holgura,
                    "bloques": sum(c[2] for c in red.centrales.values()),
                    **espacio,
                    "configuracion": configuracion,
                    **r,
                })
        print(f"E5 holgura {holgura:+d}: {2 + E5_SEMILLAS} redes "
              f"({time.perf_counter() - t0:.0f} s)", flush=True)
    return filas


def _e5_resumen(filas):
    """Agrupa las ejecuciones por familia, holgura y configuración.

    'ahorro_medio' compara el coste del plan con el de la misma red con
    oferta justa (holgura 0) y la misma configuración: cuántas maniobras se
    ahorran por tener bloques de sobra. 'maniobras_de_mas_media' compara con
    el óptimo (A* + hprec) de la misma red y holgura.

    Args:
        filas (list[dict]): Filas de _e5_ejecuciones.

    Returns:
        list[dict]: Una fila por familia, holgura y configuración.
    """
    coste = {(f["red"], f["holgura"], f["configuracion"]): f["coste"] for f in filas}
    familias = list(dict.fromkeys(f["familia"] for f in filas))

    resumen = []
    for familia in familias:
        for holgura in E5_HOLGURAS:
            for configuracion in E5_CONFIGURACIONES:
                grupo = [f for f in filas if f["familia"] == familia
                         and f["holgura"] == holgura
                         and f["configuracion"] == configuracion]
                resueltas = [f for f in grupo if f["resultado"] == "resuelto"]
                terminadas = [f for f in grupo if f["resultado"] != "limite_tiempo"]
                ahorro, de_mas = [], []
                for f in resueltas:
                    justa = coste.get((f["red"], 0, configuracion))
                    optimo = coste.get((f["red"], holgura, "A* + hprec"))
                    ahorro.append(justa - f["coste"] if justa is not None else None)
                    de_mas.append(f["coste"] - optimo if optimo is not None else None)
                resumen.append({
                    "familia": familia,
                    "holgura": holgura,
                    "configuracion": configuracion,
                    "redes": len(grupo),
                    "pct_resueltas": round(100 * len(resueltas) / len(grupo), 1),
                    "pct_sin_solucion": round(
                        100 * sum(f["resultado"] == "sin_solucion" for f in grupo)
                        / len(grupo), 1
                    ),
                    "pct_limite": round(
                        100 * (len(grupo) - len(terminadas)) / len(grupo), 1
                    ),
                    "estados_mediana": _mediana(
                        [f["estados"] for f in grupo if f["estados"] is not None]
                    ),
                    "pct_trampa_medio": _media(f["pct_trampa"] for f in grupo),
                    "pct_sin_salida_medio": _media(f["pct_sin_salida"] for f in grupo),
                    "expandidos_mediana": _mediana([f["expandidos"] for f in terminadas]),
                    "tiempo_mediana": _mediana([f["tiempo"] for f in terminadas]),
                    "coste_medio": _media(f["coste"] for f in resueltas),
                    "ahorro_medio": _media(ahorro),
                    "maniobras_de_mas_media": _media(de_mas),
                    "deslastres_medios": _media(f["deslastres"] for f in resueltas),
                })
    return resumen


def e5():
    """¿Dónde está lo difícil? Variar los bloques sobrantes.

    Hipótesis de la propuesta: pico de dificultad cuando la oferta está
    justa, como el punto crítico de SAT.

    Diseño:
        - Se varía la holgura: bloques de oferta menos bloques de demanda,
          de -1 (faltan bloques: no hay solución) a +6. Se usa la holgura y
          no el margen porque es lo que decide si un bloque mal gastado se
          puede permitir.
        - Redes: I1 e I2, que tienen la oferta justa, con bloques añadidos o
          quitados (red_con_bloques_extra), y E5_SEMILLAS redes G(n), cada
          una con todas las holguras (red_generada_con_holgura). El
          generador coloca las térmicas de forma que no haya bloqueos, así
          que sus redes sirven de contraste con las hechas a mano.
        - De cada red se clasifica el espacio de estados completo: qué
          porcentaje son estados trampa y cuántos no tienen salida. Es la
          dificultad del problema, antes de buscar.
        - Búsqueda con A* + hprec (admisible: da el óptimo), A* + hadd y
          voraz + hadd: nodos, coste, maniobras de más y deslastres.
        - Con holgura -1 se mide cuánto cuesta demostrar que no hay
          solución. En el problema relajado un bloque sirve para todo, así
          que la falta de bloques no se ve en la heurística del estado
          inicial y hay que agotar el espacio de estados.

    Salidas: resultados/e5.csv (una fila por ejecución),
    resultados/e5_resumen.csv y figuras/e5.png.
    """
    inicio = time.perf_counter()
    filas = _e5_ejecuciones()
    _guardar_csv("e5", filas)
    resumen = _e5_resumen(filas)
    _guardar_csv("e5_resumen", resumen)
    figuras.figura_e5(resumen, E5_CONFIGURACION_FIGURA)
    print(f"\nE5 terminado en {time.perf_counter() - inicio:.0f} s.")


EXPERIMENTOS = {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5}

if __name__ == "__main__":
    for nombre in sys.argv[1:] or ["E1", "E2", "E3"]:
        EXPERIMENTOS[nombre.upper()]()
