# ARGOS — Airline Route & Ground Operations System

**AI-powered OCC (Operations Control Center) for an Incheon-hub carrier**  
대한항공 취업 포트폴리오 프로젝트 · Python 3.12 · 80 tests passing

---

## Overview

ARGOS simulates the core workflow of an airline Operations Control Center at Incheon (ICN/RKSI):

```
지연 감지  →  전파 시뮬레이션  →  회복 시나리오 3개 자동 생성  →  OCC 관리자 최종 승인
```

The system combines classical OR methods (ILP/CP-SAT), ML prediction (LightGBM), graph algorithms (NetworkX), and a LangGraph multi-agent layer (Claude Sonnet) into a single OCC decision-support tool. **No recovery action is ever executed without explicit human approval.**

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data store | DuckDB (single-file analytics DB) |
| ML prediction | LightGBM (binary delay classifier) |
| Delay propagation | NetworkX DAG |
| Aircraft re-assignment | OR-Tools CP-SAT |
| Crew scheduling | OR-Tools CP-SAT + FAR 117 |
| Multi-agent OCC | LangGraph + Claude Sonnet (`claude-sonnet-4-6`) |
| UAM/UTM integration | ACROSS API simulation (국토교통부 UTM) |
| Dashboard | Streamlit + Plotly |

---

## Project Structure

```
ARGOS/
├── src/argos/
│   ├── config.py                   # Settings (pydantic-settings, .env)
│   ├── data_gen/
│   │   ├── generator.py            # Synthetic flight data generator
│   │   ├── routes.py               # 60 ICN-based route definitions
│   │   ├── schemas.py              # Pydantic models + DuckDB DDL
│   │   └── validator.py            # Data quality gate
│   ├── domain/
│   │   ├── block_time.py           # Aircraft perf table + CI adjustment
│   │   ├── far117.py               # FAR 117 FDP limits (hard constraint)
│   │   ├── mct.py                  # ICN T1/T2 minimum connection time
│   │   └── cost_index.py           # DOC-minimising CI grid search
│   ├── prediction/
│   │   ├── features.py             # Feature engineering (hour, dow, weather…)
│   │   └── model.py                # LightGBM delay predictor (P(delay≥15min))
│   ├── simulation/
│   │   └── propagation.py          # NetworkX rotation DAG + 3-scenario generator
│   ├── optimization/
│   │   ├── aircraft.py             # CP-SAT aircraft re-assignment ILP
│   │   └── crew.py                 # CP-SAT crew roster (CAPT/FO, FAR 117)
│   ├── agents/
│   │   ├── state.py                # OCCState TypedDict
│   │   ├── tools.py                # LangChain tools wrapping domain modules
│   │   └── occ_graph.py            # LangGraph StateGraph (7 nodes, human-in-the-loop)
│   ├── uav/
│   │   ├── models.py               # UAMVehicle, Vertiport, FlightPlan4D, ACROSSResponse
│   │   ├── network.py              # ICN-hub vertiport network (NetworkX)
│   │   ├── airspace.py             # ICN CTR / ILS conflict detection
│   │   └── across_client.py        # ACROSS UTM client (simulation mode)
│   └── ui/
│       └── dashboard.py            # Streamlit OCC dashboard (2 tabs)
├── scripts/
│   ├── setup_db.py                 # Initialize DuckDB schema
│   ├── generate_data.py            # Generate 3-year synthetic dataset
│   ├── validate_data.py            # Data quality gate
│   ├── train_model.py              # Train LightGBM predictor
│   ├── simulate_delay.py           # Run delay propagation from CLI
│   └── run_occ.py                  # Run LangGraph OCC agent (dry-run or full)
├── tests/
│   ├── test_data_gen/              # 7 tests
│   ├── test_optimization/          # 39 tests (aircraft + crew)
│   ├── test_agents/                # 9 tests
│   └── test_uav/                   # 25 tests
├── notebooks/
│   └── 01_eda.ipynb                # EDA notebook
└── data/
    └── db/
        └── argos.duckdb            # 161,868 flights · 58 aircraft · 60 routes
```

---

## Quick Start

```bash
# 1. Create environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# 2. Configure API key
cp .env.example .env
# → add ANTHROPIC_API_KEY=sk-ant-...

# 3. Initialize DB and generate data
python scripts/setup_db.py
python scripts/generate_data.py          # full 3-year dataset (~2 min)
# python scripts/generate_data.py --start 2024-01-01 --end 2024-06-30  # fast

# 4. Validate data quality
python scripts/validate_data.py

# 5. Train delay prediction model
python scripts/train_model.py

# 6. Run tests
pytest                                   # 80 tests, ~10 s

# 7. Launch dashboard
streamlit run src/argos/ui/dashboard.py
```

---

## Core Modules

### Delay Propagation (`simulation/propagation.py`)

Builds a directed aircraft rotation graph from the day's schedule and propagates a departure delay through all downstream legs on the same tail.

```python
from argos.simulation.propagation import DelayPropagator

propagator = DelayPropagator(db_path=Path("data/db/argos.duckdb"))
flights_df = propagator.load_flights(date(2024, 6, 15))
G = propagator.build_rotation_graph(flights_df)

result = propagator.propagate(G, trigger_flight_id, initial_delay_minutes=120)
print(f"Cascade: {result.cascade_depth} legs, {result.total_pax_impacted} PAX")

scenarios = propagator.generate_scenarios(G, trigger_flight_id, 120, dep_date)
# → 3 RecoveryScenario objects: Accept, Swap, Cancel
```

### Aircraft Re-assignment (`optimization/aircraft.py`)

CP-SAT ILP: assigns tail numbers to disrupted flights maximising covered PAX, subject to type-compatibility and no-overlap (round-trip footprint).

```python
from argos.optimization.aircraft import AircraftAssigner

assigner, tasks, resources = AircraftAssigner.load_from_db(
    db_path=Path("data/db/argos.duckdb"),
    op_date=date(2024, 6, 15),
    disrupted_flight_ids=[...],
)
result = assigner.solve(tasks, resources, op_day=date(2024, 6, 15))
print(result.summary())
```

### Crew Scheduling (`optimization/crew.py`)

CP-SAT: assigns CAPT + FO pairs to each disrupted leg. Enforces FAR 117 § 117.65(a) daily flight-time limit. Post-solve FDP window validation calls `far117.is_fdp_legal()`.

```python
from argos.optimization.crew import CrewAssigner

crew_pool = CrewAssigner.generate_crew(op_day=date(2024, 6, 15))
assigner = CrewAssigner()
result = assigner.solve(legs, crew_pool, op_day=date(2024, 6, 15))
print(result.summary())
# FAR 117 violations surfaced in result.far117_violations
```

### LangGraph OCC Agent (`agents/occ_graph.py`)

Seven-node StateGraph. The `human_gate` node uses `interrupt()` to pause for OCC manager approval before any action is recorded.

```
simulate → analyse → optimise → brief_occ → human_gate ──► execute
                                                        └──► abort
```

```python
from argos.agents.occ_graph import run_until_approval, resume_after_approval

state, graph = run_until_approval(
    db_path="data/db/argos.duckdb",
    op_date="2024-06-15",
    trigger_flight_id="<uuid>",
    initial_delay_minutes=120,
)
print(state["scenario_briefing"])          # Claude-authored OCC briefing

final = resume_after_approval(graph, approved_scenario_id=2, approval_notes="Approved")
print(final["execution_summary"])
```

**CLI (dry-run, no API key required):**
```bash
python scripts/run_occ.py --auto --delay 120 --date 2024-06-15 --dry-run
```

**Full run (requires `ANTHROPIC_API_KEY`):**
```bash
python scripts/run_occ.py --auto --delay 120 --date 2024-06-15
```

### UAM / ACROSS (`uav/`)

Models the ICN-hub UAM network (7 vertiports, 14 corridors) and simulates the Korean ACROSS UTM system for eVTOL flight plan approval.

```python
from argos.uav.across_client import ACROSSClient

client = ACROSSClient()                    # simulation mode
plan, response = client.suggest_uam_alternative(
    delayed_flight_number="KE001",
    delayed_pax=10,
    origin_vertiport_id="SBR",            # 송도
    dest_vertiport_id="YDP",              # 여의도
    etd_utc=datetime(2024, 6, 15, 3, 0, tzinfo=timezone.utc),
)
print(response.approved, response.message)
```

Conflict checks: ICN CTR altitude cap (≤ 1,000 ft AGL), ILS approach corridor protection, noise curfew (23:00–06:00 KST), UAM–UAM separation (0.3 NM minimum).

---

## OCC Dashboard

```bash
streamlit run src/argos/ui/dashboard.py
```

**Tab 1 — OCC Operations**
- KPI cards: total flights, delayed count, cancellations, PAX
- Plotly route map with delay highlighting
- Departure schedule table with colour-coded status
- Delay simulation: cascade chain, 3 recovery scenario cards with approve buttons
- Departure delay histogram

**Tab 2 — UAM / ACROSS**
- OpenStreetMap vertiport network (corridors colour-coded by CTR avoidance)
- ACROSS flight plan submission with live conflict detection
- Vertiport registry table

---

## Key Domain Constants

| Constant | Value | Source |
|----------|-------|--------|
| Hub | ICN (RKSI), UTC+9 | Korean Air network |
| Fleet | B737-800, A321neo, B777-300ER, B787-9, B747-8i | KE fleet |
| Narrow min turn | 45 min | ICN ground ops |
| Wide min turn | 60 min | ICN ground ops |
| FAR 117 max flight time | 8 h / calendar day | 14 CFR § 117.65(a) |
| FAR 117 min rest | 10 h | 14 CFR § 117.25 |
| ICN CTR radius | 5 NM | AIP Korea |
| UAM alt cap (CTR) | 1,000 ft AGL | MOLIT UAM guidelines |
| UAM–UAM separation | 0.3 NM | ACROSS draft standard |

---

## Dataset

| Table | Rows | Description |
|-------|------|-------------|
| `flights` | 161,868 | 3-year synthetic schedule (2022–2024), 60 routes |
| `routes` | 60 | ICN-based routes across 6 regions |
| `aircraft` | 58 | KE-style tail registry (HL7xxx / HL8xxx / HL80xx) |
| `route_aircraft` | — | Type assignments per route |
| `weather_events` | — | Synthetic weather windows linked to delays |
| `delay_codes_ref` | 99 | IATA AHM 730 delay code reference |

Generated with `scripts/generate_data.py` — pure Python, no API calls.

---

## Environment Variables

```env
ANTHROPIC_API_KEY=sk-ant-...      # required for LangGraph OCC agent
CLAUDE_MODEL=claude-sonnet-4-6    # default reasoning model
CLAUDE_HAIKU_MODEL=claude-haiku-4-5-20251001  # bulk inference
DUCKDB_PATH=data/db/argos.duckdb
DATA_START_DATE=2022-01-01
DATA_END_DATE=2024-12-31
RANDOM_SEED=42
```

---

## Tests

```
tests/
├── test_data_gen/test_validator.py      7 tests   data quality checks
├── test_optimization/test_aircraft.py  18 tests   CP-SAT aircraft assigner
├── test_optimization/test_crew.py      21 tests   CP-SAT crew scheduler
├── test_agents/test_tools.py            9 tests   LangGraph tools + graph structure
└── test_uav/test_uav.py                25 tests   UAM network, airspace, ACROSS
                                        ─────────
                                        80 total   ~10 s
```

```bash
pytest                     # all tests
pytest tests/test_uav/     # single module
pytest -v --tb=short       # verbose
```

---

## Safety Notes

- **FAR 117 is a hard constraint.** `far117.max_fdp_hours()` is the single authority for duty limits. No code path relaxes these limits.
- **Human-in-the-loop is mandatory.** The LangGraph `human_gate` node always interrupts before any recovery action is logged. Agents propose; the OCC manager decides.
- **Simulation only.** No connection to real airline systems. All data is synthetic.
