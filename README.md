# Práctica 2 – IA Simbólica: reposición de la red eléctrica tras un apagón total

Milagros Rodríguez Ventura y Eloísa Denia García — MUIA, curso 2026/2027.

Planificador clásico propio (búsqueda hacia delante: coste uniforme, A* y voraz) con
heurísticas independientes del dominio, sobre un dominio tipo PDDL de reposición de la red.
El dominio tiene dos versiones con la misma semántica: bloques de energía individuales y
bloques agregados en contadores por zona.

## Requisitos e instalación

Python 3.10 o superior. Dependencias: `matplotlib` y `networkx`.

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

En macOS y Linux, si no existe la orden `python`, usar `python3`.

## Ejecución

```
python main.py --instancia I2 --algoritmo astar --heuristica hprec
```

| Opción | Valores | Por defecto |
|---|---|---|
| `--instancia` | `I1` (juguete), `I2` (Norte/Sur), `I3` (peninsular simplificada), `I2-reserva` (I2 con líneas dobles y una térmica de reserva) | `I1` |
| `--generada N` | red aleatoria G(N) con N subestaciones, en lugar de `--instancia` | – |
| `--margen`, `--semilla` | oferta/demanda de G(N); semilla de G(N) y de los fallos aleatorios | `1.0`, `0` |
| `--algoritmo` | `ucs`, `astar`, `voraz` | `astar` |
| `--heuristica` | `h0`, `hprec`, `hmax`, `hadd` | `hmax` |
| `--individual` | bloques individuales en lugar de la versión agregada | agregada |
| `--limite`, `--nodos` | límite de tiempo (s) y de nodos expandidos por búsqueda | `60`, `500000` |
| `--figuras PREFIJO` | guarda un fotograma por paso del plan en `figuras/PREFIJO_NN.png` | – |
| `--fallo TIPO:ELEMENTO@PASO` | fallo programado (repetible), p. ej. `central:T1@11`; `PASO` = acciones ya ejecutadas | – |
| `--prob-fallo P`, `--tipos-fallo` | fallos aleatorios antes de cada paso; `linea` y/o `central` | `0`, ambos |

Con `--fallo` o `--prob-fallo` se ejecuta el plan con replanificación, siempre con bloques
individuales: al disparar una central hay que saber qué cargas usaban sus bloques.

Ejemplos:

```
python main.py --instancia I1 --algoritmo astar --heuristica hmax --individual
python main.py --instancia I3 --algoritmo ucs --heuristica h0
python main.py --generada 4 --margen 1.5 --semilla 3 --heuristica hprec
python main.py --instancia I1 --individual --figuras i1
python main.py --instancia I1 --heuristica hadd --fallo central:T1@11
python main.py --instancia I2-reserva --heuristica hprec --prob-fallo 0.05 --semilla 8 --tipos-fallo central
```

`python visualizacion.py` regenera los fotogramas del plan de I1 (`figuras/i1_00.png` …
`i1_14.png`).

Costes óptimos: I1 = 14, I2 = 23, I3 = 26 (iguales en las dos versiones).

## Experimentos

`python experimentos.py E1 E2 E3 E4 E5` (o solo los que se quieran; sin argumentos ejecuta
E1, E2 y E3). Cada uno guarda sus tablas en `resultados/` y su figura en `figuras/`. Las
semillas son fijas, así que los resultados se repiten salvo los tiempos.

| Id | Pregunta | Qué mide | Tarda |
|---|---|---|---|
| E1 | ¿Qué heurística guía mejor cuando los recursos se gastan? | A* con h0, hprec, hmax y hadd, y voraz con hadd, en I1-I3: nodos, tiempo y maniobras de más. Además, precisión h/h* de cada heurística en todos los estados, en los estados trampa y en los estados sin salida | ~3 min |
| E2 | ¿Hasta qué tamaño de red llega cada configuración? | Redes G(n) de 2 a 14 subestaciones: % resueltas en 10 s, nodos y tiempo | ~15 min |
| E3 | ¿Cuánto aporta agregar los bloques? | Estados alcanzables y nodos expandidos con bloques individuales y con contadores, en I1-I3 y en el juguete con k bloques | ~3 min |
| E4 | ¿Qué pasa con los fallos? | Averías de línea y disparos de central durante la ejecución, con replanificación, en I2 e I2-reserva | ~8 min |
| E5 | ¿Dónde está lo difícil? | Las mismas redes con -1 a +6 bloques sobrantes: % de estados trampa, coste del plan y nodos | ~3 min |

Términos propios de los experimentos:

- **Estado trampa**: el objetivo sigue siendo alcanzable, pero solo deshaciendo
  trabajo (`Deslastrar`), porque se gastó un bloque donde no tocaba.
- **Estado sin salida**: el objetivo ya no es alcanzable (los bloques se gastaron
  en cargas prioritarias, que no se pueden deslastrar).
- **Holgura**: bloques de oferta menos bloques de demanda (cargas más un bloque
  de auxiliares por térmica). Con 0, la oferta es justa.

## Estructura

| Archivo | Contenido | Responsable |
|---|---|---|
| `dominio.py` | Esquemas de acciones con coste e instanciación, versión con bloques individuales | Eloísa |
| `dominio_agregado.py` | Versión agregada: bloques libres contados por zona (`Libres(z,n)`) | Milagros |
| `funciones_auxiliares.py` | Consultas sobre la red usadas al instanciar | Eloísa |
| `instancias.py` | I1, I2, I3, I2-reserva, generador G(n) y `validar` | Milagros |
| `planificador.py` | Coste uniforme, A*, voraz; `validar_plan` | Milagros |
| `heuristicas.py` | h0, hprec, hmax, hadd | Eloísa |
| `replanificacion.py` | Simulador de fallos y bucle ejecutar–monitorizar–replanificar | Milagros |
| `visualizacion.py` | Dibujo de la red paso a paso | Milagros |
| `experimentos.py` | E1–E5: ejecutan las búsquedas y guardan las tablas CSV (`resultados/`) | Eloísa (E4: Milagros) |
| `analisis.py` | Espacio de estados completo, coste real de cada estado, estados trampa y sin salida | Eloísa |
| `figuras.py` | Gráficas de los experimentos (`figuras/`) | Eloísa (E4: Milagros) |
| `main.py` | Punto de entrada | Ambas |

## Contrato de interfaz

- Estado: `frozenset` de cadenas (`'ConTension(S1)'`).
- Acción: `dominio.Accion(nombre, coste, pre_pos, pre_neg, add, dele)`; `dele` es la lista de
  eliminación (`del` es palabra reservada de Python).
- `instancias.cargar(nombre, agregada=True)` → `(acciones, estado_inicial, objetivo)`.
- `planificador.buscar(acciones, inicial, objetivo, heuristica, modo, limite_tiempo, limite_nodos)`
  → `(plan, estadisticas)`.
- `h(estado, objetivo, acciones)` → número (`math.inf` si el objetivo es inalcanzable en el
  problema relajado).
- `planificador.validar_plan(plan, inicial, objetivo)` → `(valido, coste)`.

## Referencias

- Russell, S. y Norvig, P. (2021). *Artificial Intelligence: A Modern Approach* (4.ª ed.).
  Pearson. Planificación clásica, heurísticas y monitorización con replanificación.
- Bonet, B. y Geffner, H. (2001). "Planning as heuristic search". *Artificial Intelligence*,
  129(1-2), pp. 5-33. Heurísticas hmax y hadd.
- Hagberg, A. A., Schult, D. A. y Swart, P. J. (2008). "Exploring network structure, dynamics,
  and function using NetworkX". En *Proceedings of the 7th Python in Science Conference
  (SciPy 2008)*, pp. 11-15.
- Hunter, J. D. (2007). "Matplotlib: A 2D graphics environment". *Computing in Science &
  Engineering*, 9(3), pp. 90-95.
- Apuntes de la asignatura IA Simbólica (MUIA), tema de planificación.

## Uso de IA generativa

La declaración de uso de IA generativa se entrega en un documento aparte.
