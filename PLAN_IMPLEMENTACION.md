# Implementation plan: Milagros's parts

**Status (2026-10-13): all of Milagros's parts are implemented, verified and on `main`** (planner, instances + `validar` + G(n), aggregated version, replanning, experiment E4, visualisation). Each part lists **what** was built, the **design decisions** (with a one-line "why" for the oral defense), and the **real measured results**.

How to use this file for the presentation:
- **[Section 10](#10-presentation-kit)** is the presentation kit: suggested slide outline, numbers cheat sheet, likely questions with answers, glossary, live-demo commands and the list of figures.
- **[Section 9](#9-notes-for-the-presentation--oral-defense)** has the detailed notes per step.
- Sections 0–5 are the technical record (what, why, measured numbers). Section 8 records the decisions taken with Eloísa/Milagros.

---

## 0. The domain in one page (so the plan makes sense)

Think of it as a game with these pieces:

| Piece | Plain meaning | Atoms that describe it |
|---|---|---|
| Substation `S` | A node of the grid. It either has voltage ("is lit") or not. | `ConTension(S)` |
| Line `L` | A cable between two substations of the same zone. A *larga* (long) one can only be lit from a side where a load is **currently supplied**. Otherwise the cable "over-voltages" (Ferranti effect). | `Operativa(L)` |
| Plant `C` | Produces energy. *autonomo* starts alone. *termica* needs voltage at its substation **and** one free block from another plant (to power its own machinery, its "auxiliaries"). | `Operativa(C)`, `EnMarcha(C)` |
| Block `b` | One unit of energy from a plant. It must be **activated**, then it is **free** until a load (or a thermal start) uses it. | `Activado(b)`, `Libre(b)`, `Usa(k,b)`, `Auxiliar(b,C)` |
| Load `k` | A consumer. Each uses exactly one block. *prioritaria* = hospital. A normal load needs the hospitals of its substation connected first. | `Suministrada(k)` |
| Zone `z` | An island restored on its own. Two zones can share blocks only after being coupled. | `Alcanza(z1,z2)` |

**Start:** everything dark, everything working (`Operativa`), each zone reaches itself (`Alcanza(z,z)`).
**Goal:** every load `Suministrada` + every directly interconnected zone pair coupled (`Alcanza(z1,z2)` with `z1 < z2`).
**Cost:** every maneuver costs 1, except `ExtenderAlcance` (cost 0). It's a bookkeeping step: "if A reaches B and B reaches C, then A reaches C".

**Worked example, I1 (already in `instancias.py`), optimal cost 14:**
`ArrancarAutonomo(H1)` (1) → activate 2 blocks of H1 (2) → connect hospital P1 (1, so now S1 "feeds a load") → `EnergizarLarga(L12,S1,S2,N,P1)` (1; the action names the supplied load that allows it) → `ArrancarTermica(T1)` with H1's 2nd block (1) → activate 4 blocks of T1 (4) → connect B1, B2, I1, I2 (4). Total: 1+2+1+1+1+4+4 = **14**. Supply 6 blocks = demand 5 loads + 1 auxiliary block. It's exactly enough. This is the first number the planner must reproduce.

---

## 1. `planificador.py`: forward search (do this FIRST, everything else needs it to be tested)

### What
- `buscar(acciones, inicial, objetivo, heuristica, modo="astar", limite_tiempo=None, limite_nodos=None)` → `(plan, estadisticas)`
- `validar_plan(plan, inicial, objetivo)` → `(valido, coste)`

### Algorithm (one function for the three modes)
Only the priority `f` changes between modes:

| `modo` | `f(n)` | Guarantees |
|---|---|---|
| `ucs` | `g` | optimal |
| `astar` | `g + h` | optimal if `h` is admissible (h0, hprec, hmax) |
| `voraz` | `h` | fast, **not** optimal |

Steps:
1. Open list = `heapq` of tuples `(f, h, contador, g, estado)`. Python compares tuples left to right, so:
   - lowest `f` first;
   - **if `f` ties, lowest `h` first** (the node the heuristic sees as closest to the goal). *Implemented after step 1 review, see [section 9](#9-notes-for-the-presentation--oral-defense).*
   - if `h` also ties, the oldest first: `contador` is an increasing integer, so ties are FIFO (first in, first out), which is deterministic and reproducible. It never repeats, so Python never compares the frozensets.
   - `g` is stored so outdated copies can be detected in every mode (in greedy mode `f = h` says nothing about `g`).
2. `mejor_g = {estado: g}` and `padre = {estado: (estado_anterior, accion)}` to rebuild the plan at the end.
3. Pop the node with lowest `f`. If its `g` is worse than `mejor_g[estado]`, it's an outdated copy, so skip it ("lazy deletion": simpler than editing the heap in place).
4. **Goal test when popping (expanding), not when generating.** Why: with action costs 0 and 1, a goal found while generating might not be the cheapest one. Testing on expansion keeps UCS/A* optimal.
5. Add the state to `cerrados` and generate successors: for every action with `aplicable(estado, a)`, compute `resultado(estado, a)` and `g' = g + a.coste`. **g adds up the costs, not the number of steps.** This matters because `ExtenderAlcance` costs 0.
6. If the successor is new, or was reached before with a **higher g** (even if already closed), update `mejor_g`/`padre` and push it. Why reopen closed states: `hadd` is not admissible, so a state can be closed via a worse path first. Reopening keeps the search correct. With admissible and consistent heuristics it simply never happens.
7. If `h(successor) == math.inf`, don't push it. Why: hmax/hadd return infinity when the goal is unreachable even in the relaxed problem, so that branch is a dead end.
8. Stop with `plan = None` if the open list empties (no solution), or the time/node limit is hit.

### Statistics (dict)
`expandidos`, `generados` (every successor created, before checking duplicates), `tiempo` (seconds, `time.perf_counter`), `longitud` (number of actions), `coste` (sum of costs), `resultado` ∈ `"resuelto" | "sin_solucion" | "limite_tiempo" | "limite_nodos"`.
Why record `resultado`: E2 needs to tell "unsolvable" apart from "ran out of time".

### `validar_plan`
Apply actions one by one from `inicial`. If any is not applicable, return `(False, coste_hasta_ahi)`. At the end it is valid iff `objetivo <= estado`. It is independent of the search, so it is a real check, not the search grading itself.

### Known limitation (to mention, not fix now)
Finding applicable actions scans **all** actions at every expansion. That is simple and fine for I1/I2. If I3 or G(n) are too slow, the first optimisation would be an index "action → by precondition". Wait for the E2 numbers before doing that.

### Verification
- I1 individual: `ucs`, `astar+h0`, `astar+hprec`, `astar+hmax` must all give **cost 14** and `validar_plan → True`.
- `astar+hadd` and `voraz+hadd`: cost ≥ 14 (may be higher, they aren't optimal).
- Expanded nodes should decrease h0 → hprec → hmax (better-informed heuristics expand less). I'll report the real numbers.
- A deliberately broken plan (an action removed) must give `valido = False`.

### ✅ Done: real results on I1 (individual version, 68 actions, with the h tie-break)
| Mode + h | Cost | Expanded | Generated | Time | `validar_plan` |
|---|---|---|---|---|---|
| ucs + h0 | 14 | 1,273 | 6,579 | 0.01 s | (True, 14) |
| astar + h0 | 14 | 1,273 | 6,579 | 0.01 s | (True, 14) |
| astar + hprec | 14 | 904 | 4,599 | 0.01 s | (True, 14) |
| astar + hmax | 14 | 890 | 5,047 | 0.10 s | (True, 14) |
| astar + hadd | 14 | 281 | 1,595 | 0.04 s | (True, 14) |
| voraz + hadd | 14 | 36 | 164 | 0.01 s | (True, 14) |
| voraz + hprec | 14 | 27 | 88 | 0.00 s | (True, 14) |

With FIFO-only ties (no h tie-break; measured with a scratch copy of the planner), A* expands **1,273 nodes with every heuristic** (h0, hprec, hmax and hadd), the same as UCS. Removing any action from the plan gives `valido = False`; `limite_nodos=5` returns `None` with `"limite_nodos"`.

---

## 2. `instancias.py`: I1, I2, I3, G(n) and `validar(red)`

### Design decision: functions keep returning a `Red`, not `problema(red)`
The current code already does this: `red_i1()` returns the `Red` and `cargar()` turns it into a problem. **Kept** because `visualizacion.py` and `replanificacion.py` need the `Red` itself (layout, which loads hang from which plant). `cargar(nombre)` still returns `(acciones, inicial, objetivo)` as the interface contract says. *(Q3: went ahead with this default.)*

### `validar(red)` → list of problems (empty list = OK)
Structural checks, cheap, each with a readable message:
1. Every zone has at least one `autonomo` plant (otherwise nothing can start there).
2. Every line joins two substations **of the same zone**. Why: `dominio.py` silently skips cross-zone lines, so a typo would vanish without an error.
3. Every substation can get voltage: a breadth-first search (BFS) from the substations with an autonomous plant, where a *larga* line can only be crossed from a substation that has at least one load (overvoltage rule).
4. Every interconnection joins substations of **different** zones (so border substations are reachable by check 3).
5. Total blocks ≥ number of loads + number of thermal plants (each load uses 1 block, each thermal start uses 1 block for its auxiliaries).
6. Extra safety net: `hmax(inicial, objetivo, acciones) < inf`, meaning the goal is reachable in the relaxed problem.

Honest caveat for the defense: these are **necessary** conditions. They are designed so the instances are solvable, and the real proof is that the planner finds a plan. Every fixed instance will be run through the planner.

### I1 (exists)
Keep as is. Verify `validar(red_i1()) == []`.

### I2: North/South (✅ implemented, resized after review)
| Zone | Substation | Plant | Loads | Lines |
|---|---|---|---|---|
| N | S1 | H1 autonomo, 2 blocks | P1 (hospital) | S1–S2 larga |
| N | S2 | T1 termica, 2 blocks | – | S2–S3 corta |
| N | S3 | – | B1 | |
| S | S4 | H2 autonomo, 2 blocks | P2 (hospital) | S4–S5 corta, S4–S6 larga |
| S | S5 | – | B2, B3 | |
| S | S6 | T2 termica, 2 blocks | P3 (hospital) | |

Interconnection: (S3, S5). Demand: 6 loads + 2 thermals = 8; supply 2+2+2+2 = 8. By zone, N has 1 spare block (4 for 3) and S is 1 short (4 for 5), so the plan **must couple N and S and pass a block from N to S**.
Why this shape: each zone has one long line (tests the overvoltage rule), one thermal (tests the auxiliary block), hospitals in both zones, and coupling is in the goal.

**Why it was resized (decision after step 2 review, option 1; historical numbers, old `Cargada` rule).** The first version (thermals with 3 blocks, plus industries I1 in S2 and I2 in S6: 10 blocks, 189 actions) could not be solved optimally with individual blocks: UCS hit the 120 s limit after 1.1M expansions, and A* with hprec/hmax/hadd hit it too (A*+hprec with 500 s filled the 8 GB of RAM). Only greedy+hadd solved it (cost 27, which equals the counting lower bound, so it is optimal). Shrinking it gives three instances of increasing difficulty: I1 trivial, **I2 medium (every heuristic reaches the optimum, so E1 compares them fairly)**, I3 hard (shows the explosion the aggregated version solves).

**Real results (individual version, 117 actions, limit 120 s):**
| Mode + h | Cost | Expanded | Generated | Time | `validar_plan` |
|---|---|---|---|---|---|
| ucs + h0 | 23 | 68,061 | 318,128 | 1.05 s | (True, 23) |
| astar + hprec | 23 | 50,146 | 232,955 | 0.78 s | (True, 23) |
| astar + hmax | 23 | 50,350 | 260,611 | 11.6 s | (True, 23) |
| astar + hadd | 23 | 27,486 | 146,768 | 8.2 s | (True, 23) |
| voraz + hadd | 23 | 161 | 754 | 0.07 s | (True, 23) |
| voraz + hprec | **25** | 149 | 516 | 0.00 s | (True, 25): greedy, not optimal |

Optimum by counting: 2 autonomous starts + 8 activations + 2 thermal starts + 6 loads + 4 line energizations + 1 coupling = **23**.

### I3: Peninsular simplified (✅ implemented, resized after step 4 review)
| Zone | Substations (plant, blocks; loads) | Lines |
|---|---|---|
| NO | NO1 (H1 autonomo, 1; P1 hospital, B1), NO2 (T1 termica, 3; I1) | NO1–NO2 corta |
| NE | NE1 (H2 autonomo, 2; P2 hospital), NE2 (border, no load) | NE1–NE2 **larga** |
| C | C1 (H3 autonomo, 1; P3 hospital), C2 (B2) | C1–C2 **larga** |
| S | S1 (H4 autonomo, 1; P4 hospital) | – |

- **Interconnections:** a **chain through C**: NO2–C1, C1–NE2, C1–S1. NO–NE, NO–S and NE–S have no direct link, so `ExtenderAlcance` is grounded. Goal: 7 `Suministrada` + `Alcanza(C,NE)`, `Alcanza(C,NO)`, `Alcanza(C,S)`.
- **Supply = demand = 8** (7 loads + 1 thermal start). By zone: NO 4/4, NE 2/1 (+1), **C 1/2 (−1)**, S 1/1 → zones must couple and share a block.
- Keeps: 4 zones, one autonomous plant per zone, 1 thermal (reached from H1 by a short line), 2 long lines, 4 hospitals, B1 sharing NO1 with hospital P1 (priority rule).
- **One exception to the generator's rule:** NE's border (NE2) sits behind NE's long line. It's solvable because NE has a spare block: after P2 is connected, one block stays free to couple with C. The version that follows the rule strictly was too big even aggregated (971k states).
- Size: 7 substations, **138 aggregated / 121 individual** actions.

**Why it was resized (decision after step 4 review, option 1; historical numbers, old `Cargada` rule).** The original I3 (4 zones × 3 substations, 12 loads, 2 thermals, 14 blocks, 383 individual / 427 aggregated actions) could not be solved optimally by **any** configuration, not even aggregated (UCS and A*+hprec hit 500k nodes; A*+hprec with 1.5M nodes used 2.2 GB of RAM). Only greedy+hprec found a plan (cost 53, optimum 43 by counting). The goal of the resize: **aggregated solves it optimally, individual doesn't**, so I3 shows what aggregation gains (E3).

**Candidates tried** (historical: measured with the old `Cargada` rule while designing I3; aggregated unless noted, 120 s / 500k nodes):
| Candidate | Description | Result |
|---|---|---|
| A | 8 substations, 9 loads, 1 thermal, 10 blocks | UCS / A*+hprec hit 500k (2 GB); A*+hmax/hadd hit 120 s |
| B | 7 substations, 7 loads, T1 with 2 blocks, NE load behind the long line | UCS / A*+hprec hit 500k; 899k reachable states (1.4 GB) |
| B2 / B3 | B with only NO+C / NO+NE+C | 417 / 32.7k states: **each extra zone multiplies the space ×30–80** |
| D | 6 loads, T1 with 1 block | Rejected: the thermal is useless (uses 1 block, gives 1), optimum 22 < bound 24 |
| D2 | D with H1 1 block, T1 2 blocks | Aggregated UCS 0.6 s, but individual UCS also solves it (2.7 s): gain too small |
| **E (final)** | D2 + T1 with 3 blocks + load I1 at NO2 | chosen; current results below |
| E2 | Like D2 but following the border rule strictly | 971k states; UCS hits 500k in both versions |

**Real results, aggregated** (`cargar('I3')`, 138 actions):
| Mode + h | Cost | Length | Expanded | Generated | Time | `validar_plan` |
|---|---|---|---|---|---|---|
| ucs + h0 | 26 | 26 | 88,689 | 566,640 | 1.78 s | (True, 26) |
| astar + hprec | 26 | 27 | 76,865 | 484,275 | 1.62 s | (True, 26) |
| astar + hmax | 26 | 27 | 52,841 | 384,468 | 15.3 s | (True, 26) |
| astar + hadd | 26 | 26 | 17,046 | 134,286 | 7.55 s | (True, 26) |
| voraz + hadd | 26 | 26 | 164 | 1,094 | 0.08 s | (True, 26) |
| voraz + hprec | 30 | 31 | 9,093 | 37,779 | 0.14 s | (True, 30) |

**Real results, individual** (`cargar('I3', agregada=False)`, 121 actions):
| Mode + h | Cost | Expanded | Generated | Time | Result |
|---|---|---|---|---|---|
| ucs + h0 | – | 500,000 | 3,486,222 | 12.9 s | node limit |
| astar + hprec | – | 500,000 | 3,388,253 | 14.8 s | node limit |
| astar + hmax | – | 327,292 | 2,378,969 | 120 s | time limit |
| astar + hadd | 26 | 176,113 | 1,463,207 | 81.3 s | solved, (True, 26) |
| voraz + hadd | 26 | 167 | 1,141 | 0.08 s | solved, (True, 26) |
| voraz + hprec | 30 | 57,021 | 266,583 | 0.91 s | solved, (True, 30) |

**Optimum by counting:** 4 autonomous starts + 8 activations + 1 thermal start + 7 loads + 3 line energizations + 3 couplings = **26**, equal to what UCS and A* find. (Plan length 27 with cost 26 = one `ExtenderAlcance`, which costs 0.)

**`ExtenderAlcance`:** UCS and A*+hadd don't use it (length 26); A*+hprec and A*+hmax use it once (length 27, cost 26, because it costs 0). Blocks can also travel through C by swaps.

**Aggregated optimal plan (UCS, cost 26):** start the 4 hydro plants (1–4) → activate their 5 blocks (5–9) → `EnergizarCorta(LNO12)` (10) → `ArrancarTermica(T1,NO2,NO,NO,1)` (11) → activate T1's 3 blocks (12–14) → `ConectarPrioritaria` P1 (15), P2 (16) → `EnergizarLarga(LNE12,NE1,NE2,NE,P2)` (17) → `ConectarCarga` B1 (18) → `AcoplarZonas(NO,C)` (19) → P3 with a NO block (20) → `EnergizarLarga(LC12,C1,C2,C,P3)` (21) → `AcoplarZonas(C,NE)` (22) → B2 with an NE block (23) → `AcoplarZonas(C,S)` (24) → P4 (25) → I1 with C's block (26).

### G(n): generator (✅ implemented)
**Purpose.** I1–I3 are three fixed, hand-made grids. Experiments E2 ("how does the search scale?") and E5 ("where is it hard?") need **many grids of controlled size and difficulty**, so the generator builds them automatically. `n` controls the size, `margen` controls how many blocks there are compared to what's needed, and `semilla` makes it reproducible.

`red_generada(n, margen=1.0, semilla=0)`, `n` = number of substations.
1. `rng = random.Random(semilla)`. Why a private `Random` and not `random.seed`: it doesn't affect other modules, and the same `(n, margen, semilla)` always gives the same grid.
2. Zones: `n_zonas = max(1, n // 4)`, substations spread as evenly as possible, numbered S1..Sn zone by zone.
3. Per zone, a **tree**: the first substation (root) gets the zone's hydro plant `H<i>` and a hospital. Every next substation hangs from a random earlier one with a *corta* or *larga* line (`PROB_LARGA = 0.3`).
4. Random loads: 0–2 per substation (`MAX_CARGAS = 2`), each a hospital with probability `PROB_PRIORITARIA = 0.25`. Then, if a long line starts at a substation without a load, one is added there. So every substation can get voltage **by construction**.
5. **Candidate substations** = those the root reaches through **short lines only**. Thermals (`PROB_TERMICA = 0.3` per candidate except the root) and border substations are only placed on candidates. *Added during implementation:* without it, `margen = 1.0` could build grids that pass `validar` but are **unsolvable** (e.g. a 1-block hydro plant, a thermal behind a long line: crossing the long line needs a load connected, which uses the only block, so the thermal can never start).
6. Blocks: `total = ceil(margen × (loads + thermals))`, 1 per plant first, the rest one by one to random plants. If there are more plants than blocks, the 1-block minimum wins (documented). `margen < 1` makes it **unsolvable on purpose** (E5).
7. Interconnections: chain Z1–Z2, Z2–Z3, … with a random candidate border substation in each zone.
8. Names: zones `Z1…`, substations `S1..Sn`, lines `L<a>_<b>` (a = parent), hydro `H<i>`, thermals `T<j>`, hospitals `P<k>`, normal loads `B<k>`.

**Real results:**
- Reproducible: same `(n, margen, semilla)` → identical grid; different seeds → different grids; global `random` untouched.
- `validar` returns `[]` for n ∈ {4, 8, 12, 16, 20} × seeds 0–2 × margen {1.0, 1.2}. With margen 0.8 it reports the shortage in 14 of 15 cases (exception: n = 4, seed 1, where `ceil(0.8 × 3) = 3` removes the shortage).
- Solvability: a fixed-order script plan validated **all 120** grids tested (n ∈ {4,8,12,16,20,40} × seeds 0–9 × margen {1.0, 1.2}).
- Size (margen 1.0, seed 0, individual / aggregated actions): n = 4 → 58 / 90, n = 8 → 388 / 499, n = 12 → 681 / 809, n = 16 → 1,240 / 1,446, n = 20 → 1,598 / 1,789.

Searches (individual version, seed 0, margen 1.0, limits 60 s / 300,000 nodes, one at a time):
| n | ucs + h0 | astar + hprec | astar + hadd | voraz + hadd | voraz + hprec |
|---|---|---|---|---|---|
| 4 | 16 (22,239 exp., 0.26 s) | 16 (14,012 exp., 0.13 s) | 16 (1,182 exp., 0.26 s) | 16 (170 exp., 0.03 s) | 16 (39 exp., 0.00 s) |
| 8 (bound 39) | node limit | node limit | time limit | 41 (703 exp., 1.8 s) | 41 (1,028 exp., 0.03 s) |
| 12 (bound 54) | node limit | node limit | time limit | time limit | 64 (8,640 exp., 0.55 s) |

Consequences for the experiments: E2 jumps from "solved" (n = 4) to "nothing optimal finishes" (n = 8) with individual blocks, so E2 should step n by 1 and/or use the aggregated version. E5 should use n ≥ 8 so rounding doesn't hide the shortage.

### Verification
`validar` on I1, I2, I3, and G(n) for n = 4, 8, 12, 16 with 3 seeds. Solve I1, I2 and I3 with A*+hmax and report cost, nodes and time.

✅ `validar` returns `[]` for I1, I2, I3 and detects every broken network tested: zone without an autonomous plant, cross-zone line, substation unreachable behind an unloaded long line, too few blocks, interconnection inside one zone, load on a missing substation, goal unreachable even relaxed (hmax = inf).

---

## 3. `problema_agregado`: aggregated version with counters (✅ implemented in `dominio_agregado.py`)

### Idea in plain words
In the individual version, "load B1 uses block bH1_1" and "load B1 uses block bH1_2" are **different states**, even though they're equivalent for the plan. That multiplies the search space. The aggregated version only counts **how many** free blocks each zone has: `Libres(z,n)`.

### How a counter works without numbers in the logic
The planner only knows sets of atoms, so "n" is part of the atom name: `Libres(N,2)`. To go from 2 to 3 the action deletes `Libres(N,2)` and adds `Libres(N,3)`. "3 follows 2" is the static fact `Sig(2,3)`. Following the domain's convention, it is **resolved at instantiation**: there is one action copy per value of n, and `Sig` never appears in states.

### Changes per action (same semantics as the individual version), as implemented
| Individual | Aggregated |
|---|---|
| `ArrancarAutonomo(c,s)` | identical (imported from `dominio.py`) |
| `ActivarBloque(b,c)`: `Activado(b)`, `Libre(b)` | `ActivarBloque(c,z,m,n)`: `Activados(c,m)→(c,m+1)` with `m < n_bloques`, and `Libres(z,n)→(z,n+1)` |
| `EnergizarCorta` / `EnergizarLarga` | identical (imported) |
| `ArrancarTermica(c,s,b,zb,zs)` | `ArrancarTermica(c,s,zb,zs,n)`: `n ≥ 1`, `Libres(zb,n)→(zb,n-1)`, adds `Auxiliar(c,zb)` |
| `ConectarPrioritaria` / `ConectarCarga(k,s,b,zb,zs)` | `(k,s,zb,zs,n)`: `n ≥ 1`, `Libres(zb,n)→(zb,n-1)`, adds `Usa(k,zb)` (the **zone**, needed to give the block back); same `Alcanza` and priority preconditions |
| `Deslastrar(k,b)` | `Deslastrar(k,z,n)`: needs `Usa(k,z)` and `n < max`; `Libres(z,n)→(z,n+1)`; deletes `Usa` and `Suministrada` |
| `AcoplarZonas(z1,z2,s1,s2,b1,b2)` | `AcoplarZonas(z1,z2,s1,s2,n1,n2)`: `n1, n2 ≥ 1`; counters unchanged (blocks are only a margin) |
| `ExtenderAlcance` | identical (imported) |

**A thermal can't use its own blocks, and no extra rule is needed for that.** Its blocks are only activated with `EnMarcha(c)`, and `ArrancarTermica` requires `c` to be stopped, so none of them can be in `Libres` at that moment (explained in a code comment).

**Quirks of the individual version kept on purpose** (same semantics, so E3 compares like with like): ~~`Deslastrar` does not delete `Cargada(s)`~~ (gone: `Cargada` was removed on 2026-10-12, see section 7.1); `ActivarBloque` does not require `Operativa(c)`; only one coupling action per interconnection, in its listed direction.

Initial state adds `Libres(z,0)` and `Activados(c,0)`. Goal is unchanged. The upper bound of each counter is the number of blocks in that zone/plant. This also keeps the "no action achieves two goal atoms" property, so hprec stays admissible.

### Where the code goes (decided: Q2 and Q6)
New file **`dominio_agregado.py`** with `problema_agregado(red)`; it imports from `dominio.py` the unchanged parts (`Accion`, `atomo`, `estado_inicial`, `objetivo`, the schemas without blocks). **`dominio.py` was not touched by Milagros**; Eloísa later deleted its old `problema_agregado` stub (commit `689c54f`). `instancias.cargar(nombre, agregada=True)` now calls `dominio_agregado.problema_agregado`, so `python main.py` works without `--individual` (this also solves Q5). Q6 ("same fixes") was read as **same rules**: every rule of the individual version is copied exactly, including its quirks.

### Verification
- I1 aggregated: optimal cost must be **14 as well** (same semantics ⇒ same optimal cost).
- Compare expanded nodes individual vs aggregated on I1/I2/I3 (expected: far fewer with aggregation; that's E3).
- The aggregated plan validates with `validar_plan` on the aggregated problem.

### ✅ Real results

**Invariants** (measured before the 2026-10-12 change; that change only touched `EnergizarLarga`, which doesn't touch any counter, so they still hold). 200 random walks × 50 actions (seed 42) on I1, I2, I3, G(4) seeds 0/1/2 and G(16): 10,000 states per instance, 0 failures. Always exactly one `Libres(z,·)` per zone and one `Activados(c,·)` per plant, all within bounds, and per zone *free + in use (`Usa` + `Auxiliar`) = activated*. No action adds more than one goal atom and no cost-0 action adds any, so **hprec stays admissible**.

**Same semantics, checked on the whole state space** (re-checked after the 2026-10-12 change). Every reachable state of both versions was enumerated; converting each individual state into counters gives **exactly** the set of aggregated reachable states:
| Instance | Individual states | Aggregated states | Sets equal |
|---|---|---|---|
| I1 | 1,321 | 62 | yes |
| I2 | 70,365 | 3,287 | yes |
| G(4) seed 0 | 24,399 | 403 | yes |
| G(4) seed 1 | 217 | 52 | yes |
| G(4) seed 2 | 3,993 | 82 | yes |

**Individual vs aggregated** (120 s / 500k nodes; every plan passes `validar_plan`). Cells: cost / expanded / generated / time (s).
| Instance | Config | Individual | Aggregated |
|---|---|---|---|
| I1 (68 vs 102 actions) | ucs | 14 / 1273 / 6579 / 0.01 | 14 / 61 / 214 / 0.00 |
| I1 | A*+hprec | 14 / 904 / 4599 / 0.01 | 14 / 47 / 158 / 0.00 |
| I1 | A*+hmax | 14 / 890 / 5047 / 0.10 | 14 / 54 / 186 / 0.01 |
| I1 | A*+hadd | 14 / 281 / 1595 / 0.04 | 14 / 33 / 119 / 0.01 |
| I1 | voraz+hadd | 14 / 36 / 164 / 0.01 | 14 / 26 / 84 / 0.01 |
| I2 (117 vs 145 actions) | ucs | 23 / 68061 / 318128 / 1.05 | 23 / 3252 / 13485 / 0.05 |
| I2 | A*+hprec | 23 / 50146 / 232955 / 0.78 | 23 / 2881 / 11931 / 0.04 |
| I2 | A*+hmax | 23 / 50350 / 260611 / 11.63 | 23 / 2868 / 12288 / 0.81 |
| I2 | A*+hadd | 23 / 27486 / 146768 / 8.23 | 23 / 1694 / 8001 / 0.61 |
| I2 | voraz+hadd | 23 / 161 / 754 / 0.07 | 23 / 94 / 434 / 0.06 |
| G(4) s0 (58 vs 90 actions) | ucs | 16 / 22239 / 106320 / 0.26 | 16 / 396 / 1450 / 0.00 |
| G(4) s0 | A*+hprec | 16 / 14012 / 64339 / 0.13 | 16 / 314 / 1142 / 0.00 |
| G(4) s0 | A*+hmax | 16 / 16256 / 85898 / 1.89 | 16 / 362 / 1358 / 0.05 |
| G(4) s0 | A*+hadd | 16 / 1182 / 5950 / 0.26 | 16 / 86 / 373 / 0.03 |
| G(4) s0 | voraz+hadd | 16 / 170 / 621 / 0.03 | 16 / 31 / 118 / 0.01 |
| G(4) s1 | ucs | 9 / 197 / 641 / 0.00 | 9 / 50 / 129 / 0.00 |
| G(4) s1 | A*+hprec | 9 / 145 / 507 / 0.00 | 9 / 38 / 106 / 0.00 |
| G(4) s1 | A*+hmax | 9 / 111 / 407 / 0.01 | 9 / 34 / 90 / 0.00 |
| G(4) s1 | A*+hadd | 9 / 16 / 61 / 0.00 | 9 / 9 / 24 / 0.00 |
| G(4) s1 | voraz+hadd | 9 / 10 / 37 / 0.00 | 9 / 9 / 24 / 0.00 |
| G(4) s2 | ucs | 14 / 3873 / 16601 / 0.03 | 14 / 81 / 243 / 0.00 |
| G(4) s2 | A*+hprec | 14 / 3209 / 13864 / 0.03 | 14 / 71 / 213 / 0.00 |
| G(4) s2 | A*+hmax | 14 / 2974 / 13844 / 0.26 | 14 / 74 / 222 / 0.01 |
| G(4) s2 | A*+hadd | 14 / 154 / 718 / 0.02 | 14 / 24 / 82 / 0.00 |
| G(4) s2 | voraz+hadd | 14 / 20 / 95 / 0.01 | 14 / 16 / 50 / 0.00 |

Same optimum everywhere both finish; the aggregated version expands **16–21× fewer nodes on I2 and 14–56× fewer on G(4) seed 0**. The current I3 is in section 2: aggregated, every configuration finishes (UCS 1.8 s); individual, only A*+hadd (81 s) and the greedy searches do.

**Original I3 (12 substations, 14 blocks), aggregated, before resizing** (historical, old `Cargada` rule):
| Config | Result | Expanded | Generated | Time (s) |
|---|---|---|---|---|
| ucs | node limit | 500,000 | 4,274,366 | 24.6 |
| A*+hprec | node limit | 500,000 | 4,228,151 | 30.7 |
| A*+hprec (300 s / 1.5M) | node limit, 2.18 GB RAM | 1,500,000 | 13,359,670 | 256.6 |
| A*+hmax | time limit | 68,322 | 533,190 | 120 |
| A*+hadd | time limit | 20,523 | 329,129 | 120 |
| voraz+hadd | time limit | 54,707 | 603,786 | 120 |
| voraz+hprec | solved, cost 53 (optimum 43) | 312 | 2,440 | 0.01 |

→ I3 was resized (decision after step 4 review, see section 2).

**G(n) aggregated, margen 1.0, seed 0 (120 s / 500k):**
| n | ucs | A*+hprec | A*+hadd | voraz+hadd | voraz+hprec |
|---|---|---|---|---|---|
| 8 (bound 39) | node limit, 26 s | node limit, 28 s | time limit (26,866 exp.) | **41**, 314 exp., 1.1 s | **41**, 375 exp., 0.01 s |
| 12 (bound 54) | node limit, 36 s | node limit, 42 s | time limit (7,335 exp.) | time limit (35,067 exp.) | **64**, 1,611 exp., 0.10 s |
| 16 (bound 72) | node limit, 55 s | node limit, 58 s | time limit (3,336 exp.) | time limit (5,850 exp.) | node limit, 76 s |

**Heuristic values at the initial state are identical in both versions:**
| Instance | hprec | hmax | hadd |
|---|---|---|---|
| I1 | 5 | 5 | 38 |
| I2 | 7 | 6 | 51 |
| I3 | 10 | 5 | 65 |

**`main.py`:** `python3 main.py --instancia I2 --algoritmo astar --heuristica hprec` now runs aggregated by default: valid 23-step plan, 2,881 expanded, 0.04 s.

**I1 aggregated optimal plan (ucs, cost 14):** `ArrancarAutonomo(H1,S1)` → `ActivarBloque(H1,N,0,0)` → `ActivarBloque(H1,N,1,1)` → `ConectarPrioritaria(P1,S1,N,N,2)` → `EnergizarLarga(L12,S1,S2,N,P1)` → `ArrancarTermica(T1,S2,N,N,1)` → `ActivarBloque(T1,N,0,0)` … `(T1,N,3,3)` (4 steps) → `ConectarCarga(B1,S1,N,N,4)` → `ConectarCarga(B2,S1,N,N,3)` → `ConectarCarga(I1,S2,N,N,2)` → `ConectarCarga(I2,S2,N,N,1)`. Reading the numbers: `ActivarBloque(c,z,m,n)` = plant `c` had `m` activated, zone `z` had `n` free; `Conectar…(…,n)` = zone had `n` free before connecting.

---

## 4. `replanificacion.py`: execute, monitor, replan

### Two states, a key idea for the defense
- **Believed state:** what the plan assumes will happen.
- **Real state:** the simulated world, where unexpected events happen. The agent only knows reality by *observing* it before each step.

It runs on the **individual** version. Why: when a plant trips, we need to know *which* loads were using *its* blocks (`Usa(k,b)`), and the counter version forgets that.

### Events (they are not agent actions, so they cost nothing and aren't in the plan)
- `averia_linea(estado, l)`: deletes `Operativa(l)`. Substations already lit stay lit (the line is only needed to light new ones).
- `disparo_central(estado, c)` (semantics confirmed, Q4):
  - deletes `EnMarcha(c)` and `Operativa(c)` (it can't be restarted);
  - its blocks disappear: deletes `Activado(b)` and `Libre(b)` for each block of `c`;
  - every load `k` with `Usa(k,b)` on one of those blocks loses supply: deletes `Usa(k,b)` and `Suministrada(k)` (counted as **lost loads**);
  - if `c` is thermal, its auxiliary block from another plant is **released**: deletes `Auxiliar(b',c)`, adds `Libre(b')`;
  - simplification: substations keep `ConTension` (other sources in the island hold the voltage).
  - no cascade: if a block of `c` was the auxiliary block of a running thermal, that thermal keeps running (`Auxiliar(b,T)` stays, pointing to a block that no longer exists); auxiliaries are only needed to start.

### Loop `ejecutar_con_fallos(red, acciones, inicial, objetivo, heuristica, modo, prob_fallo, semilla, limite_tiempo)`
1. Plan from `inicial`.
2. For each step: with probability `prob_fallo`, inject a random event (random line or plant still `Operativa`), using `rng = random.Random(semilla)`.
3. Monitor: check that the **rest of the plan** still works from the real state (`validar_plan` on the remaining actions). If not → replan from the real state and measure the replanning time. Why check the whole remainder and not only the next action: a failure may break a later step, and detecting it early avoids wasted maneuvers.
4. Execute the next action on the real state (`resultado`).
5. If replanning returns `None` → record as **unsolvable** and stop (e.g. the only autonomous plant of a zone tripped).

Returns: `resuelto`, `maniobras` (executed), `maniobras_extra` (executed − original plan cost), `cargas_perdidas`, `replanificaciones`, `tiempo_replanificacion`, `eventos` (list, for the report).

### Verification
- `prob_fallo = 0` ⇒ executes the original plan exactly, 0 extra maneuvers.
- Hand test on I1: trip T1 mid-plan ⇒ expect unsolvable (I1 has no spare blocks).
- I2 with seeds 0–9: same seed ⇒ same result twice (reproducibility).

### ✅ Done: implemented in `replanificacion.py` (real results)

**Final interface** (used by E4 in `experimentos.py`):
- `averia_linea(estado, linea) -> estado`
- `disparo_central(estado, central, red) -> (estado, cargas_perdidas)` (rules A–E of Q4 in the docstring)
- `ejecutar_con_fallos(red, acciones, inicial, objetivo, heuristica, modo="astar", prob_fallo=0.1, semilla=0, limite_tiempo=60, limite_nodos=300_000, tipos_fallo=("linea", "central"), eventos_programados=None) -> dict`
- Returned keys: `resuelto`, `motivo` (`resuelto` / `sin_solucion` / `limite_tiempo` / `limite_nodos`), `maniobras`, `coste`, `coste_plan_original`, `tiempo_plan_original`, `maniobras_extra` (`None` if not solved), `cargas_perdidas` (count), `lista_cargas_perdidas`, `replanificaciones`, `tiempo_replanificacion`, `eventos` (e.g. `"paso 11: disparo de la central T1 (pierden suministro: B1, B2)"`), `plan_ejecutado`.
- Must be called with the **individual** version: `a, s, g = instancias.cargar(nombre, agregada=False)`.

**Design decisions beyond the spec:**
- **Signature takes `red`** (the stub didn't): the events need it to know a plant's blocks and type.
- **`tipos_fallo`** lets E4 compare line failures vs plant trips. **`eventos_programados`** (`{paso: (tipo, elemento)}`) forces an event at a given step, for hand tests and for the defense demo.
- **The die is rolled before every step, even without an event**, and candidates are sorted: the random sequence then depends only on the seed (reproducible).
- **Only elements still `Operativa` can fail**, so the loop always ends: there are finitely many elements, and between events the current plan is valid and runs to the end.
- **Replan only if the rest of the plan stops working.** A line that fails after it was used changes nothing (lit substations stay lit), so no replan.
- **Rule (C) refinement:** the thermal's borrowed block is freed only if it still exists (`Activado`). Otherwise "H1 trips, then T1 trips" would bring a block of the dead plant H1 back.
- **`maniobras_extra = None` when not solved:** subtracting costs from a half-executed run would distort E4's averages.
- `cargas_perdidas` counts supply losses: a load lost twice counts twice.

**Verification (individual version, one search at a time, 60 s / 300k nodes). Re-run after the 2026-10-12 change: identical outcomes.**

| Test | Config | Result |
|---|---|---|
| `prob_fallo = 0`, I1 | A*+hadd | solved, cost 14, extra 0, 0 replans (same plan as `buscar`) |
| `prob_fallo = 0`, I2 | A*+hadd | solved, cost 23, extra 0, 0 replans (8.2 s initial search) |
| I1, T1 trips before step 11 | A*+hadd | `sin_solucion`: B1, B2 lost; 4 blocks needed, only 1 left (H1's block given back by C) |
| I1, line L12 fails before step 0 | A*+hadd | `sin_solucion`: L12 is the only way to S2 |
| I1, L12 fails at step 6 (already used) | A*+hadd | solved, extra 0, no replan |
| I1 + spare parallel line (scratch only) | A*+hadd | L12 fails at step 0 → 1 replan, solved, extra 0 |
| I1 + spare thermal T2 with 4 blocks (scratch only) | A*+hadd | T1 trips at step 11 → 1 replan, solved, cost 20 (extra 6: start T2, 4 blocks, reconnect B1, B2) |

I2, `prob_fallo = 0.1`, A*+hprec (fastest optimal config on individual I2, cheap per node; each replan ≤ 0.08 s):

| Seed | Result | Extra | Events |
|---|---|---|---|
| 0 | solved | 0 | none |
| 1 | solved | 1 | step 8: L12 fails (already used); step 19: T1 trips, B2 lost |
| 2 | `sin_solucion` | – | step 2: L23 fails |
| 3 | `sin_solucion` | – | step 5: L12 fails |
| 4 | `sin_solucion` | – | step 4: T1 trips |
| 5 | `sin_solucion` | – | step 6: T2 trips |
| 6 | `sin_solucion` | – | step 4: T2 trips |
| 7 | `sin_solucion` | – | step 3: L23 fails |
| 8 | `sin_solucion` | – | step 4: L46 fails |
| 9 | `sin_solucion` | – | step 4: T2 trips |

- Lines only: seeds 0, 1 solved (extra 0), 2–9 `sin_solucion`. Plants only: seed 0 solved (no event), 1–9 `sin_solucion`.
- Same seed twice ⇒ identical result (checked on seeds 0 and 1, time fields excluded).
- `limite_nodos = 10` on I2 ⇒ `motivo = "limite_nodos"`, `coste_plan_original = None` (the "search gave up" path works).

**⚠️ Finding for E4:** I1–I3 have **exact supply and no spare paths**, so almost every failure is fatal. A plant trip that hits a needed block, or a line failure before the line is used, ends in `sin_solucion`. A line failure after use does nothing. On these instances E4 would mostly measure "% unsolvable", not extra maneuvers, and can't really test the proposal's prediction "trips cost more than line failures". To show recoveries, E4 needs grids with spare capacity: `red_generada(n, margen > 1)` gives spare blocks (helps with trips) but still no spare lines. Alternatively, add a spare line/plant variant. **Solved:** E4 was implemented by Milagros with a redundant variant `red_i2_reserva` (see section 4b).

## 4b. Experiment E4: failures and replanning (✅ done, Milagros)

### What was added
- `instancias.red_i2_reserva()`: I2 plus **twin lines** (`L12b`, `L23b`, `L45b`, `L46b`, each parallel to the original and of the same type) and a **spare thermal** `T3` (2 blocks) at S6. Not in `REDES` (E1–E3 and the CLI are unchanged). `validar` = [], optimum **23** (same as I2: the spares are never used without failures), A*+hprec 147,846 expanded, 3.4 s.
- `experimentos.e4()` plus helpers `_e4_*` and constants `E4_*`. Run: `python3 experimentos.py E4`. Outputs: `resultados/e4.csv` (one row per run), `resultados/e4_resumen.csv`, `figuras/e4.png`.

### Design decisions (with the why)
- **Why I2-reserva exists:** I2 has exact supply and one path per substation, so almost any failure is final. Without spares, E4 could only measure "% unsolvable".
- **Why twin lines and not lines closing a loop:** a loop line (S1–S3, S5–S6) multiplies the possible energizing orders, and A*+hprec didn't finish in 1M nodes. A parallel line creates no new states (the destination ends up lit either way), so the search doesn't grow.
- **Why a 2-block thermal as the spare and not a spare block:** a spare block on a hydro or thermal plant makes the plan *cheaper* (optimum 20–21), so "extra maneuvers" would be measured against a different optimum. A 2-block thermal costs the same as using T1/T2 (start + 2 activations for 1 net block), so the optimum stays 23. It sits at S6 because the search grows least there (compared with S2/S3/S5).
- **Why I3 and I1 are left out:** with individual blocks, the only optimal search that solves I3 is A*+hadd, in ~81 s per search, which is too slow to repeat for many seeds. I1 is a toy with no redundancy and adds nothing beyond I2.
- **Factors:** failure type (lines only vs plants only, to compare them) × `prob_fallo` ∈ {0.05, 0.1, 0.2} × 15 seeds (`SEMILLA + i`). The whole E4 takes 443 s (~7.4 min, 180 runs).
- **Paired comparison:** the same seed rolls the die the same way for both failure types, so failures land on the same steps.
- **A* + hprec:** admissible, so every plan and replan is optimal and "extra" is measured against the minimum. It's the fastest optimal config on individual I2. Limits: 60 s / 300k nodes per search (never reached).

### Real results (15 runs per row; "Extra" = mean over solved runs; % hit limit = 0 everywhere)

| Instance | Failure | p | Events | % solved | % unsolvable | Extra | Lost loads | Replans | Replan time (s) |
|---|---|---|---|---|---|---|---|---|---|
| I2 | line | 0.05 | 0.80 | 46.7 | 53.3 | 0 | 0 | 0.53 | 0.01 |
| I2 | line | 0.1 | 1.07 | 40.0 | 60.0 | 0 | 0 | 0.60 | 0.01 |
| I2 | line | 0.2 | 0.93 | 6.7 | 93.3 | 0 | 0 | 0.93 | 0.02 |
| I2 | plant | 0.05 | 0.80 | 20.0 | 80.0 | 0 | 0.33 | 0.80 | 0.02 |
| I2 | plant | 0.1 | 0.87 | 13.3 | 86.7 | 0 | 0.33 | 0.87 | 0.02 |
| I2 | plant | 0.2 | 0.93 | 6.7 | 93.3 | 0 | 0.13 | 0.93 | 0.02 |
| I2-reserva | line | 0.05 | 1.47 | 100.0 | 0.0 | 0 | 0 | 0.20 | 0.16 |
| I2-reserva | line | 0.1 | 2.80 | 100.0 | 0.0 | 0 | 0 | 0.27 | 0.39 |
| I2-reserva | line | 0.2 | 4.40 | 66.7 | 33.3 | 0 | 0 | 1.07 | 1.58 |
| I2-reserva | plant | 0.05 | 1.07 | 60.0 | 40.0 | 0.67 | 0.53 | 0.93 | 0.19 |
| I2-reserva | plant | 0.1 | 1.33 | 20.0 | 80.0 | 0 | 0.53 | 1.13 | 0.11 |
| I2-reserva | plant | 0.2 | 1.33 | 6.7 | 93.3 | 0 | 0.2 | 1.07 | 0.10 |

Checked by the main session: `validar` and optimum 23 of I2-reserva; individual runs re-executed by hand match the CSV (e.g. reserva/plant/p=0.05/seed 8: T1 trips at step 16, B2 lost, solved with +3; reserva/line/p=0.2/seed 1: L12b then L12 fail before use → `sin_solucion`).

### Reading
- **Hypothesis "trips cost more than line failures": supported on solvability and lost loads.** With redundancy, line failures are survived 100/100/67% of the time vs 60/20/7% for trips. Only trips lose loads (by construction: a line failure never disconnects a load in our model).
- **Not testable on extra maneuvers.** All solved runs had 0 extra except two trip runs with +3 (T1 trips after feeding B2 → start T3 = start + activation + reconnect). Why so many zeros: (1) a recovered failure often costs nothing extra (the twin line costs the same; a T2 trip before T2 starts is replaced by T3 at the same price); (2) **selection bias**: expensive failures tend to be unsolvable, and "extra" is averaged only over solved runs; (3) a line that fails after use changes nothing (lit substations stay lit).
- **The redundancy is uneven:** every line has a 1:1 twin, but four plants share one spare thermal. That favors lines; mention it.
- **Why trips are often fatal even with the spare:** a hydro trip (H1/H2) is always fatal (each zone's only plant that starts alone). H1 tripping even after starting leaves zone N with no free block, so T1 can't start and the zones can't couple (both need a free block). Any second trip is fatal (only one spare).
- **Oddity:** the mean number of events barely grows with p (I2 line: 0.80 → 1.07 → 0.93; I2-reserva plant: 1.07 → 1.33 → 1.33), because a run stops at its first fatal failure. Higher p brings the fatal failure earlier, which leaves fewer steps for more failures.
- **Possible speed-up (not done):** most of the runtime is the same 3.4 s initial search repeated in each I2-reserva run. An optional "initial plan" parameter in `ejecutar_con_fallos` would remove it.

---

## 5. `visualizacion.py`: frames of the plan

- Graph with `networkx`: nodes = substations, edges = lines. Interconnections are drawn too (dotted, different color).
- **Fixed layout**: `nx.spring_layout(G, seed=0)` computed **once** and reused for every frame. Why: if nodes moved between frames, the slides would be unreadable.
- Colors: grey = no voltage, yellow = `ConTension`. *larga* lines dashed, *corta* solid.
- Text next to each node: plants (in operation or not) and loads (supplied or not) as short labels, to keep it simple.
- Title: `Paso i: <action name>`.
- `fotogramas(red, plan, inicial, prefijo)`: applies the plan with `resultado()` and saves `figuras/<prefijo>_00.png`, `_01.png`…
- `matplotlib.use("Agg")` so it saves images without opening windows (it works on any machine and inside scripts).
- Citation in the module docstring and README: Hagberg, Schult & Swart (2008), *NetworkX*; Hunter (2007), *Matplotlib: A 2D graphics environment*.

### Verification
Generate I1 frames (15 images: initial + 14 steps) and open a couple to check them visually.

### ✅ Done: implemented in `visualizacion.py` (branch `feature/visualizacion-plan`)

**Interface:**
- `dibujar_red(red, estado, ax=None, titulo=None, pos=None) -> Axes`: draws one state.
- `fotogramas(red, plan, inicial, prefijo) -> list[str]`: applies the plan with `dominio.resultado()` and saves `figuras/<prefijo>_00.png` (`Paso 0: estado inicial`), `_01.png` (`Paso 1: <action>`)…
- `posiciones(red)` (layout, computed once per network) and `grafo(red)` (`nx.MultiGraph`).
- `python3 visualizacion.py` regenerates the I1 frames: A*+hmax on the **individual** version (890 expanded, 0.1 s), cost 14, 15 images `figuras/i1_00.png` … `i1_14.png`. **Decision (Milagros):** the frames use the individual plan because its titles name the block used (`ActivarBloque(bT1_2,T1)`, `ConectarCarga(I2,S2,bT1_4,N,N)`), easier to explain than the aggregated counters (`ActivarBloque(T1,N,0,0)`). The drawing is the same with either version.

**Design decisions (with the why):**
- **Only atoms that exist in both versions** (`ConTension`, `EnMarcha`, `Operativa`, `Suministrada`, `Alcanza`), so the same function draws individual and aggregated states.
- **Fixed, two-level layout:** zone centres on a circle, then `spring_layout(seed=0)` for each zone's substations around its centre. Plain `spring_layout` mixed I3's zones together. The zone graph is built in a fixed order because `g.subgraph()` changed node order between Python runs and flipped the layout. It's computed once, so nodes never move between frames.
- **`MultiGraph`, with parallel lines drawn offset:** a simple `Graph` would merge the twin lines of `red_i2_reserva` into one.
- **Colours:**
  - Substations: grey = no voltage, yellow = voltage.
  - Lines: short solid, long dashed; a failed line (no `Operativa`) is red with an X, useful for replanning frames.
  - Interconnections: dotted purple, thicker once the zones are coupled (`Alcanza`).
- **Labels next to each substation:** plants `H1 ✓ en marcha` / `✗ parada` / `averiada`, loads `P1 (H) ✓` (H = hospital). Green when done. The side is chosen to avoid neighbours.

**Checked visually (main session too):**
- I1 frames 00, 05 (`EnergizarLarga`, S2 lights up, with P1 as the connected load), 07 and 14 (everything green).
- I3 final state: 4 zones well separated, couplings drawn thick.
- I2 and `red_i2_reserva` (twin lines visible, failed line and failed plant drawn in red).
- Same network ⇒ identical image across runs.

**Limitations:**
- Blocks aren't drawn (they don't exist in both versions), so `ActivarBloque` frames only change the title.
- Label placement is a heuristic: dense G(n) networks may still overlap. In `red_i2_reserva`, twin line names sit close together.

---

## 6. Order of work and checkpoints

| # | Part | Depends on | Checkpoint (real numbers reported to you) | Status |
|---|---|---|---|---|
| 1 | `planificador.py` | – | I1 optimal = 14 with ucs/A*; nodes per heuristic | ✅ done (+ tie-break by lower h) |
| 2 | `validar` + I2 + I3 | 1 | `validar` OK; cost/nodes/time of I2, I3 | ✅ done (I2 resized) |
| 3 | G(n) | 2 | `validar` OK for several n and seeds; time for growing n | ✅ done |
| 4 | aggregated version | 1 | I1 aggregated = 14; node reduction on I1–I3 | ✅ done (`dominio_agregado.py`; I3 resized) |
| 5 | replanning | 1, 2 | p=0 sanity; I2 results with seeds | ✅ done (`replanificacion.py`; I1–I3 have no redundancy, see finding) |
| 5b | E4 (failures experiment) | 5 | I2 / I2-reserva table + figure | ✅ done (`e4()`, `red_i2_reserva`) |
| 6 | visualisation | 2 | I1 frames saved | ✅ done (15 frames `figuras/i1_*.png`) |

**Summary of optimal costs:** I1 = 14, I2 = 23, I3 = 26 (all equal to the counting bound; same in both versions).

**All numbers in this file were re-measured on 2026-10-13, after Eloísa's `Cargada` change** (except the tables labelled "historical").

After each part: run it, report the real output, and stop for your review if you want to go step by step.

---

## 7. Things noticed in Eloísa's `dominio.py` (not touching them, just flagging)

1. ✅ ~~**`Cargada(S)` is never deleted.**~~ **Fixed by Eloísa (commit `689c54f` "quitar cargada", 2026-10-12):** `Cargada` no longer exists. `EnergizarLarga` now has one copy per load k of the origin substation and requires `Suministrada(k)`: a load must be connected **right now**, so shedding the only load blocks the long line again. The aggregated version imports `energizar_larga` from `dominio.py`, so both versions stay identical (stale docstrings fixed). The same commit also: removed the `dominio.problema_agregado` stub; added a `validar` check "at most one autonomous plant per zone" (I1–I3, I2-reserva and G(8) seeds 0–2 still pass); and reformatted `instancias.py` / `replanificacion.py` (rule E of `disparo_central` no longer mentions `Cargada`).
   **Re-checked after the change (2026-10-13):** optimal costs unchanged (I1 14, I2 23, I3 26, both versions), the two versions still have exactly the same reachable states, and every table in sections 1–4 was re-measured with the new rule (searches now expand fewer nodes: e.g. I2 individual UCS 68k instead of 108k). Tables labelled "historical" record how instances were designed and keep their old numbers on purpose.

2. **Cross-zone lines are silently ignored** in `energizar_corta/larga`. `validar(red)` will catch it on the instance side.
3. ~~`instancias.cargar` defaults to `agregada=True`, but the aggregated version doesn't exist yet, so `python main.py` without `--individual` crashes.~~ **Solved in step 4:** `cargar` now uses `dominio_agregado.py`. Eloísa deleted the old stub in `dominio.py` (commit `689c54f`).
4. README says the delete field is `del`. In the code it's `dele` (`del` is a reserved Python word).

---

## 8. Questions to confirm before implementing

1. **Files:** mine = `instancias.py`, `planificador.py`, `replanificacion.py`, `visualizacion.py`, the aggregated version, and experiment **E4** in `experimentos.py` (its header says E4 is yours). `programacion.py` (optional) and `main.py` are not in scope. Correct? → ✅ **Answered: experiments E1–E3, E5, E6 are Eloísa's. E4 was then implemented by Milagros** (after step 5 showed I1–I3 can't recover from failures). Only `e4()` and its `_e4_*` helpers/`E4_*` constants were added to `experimentos.py`; Eloísa's stubs are untouched. Tell Eloísa she doesn't need to write E4.
2. ✅ **Aggregated version location:** new file `dominio_agregado.py` (decided).
3. ✅ Instance functions keep returning a `Red`; `cargar` builds the problem (went ahead with the default).
4. ✅ **DisparoCentral semantics (answered "OK to all"):** (A) the plant's blocks disappear (`Activado`/`Libre` deleted); (B) loads using them lose supply and count as lost loads; (C) if the tripped plant is thermal, its borrowed auxiliary block is given back (`Libre`); (D) **no cascade**: a thermal started with a block of the tripped plant keeps running (the auxiliary block is only needed to start); (E) substations keep `ConTension` (`Cargada` no longer exists since 2026-10-12).
5. ✅ No longer needed: the aggregated version exists, so `cargar`'s default `agregada=True` works.
6. ✅ "Same fixes" read as **same rules**: the aggregated version copies every rule of the individual one exactly, including its quirks (section 7).

---

## 9. Notes for the presentation / oral defense

Points worth a slide or a prepared answer. Added as they come up during implementation.

### 9.1 Tie-break by lower h in A* (step 1)
- **What:** when two nodes in the open list have the same `f = g + h`, A* expands the one with the **lower h** first, i.e. the one the heuristic estimates closest to the goal. If `h` also ties, the oldest one (FIFO).
- **Why it was needed:** I1 is small (1,321 reachable states) and many states share `f = 14` (the optimal cost). With FIFO only, A* first expanded the old, shallow states with `f = 14` (lots of `g`, little progress) before reaching those close to the goal. That hid the benefit of the heuristics: A* expanded **1,273 nodes with every heuristic**, exactly as many as h0 / UCS.
- **Why it doesn't break optimality:** A* is optimal because it never expands a node with `f` greater than the optimal cost before finding the goal. The tie-break only reorders nodes **with the same f**, so that guarantee is untouched. All admissible configurations still return cost 14.
- **Effect (I1, expanded nodes, FIFO → lower-h tie-break):** hprec 1,273 → 904, hmax 1,273 → 890, hadd 1,273 → 281. UCS (h = 0 always) and greedy (f is already h) are unchanged, as expected.
- **One sentence to say:** *"When two nodes have the same f we expand the one with smaller h, because it is probably closer to the goal; it doesn't affect optimality since A\* only reorders nodes with equal f, but it avoids exploring many equivalent shallow nodes."*

### 9.2 Results that may get questions (step 1)
- **hprec and hmax expand almost the same on I1 (904 vs 890) and I2 (50,146 vs 50,350).** Not a contradiction: hmax takes the **most expensive single** goal and ignores the rest, hprec **counts every** missing goal. With many similar goals (5 loads in I1) both give similar guidance. Both are admissible and neither dominates the other in general (aggregated I2: hprec 2,881 vs hmax 2,868).
- **hmax/hadd are ~15× slower per node than hprec**, even when they expand fewer nodes: they recompute the relaxed problem (a fixpoint over all actions) for each generated state. I2 individual: hprec 0.78 s vs hmax 11.6 s for ~50k nodes each. Fewer nodes ≠ less time; E1/E2 should report both.
- **hadd is not admissible but found the optimal cost (14) on I1.** Allowed, not guaranteed: on bigger instances it may return cost > optimal.
- **Greedy + hadd needed only 36 expansions** and also found 14 on I1, by luck of the instance, not by guarantee. **Greedy + hprec shows the risk:** on I2 it returns cost **25** instead of 23, and on I3 30 instead of 26.

### 9.3 Instances and `validar` (step 2)
- **Three instances of increasing difficulty, on purpose.** I1 is the toy explained by hand (optimum 14). I2 is sized so that **every** search finds the optimum (23) with individual blocks, which makes E1 a fair comparison of heuristics. I3 (resized in step 4, optimum 26) is solved optimally by every search in the aggregated version but not by UCS / A*+hprec / A*+hmax in the individual one, so it shows what aggregation gains (E3).
- **Why individual blocks explode.** Once zones are coupled, any free block can feed any load. "B2 uses block 1" and "B2 uses block 2" are different states for the search but equivalent in practice. The first I2 (10 blocks) reached 1.1M expanded nodes in 120 s without finishing, while the resized I2 (8 blocks) is solved by UCS in about 1 s.
- **Optimal cost by counting.** When supply equals demand, every block must be activated, every substation energized and every load connected, so the optimum is the number of unavoidable maneuvers: I1 14, I2 23, I3 26 (the original, bigger I3: 43). It is an independent check of the planner's result.
- **`validar` checks necessary conditions, not a proof.** It covers an autonomous plant per zone, lines inside one zone, a BFS that respects the long-line rule, interconnections between zones, enough blocks, and hmax ≠ ∞. The planner finding a plan is the real proof.
- **`ExtenderAlcance` is available in I3 but never strictly needed.** Blocks are interchangeable, so a block can also "travel" N→C→S as a chain of swaps at the same cost. It is still correct to include it: the goal only contains directly interconnected pairs, as the domain requires.
- **Practical limit of the experiments.** The search keeps every state in memory and checks the time limit only between expansions, so a run that fills the RAM can overshoot its limit (223 s on a 120 s limit). Experiments run one configuration at a time and also use `limite_nodos`.

### 9.4 The generator G(n) (step 3)
- **What it's for.** Fixed instances give three data points; E2 (scaling) and E5 (difficulty vs. margin) need many grids of controlled size and margin, reproducible with a seed.
- **Solvable by construction, not just by `validar`.** When supply is exact, a thermal or a border substation behind a long line can lock the plan: the only block goes to the load that "unlocks" the long line, and nothing is left to start the thermal or to couple zones. G(n) only puts thermals and borders where the root reaches them through short lines, so each zone can start, start its thermals and couple before connecting any load; after that, any free block feeds any load. A script-built plan validated all 120 generated grids. `validar` can't see this kind of deadlock because its checks (including hmax) ignore that blocks get used up.
- **The counting bound only counts substations that need voltage.** G(n) can create empty leaf substations that nobody needs to energize. G(4) seed 0: optimum 16 = bound. From n = 8 up, optimal searches don't finish in 60 s / 300k nodes; greedy finds plans 5–18% above the bound because it sheds and reconnects loads.
- **`margen < 1` is unsolvable, but `ceil` rounds up.** Each load and each thermal start use a block for good, so fewer blocks than that can't work. With very small demand, though, `ceil(0.8 × 3) = 3` removes the shortage, so E5 uses n ≥ 8.
- **Known quirks.** Hospitals end up ~40–55% of loads (each zone's root always gets one), and blocks can be spread unevenly among plants, which adds equivalent states and makes the search explode sooner.

### 9.5 The aggregated version (step 4)
- **Idea in one sentence.** Instead of naming each block, count how many free blocks each zone has (`Libres(z,n)`); the number is part of the atom's name and "3 follows 2" is resolved at instantiation, like every static predicate. States that differ only in *which* block a load uses collapse into one.
- **Same semantics, proved on every reachable state.** Converting each individual state into counters gives exactly the set of aggregated states (I1 1,321 → 62, I2 70,365 → 3,287, G(4) s0 24,399 → 403), so the optimal costs are identical: 14, 23, 16, 9, 14.
- **Aggregation removes symmetry, not combinations.** 16–21× fewer expanded nodes on I2 and 14–56× on G(4) s0 with the same optimum, but the original I3 and G(n ≥ 8) still don't finish optimally: zones progress independently and the number of possible orders still grows exponentially. That is why I3 was resized.
- **hmax and hadd give exactly the same values in both versions.** In both relaxations one free block "never runs out" (`Libre(b)` or `Libres(z,1)` is never deleted), so the relaxation is equally optimistic. The gain of aggregation is in the number of states, not in the heuristic.
- **Greedy + hprec scales better than greedy + hadd on big instances** (original I3: 53 in 0.01 s; G(12): 64 in 0.10 s aggregated, 0.55 s individual), but its plans are above the optimum. *Hypothesis, not measured:* greedy + hadd gets lost because the relaxation doesn't see blocks running out, and each hadd evaluation is expensive.
- **More grounded actions, not slower.** There is one action copy per counter value (I1: 102 vs 68 actions), but only one copy can apply in each state.

### 9.6 The resized I3 (after step 4)
- **I3 shows the gain of aggregation on one instance.** Same network, same optimum (26): aggregated UCS finishes in 1.8 s (88.7k expansions); individual UCS and A*+hprec stop at the 500k-node limit and A*+hmax at 120 s. Of the optimal searches, only A*+hadd finishes individually, in 81 s.
- **Why I3 is small: zones multiply the space.** Each zone's maneuvers can be interleaved with the others', so every extra zone multiplied the reachable space ×30–80 in the design tests (old rule) (2 zones: 417 states; 3 zones: 32.7k; 4 zones: hundreds of thousands). The original 12-substation I3 couldn't be solved optimally even aggregated.
- **Why it was resized and not kept big.** An instance that no optimal search finishes gives E1 nothing to compare. The scaling limit is shown instead by G(n) in E2, where it can be measured step by step.
- **`ExtenderAlcance` is grounded but optional.** The goal only has C–NO, C–NE and C–S. UCS reaches the optimum without it (blocks swap through C); A*+hprec and A*+hmax use it once, at cost 0.
- **A thermal must be worth starting.** A candidate with a 1-block thermal was rejected: starting it costs a block and gives one back, so the optimum (22) was below the expected count (24). The final T1 has 3 blocks.

### 9.7 Replanning (step 5)
- **Two states, one sentence.** *"The plan lives in the believed state; the world lives in the real state. Before every step the agent observes the real state and checks that the rest of the plan still reaches the goal from there; if not, it replans from what is really there."*
- **Why check the whole rest of the plan, not just the next action.** A broken line may only be needed 10 steps later. Checking the whole rest detects it now, before wasting maneuvers on a plan that will fail.
- **Why replan instead of "repairing" the plan.** The planner is already there and is optimal with A*: replanning from the real state gives the cheapest way to finish from where we actually are. Replans on I2 take ≤ 0.08 s.
- **Why the individual version.** When a plant trips we must know *which* loads were using *its* blocks (`Usa(k,b)`). Counters (`Libres(z,n)`) forget that.
- **DisparoCentral rules (A–E), each with its why:** blocks disappear (the plant produces nothing); their loads are lost (they had no other energy); a tripped thermal gives back its borrowed block (its machinery is off), only if that block still exists; no chain reaction (the borrowed block is only needed to *start* a thermal, no action checks it later); voltage stays (simplification: other sources hold it).
- **Possible question: "seed 1 recovers with only +1, isn't T1's trip suspicious?"** T1's second block had been lent to start T2. By rule D, T2 keeps running, and by rule C, T1's own borrowed block comes back. So losing T1 costs no blocks overall, and only B2 needs to be reconnected (+1). It follows the agreed rules; a cascade (rule D the other way) would have made it fatal.
- **Reproducible randomness.** Only `random.Random(semilla)`, the die is rolled before every step even without an event, and candidates are sorted. The same seed gives the same run.
- **Main finding: our instances are fragile by design.** They have exact supply (built that way so the optimum can be checked by counting) and no spare lines, so most failures are fatal (I2: 8 of 10 seeds unsolvable at p = 0.1). That isn't a planner bug: the search *proves* there's no solution (`sin_solucion`, in ≤ 0.08 s). The scratch variants of I1 with a spare line or a spare thermal recover (extra 0 and 6), which shows that replanning works when the grid has redundancy. Message for the slide: *"replanning can only use the redundancy the grid has; with no spare blocks or lines, a failure is final."*

### 9.8 Experiment E4 (failures)
- **The question:** *"If things break during the plan, how often can we still finish, and at what price?"* We measure the % of runs solved, extra maneuvers, lost loads and replanning time, separately for line failures and plant trips, at three failure probabilities.
- **Why we had to build I2-reserva.** On the original I2 almost every failure is final (exact supply, one cable to each place). To measure *recovery*, the grid must have something to recover with: twin cables and one spare thermal plant. They are designed so that **with no failures the optimum is still 23**; otherwise "extra maneuvers" would be measured against a different plan.
- **Main result (one sentence):** *"With spare capacity, the agent survives cable failures almost always (100% at low probability) but plant shutdowns much less often (60% → 7%), and only plant shutdowns leave customers without power; replanning takes under 2 s."*
- **Honest limitation, say it before they ask:** extra maneuvers are almost always 0, so they don't show the difference. The reasons are that recovered failures are often free (twin cable, same-price spare plant), that the costly failures end up unsolvable and drop out of the average (selection bias), and that a cable breaking after use changes nothing. The comparison also favors cables: each cable has its own twin, while four plants share one spare.
- **Why a hydro plant trip is always fatal:** each zone has only one plant that can start from zero. Without it the zone can't produce its first block, and every other plant needs a block to start.
- **Paired design:** the same seeds are used for both failure types, so failures happen at the same steps and only the *type* changes.

### 9.9 Visualisation (step 6)
- **What the frames show:** one image per step of the plan, and power "spreading" across the grid. Grey substations turn yellow, plants switch to "en marcha", customers get a ✓. Good for explaining I1's 14 steps on one slide sequence.
- **Why the layout is fixed:** if nodes moved between frames, the eye would follow the movement instead of the change of colour. Positions are computed once (seeded) and reused.
- **Why the titles name blocks (`bT1_2`) if the drawing doesn't show them:** the frames draw the individual version's plan, whose step names say which block is used ("block 2 of T1"); the aggregated version would only show counters. Same plan cost (14), same picture.
- **Why the blocks aren't drawn:** the drawing only uses facts that exist in both versions (individual and aggregated), so one function serves both. Blocks are "bookkeeping" of energy, not a place on the map. Consequence: an `ActivarBloque` step only changes the title.
- **Reading a long line in the pictures:** the dashed line S1–S2 in I1 can only be switched on once a customer at S1 is supplied (step 5, after hospital P1). That's the Ferranti rule, visible in the picture.
- **Citations:** NetworkX (Hagberg, Schult & Swart, 2008), Matplotlib (Hunter, 2007).

---

## 10. Presentation kit

Everything here uses numbers measured **after** Eloísa's `Cargada` change (2026-10-12). Facts from the assignment PDF (`Instrucciones practica 2.pdf`) are marked 📄.

### 10.1 Practical constraints (📄)
- **Presentation: Thursday 22/10, 18:00–18:15** (Eloísa + Milagros). **Delivery deadline: 18/10, 23:59** (code as .zip, slides as **PDF**, and the **generative-AI use declaration**). Late delivery: −20% of the grade per day. Missing AI declaration: **−1 point**. Slides can't be changed after the deadline.
- **Talk: 9–11 minutes** for full marks on timing (8–9 or 11–12 → half; < 8 or > 12 → zero). Then **2 questions per person**, worth 3 of 10 points in total (0.5 each in the rubric).
- **Required on the slides** (each one is graded in "structure"): motivation, problem definition/formalization, methodology (algorithms + tools), results **with critical analysis**, conclusions, and **each member's personal contribution** (balanced and explicit).
- **Rubric weights to keep in mind:** problem complexity 0.65 and adequacy of the solution 0.35 (2.5 pts); code quality (1.75 pts: it must run without errors); slides 0.6 / delivery 0.4 (2.75 pts; inside "slides": critical analysis 0.3, visual support 0.3, structure 0.2, motivation 0.1, contribution 0.1); questions 3 pts.
- **References are mandatory** for any reused library, figure or idea (NetworkX, Matplotlib, the textbook). Teamwork is graded: both must speak.

### 10.2 Suggested slide outline (≈ 10 min)
Proposed split; Eloísa's parts are in *italics* (she owns the domain, heuristics and E1–E3, E5–E6), adjust together.

| # | Slide | ~min | Who | Content / figure |
|---|---|---|---|---|
| 1 | Title + motivation | 1 | *both* | Why a blackout restart: real, critical (hospitals first), naturally a **planning** problem (order of maneuvers matters, actions have preconditions). |
| 2 | The domain in one picture | 1 | *Eloísa* | Pieces of section 0 (substation, line, plant, block, load, zone) + I1 drawing `figuras/i1_00.png`. |
| 3 | Formalization | 1 | *Eloísa* | STRIPS-like: states = sets of atoms; actions with pre+/pre−/add/del; 2–3 example actions (`EnergizarLarga` with Ferranti, `ArrancarTermica`); goal; costs (1 per maneuver, 0 for `ExtenderAlcance`). |
| 4 | Planner | 1 | Milagros | One forward search, 3 modes (UCS / A* / greedy) by changing only `f`; tie-break by lower h; goal test on expansion; reopen if better g. |
| 5 | Heuristics | 1 | *Eloísa* | h0, hprec, hmax, hadd: what each counts, which are admissible. |
| 6 | Instances + I1 step by step | 1.5 | Milagros | I1/I2/I3 table (sizes, optima 14/23/26, "optimum by counting"); 3–4 frames of I1 (`i1_00`, `i1_03`, `i1_05`, `i1_14`). |
| 7 | E1 heuristics comparison | 1 | *Eloísa* | Her table/figure. |
| 8 | Aggregation (E3) | 1 | Milagros (+ *Eloísa's E3 figure*) | "Name each block" vs "count blocks per zone"; same states up to block names; 20× fewer states on I2; I3: aggregated solves it in seconds, individual mostly doesn't. |
| 9 | Scaling (E2) / G(n) | 0.5 | *Eloísa* (generator: Milagros) | Generator in one line; where optimal search stops (n = 8). |
| 10 | Failures + replanning (E4) | 1.5 | Milagros | Loop "act → observe → replan"; `figuras/e4.png`; the 2 key numbers; honest limitations. |
| 11 | Conclusions + critical analysis | 1 | *both* | 3–4 bullets (10.6). |
| 12 | Who did what | 0.5 | *both* | Table of 10.7. |
| 13 | References | – | – | 10.9. |

Tips: one message per slide; read numbers from the slide, not from memory; rehearse with a timer (target 10:00).

### 10.3 Story in 5 sentences (to open or close)
1. After a total blackout the grid must be restarted **in the right order**: some plants start alone, others need energy to start, long lines need a load connected, hospitals go first.
2. We model it as a **classical planning problem** and solve it with our own forward search (UCS, A*, greedy) and domain-independent heuristics.
3. The main difficulty is **symmetry**: with named energy blocks, many states are "the same" in practice; counting blocks per zone (aggregation) removes it and cuts the search by 1–2 orders of magnitude without changing the optimum.
4. Even so, the problem grows **exponentially with the number of zones**, so optimal planning stops at small grids; greedy search still finds plans, without guarantees.
5. When things break during execution, the agent **replans** from what it observes; it recovers only if the grid has spare capacity, and plant failures are much harder than line failures.

### 10.4 Numbers cheat sheet (all current)
| What | Number | Where from |
|---|---|---|
| Optimal costs | **I1 14, I2 23, I3 26** (both versions; = counting bound) | sections 2–3 |
| I1 frames | 15 pictures (initial + 14 maneuvers) | `figuras/i1_*.png` |
| Reachable states, individual → aggregated | I1 1,321 → 62; I2 70,365 → 3,287 (×21); G(4) s0 24,399 → 403 (×61) | section 3 |
| I2 UCS, individual → aggregated | 68,061 → 3,252 expanded (×21), 1.05 s → 0.05 s | section 3 |
| I3 | aggregated UCS 26 in 1.8 s; individual: UCS and A*+hprec stop at 500k nodes, A*+hmax at 120 s; only A*+hadd finishes (81 s) | section 2 |
| hmax/hadd per node vs hprec | ~15× slower per expanded node (I2 ind.: hprec 0.78 s / 50k nodes vs hmax 11.6 s / 50k) | section 3 |
| Zones multiply the space | ×30–80 per extra zone (I3 design tests, old rule) | 9.6 |
| Greedy is not optimal | greedy + hprec: I2 25 (opt. 23), I3 30 (opt. 26) | sections 2, 9.2 |
| Optimal search limit | G(8): no optimal search finishes (300k–500k nodes); greedy finds 41 (bound 39) | sections 2–3 |
| E4, with spares | cables survived 100 / 100 / 67 %, plants 60 / 20 / 7 % (p = 0.05 / 0.1 / 0.2) | 4b |
| E4 replanning time | ≤ 1.6 s summed per run; I2 replans ~0.01–0.02 s | 4b |
| E4 runtime | 180 runs in 443 s | 4b |

### 10.5 Likely questions with short answers
**Domain and model**
- *Why is this a planning problem and not just a graph search on the grid?* Because what matters is the **order of maneuvers** with preconditions (a thermal needs energy to start, a long line needs a load), and resources (blocks) get used up. The state is the whole situation, not a node of the grid.
- *What is the Ferranti effect / why can't a long line be switched on empty?* An unloaded long line raises the voltage at its far end; in the model, `EnergizarLarga` requires a load **currently supplied** at the origin (`Suministrada(k)` after the 2026-10-12 change).
- *Why do thermal plants need a block from another plant?* Their own machinery ("auxiliaries") needs energy to start. That's what makes the order non-trivial: hydro first, then thermals.
- *Why is `ExtenderAlcance` free (cost 0)?* It isn't a physical maneuver, it's bookkeeping ("if A reaches B and B reaches C, A reaches C"). Charging for it would distort the optimum.
- *What does a "block" represent?* A unit of energy that one load needs. It abstracts real power flows (no voltages or flows are computed). Honest limitation: "the plan is a sequence of maneuvers, not an electrical simulation".

**Search and heuristics**
- *Why is A\* optimal here, and with which heuristics?* A* with an admissible h never overestimates, so the first goal expanded is optimal. h0, hprec and hmax are admissible; hadd is not.
- *Why is hprec admissible?* Each action achieves at most one goal atom and cost-0 actions achieve none, so each missing goal atom needs at least one maneuver of cost 1. (Kept true on purpose: the goal uses `z1 < z2` for couplings.)
- *Why does hadd find optimal plans if it isn't admissible?* On our instances it happens to; nothing guarantees it. It's faster in nodes but each evaluation is expensive.
- *Why test the goal when expanding and not when generating?* With costs 0 and 1, the first goal generated might not be the cheapest; testing on expansion keeps UCS/A* optimal.
- *What's the tie-break and does it break optimality?* Equal f → lower h first. It only reorders nodes with the same f, so A*'s guarantee holds. Effect on I1 in 9.1.
- *Why are hmax/hadd slower in time even with fewer nodes?* They solve a relaxed problem (fixpoint over all actions) at every generated state.

**Aggregation**
- *Is the aggregated version the same problem?* Yes: we enumerated every reachable state of both and mapped individual states to counters; the sets are identical (I1, I2, G(4) × 3 seeds), so optima are identical.
- *Why doesn't aggregation solve everything?* It removes symmetry (which block), not combinatorics (which order). Zones still interleave: each extra zone multiplies the space.
- *How do you put numbers in a propositional model?* The number is part of the atom name (`Libres(N,2)`); "3 follows 2" is resolved when grounding, one action copy per value.

**Replanning / E4**
- *Why replan from scratch instead of repairing the plan?* The planner is fast on these sizes and A* gives the cheapest continuation from the real state; repair would need extra machinery without a clear gain.
- *Why check the whole rest of the plan and not just the next action?* A broken line may be needed 10 steps later; finding out now avoids useless maneuvers.
- *Why do almost all failures end unsolvable on I2?* I1–I3 have exact supply and one path per substation (on purpose, to check optima by counting). With spares (I2-reserva) cable failures are survived 100% at low probability.
- *Why are extra maneuvers almost always 0?* Recovered failures are often free (twin line, same-price spare), and expensive failures become unsolvable and drop out of the average (selection bias). Said openly in the analysis.
- *Is the comparison cables vs plants fair?* Partly: every cable has a twin, four plants share one spare. Plants are still worse because a hydro trip is always fatal (only self-starting plant of its zone).
- *Why the individual version for replanning?* After a trip we must know which loads used that plant's blocks; counters forget it.

**Code / tools**
- *What did you reuse?* Only the Python standard library (heapq, collections, random, time, csv), NetworkX for the graph and Matplotlib for figures (cited). Planner and heuristics are our own.
- *How are results reproducible?* Fixed seeds with private `random.Random(semilla)`; same seed → same grid / same failures. Every search has time and node limits.

### 10.6 Critical analysis and conclusions (slide material)
- ✅ **Correctness evidence:** every plan is checked with `validar_plan` independently of the search; optima equal the counting bound (14 / 23 / 26); the two versions are proven equivalent on their whole state space.
- ✅ **Aggregation pays off:** ×20–60 fewer states with the same optimum; it's what makes I3 solvable optimally in seconds.
- ⚠️ **Exponential wall:** optimal search stops around G(8) even aggregated; zones interleave. Greedy finds plans but above the optimum and without guarantees.
- ⚠️ **Heuristics:** better-informed (hmax/hadd) ≠ faster: fewer nodes but much more time per node; on I1 hprec and hmax expand almost the same.
- ⚠️ **Robustness depends on the grid, not on the planner:** with no spare capacity a failure is final (and the planner proves it quickly); with spares, line failures are almost always absorbed, plant failures much less.
- ⚠️ **Model simplifications:** no real power flows/voltages; voltage stays after a plant trip; no cascades. Worth saying as future work.
- 🔭 **Future work:** action index by precondition (faster successor generation), symmetry reduction across zones, plans as partial orders (parallel maneuvers, `programacion.py`), richer failure model.

### 10.7 Personal contribution (for the "who did what" slide)
From the README ownership table and this plan:
- **Milagros:** planner (`planificador.py`: UCS/A*/greedy, tie-break, validation); instances (`instancias.py`: I1–I3 design and resizing, `validar`, generator G(n), `red_i2_reserva`); aggregated version (`dominio_agregado.py`, equivalence proof); replanning (`replanificacion.py`); experiment E4; visualisation (`visualizacion.py`, frames).
- **Eloísa:** domain and grounding (`dominio.py`, `funciones_auxiliares.py`, incl. the `Cargada` → `Suministrada` fix); heuristics (`heuristicas.py`); experiments E1–E3 (and optional E5–E6) in `experimentos.py`.
- **Both:** `main.py` (entry point), README.
- Check with Eloísa that this split is exact before putting it on a slide; the rubric rewards a **balanced and explicit** split.

### 10.8 Live-demo commands (optional, rehearse before)
```
python3 main.py --instancia I1 --algoritmo astar --heuristica hmax --individual   # 14-step plan
python3 visualizacion.py                                                         # regenerates figuras/i1_00..14.png
python3 experimentos.py E4                                                       # ~7.5 min: too long live, show the figure instead
```
A one-off failure demo (I1, plant T1 trips before step 11 → no solution; reproducible):
```
python3 -c "import dominio,instancias,heuristicas as h; from replanificacion import ejecutar_con_fallos as e; r=instancias.red_i1(); a,s,g=dominio.problema(r); print(e(r,a,s,g,h.hadd,'astar',prob_fallo=0,eventos_programados={11:('central','T1')},limite_tiempo=60,limite_nodos=300_000)['eventos'])"
```

### 10.9 Figures available and references
- `figuras/i1_00.png` … `i1_14.png`: I1 plan step by step (individual plan, titles name the block used). Steps: 1 start H1, 2 activate bH1_1, 3 connect hospital P1, 4 activate bH1_2, 5 long line S1→S2 (allowed by P1), 6 start T1 with bH1_2, 7–10 activate T1's 4 blocks, 11–14 connect B1, B2, I1, I2. Good picks: 00 (all dark), 01 (H1 starts, S1 lit), 03 (hospital first), 05 (long line, Ferranti rule), 06 (thermal starts with a borrowed block), 14 (all green).
- `figuras/e4.png`: E4, three panels (% solved, extra maneuvers, lost loads).
- `dibujar_red` can draw any other state (I2, I3, a failed line in red) if a slide needs it.
- References: Hagberg, Schult & Swart (2008), *Exploring network structure, dynamics, and function using NetworkX*; Hunter (2007), *Matplotlib: A 2D graphics environment*; Russell & Norvig, *Artificial Intelligence: A Modern Approach* (planning, heuristics, monitoring and replanning, ch. 10–11); course notes (Tema 4, state abstraction).
