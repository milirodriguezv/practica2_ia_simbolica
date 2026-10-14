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
```

- `--instancia`: `I1` (juguete), `I2` (Norte/Sur), `I3` (peninsular simplificada).
- `--algoritmo`: `ucs`, `astar`, `voraz`.
- `--heuristica`: `h0`, `hprec`, `hmax`, `hadd`.
- `--individual`: bloques individuales en lugar de la versión agregada.

## Experimentos

`python experimentos.py E1 E2 E3 E4 E5` (o solo los que se quieran). Cada uno
guarda sus tablas en `resultados/` y su figura en `figuras/`. Las semillas son
fijas, así que los resultados se repiten salvo los tiempos.

| Id | Pregunta | Qué mide | Tarda |
|---|---|---|---|
| E1 | ¿Qué heurística guía mejor cuando los recursos se gastan? | A* con h0, hprec, hmax y hadd, y voraz con hadd, en I1-I3: nodos, tiempo y maniobras de más. Además, precisión h/h* de cada heurística en todos los estados, en los estados trampa y en los estados sin salida | ~3 min |
| E2 | ¿Hasta qué tamaño de red llega cada configuración? | Redes G(n) de 2 a 14 subestaciones: % resueltas en 10 s, nodos y tiempo | ~15 min |
| E3 | ¿Cuánto aporta agregar los bloques? | Estados alcanzables y nodos expandidos con bloques individuales y con contadores, en I1-I3 y en el juguete con k bloques | ~3 min |
| E4 | ¿Qué pasa con los fallos? | Averías de línea y disparos de central durante la ejecución, con replanificación | ~10 min |
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
| `dominio.py` | Esquemas de acciones con coste e instanciación (individual y agregada) | Eloísa |
| `instancias.py` | I1, I2, I3 y generador G(n) | Milagros |
| `planificador.py` | Coste uniforme, A*, voraz; `validar_plan` | Milagros |
| `heuristicas.py` | h0, hprec, hmax, hadd (hFF opcional) | Eloísa |
| `replanificacion.py` | Simulador de fallos y bucle ejecutar–monitorizar–replanificar | Milagros |
| `visualizacion.py` | Dibujo de la red paso a paso | Milagros |
| `programacion.py` | (Opcional) precedencias, ruta crítica, Gantt | Milagros |
| `experimentos.py` | E1–E5: ejecutan las búsquedas y guardan las tablas CSV (`resultados/`) | Eloísa (E4: Milagros) |
| `analisis.py` | Espacio de estados completo, coste real de cada estado, estados trampa y sin salida | Eloísa |
| `figuras.py` | Gráficas de los experimentos (`figuras/`) | Eloísa (E4: Milagros) |
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
