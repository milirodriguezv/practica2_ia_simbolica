# Implementation plan: Milagros's parts

For review only. Nothing here is implemented yet. Each part lists **what** gets built, the **design decisions** (with a one-line "why" you can use in the oral defense), and **how it will be verified** by running it.

Open questions that need your answer before starting are collected in [section 8](#8-questions-to-confirm-before-implementing).

---

## 0. The domain in one page (so the plan makes sense)

Think of it as a game with these pieces:

| Piece | Plain meaning | Atoms that describe it |
|---|---|---|
| Substation `S` | A node of the grid. It either has voltage ("is lit") or not. | `ConTension(S)` |
| Line `L` | A cable between two substations of the same zone. A *larga* (long) one can only be lit from a side that already feeds a load. Otherwise the cable "over-voltages" (Ferranti effect). | `Operativa(L)` |
| Plant `C` | Produces energy. *autonomo* starts alone. *termica* needs voltage at its substation **and** one free block from another plant (to power its own machinery, its "auxiliaries"). | `Operativa(C)`, `EnMarcha(C)` |
| Block `b` | One unit of energy from a plant. It must be **activated**, then it is **free** until a load (or a thermal start) uses it. | `Activado(b)`, `Libre(b)`, `Usa(k,b)`, `Auxiliar(b,C)` |
| Load `k` | A consumer. Each uses exactly one block. *prioritaria* = hospital. A normal load needs the hospitals of its substation connected first. | `Suministrada(k)`, `Cargada(S)` |
| Zone `z` | An island restored on its own. Two zones can share blocks only after being coupled. | `Alcanza(z1,z2)` |

**Start:** everything dark, everything working (`Operativa`), each zone reaches itself (`Alcanza(z,z)`).
**Goal:** every load `Suministrada` + every directly interconnected zone pair coupled (`Alcanza(z1,z2)` with `z1 < z2`).
**Cost:** every maneuver costs 1, except `ExtenderAlcance` (cost 0). It's a bookkeeping step: "if A reaches B and B reaches C, then A reaches C".

**Worked example, I1 (already in `instancias.py`), optimal cost 14:**
`ArrancarAutonomo(H1)` (1) → activate 2 blocks of H1 (2) → connect hospital P1 (1, so now S1 "feeds a load") → `EnergizarLarga S1→S2` (1) → `ArrancarTermica(T1)` with H1's 2nd block (1) → activate 4 blocks of T1 (4) → connect B1, B2, I1, I2 (4). Total: 1+2+1+1+1+4+4 = **14**. Supply 6 blocks = demand 5 loads + 1 auxiliary block. It's exactly enough. This is the first number the planner must reproduce.

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

### ✅ Done: real results on I1 (individual version, with the h tie-break)
| Mode + h | Cost | Expanded | Generated | Time | `validar_plan` |
|---|---|---|---|---|---|
| ucs + h0 | 14 | 1511 | 8141 | 0.014 s | (True, 14) |
| astar + h0 | 14 | 1511 | 8141 | 0.014 s | (True, 14) |
| astar + hprec | 14 | 936 | 4737 | 0.008 s | (True, 14) |
| astar + hmax | 14 | 1040 | 6113 | 0.123 s | (True, 14) |
| astar + hadd | 14 | 287 | 1605 | 0.047 s | (True, 14) |
| voraz + hadd | 14 | 39 | 169 | 0.009 s | (True, 14) |

Before the tie-break change (FIFO only), A* expanded h0 1511 / hprec 1389 / hmax 1511 / hadd 1347. Removing any action from the plan gives `valido = False`; `limite_nodos=5` returns `None` with `"limite_nodos"`.

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

**Why it was resized (decision after step 2 review, option 1).** The first version (thermals with 3 blocks, plus industries I1 in S2 and I2 in S6: 10 blocks, 189 actions) could not be solved optimally with individual blocks: UCS hit the 120 s limit after 1.1M expansions, and A* with hprec/hmax/hadd hit it too (A*+hprec with 500 s filled the 8 GB of RAM). Only greedy+hadd solved it (cost 27, which equals the counting lower bound, so it is optimal). Shrinking it gives three instances of increasing difficulty: I1 trivial, **I2 medium (every heuristic reaches the optimum, so E1 compares them fairly)**, I3 hard (shows the explosion the aggregated version solves).

**Real results (individual version, 118 actions, limit 120 s):**
| Mode + h | Cost | Expanded | Generated | Time | `validar_plan` |
|---|---|---|---|---|---|
| ucs + h0 | 23 | 108,456 | 552,926 | 1.95 s | (True, 23) |
| astar + hprec | 23 | 60,805 | 287,608 | 1.0 s | (True, 23) |
| astar + hmax | 23 | 74,589 | 417,416 | 19.1 s | (True, 23) |
| astar + hadd | 23 | 32,432 | 177,178 | 11.9 s | (True, 23) |
| voraz + hadd | 23 | 211 | 1,052 | 0.1 s | (True, 23) |

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
- Size: 7 substations, **139 aggregated / 122 individual** actions, 166k reachable aggregated states.

**Why it was resized (decision after step 4 review, option 1).** The original I3 (4 zones × 3 substations, 12 loads, 2 thermals, 14 blocks, 383 individual / 427 aggregated actions) could not be solved optimally by **any** configuration, not even aggregated (UCS and A*+hprec hit 500k nodes; A*+hprec with 1.5M nodes used 2.2 GB of RAM). Only greedy+hprec found a plan (cost 53, optimum 43 by counting). The goal of the resize: **aggregated solves it optimally, individual doesn't**, so I3 shows what aggregation gains (E3).

**Candidates tried** (aggregated unless noted, 120 s / 500k nodes):
| Candidate | Description | Result |
|---|---|---|
| A | 8 substations, 9 loads, 1 thermal, 10 blocks | UCS / A*+hprec hit 500k (2 GB); A*+hmax/hadd hit 120 s |
| B | 7 substations, 7 loads, T1 with 2 blocks, NE load behind the long line | UCS / A*+hprec hit 500k; 899k reachable states (1.4 GB) |
| B2 / B3 | B with only NO+C / NO+NE+C | 417 / 32.7k states: **each extra zone multiplies the space ×30–80** |
| D | 6 loads, T1 with 1 block | Rejected: the thermal is useless (uses 1 block, gives 1), optimum 22 < bound 24 |
| D2 | D with H1 1 block, T1 2 blocks | Aggregated UCS 0.6 s, but individual UCS also solves it (2.7 s): gain too small |
| **E (final)** | D2 + T1 with 3 blocks + load I1 at NO2 | 166k reachable states, results below |
| E2 | Like D2 but following the border rule strictly | 971k states; UCS hits 500k in both versions |

**Real results, aggregated** (`cargar('I3')`, 139 actions):
| Mode + h | Cost | Length | Expanded | Generated | Time | `validar_plan` |
|---|---|---|---|---|---|---|
| ucs + h0 | 26 | 26 | 157,168 | 1,016,888 | 3.45 s | (True, 26) |
| astar + hprec | 26 | 27 | 106,838 | 660,080 | 2.31 s | (True, 26) |
| astar + hmax | 26 | 27 | 80,435 | 601,160 | 25.9 s | (True, 26) |
| astar + hadd | 26 | 26 | 19,373 | 154,023 | 9.42 s | (True, 26) |
| voraz + hadd | 26 | 26 | 264 | 1,924 | 0.13 s | (True, 26) |
| voraz + hprec | 30 | 31 | 11,903 | 49,591 | 0.19 s | (True, 30) |

**Real results, individual** (`cargar('I3', agregada=False)`, 122 actions):
| Mode + h | Cost | Expanded | Generated | Time | Result |
|---|---|---|---|---|---|
| ucs + h0 | – | 500,000 | 3,512,941 | 13.0 s | node limit |
| astar + hprec | – | 500,000 | 3,321,338 | 18.0 s | node limit |
| astar + hmax | – | 286,884 | 2,088,808 | 120 s | time limit |
| astar + hadd | 26 | 180,433 | 1,500,214 | 97.3 s | solved, (True, 26) |
| voraz + hadd | 26 | 267 | 1,971 | 0.14 s | solved, (True, 26) |
| voraz + hprec | 30 | 74,477 | 352,985 | 1.25 s | solved, (True, 30) |

Memory peak: ~1.6 GB individual, ~0.4 GB aggregated.

**Optimum by counting:** 4 autonomous starts + 8 activations + 1 thermal start + 7 loads + 3 line energizations + 3 couplings = **26**, equal to what UCS and A* find. (Plan length 27 with cost 26 = one `ExtenderAlcance`, which costs 0.)

**`ExtenderAlcance`:** UCS and A*+hadd don't use it; A*+hprec and A*+hmax use `ExtenderAlcance(NE,C,S)` once so P4 (in S) uses NE's block, at the same cost. Blocks can also travel through C by swaps.

**Aggregated optimal plan (UCS, cost 26):** start the 4 hydro plants (1–4) → activate their 5 blocks (5–9) → `EnergizarCorta(LNO12)` (10) → `ArrancarTermica(T1,NO2,NO,NO,1)` (11) → activate T1's 3 blocks (12–14) → `ConectarPrioritaria` P1 (15), P2 (16) → `EnergizarLarga(LNE12,NE1,NE2)` (17) → `ConectarCarga` B1 (18) → `AcoplarZonas(NO,C)` (19) → P3 with a NO block (20) → `EnergizarLarga(LC12,C1,C2)` (21) → `AcoplarZonas(C,NE)` (22) → B2 with an NE block (23) → `AcoplarZonas(C,S)` (24) → P4 (25) → I1 with C's block (26).

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
- Size (margen 1.0, seed 0): n = 4 → 59 actions, n = 8 → 389, n = 12 → 681, n = 16 → 1237, n = 20 → 1595.

Searches (individual version, seed 0, margen 1.0, limits 60 s / 300,000 nodes, one at a time):
| n | ucs + h0 | astar + hprec | astar + hadd | voraz + hadd |
|---|---|---|---|---|
| 4 | 16 (23,422 exp., 0.23 s) | 16 (15,091 exp., 0.15 s) | 16 (1,182 exp., 0.27 s) | 16 (170 exp., 0.03 s) |
| 8 | node limit | node limit | time limit | 41 (bound 39) |
| 12 | node limit | node limit | time limit | time limit |

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

**Quirks of the individual version kept on purpose** (same semantics, so E3 compares like with like): `Deslastrar` does not delete `Cargada(s)`; `ActivarBloque` does not require `Operativa(c)`; only one coupling action per interconnection, in its listed direction.

Initial state adds `Libres(z,0)` and `Activados(c,0)`. Goal is unchanged. The upper bound of each counter is the number of blocks in that zone/plant. This also keeps the "no action achieves two goal atoms" property, so hprec stays admissible.

### Where the code goes (decided: Q2 and Q6)
New file **`dominio_agregado.py`** with `problema_agregado(red)`; it imports from `dominio.py` the unchanged parts (`Accion`, `atomo`, `estado_inicial`, `objetivo`, the schemas without blocks). **`dominio.py` is untouched**: its `problema_agregado` stub remains (Eloísa can delete it or point it to the new file). `instancias.cargar(nombre, agregada=True)` now calls `dominio_agregado.problema_agregado`, so `python main.py` works without `--individual` (this also solves Q5). Q6 ("same fixes") was read as **same rules**: every rule of the individual version is copied exactly, including its quirks.

### Verification
- I1 aggregated: optimal cost must be **14 as well** (same semantics ⇒ same optimal cost).
- Compare expanded nodes individual vs aggregated on I1/I2/I3 (expected: far fewer with aggregation; that's E3).
- The aggregated plan validates with `validar_plan` on the aggregated problem.

### ✅ Real results

**Invariants.** 200 random walks × 50 actions (seed 42) on I1, I2, I3, G(4) seeds 0/1/2 and G(16): 10,000 states per instance, 0 failures. Always exactly one `Libres(z,·)` per zone and one `Activados(c,·)` per plant, all within bounds, and per zone *free + in use (`Usa` + `Auxiliar`) = activated*. No action adds more than one goal atom and no cost-0 action adds any, so **hprec stays admissible**.

**Same semantics, checked on the whole state space.** Every reachable state of both versions was enumerated; converting each individual state into counters gives **exactly** the set of aggregated reachable states:
| Instance | Individual states | Aggregated states | Sets equal |
|---|---|---|---|
| I1 | 1,583 | 81 | yes |
| I2 | 121,320 | 6,066 | yes |
| G(4) seed 0 | 25,582 | 446 | yes |
| G(4) seed 1 | 217 | 52 | yes |
| G(4) seed 2 | 5,108 | 102 | yes |

**Individual vs aggregated** (120 s / 500k nodes; every plan passes `validar_plan`). Cells: cost / expanded / generated / time (s).
| Instance | Config | Individual | Aggregated |
|---|---|---|---|
| I1 (65 vs 99 actions) | ucs | 14 / 1511 / 8141 / 0.02 | 14 / 79 / 279 / 0.00 |
| I1 | A*+hprec | 14 / 936 / 4737 / 0.01 | 14 / 54 / 173 / 0.00 |
| I1 | A*+hmax | 14 / 1040 / 6113 / 0.12 | 14 / 68 / 235 / 0.01 |
| I1 | A*+hadd | 14 / 287 / 1605 / 0.05 | 14 / 36 / 124 / 0.01 |
| I1 | voraz+hadd | 14 / 39 / 169 / 0.01 | 14 / 29 / 89 / 0.01 |
| I2 (118 vs 146 actions) | ucs | 23 / 108456 / 552926 / 1.74 | 23 / 5791 / 25498 / 0.09 |
| I2 | A*+hprec | 23 / 60805 / 287608 / 0.98 | 23 / 4190 / 17723 / 0.06 |
| I2 | A*+hmax | 23 / 74589 / 417416 / 18.80 | 23 / 4815 / 21989 / 1.35 |
| I2 | A*+hadd | 23 / 32432 / 177178 / 11.05 | 23 / 2353 / 11640 / 0.95 |
| I2 | voraz+hadd | 23 / 211 / 1052 / 0.10 | 23 / 125 / 594 / 0.08 |
| G(4) s0 | ucs | 16 / 23422 / 113451 / 0.24 | 16 / 439 / 1627 / 0.00 |
| G(4) s0 | A*+hprec | 16 / 15091 / 70846 / 0.15 | 16 / 354 / 1310 / 0.00 |
| G(4) s0 | A*+hmax | 16 / 17359 / 92629 / 2.04 | 16 / 404 / 1532 / 0.06 |
| G(4) s0 | A*+hadd | 16 / 1182 / 5950 / 0.26 | 16 / 86 / 373 / 0.02 |
| G(4) s0 | voraz+hadd | 16 / 170 / 621 / 0.03 | 16 / 31 / 118 / 0.01 |
| G(4) s1 | ucs | 9 / 197 / 605 / 0.00 | 9 / 50 / 123 / 0.00 |
| G(4) s1 | A*+hprec | 9 / 145 / 476 / 0.00 | 9 / 38 / 100 / 0.00 |
| G(4) s1 | A*+hmax | 9 / 111 / 395 / 0.01 | 9 / 34 / 88 / 0.00 |
| G(4) s1 | A*+hadd | 9 / 16 / 61 / 0.00 | 9 / 9 / 24 / 0.00 |
| G(4) s1 | voraz+hadd | 9 / 10 / 37 / 0.00 | 9 / 9 / 24 / 0.00 |
| G(4) s2 | ucs | 14 / 4628 / 20221 / 0.04 | 14 / 97 / 291 / 0.00 |
| G(4) s2 | A*+hprec | 14 / 3269 / 13964 / 0.03 | 14 / 74 / 216 / 0.00 |
| G(4) s2 | A*+hmax | 14 / 3264 / 15404 / 0.31 | 14 / 82 / 245 / 0.01 |
| G(4) s2 | A*+hadd | 14 / 154 / 718 / 0.03 | 14 / 24 / 82 / 0.01 |
| G(4) s2 | voraz+hadd | 14 / 20 / 95 / 0.01 | 14 / 24 / 82 / 0.01 |

Same optimum everywhere both finish; the aggregated version expands **14–50× fewer nodes** on I2 and G(4) seed 0.

**Original I3 (12 substations, 14 blocks), aggregated, before resizing:**
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
| 8 (bound 39) | node limit, 27 s | node limit, 34 s | time limit (25,895 exp.) | **41**, 344 exp., 1.3 s | **41**, 380 exp., 0.01 s |
| 12 (bound 54) | node limit, 40 s | node limit, 48 s | time limit (7,135 exp.) | time limit (34,195 exp.) | **64**, 1,616 exp., 0.11 s |
| 16 (bound 72) | node limit, 57 s | node limit, 65 s | time limit (3,216 exp.) | time limit (5,376 exp.) | node limit, 83 s |

**Heuristic values at the initial state are identical in both versions:**
| Instance | hprec | hmax | hadd |
|---|---|---|---|
| I1 | 5 | 5 | 38 |
| I2 | 7 | 6 | 51 |
| original I3 | 15 | 6 | 129 |

**`main.py`:** `python3 main.py --instancia I2 --algoritmo astar --heuristica hprec` now runs aggregated by default: valid 23-step plan, 4,190 expanded, 0.07 s.

**I1 aggregated optimal plan (ucs, cost 14):** `ArrancarAutonomo(H1,S1)` → `ActivarBloque(H1,N,0,0)` → `ActivarBloque(H1,N,1,1)` → `ConectarPrioritaria(P1,S1,N,N,2)` → `EnergizarLarga(L12,S1,S2,N)` → `ArrancarTermica(T1,S2,N,N,1)` → `ActivarBloque(T1,N,0,0)` … `(T1,N,3,3)` (4 steps) → `ConectarCarga(B1,S1,N,N,4)` → `ConectarCarga(B2,S1,N,N,3)` → `ConectarCarga(I1,S2,N,N,2)` → `ConectarCarga(I2,S2,N,N,1)`. Reading the numbers: `ActivarBloque(c,z,m,n)` = plant `c` had `m` activated, zone `z` had `n` free; `Conectar…(…,n)` = zone had `n` free before connecting.

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

**Final interface** (E4 is Eloísa's; this is what she calls):
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

**Verification (individual version, one search at a time, 60 s / 300k nodes). Re-run by the main session: identical.**

| Test | Config | Result |
|---|---|---|
| `prob_fallo = 0`, I1 | A*+hadd | solved, cost 14, extra 0, 0 replans (same plan as `buscar`) |
| `prob_fallo = 0`, I2 | A*+hadd | solved, cost 23, extra 0, 0 replans (11 s initial search) |
| I1, T1 trips before step 11 | A*+hadd | `sin_solucion`: B1, B2 lost; 4 blocks needed, only 1 left (H1's block given back by C) |
| I1, line L12 fails before step 0 | A*+hadd | `sin_solucion`: L12 is the only way to S2 |
| I1, L12 fails at step 6 (already used) | A*+hadd | solved, extra 0, no replan |
| I1 + spare parallel line (scratch only) | A*+hadd | L12 fails at step 0 → 1 replan, solved, extra 0 |
| I1 + spare thermal T2 with 4 blocks (scratch only) | A*+hadd | T1 trips at step 11 → 1 replan, solved, cost 20 (extra 6: start T2, 4 blocks, reconnect B1, B2) |

I2, `prob_fallo = 0.1`, A*+hprec (fastest optimal config on individual I2, cheap per node; each run 1.0–1.3 s, replans ≤ 0.11 s):

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

**⚠️ Finding for E4 (Eloísa's):** I1–I3 have **exact supply and no spare paths**, so almost every failure is fatal. A plant trip that hits a needed block, or a line failure before the line is used, ends in `sin_solucion`. A line failure after use does nothing. On these instances E4 would mostly measure "% unsolvable", not extra maneuvers, and can't really test the proposal's prediction "trips cost more than line failures". To show recoveries, E4 needs grids with spare capacity: `red_generada(n, margen > 1)` gives spare blocks (helps with trips) but still no spare lines. Alternatively, add a spare line/plant variant. **Solved:** E4 was implemented by Milagros with a redundant variant `red_i2_reserva` (see section 4b).

## 4b. Experiment E4: failures and replanning (✅ done, Milagros)

### What was added
- `instancias.red_i2_reserva()`: I2 plus **twin lines** (`L12b`, `L23b`, `L45b`, `L46b`, each parallel to the original and of the same type) and a **spare thermal** `T3` (2 blocks) at S6. Not in `REDES` (E1–E3 and the CLI are unchanged). `validar` = [], optimum **23** (same as I2: the spares are never used without failures), A*+hprec 166,173 expanded, ~4.5 s.
- `experimentos.e4()` plus helpers `_e4_*` and constants `E4_*`. Run: `python3 experimentos.py E4`. Outputs: `resultados/e4.csv` (one row per run), `resultados/e4_resumen.csv`, `figuras/e4.png`.

### Design decisions (with the why)
- **Why I2-reserva exists:** I2 has exact supply and one path per substation, so almost any failure is final. Without spares, E4 could only measure "% unsolvable".
- **Why twin lines and not lines closing a loop:** a loop line (S1–S3, S5–S6) multiplies the possible energizing orders, and A*+hprec didn't finish in 1M nodes. A parallel line creates no new states (the destination ends up lit either way), so the search doesn't grow.
- **Why a 2-block thermal as the spare and not a spare block:** a spare block on a hydro or thermal plant makes the plan *cheaper* (optimum 20–21), so "extra maneuvers" would be measured against a different optimum. A 2-block thermal costs the same as using T1/T2 (start + 2 activations for 1 net block), so the optimum stays 23. It sits at S6 because the search grows least there (166k nodes vs 308–343k at S2/S3/S5).
- **Why I3 and I1 are left out:** with individual blocks, only A*+hadd solves I3, in ~97 s per search, which is too slow to repeat for many seeds. I1 is a toy with no redundancy and adds nothing beyond I2.
- **Factors:** failure type (lines only vs plants only, to compare them) × `prob_fallo` ∈ {0.05, 0.1, 0.2} × 15 seeds (`SEMILLA + i`). The whole E4 takes ~9.5 min (180 runs, ~1 GB RAM peak).
- **Paired comparison:** the same seed rolls the die the same way for both failure types, so failures land on the same steps.
- **A* + hprec:** admissible, so every plan and replan is optimal and "extra" is measured against the minimum. It's the fastest optimal config on individual I2. Limits: 60 s / 300k nodes per search (never reached).

### Real results (15 runs per row; "Extra" = mean over solved runs; % hit limit = 0 everywhere)

| Instance | Failure | p | Events | % solved | % unsolvable | Extra | Lost loads | Replans | Replan time (s) |
|---|---|---|---|---|---|---|---|---|---|
| I2 | line | 0.05 | 0.80 | 46.7 | 53.3 | 0 | 0 | 0.53 | 0.02 |
| I2 | line | 0.1 | 1.07 | 40.0 | 60.0 | 0 | 0 | 0.60 | 0.02 |
| I2 | line | 0.2 | 0.93 | 6.7 | 93.3 | 0 | 0 | 0.93 | 0.03 |
| I2 | plant | 0.05 | 0.80 | 20.0 | 80.0 | 0 | 0.33 | 0.80 | 0.04 |
| I2 | plant | 0.1 | 0.87 | 13.3 | 86.7 | 0 | 0.33 | 0.87 | 0.03 |
| I2 | plant | 0.2 | 0.93 | 6.7 | 93.3 | 0 | 0.13 | 0.93 | 0.04 |
| I2-reserva | line | 0.05 | 1.47 | 100.0 | 0.0 | 0 | 0 | 0.20 | 0.19 |
| I2-reserva | line | 0.1 | 2.80 | 100.0 | 0.0 | 0 | 0 | 0.27 | 0.44 |
| I2-reserva | line | 0.2 | 4.40 | 66.7 | 33.3 | 0 | 0 | 1.07 | 1.87 |
| I2-reserva | plant | 0.05 | 1.07 | 60.0 | 40.0 | 0.67 | 0.53 | 0.93 | 0.22 |
| I2-reserva | plant | 0.1 | 1.33 | 20.0 | 80.0 | 0 | 0.53 | 1.13 | 0.14 |
| I2-reserva | plant | 0.2 | 1.33 | 6.7 | 93.3 | 0 | 0.20 | 1.07 | 0.14 |

Checked by the main session: `validar` and optimum 23 of I2-reserva; two CSV rows re-run gave identical results (reserva/plant/p=0.05/seed 8: T1 trips at step 16, B2 lost, solved with +3; reserva/line/p=0.2: L12b then L12 fail before use → `sin_solucion`).

### Reading
- **Hypothesis "trips cost more than line failures": supported on solvability and lost loads.** With redundancy, line failures are survived 100/100/67% of the time vs 60/20/7% for trips. Only trips lose loads (by construction: a line failure never disconnects a load in our model).
- **Not testable on extra maneuvers.** All solved runs had 0 extra except two trip runs with +3 (T1 trips after feeding B2 → start T3 = start + activation + reconnect). Why so many zeros: (1) a recovered failure often costs nothing extra (the twin line costs the same; a T2 trip before T2 starts is replaced by T3 at the same price); (2) **selection bias**: expensive failures tend to be unsolvable, and "extra" is averaged only over solved runs; (3) a line that fails after use changes nothing (lit substations stay lit).
- **The redundancy is uneven:** every line has a 1:1 twin, but four plants share one spare thermal. That favors lines; mention it.
- **Why trips are often fatal even with the spare:** a hydro trip (H1/H2) is always fatal (each zone's only plant that starts alone). H1 tripping even after starting leaves zone N with no free block, so T1 can't start and the zones can't couple (both need a free block). Any second trip is fatal (only one spare).
- **Oddity:** the mean number of events barely grows with p (I2 line: 0.80 → 1.07 → 0.93; I2-reserva plant: 1.07 → 1.33 → 1.33), because a run stops at its first fatal failure. Higher p brings the fatal failure earlier, which leaves fewer steps for more failures.
- **Possible speed-up (not done):** ~90% of runtime is the same 4.5 s initial search repeated in each I2-reserva run. An optional "initial plan" parameter in `ejecutar_con_fallos` would remove it.

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
| 6 | visualisation | 2 | I1 frames saved | pending |

**Summary of optimal costs:** I1 = 14, I2 = 23, I3 = 26 (all equal to the counting bound; same in both versions).

After each part: run it, report the real output, and stop for your review if you want to go step by step.

---

## 7. Things noticed in Eloísa's `dominio.py` (not touching them, just flagging)

1. **`Cargada(S)` is never deleted.** `Deslastrar` removes the load but the substation keeps counting as "feeding a load", so a long line could be lit after shedding its only load. It's probably minor, but someone could ask about it in the defense.
2. **Cross-zone lines are silently ignored** in `energizar_corta/larga`. `validar(red)` will catch it on the instance side.
3. ~~`instancias.cargar` defaults to `agregada=True`, but the aggregated version doesn't exist yet, so `python main.py` without `--individual` crashes.~~ **Solved in step 4:** `cargar` now uses `dominio_agregado.py`. The `problema_agregado` stub in `dominio.py` remains (Eloísa can delete it or point it to the new file).
4. README says the delete field is `del`. In the code it's `dele` (`del` is a reserved Python word).

---

## 8. Questions to confirm before implementing

1. **Files:** mine = `instancias.py`, `planificador.py`, `replanificacion.py`, `visualizacion.py`, the aggregated version, and experiment **E4** in `experimentos.py` (its header says E4 is yours). `programacion.py` (optional) and `main.py` are not in scope. Correct? → ✅ **Answered: experiments E1–E3, E5, E6 are Eloísa's. E4 was then implemented by Milagros** (after step 5 showed I1–I3 can't recover from failures). Only `e4()` and its `_e4_*` helpers/`E4_*` constants were added to `experimentos.py`; Eloísa's stubs are untouched. Tell Eloísa she doesn't need to write E4.
2. ✅ **Aggregated version location:** new file `dominio_agregado.py` (decided).
3. ✅ Instance functions keep returning a `Red`; `cargar` builds the problem (went ahead with the default).
4. ✅ **DisparoCentral semantics (answered "OK to all"):** (A) the plant's blocks disappear (`Activado`/`Libre` deleted); (B) loads using them lose supply and count as lost loads; (C) if the tripped plant is thermal, its borrowed auxiliary block is given back (`Libre`); (D) **no cascade**: a thermal started with a block of the tripped plant keeps running (the auxiliary block is only needed to start); (E) substations keep `ConTension` (and `Cargada`, same quirk as `Deslastrar`).
5. ✅ No longer needed: the aggregated version exists, so `cargar`'s default `agregada=True` works.
6. ✅ "Same fixes" read as **same rules**: the aggregated version copies every rule of the individual one exactly, including its quirks (section 7).

---

## 9. Notes for the presentation / oral defense

Points worth a slide or a prepared answer. Added as they come up during implementation.

### 9.1 Tie-break by lower h in A* (step 1)
- **What:** when two nodes in the open list have the same `f = g + h`, A* expands the one with the **lower h** first, i.e. the one the heuristic estimates closest to the goal. If `h` also ties, the oldest one (FIFO).
- **Why it was needed:** I1 is small (1583 reachable states) and many states share `f = 14` (the optimal cost). With FIFO only, A* first expanded the old, shallow states with `f = 14` (lots of `g`, little progress) before reaching those close to the goal. That hid the benefit of the heuristics: A*+hmax expanded exactly as many nodes as h0 (1511).
- **Why it doesn't break optimality:** A* is optimal because it never expands a node with `f` greater than the optimal cost before finding the goal. The tie-break only reorders nodes **with the same f**, so that guarantee is untouched. All admissible configurations still return cost 14.
- **Effect (I1, expanded nodes):** hprec 1389 → 936, hmax 1511 → 1040, hadd 1347 → 287. UCS (h = 0 always) and greedy (f is already h) are unchanged, as expected.
- **One sentence to say:** *"When two nodes have the same f we expand the one with smaller h, because it is probably closer to the goal; it doesn't affect optimality since A\* only reorders nodes with equal f, but it avoids exploring many equivalent shallow nodes."*

### 9.2 Results that may get questions (step 1)
- **hprec (936) expands fewer nodes than hmax (1040) on I1.** Not a bug: hmax takes the **most expensive single** goal and ignores the rest, while hprec **counts every** missing goal. In I1 the goals (5 loads) are many and similar in cost, so "how many are missing" is more informative than "the hardest one". Both are admissible, neither dominates the other in general.
- **hmax/hadd are ~10× slower per node than hprec**, even if they expand fewer nodes: they recompute the relaxed problem (a fixpoint over all actions) for each generated state. Fewer nodes ≠ less time; E1/E2 should report both.
- **hadd is not admissible but found the optimal cost (14) on I1.** Allowed, not guaranteed: on bigger instances it may return cost > optimal.
- **Greedy + hadd needed only 39 expansions** and also found 14 on I1, by luck of the instance, not by guarantee.

### 9.3 Instances and `validar` (step 2)
- **Three instances of increasing difficulty, on purpose.** I1 is the toy explained by hand (optimum 14). I2 is sized so that **every** search finds the optimum (23) with individual blocks, which makes E1 a fair comparison of heuristics. I3 (resized in step 4, optimum 26) is solved optimally by every search in the aggregated version but not by UCS / A*+hprec / A*+hmax in the individual one, so it shows what aggregation gains (E3).
- **Why individual blocks explode.** Once zones are coupled, any free block can feed any load. "B2 uses block 1" and "B2 uses block 2" are different states for the search but equivalent in practice. The first I2 (10 blocks) reached 1.1M expanded nodes in 120 s without finishing, while the resized I2 (8 blocks) is solved by UCS in 2 s.
- **Optimal cost by counting.** When supply equals demand, every block must be activated, every substation energized and every load connected, so the optimum is the number of unavoidable maneuvers: I1 14, I2 23, I3 43. It is an independent check of the planner's result.
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
- **Same semantics, proved on every reachable state.** Converting each individual state into counters gives exactly the set of aggregated states (I1 1,583 → 81, I2 121,320 → 6,066, G(4) s0 25,582 → 446), so the optimal costs are identical: 14, 23, 16, 9, 14.
- **Aggregation removes symmetry, not combinations.** 14–50× fewer expanded nodes on I2 and G(4) with the same optimum, but the original I3 and G(n ≥ 8) still don't finish optimally: zones progress independently and the number of possible orders still grows exponentially. That is why I3 was resized.
- **hmax and hadd give exactly the same values in both versions.** In both relaxations one free block "never runs out" (`Libre(b)` or `Libres(z,1)` is never deleted), so the relaxation is equally optimistic. The gain of aggregation is in the number of states, not in the heuristic.
- **Greedy + hprec scales better than greedy + hadd on big instances** (original I3: 53 in 0.01 s; G(12): 64 in 0.11 s), but its plans are above the optimum. *Hypothesis, not measured:* greedy + hadd gets lost because the relaxation doesn't see blocks running out, and each hadd evaluation is expensive.
- **More grounded actions, not slower.** There is one action copy per counter value (I1: 99 vs 65 actions), but only one copy can apply in each state.

### 9.6 The resized I3 (after step 4)
- **I3 shows the gain of aggregation on one instance.** Same network, same optimum (26): aggregated UCS finishes in 3.5 s (157k expansions); individual UCS and A*+hprec stop at the 500k-node limit and A*+hmax at 120 s. Only A*+hadd finishes individually, in 97 s.
- **Why I3 is small: zones multiply the space.** Each zone's maneuvers can be interleaved with the others', so every extra zone multiplied the reachable space ×30–80 in the tests (2 zones: 417 states; 3 zones: 32.7k; 4 zones: hundreds of thousands). The original 12-substation I3 couldn't be solved optimally even aggregated.
- **Why it was resized and not kept big.** An instance that no optimal search finishes gives E1 nothing to compare. The scaling limit is shown instead by G(n) in E2, where it can be measured step by step.
- **`ExtenderAlcance` is grounded but optional.** The goal only has C–NO, C–NE and C–S. UCS reaches the optimum without it (blocks swap through C); A*+hprec and A*+hmax use it once, at cost 0.
- **A thermal must be worth starting.** A candidate with a 1-block thermal was rejected: starting it costs a block and gives one back, so the optimum (22) was below the expected count (24). The final T1 has 3 blocks.

### 9.7 Replanning (step 5)
- **Two states, one sentence.** *"The plan lives in the believed state; the world lives in the real state. Before every step the agent observes the real state and checks that the rest of the plan still reaches the goal from there; if not, it replans from what is really there."*
- **Why check the whole rest of the plan, not just the next action.** A broken line may only be needed 10 steps later. Checking the whole rest detects it now, before wasting maneuvers on a plan that will fail.
- **Why replan instead of "repairing" the plan.** The planner is already there and is optimal with A*: replanning from the real state gives the cheapest way to finish from where we actually are. Replans on I2 take ≤ 0.11 s.
- **Why the individual version.** When a plant trips we must know *which* loads were using *its* blocks (`Usa(k,b)`). Counters (`Libres(z,n)`) forget that.
- **DisparoCentral rules (A–E), each with its why:** blocks disappear (the plant produces nothing); their loads are lost (they had no other energy); a tripped thermal gives back its borrowed block (its machinery is off), only if that block still exists; no chain reaction (the borrowed block is only needed to *start* a thermal, no action checks it later); voltage stays (simplification: other sources hold it).
- **Possible question: "seed 1 recovers with only +1, isn't T1's trip suspicious?"** T1's second block had been lent to start T2. By rule D, T2 keeps running, and by rule C, T1's own borrowed block comes back. So losing T1 costs no blocks overall, and only B2 needs to be reconnected (+1). It follows the agreed rules; a cascade (rule D the other way) would have made it fatal.
- **Reproducible randomness.** Only `random.Random(semilla)`, the die is rolled before every step even without an event, and candidates are sorted. The same seed gives the same run.
- **Main finding: our instances are fragile by design.** They have exact supply (built that way so the optimum can be checked by counting) and no spare lines, so most failures are fatal (I2: 8 of 10 seeds unsolvable at p = 0.1). That isn't a planner bug: the search *proves* there's no solution (`sin_solucion`, in ≤ 0.11 s). The scratch variants of I1 with a spare line or a spare thermal recover (extra 0 and 6), which shows that replanning works when the grid has redundancy. Message for the slide: *"replanning can only use the redundancy the grid has; with no spare blocks or lines, a failure is final."*

### 9.8 Experiment E4 (failures)
- **The question:** *"If things break during the plan, how often can we still finish, and at what price?"* We measure the % of runs solved, extra maneuvers, lost loads and replanning time, separately for line failures and plant trips, at three failure probabilities.
- **Why we had to build I2-reserva.** On the original I2 almost every failure is final (exact supply, one cable to each place). To measure *recovery*, the grid must have something to recover with: twin cables and one spare thermal plant. They are designed so that **with no failures the optimum is still 23**; otherwise "extra maneuvers" would be measured against a different plan.
- **Main result (one sentence):** *"With spare capacity, the agent survives cable failures almost always (100% at low probability) but plant shutdowns much less often (60% → 7%), and only plant shutdowns leave customers without power; replanning takes under 2 s."*
- **Honest limitation, say it before they ask:** extra maneuvers are almost always 0, so they don't show the difference. The reasons are that recovered failures are often free (twin cable, same-price spare plant), that the costly failures end up unsolvable and drop out of the average (selection bias), and that a cable breaking after use changes nothing. The comparison also favors cables: each cable has its own twin, while four plants share one spare.
- **Why a hydro plant trip is always fatal:** each zone has only one plant that can start from zero. Without it the zone can't produce its first block, and every other plant needs a block to start.
- **Paired design:** the same seeds are used for both failure types, so failures happen at the same steps and only the *type* changes.

