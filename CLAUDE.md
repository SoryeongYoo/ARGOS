# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project

ARGOS (Airline Route & Ground Operations System) — AI-powered OCC (Operations Control Center) for an Incheon-hub carrier (modelled on Korean Air). Portfolio project for 대한항공 취업.

Core flow: **지연 감지 → 전파 시뮬레이션 → 회복 시나리오 3개 자동 생성 → OCC 관리자 최종 승인**

## Environment setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.example .env           # add ANTHROPIC_API_KEY
```

## Common commands

```bash
# Initialize DuckDB schema (no API calls)
python scripts/setup_db.py

# Generate 3-year synthetic dataset (pure Python, no API calls)
python scripts/generate_data.py

# Quick test with short date range
python scripts/generate_data.py --start 2024-01-01 --end 2024-01-31

# Specific routes only
python scripts/generate_data.py --routes ICN-NRT ICN-JFK --start 2024-06-01 --end 2024-06-30

# Data quality gate (run before any ML training)
python scripts/validate_data.py
python scripts/validate_data.py --strict   # warnings treated as errors

# EDA notebook
jupyter lab notebooks/01_eda.ipynb

# Run tests
pytest

# Lint / type-check
ruff check src tests
mypy src
```

## Architecture

### Data generation pipeline (`src/argos/data_gen/`)

Two-phase design:
1. **Claude API phase** — `generator.py:SyntheticDataGenerator.generate_route_params()` asks Claude to produce realistic delay distribution parameters (probability, shape, seasonal factors, IATA delay codes) for each of the 60 routes. Uses **prompt caching** on the aviation domain system prompt and **tool use** (`set_route_delay_parameters`) for structured JSON output.
2. **NumPy phase** — `generate_flights()` samples from those distributions at scale (~120k rows over 3 years). Never calls the API per-row.

`routes.py` contains the full 60-route definition (all `RouteDefinition` objects, `ROUTE_MAP` dict). `schemas.py` has Pydantic models and DuckDB DDL.

### Domain models (`src/argos/domain/`)

Pure calculation modules — no I/O, no LLM calls:

| Module | Key function | Notes |
|--------|-------------|-------|
| `block_time.py` | `calculate_block_time(distance_nm, aircraft_type, ci, wind)` | Aircraft perf table + CI adjustment |
| `far117.py` | `max_fdp_hours(report_hour, num_segments, augmented)` | FAR 117 Appendix B table; hard constraint in crew optimizer |
| `mct.py` | `get_mct(arriving_type, departing_type, ...)` | ICN MCT matrix incl. T1/T2 terminal buffer |
| `cost_index.py` | `optimal_ci(distance, aircraft_type, fuel_price, crew_cost)` | Grid-search CI for min DOC |

### Planned modules (Weeks 2–10)

| Module | Tech | Status |
|--------|------|--------|
| `prediction/` | LightGBM delay prediction | ✅ Week 3 |
| `optimization/aircraft.py` | OR-Tools ILP aircraft assignment | Week 5 |
| `optimization/crew.py` | OR-Tools CP-SAT roster | Week 6 |
| `simulation/propagation.py` | NetworkX DAG delay propagation | Week 4 |
| `agents/` | LangGraph multi-agent OCC | Week 7-8 |
| `uav/` | UAV/AAM ACROSS integration | Week 9 |
| `ui/` | Streamlit OCC dashboard | Week 10 |

### Storage

DuckDB at `data/db/argos.duckdb`. Main tables: `flights`, `routes`, `route_aircraft`, `aircraft`, `weather_events`, `delay_codes_ref`.

`dep_hour_utc`, `dep_month`, `dep_dow` are DuckDB generated columns on `flights` — do not insert them manually.

## Key domain constants

- **Hub**: ICN (RKSI), UTC+9 (KST). All timestamps stored in UTC.
- **Fleet**: B737-800 (HL74xx), A321neo (HL82xx), B777-300ER (HL77xx), B787-9 (HL80xx), B747-8i (HL75xx)
- **Delay codes**: IATA AHM 730 standard, 2-digit `"00"`–`"99"`. Full reference in `schemas.py:IATA_DELAY_CODES`.
- **FAR 117**: Hard constraint in crew optimizer. Safety constraints are never relaxed. `far117.py:max_fdp_hours()` is the authority — do not use ad-hoc limits.
- **Human-in-the-loop**: Final OCC approval is always required before any recovery action is executed. Agents propose; humans decide.

## Claude API usage patterns

- System prompt is **prompt-cached** (`cache_control: ephemeral`) in all generator calls — the aviation domain knowledge is large and reused across batch iterations.
- Use **tool use** (not free-form JSON parsing) for all structured outputs from Claude.
- Default models: `claude-sonnet-4-6` for complex reasoning, `claude-haiku-4-5-20251001` for bulk/cheap inference.
- All Claude API calls go through `anthropic.Anthropic(api_key=settings.anthropic_api_key)` — never hardcode keys.

## Sprint plan

| Week | Deliverable |
|------|-------------|
| 1 | Project structure + synthetic data generator ✅ |
| 2 | EDA notebook + data quality validation ✅ |
| 3 | LightGBM delay prediction model ✅ |
| 4 | NetworkX delay propagation simulator |
| 5 | OR-Tools aircraft assignment ILP |
| 6 | CP-SAT crew roster optimizer |
| 7-8 | LangGraph multi-agent OCC system |
| 9 | UAV/AAM integration module |
| 10 | Streamlit dashboard + Docker Compose |
