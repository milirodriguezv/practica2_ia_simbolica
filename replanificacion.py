"""Replanificación ante fallos (propuesta v2, secc. 8.3).

Responsable: Milagros.

Ciclo: planificar -> ejecutar acción a acción -> monitorizar -> replanificar.

Hay dos estados:
    - Estado creído: el que el plan supone que se irá alcanzando.
    - Estado real: el mundo simulado, donde ocurren sucesos inesperados. El
      agente solo lo conoce observándolo antes de cada paso.

Los eventos (avería de línea, disparo de central) son del entorno, no
acciones del agente: no cuestan nada y no forman parte del plan.

Se usa la versión con bloques individuales (dominio.problema), porque al
disparar una central hay que saber qué cargas usaban sus bloques (Usa(k,b)).

Contrato de interfaz:
  averia_linea(estado, linea) -> estado
  disparo_central(estado, central, red) -> (estado, cargas_perdidas)
  ejecutar_con_fallos(red, acciones, inicial, objetivo, heuristica, ...) -> dict
"""

import random

from dominio import atomo, resultado
from funciones_auxiliares import bloques_de_central
from planificador import buscar, validar_plan

TIPOS_FALLO = ("linea", "central")


def averia_linea(estado, linea):
    """Avería de una línea: deja de estar operativa.

    Las subestaciones que ya tenían tensión la conservan: la línea solo hace
    falta para dar tensión a subestaciones nuevas.

    Args:
        estado (frozenset[str]): Estado real antes del evento.
        linea (str): Nombre de la línea averiada.

    Returns:
        frozenset[str]: El estado sin Operativa(linea).
    """
    return estado - {atomo("Operativa", linea)}


def disparo_central(estado, central, red):
    """Disparo de una central: se para y no se puede volver a arrancar.

    Efectos:
      (A) Borra EnMarcha(c) y Operativa(c), y Activado(b) y Libre(b) de cada
          bloque b de c. Por qué: la energía de la central desaparece y la
          avería impide rearrancarla.
      (B) Cada carga k con Usa(k,b) en uno de esos bloques pierde Usa(k,b) y
          Suministrada(k). Por qué: se queda sin el bloque que la alimentaba;
          son las cargas perdidas.
      (C) Si c es térmica, su bloque de auxiliares b' (de otra central) se
          devuelve: borra Auxiliar(b',c) y añade Libre(b'). Por qué: la
          térmica parada ya no consume ese bloque. Solo si b' sigue
          Activado: si su central también disparó, el bloque ya no existe.
      (D) Sin cascada: si un bloque de c era Auxiliar(b,T) de una térmica T en
          marcha, T sigue en marcha y Auxiliar(b,T) se queda. Por qué: los
          auxiliares solo hacen falta para arrancar.
      (E) Las subestaciones conservan ConTension. Por qué:
          simplificación, otras fuentes de la isla mantienen la tensión.

    Args:
        estado (frozenset[str]): Estado real antes del evento.
        central (str): Nombre de la central que dispara.
        red (dominio.Red): Red, para saber los bloques y el tipo de la central.

    Returns:
        tuple: (nuevo_estado, cargas_perdidas).
            nuevo_estado (frozenset[str]): Estado tras el disparo.
            cargas_perdidas (list[str]): Cargas que han perdido el suministro,
            en orden alfabético.
    """
    borrar = {atomo("EnMarcha", central), atomo("Operativa", central)}
    anadir = set()
    cargas_perdidas = []

    # (A) Los bloques de la central desaparecen.
    bloques = bloques_de_central(red, central)
    for b in bloques:
        borrar.add(atomo("Activado", b))
        borrar.add(atomo("Libre", b))

    # (B) Las cargas alimentadas por esos bloques pierden el suministro.
    for k in sorted(red.cargas):
        for b in bloques:
            if atomo("Usa", k, b) in estado:
                borrar.add(atomo("Usa", k, b))
                borrar.add(atomo("Suministrada", k))
                cargas_perdidas.append(k)

    # (C) Una térmica parada devuelve su bloque de auxiliares, si aún existe.
    if red.centrales[central][1] == "termica":
        for otra in red.centrales:
            if otra == central:
                continue
            for b in bloques_de_central(red, otra):
                aux = atomo("Auxiliar", b, central)
                if aux in estado:
                    borrar.add(aux)
                    if atomo("Activado", b) in estado:
                        anadir.add(atomo("Libre", b))

    # (D) y (E): no se toca nada más.
    return (estado - borrar) | anadir, cargas_perdidas


def _candidatos(estado, red, tipos_fallo):
    """Elementos que todavía pueden fallar: líneas y centrales operativas.

    Se ordenan para que la elección con el generador aleatorio sea
    reproducible (el orden de un dict o un set no debe influir).

    Args:
        estado (frozenset[str]): Estado real.
        red (dominio.Red): Red del problema.
        tipos_fallo (tuple[str]): Tipos permitidos, "linea" y/o "central".

    Returns:
        list[tuple]: Pares (tipo, elemento) ordenados.
    """
    candidatos = []
    if "linea" in tipos_fallo:
        for l in sorted(red.lineas):
            if atomo("Operativa", l) in estado:
                candidatos.append(("linea", l))
    if "central" in tipos_fallo:
        for c in sorted(red.centrales):
            if atomo("Operativa", c) in estado:
                candidatos.append(("central", c))
    return candidatos


def _aplicar_evento(estado, tipo, elemento, red):
    """Aplica un evento del entorno al estado real.

    Args:
        estado (frozenset[str]): Estado real antes del evento.
        tipo (str): "linea" o "central".
        elemento (str): Línea o central que falla.
        red (dominio.Red): Red del problema.

    Returns:
        tuple: (nuevo_estado, cargas_perdidas, descripcion).
    """
    if tipo == "linea":
        return averia_linea(estado, elemento), [], f"avería de la línea {elemento}"
    nuevo, perdidas = disparo_central(estado, elemento, red)
    texto = f"disparo de la central {elemento}"
    if perdidas:
        texto += f" (pierden suministro: {', '.join(perdidas)})"
    return nuevo, perdidas, texto


def ejecutar_con_fallos(
    red,
    acciones,
    inicial,
    objetivo,
    heuristica,
    modo="astar",
    prob_fallo=0.1,
    semilla=0,
    limite_tiempo=60,
    limite_nodos=300_000,
    tipos_fallo=TIPOS_FALLO,
    eventos_programados=None,
):
    """Bucle ejecutar-monitorizar-replanificar.

    1. Planifica desde el estado inicial.
    2. Antes de cada paso, con probabilidad prob_fallo, falla un elemento
       (línea o central, según tipos_fallo) elegido al azar entre los que
       siguen operativos en el estado real. Solo se usa
       random.Random(semilla), así que con la misma semilla sale lo mismo.
    3. Monitoriza: el agente observa el estado real y comprueba que el
       RESTO del plan sigue siendo aplicable y llega al objetivo
       (validar_plan). Se comprueba todo el resto y no solo la siguiente
       acción porque un fallo puede romper un paso posterior, y detectarlo
       pronto evita maniobras inútiles. Si no vale, replanifica desde el
       estado real.
    4. Ejecuta la siguiente acción sobre el estado real.
    5. Si una búsqueda no devuelve plan, se para y se anota por qué:
       "sin_solucion" (demostrado imposible) o "limite_tiempo" /
       "limite_nodos" (la búsqueda se rindió, no se sabe si hay solución).

    Termina siempre: cada evento quita un elemento operativo (hay un número
    finito) y, entre eventos, el plan vigente es válido y se ejecuta entero.

    Args:
        red (dominio.Red): Red del problema, para aplicar los eventos.
        acciones (list[Accion]): Acciones instanciadas (versión individual).
        inicial (frozenset[str]): Estado inicial.
        objetivo (frozenset[str]): Átomos que deben cumplirse al final.
        heuristica (callable): h(estado, objetivo, acciones) -> número.
        modo (str): Uno de planificador.MODOS.
        prob_fallo (float): Probabilidad de un evento antes de cada paso.
        semilla (int): Semilla del generador aleatorio de eventos.
        limite_tiempo (float): Segundos máximos de cada búsqueda.
        limite_nodos (int): Nodos expandidos máximos de cada búsqueda.
        tipos_fallo (tuple[str]): Eventos posibles: "linea" y/o "central".
        eventos_programados (dict | None): paso -> (tipo, elemento). Eventos
            fijos para pruebas a mano; en esos pasos sustituyen al sorteo.

    Returns:
        dict: Resumen de la ejecución.
            'resuelto' (bool): si el estado real llegó al objetivo.
            'motivo' (str): "resuelto", "sin_solucion", "limite_tiempo" o
            "limite_nodos".
            'maniobras' (int): acciones ejecutadas.
            'coste' (float): coste ejecutado (ExtenderAlcance cuesta 0).
            'coste_plan_original' (float | None): None si no hubo plan inicial.
            'tiempo_plan_original' (float): segundos de la primera búsqueda.
            'maniobras_extra' (float | None): coste - coste_plan_original;
            None si no se resolvió.
            'cargas_perdidas' (int) y 'lista_cargas_perdidas' (list[str]):
            pérdidas de suministro por disparos (una carga puede repetirse).
            'replanificaciones' (int): búsquedas tras la inicial.
            'tiempo_replanificacion' (float): segundos sumados de esas búsquedas.
            'eventos' (list[str]): descripciones con el paso en que ocurrieron.
            'plan_ejecutado' (list[str]): nombres de las acciones ejecutadas.
    """
    rng = random.Random(semilla)
    eventos_programados = eventos_programados or {}

    resumen = {
        "resuelto": False,
        "motivo": "",
        "maniobras": 0,
        "coste": 0,
        "coste_plan_original": None,
        "tiempo_plan_original": 0.0,
        "maniobras_extra": None,
        "cargas_perdidas": 0,
        "lista_cargas_perdidas": [],
        "replanificaciones": 0,
        "tiempo_replanificacion": 0.0,
        "eventos": [],
        "plan_ejecutado": [],
    }

    # 1. Plan inicial.
    plan, est = buscar(
        acciones, inicial, objetivo, heuristica, modo, limite_tiempo, limite_nodos
    )
    resumen["tiempo_plan_original"] = est["tiempo"]
    if plan is None:
        resumen["motivo"] = est["resultado"]
        return resumen
    resumen["coste_plan_original"] = est["coste"]

    estado_real = inicial  # el mundo simulado
    pendiente = list(plan)  # lo que queda del plan: el estado creído es el
    # que se obtendría aplicándolo, y se supone que llega al objetivo
    paso = 0  # acciones ejecutadas hasta ahora

    while not objetivo <= estado_real:
        # 2. El entorno puede provocar un evento antes del paso. Se tira el
        # dado siempre, para que la secuencia aleatoria no dependa de nada más.
        sorteo = rng.random()
        evento = None
        if paso in eventos_programados:
            evento = eventos_programados[paso]
        elif sorteo < prob_fallo:
            candidatos = _candidatos(estado_real, red, tipos_fallo)
            if candidatos:
                evento = rng.choice(candidatos)
        if evento is not None:
            tipo, elemento = evento
            estado_real, perdidas, texto = _aplicar_evento(
                estado_real, tipo, elemento, red
            )
            resumen["eventos"].append(f"paso {paso}: {texto}")
            resumen["lista_cargas_perdidas"].extend(perdidas)

        # 3. Monitorización: el agente observa el estado real y comprueba si
        # el resto del plan sigue llevando al objetivo desde él.
        valido, _ = validar_plan(pendiente, estado_real, objetivo)
        if not valido:
            plan, est = buscar(
                acciones,
                estado_real,
                objetivo,
                heuristica,
                modo,
                limite_tiempo,
                limite_nodos,
            )
            resumen["replanificaciones"] += 1
            resumen["tiempo_replanificacion"] += est["tiempo"]
            if plan is None:
                resumen["motivo"] = est["resultado"]
                break
            pendiente = list(plan)

        # 4. Ejecución de la siguiente acción sobre el mundo real.
        accion = pendiente.pop(0)
        estado_real = resultado(estado_real, accion)
        resumen["plan_ejecutado"].append(accion.nombre)
        resumen["maniobras"] += 1
        resumen["coste"] += accion.coste
        paso += 1

    resumen["cargas_perdidas"] = len(resumen["lista_cargas_perdidas"])
    if objetivo <= estado_real:
        resumen["resuelto"] = True
        resumen["motivo"] = "resuelto"
        resumen["maniobras_extra"] = resumen["coste"] - resumen["coste_plan_original"]
    return resumen
