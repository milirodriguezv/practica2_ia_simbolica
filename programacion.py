"""(Opcional) Planificar primero, programar después (propuesta v2, secc. 8.4).

Responsable: Milagros (E6 y duraciones: Eloísa).

Se decide en el punto de control del 13/10. Las precedencias se construyen
sobre el plan con bloques individuales: en la versión agregada el contador
Libres(z,n) encadenaría todas las acciones y se perdería el paralelismo.
"""

# Duraciones orientativas en minutos [Diseño propio]; rangos -> valor medio.
DURACION = {
    "ArrancarAutonomo": 12,
    "ActivarBloque": 8,
    "EnergizarCorta": 5,
    "EnergizarLarga": 15,
    "ArrancarTermica": 180,
    "ConectarPrioritaria": 5,
    "ConectarCarga": 5,
    "AcoplarZonas": 30,
    "Deslastrar": 2,
    "ExtenderAlcance": 0,
}


def precedencias(plan):
    """Grafo de precedencias: a < b si a añade una precondición de b, o si b
    borra algo que a necesita."""
    raise NotImplementedError


def ruta_critica(plan, grafo):
    """Inicio más temprano, más tardío y holgura de cada acción; makespan."""
    raise NotImplementedError


def programar_con_equipos(plan, grafo, equipos_por_zona=2):
    """Programación voraz por mínima holgura con equipos de maniobra limitados."""
    raise NotImplementedError


def gantt(programa, ruta_salida):
    """Guarda el diagrama de Gantt del programa."""
    raise NotImplementedError
