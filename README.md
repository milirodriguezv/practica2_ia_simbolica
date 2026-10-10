# Práctica 2 – IA Simbólica: reposición de la red eléctrica tras un apagón total

Milagros Rodríguez Ventura y Eloísa Denia García — MUIA, curso 2026/2027.

Planificador clásico propio (búsqueda hacia delante: coste uniforme, A* y voraz) con
heurísticas independientes del dominio, sobre un dominio tipo PDDL de reposición de la red.

## Requisitos e instalación

Python 3.10 o superior.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```
python main.py --instancia I2 --algoritmo astar --heuristica hadd
python experimentos.py E1 E2 E3
```

- `--instancia`: `I1` (juguete), `I2` (Norte/Sur), `I3` (peninsular simplificada).
- `--algoritmo`: `ucs`, `astar`, `voraz`.
- `--heuristica`: `h0`, `hprec`, `hmax`, `hadd`, `hff`.
- `--individual`: bloques individuales en lugar de la versión agregada.

## Estructura

| Archivo | Contenido | Responsable |
|---|---|---|
| `dominio.py` | Esquemas de acciones con coste e instanciación (individual y agregada) | Eloísa |
| `instancias.py` | I1, I2, I3 y generador G(n) | Milagros |
| `planificador.py` | Coste uniforme, A*, voraz; `validar_plan` | Milagros |
| `heuristicas.py` | h0, hprec, hmax, hadd (hFF opcional) | Eloísa |
| `replanificacion.py` | Simulador de fallos y bucle ejecutar–monitorizar–replanificar | Milagros |
| `visualizacion.py` | Dibujo de la red paso a paso | Milagros |
| `programacion.py` | (Opcional) precedencias, ruta crítica, Gantt | Milagros |
| `experimentos.py` | E1–E6, tablas CSV (`resultados/`) y gráficas (`figuras/`) | Eloísa |
| `main.py` | Punto de entrada | Ambas |

## Contrato de interfaz

- Estado: `frozenset` de cadenas (`'ConTension(S1)'`).
- Acción: tupla `(nombre, coste, pre_pos, pre_neg, add, del)` (`dominio.Accion`).
- `instancias.cargar(nombre)` → `(acciones, estado_inicial, objetivo)`.
- `planificador.buscar(acciones, inicial, objetivo, heuristica, modo)` → `(plan, estadisticas)`.
- `h(estado, objetivo, acciones)` → número.
- `planificador.validar_plan(plan, inicial, objetivo)` → `(valido, coste)`.

## Referencias

Pendiente: copiar aquí la lista de la propuesta y citar cualquier fragmento reutilizado.

## Uso de IA generativa

Pendiente: resumen de la declaración de uso de IAG.
