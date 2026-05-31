# OCC Dashboard — UI Kit

A high-fidelity recreation of ARGOS' **Operations Control Center** dashboard as React + JSX components running directly in the browser.

The original is built with **Streamlit + Plotly + DuckDB**: `src/argos/ui/dashboard.py` in [SoryeongYoo/ARGOS](https://github.com/SoryeongYoo/ARGOS). This kit cosmetically mirrors that interface so designers can compose mockups without spinning up the Python stack.

## Tabs

1. **OCC Operations** — KPI strip · route map · departure schedule · delay-propagation simulation panel · 3 recovery-scenario cards · delay distribution histogram
2. **UAM / ACROSS** — vertiport network map · ACROSS flight-plan submission form · vertiport registry table

## Interactive flow

1. Pick an operating date and trigger flight from the sidebar.
2. Set a departure delay (slider, 15–300 min, 15 min step).
3. Click **▶ Run simulation** — cascade chain + 3 scenarios materialize.
4. **Approve** Scenario 1 / 2 / 3 → success toast logs the action.
5. Switch to the UAM tab → submit an ACROSS plan → see approval/denial result.

## Files

| File | Role |
|---|---|
| `index.html` | Entry point — loads React, Babel, components, mounts `<App/>` |
| `app.jsx` | Root component, tab state, exposes `useDashboard()` |
| `components.jsx` | Atoms: `PillButton`, `Badge`, `KPICard`, `Icon`, `Sparkline` |
| `sidebar.jsx` | Operating-date picker, trigger-flight combo, delay slider, primary CTA |
| `tab_occ.jsx` | OCC Operations tab content |
| `tab_uam.jsx` | UAM / ACROSS tab content |
| `data.jsx` | Fake `FLIGHTS`, `SCENARIOS`, `VERTIPORTS`, `CORRIDORS` |

## Fidelity notes

- **Layout, color, type, motion** match the design system 1:1.
- **Maps and charts are SVG mocks**, not Plotly. Lat/lon coordinates and corridor data are pulled from `src/argos/uav/network.py` and the dashboard schedule query, but rendered as a simplified custom SVG. This is intentional — the kit is for visual mockups, not production rendering.
- **No real DuckDB.** All flight and scenario data lives in `data.jsx`.
