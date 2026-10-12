"""Planificador de búsqueda hacia delante 
Búsqueda en grafo con conjunto de cerrados. Un único algoritmo sirve para los
tres modos; solo cambia la prioridad f con la que se ordena la lista abierta:

    - ucs: f = g. Óptimo.
    - astar: f = g + h. Óptimo si h es admisible (h0, hprec, hmax).
    - voraz: f = h. Rápido, pero no garantiza el plan más barato.

g es la suma de los costes de las acciones (no el número de pasos), porque
ExtenderAlcance cuesta 0.

Contrato de interfaz:
  buscar(acciones, inicial, objetivo, heuristica, modo) -> (plan, estadisticas)
  validar_plan(plan, inicial, objetivo) -> (valido, coste)
"""

import heapq
import math
import time

from dominio import aplicable, resultado

MODOS = ("ucs", "astar", "voraz")  # f = g, f = g + h, f = h


def _prioridad(modo, g, h):
    """Calcula la prioridad f de un nodo según el modo de búsqueda.

    Args:
        modo (str): Uno de MODOS.
        g (float): Coste acumulado desde el estado inicial.
        h (float): Estimación de la heurística.

    Returns:
        float: Valor f con el que se ordena la lista abierta.
    """
    if modo == "ucs":
        return g
    if modo == "astar":
        return g + h
    return h  # voraz


def _reconstruir_plan(padre, estado):
    """Reconstruye el plan siguiendo los padres desde el estado final.

    Args:
        padre (dict): estado -> (estado_anterior, accion). El estado inicial
            no tiene entrada.
        estado (frozenset[str]): Estado objetivo alcanzado.

    Returns:
        list[Accion]: Acciones en orden, del estado inicial al final.
    """
    plan = []
    while estado in padre:
        anterior, accion = padre[estado]
        plan.append(accion)
        estado = anterior
    plan.reverse()
    return plan


def buscar(
    acciones,
    inicial,
    objetivo,
    heuristica,
    modo="astar",
    limite_tiempo=None,
    limite_nodos=None,
):
    """Busca un plan desde el estado inicial hasta uno que cumpla el objetivo.

    Búsqueda en grafo con lista abierta (cola de prioridad) y cerrados:
      1. La lista abierta guarda tuplas (f, h, contador, g, estado). Python
         compara las tuplas de izquierda a derecha, así que:
           - primero gana la menor f;
           - si empatan en f, gana la menor h: el nodo que la heurística ve
             más cerca del objetivo. Así A* no se entretiene con muchos
             nodos poco profundos de la misma f. No afecta a la optimalidad,
             porque solo reordena nodos con la misma f;
           - si también empatan en h, gana el más antiguo (contador, FIFO).
         El contador crece en cada inserción y nunca se repite, así que
         Python no llega a comparar g ni los frozenset y el resultado es
         reproducible.
      2. mejor_g guarda el menor g conocido de cada estado y padre la acción
         con la que se llegó, para reconstruir el plan al final.
      3. Si un nodo extraído tiene un g peor que mejor_g, es una copia
         desfasada (luego se encontró un camino mejor) y se descarta
         (borrado perezoso: más simple que modificar el montículo).
      4. El test de objetivo se hace al expandir, no al generar, para que
         UCS y A* sigan siendo óptimos.
      5. Un sucesor se inserta si es nuevo o si se llega a él con menor g,
         aunque ya esté cerrado (puede pasar con heurísticas no admisibles
         como hadd).
      6. Los sucesores con h infinita no se insertan: ni en el problema
         relajado alcanzan el objetivo.

    Args:
        acciones (list[Accion]): Acciones instanciadas del problema.
        inicial (frozenset[str]): Estado inicial.
        objetivo (frozenset[str]): Átomos que deben cumplirse al final.
        heuristica (callable): h(estado, objetivo, acciones) -> número.
        modo (str): Uno de MODOS ("ucs", "astar" o "voraz").
        limite_tiempo (float | None): Segundos máximos de búsqueda.
        limite_nodos (int | None): Número máximo de nodos expandidos.

    Returns:
        tuple: (plan, estadisticas).
            plan (list[Accion] | None): Acciones en orden, o None si no hay
            solución o se alcanza un límite.
            estadisticas (dict): 'expandidos', 'generados', 'tiempo'
            (segundos), 'longitud', 'coste' y 'resultado' ("resuelto",
            "sin_solucion", "limite_tiempo" o "limite_nodos").

    Raises:
        ValueError: Si el modo no es uno de MODOS.
    """
    if modo not in MODOS:
        raise ValueError(f"Modo desconocido: {modo}. Usa uno de {MODOS}.")

    inicio = time.perf_counter()
    estadisticas = {
        "expandidos": 0,
        "generados": 0,
        "tiempo": 0.0,
        "longitud": 0,
        "coste": 0,
        "resultado": "sin_solucion",
    }

    abiertos = []
    contador = 0
    mejor_g = {inicial: 0}
    padre = {}
    cerrados = set()

    h_inicial = heuristica(inicial, objetivo, acciones)
    if h_inicial != math.inf:
        f_inicial = _prioridad(modo, 0, h_inicial)
        heapq.heappush(abiertos, (f_inicial, h_inicial, contador, 0, inicial))
        contador += 1

    plan = None
    while abiertos:
        # Comprobación de límites antes de expandir otro nodo.
        transcurrido = time.perf_counter() - inicio
        if limite_tiempo is not None and transcurrido > limite_tiempo:
            estadisticas["resultado"] = "limite_tiempo"
            break
        if limite_nodos is not None and estadisticas["expandidos"] >= limite_nodos:
            estadisticas["resultado"] = "limite_nodos"
            break

        _, _, _, g, estado = heapq.heappop(abiertos)

        # Borrado perezoso: si ya se conoce un camino más barato a este
        # estado, o ya está cerrado, esta entrada es una copia antigua.
        if g > mejor_g[estado] or estado in cerrados:
            continue

        # Test de objetivo al expandir.
        if objetivo <= estado:
            plan = _reconstruir_plan(padre, estado)
            estadisticas["resultado"] = "resuelto"
            estadisticas["coste"] = g
            break

        cerrados.add(estado)
        estadisticas["expandidos"] += 1

        for accion in acciones:
            if not aplicable(estado, accion):
                continue
            sucesor = resultado(estado, accion)
            g_sucesor = g + accion.coste
            estadisticas["generados"] += 1

            # Solo interesa si es nuevo o si mejora el g conocido.
            if sucesor in mejor_g and g_sucesor >= mejor_g[sucesor]:
                continue

            h = heuristica(sucesor, objetivo, acciones)
            if h == math.inf:
                continue  # callejón sin salida en el problema relajado

            mejor_g[sucesor] = g_sucesor
            padre[sucesor] = (estado, accion)
            cerrados.discard(sucesor)  # reabrir si ya estaba cerrado
            f = _prioridad(modo, g_sucesor, h)
            # Desempate por menor h si hay empate en f (ver punto 1).
            heapq.heappush(abiertos, (f, h, contador, g_sucesor, sucesor))
            contador += 1

    estadisticas["tiempo"] = time.perf_counter() - inicio
    if plan is not None:
        estadisticas["longitud"] = len(plan)
    return plan, estadisticas


def validar_plan(plan, inicial, objetivo):
    """Aplica el plan acción a acción comprobando precondiciones y objetivo.

    Es independiente de la búsqueda: solo usa aplicable y resultado del
    dominio, así que sirve como comprobación real del plan devuelto.

    Args:
        plan (list[Accion]): Acciones en el orden en que se ejecutan.
        inicial (frozenset[str]): Estado inicial.
        objetivo (frozenset[str]): Átomos que deben cumplirse al final.

    Returns:
        tuple: (valido, coste).
            valido (bool): True si todas las acciones son aplicables en su
            turno y el estado final cumple el objetivo.
            coste (float): Suma de los costes de las acciones aplicadas. Si
            una acción no es aplicable, el coste acumulado hasta ella.
    """
    estado = inicial
    coste = 0
    for accion in plan:
        if not aplicable(estado, accion):
            return False, coste
        estado = resultado(estado, accion)
        coste += accion.coste
    return objetivo <= estado, coste
