"""
ARGOS OCC Dashboard — Streamlit UI

Layout
------
Sidebar   : date picker, delay trigger controls
Col-left  : KPI cards (flights, delays, PAX impacted)
Col-right : Flight map (Plotly scatter_geo)
Bottom    : Cascade chain table + Recovery scenario cards
UAM tab   : Vertiport network map + ACROSS status

Run with:
    streamlit run src/argos/ui/dashboard.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Allow running as `streamlit run src/argos/ui/dashboard.py` from project root
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from argos.simulation.propagation import DelayPropagator
from argos.uav.across_client import ACROSSClient
from argos.uav.models import FlightRules, GeoPoint, UAMFlightPlan, Waypoint4D
from argos.uav.network import VERTIPORTS, build_uam_network, find_route

# ── Constants ─────────────────────────────────────────────────────────────────

DB_PATH = str((_ROOT / "data" / "db" / "argos.duckdb").resolve())
KST = timezone(timedelta(hours=9))

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ARGOS OCC",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_flights_for_day(dep_date_str: str) -> pd.DataFrame:
    dep_date = date.fromisoformat(dep_date_str)
    day_start = datetime(dep_date.year, dep_date.month, dep_date.day, tzinfo=timezone.utc)
    day_end   = day_start + timedelta(days=1)

    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute("""
            SELECT f.flight_id, f.flight_number, f.route_id,
                   f.origin_iata, f.dest_iata,
                   f.aircraft_registration, f.aircraft_type,
                   f.scheduled_dep_utc, f.scheduled_arr_utc,
                   f.block_time_minutes, f.dep_delay_minutes,
                   COALESCE(f.pax_boarded, 0) AS pax_boarded,
                   f.status,
                   r.origin_lat, r.origin_lon, r.dest_lat, r.dest_lon
            FROM flights f
            JOIN routes r ON f.route_id = r.route_id
            WHERE f.scheduled_dep_utc >= ? AND f.scheduled_dep_utc < ?
            ORDER BY f.scheduled_dep_utc
        """, [day_start, day_end]).df()
    finally:
        con.close()

    df["scheduled_dep_utc"] = pd.to_datetime(df["scheduled_dep_utc"], utc=True)
    df["dep_kst"] = df["scheduled_dep_utc"].dt.tz_convert("Asia/Seoul")
    return df


@st.cache_data(ttl=300)
def load_routes_latlon() -> pd.DataFrame:
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute(
            "SELECT route_id, origin_lat, origin_lon, dest_lat, dest_lon FROM routes"
        ).df()
    finally:
        con.close()
    return df


def run_propagation(flight_id: str, delay_min: int, dep_date: date):
    propagator = DelayPropagator(db_path=Path(DB_PATH))
    flights_df = propagator.load_flights(dep_date)
    G = propagator.build_rotation_graph(flights_df)
    result = propagator.propagate(G, flight_id, delay_min)
    scenarios = propagator.generate_scenarios(G, flight_id, delay_min, dep_date)
    return result, scenarios, G, flights_df


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("ARGOS OCC")
    st.caption("Airline Route & Ground Operations System")
    st.divider()

    dep_date = st.date_input(
        "Operating Date",
        value=date(2024, 6, 15),
        min_value=date(2022, 1, 1),
        max_value=date(2024, 12, 31),
    )

    st.subheader("Simulate Delay")
    flights_df = load_flights_for_day(str(dep_date))

    if flights_df.empty:
        st.warning("No flights for this date.")
        st.stop()

    # Only show flights with downstream rotations (cascade candidates)
    cascade_candidates = (
        flights_df.groupby("aircraft_registration")
        .filter(lambda g: len(g) >= 2)
        .sort_values("scheduled_dep_utc")
        .drop_duplicates("aircraft_registration", keep="first")
    )
    flight_labels = (
        cascade_candidates["flight_number"].astype(str)
        + "  "
        + cascade_candidates["route_id"].astype(str)
        + "  ("
        + cascade_candidates["dep_kst"].dt.strftime("%H:%M KST")
        + ")"
    ).tolist()
    flight_ids = cascade_candidates["flight_id"].tolist()

    selected_idx = st.selectbox(
        "Trigger Flight",
        range(len(flight_labels)),
        format_func=lambda i: flight_labels[i],
    )
    selected_flight_id = flight_ids[selected_idx]

    delay_min = st.slider("Departure Delay (min)", 15, 300, 90, step=15)

    run_sim = st.button("▶ Run Simulation", type="primary", use_container_width=True)
    st.divider()
    st.caption(f"DB: {flights_df.shape[0]:,} flights loaded")


# ── Main tabs ─────────────────────────────────────────────────────────────────

tab_occ, tab_uam = st.tabs(["OCC Operations", "UAM / ACROSS"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OCC Operations
# ══════════════════════════════════════════════════════════════════════════════
with tab_occ:
    # ── KPI row ───────────────────────────────────────────────────────────────
    total_flights = len(flights_df)
    delayed = (flights_df["dep_delay_minutes"] > 15).sum()
    cancelled = (flights_df["status"] == "CNX").sum()
    total_pax = int(flights_df["pax_boarded"].sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Flights",   f"{total_flights:,}")
    k2.metric("Delayed (>15 min)", f"{delayed:,}",
              delta=f"{delayed/total_flights:.1%}", delta_color="inverse")
    k3.metric("Cancelled",       f"{cancelled:,}", delta_color="inverse")
    k4.metric("PAX Today",       f"{total_pax:,}")

    st.divider()

    # ── Flight map + schedule ──────────────────────────────────────────────────
    map_col, sched_col = st.columns([3, 2])

    with map_col:
        st.subheader("Route Map")
        sample = flights_df.head(300)  # limit for rendering speed
        fig_map = go.Figure()
        for _, row in sample.iterrows():
            color = "red" if row["dep_delay_minutes"] > 15 else "#1f77b4"
            fig_map.add_trace(go.Scattergeo(
                lon=[row["origin_lon"], row["dest_lon"]],
                lat=[row["origin_lat"], row["dest_lat"]],
                mode="lines",
                line=dict(width=1, color=color),
                opacity=0.5,
                showlegend=False,
                hoverinfo="skip",
            ))
        fig_map.add_trace(go.Scattergeo(
            lon=[126.4505],
            lat=[37.4691],
            mode="markers+text",
            marker=dict(size=12, color="gold", symbol="star"),
            text=["ICN"],
            textposition="top center",
            showlegend=False,
        ))
        fig_map.update_geos(
            projection_type="natural earth",
            showcountries=True, countrycolor="lightgray",
            showland=True, landcolor="#f5f5f5",
            showocean=True, oceancolor="aliceblue",
            center=dict(lat=37, lon=127),
            projection_scale=8,
        )
        fig_map.update_layout(
            height=380,
            margin=dict(l=0, r=0, t=0, b=0),
            geo=dict(bgcolor="aliceblue"),
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with sched_col:
        st.subheader("Departure Schedule")
        sched_display = flights_df[[
            "flight_number", "route_id", "dep_kst", "dep_delay_minutes", "status"
        ]].copy()
        sched_display["dep_kst"] = sched_display["dep_kst"].dt.strftime("%H:%M")
        sched_display.columns = ["Flight", "Route", "Dep(KST)", "Delay(min)", "Status"]
        sched_display = sched_display.head(20)

        def _color_row(row):
            if row["Status"] == "CNX":
                return ["background-color: #ffcccc"] * len(row)
            if row["Delay(min)"] > 15:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            sched_display.style.apply(_color_row, axis=1),
            use_container_width=True,
            height=340,
        )

    # ── Simulation results ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("Delay Propagation Simulation")

    if run_sim or "sim_result" in st.session_state:
        if run_sim:
            with st.spinner("Running delay propagation..."):
                result, scenarios, G, all_flights = run_propagation(
                    selected_flight_id, delay_min, dep_date
                )
            st.session_state["sim_result"]   = result
            st.session_state["sim_scenarios"] = scenarios
            st.session_state["sim_flight_id"] = selected_flight_id
            st.session_state["sim_delay"]     = delay_min

        result    = st.session_state["sim_result"]
        scenarios = st.session_state["sim_scenarios"]

        # Cascade summary
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cascade Depth",  result.cascade_depth)
        c2.metric("Total Delay",    f"{result.total_delay_minutes} min")
        c3.metric("PAX Impacted",   f"{result.total_pax_impacted:,}")
        c4.metric("Trigger Delay",  f"{result.initial_delay_minutes} min")

        # Cascade chain
        if result.cascade_chain:
            st.markdown("**Cascade chain:** " + " → ".join(result.cascade_chain[:6])
                        + ("…" if len(result.cascade_chain) > 6 else ""))

        # Scenario cards
        st.markdown("### Recovery Scenarios")
        scen_cols = st.columns(3)
        feasibility_color = {"HIGH": "green", "MEDIUM": "orange", "LOW": "red"}
        for i, s in enumerate(scenarios):
            with scen_cols[i]:
                fc = feasibility_color.get(s.feasibility, "gray")
                st.markdown(
                    f"**[{s.scenario_id}] {s.name}**  \n"
                    f":{fc}[{s.feasibility}]  |  Cost index: {s.cost_index:.1f}  \n"
                    f"{s.description}  \n"
                    f"*Action:* {s.action_required}  \n"
                    f"Residual: {s.residual.cascade_depth} legs, "
                    f"{s.residual.total_delay_minutes} min, "
                    f"{s.residual.total_pax_impacted} PAX"
                )
                if st.button(f"Approve Scenario {s.scenario_id}", key=f"approve_{i}"):
                    st.success(
                        f"✅ Scenario {s.scenario_id} approved.  \n"
                        f"Action logged: {s.action_required}  \n"
                        "**[Simulation]** No real operations affected."
                    )
    else:
        st.info("Select a trigger flight and click **▶ Run Simulation** to begin.")

    # ── Delay histogram ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Delay Distribution")
    delayed_df = flights_df[flights_df["dep_delay_minutes"] > 0]
    if not delayed_df.empty:
        fig_hist = px.histogram(
            delayed_df,
            x="dep_delay_minutes",
            nbins=40,
            labels={"dep_delay_minutes": "Departure Delay (min)"},
            color_discrete_sequence=["#1f77b4"],
        )
        fig_hist.update_layout(height=250, margin=dict(t=10))
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No delayed flights on this date.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: UAM / ACROSS
# ══════════════════════════════════════════════════════════════════════════════
with tab_uam:
    st.subheader("UAM Vertiport Network — ICN Hub Region")

    G_uam = build_uam_network()

    # Vertiport map
    vp_data = []
    for vid, vp in VERTIPORTS.items():
        vp_data.append({
            "id":   vid,
            "name": vp.name_en,
            "lat":  vp.position.lat,
            "lon":  vp.position.lon,
            "pads": vp.pad_count,
        })
    vp_df = pd.DataFrame(vp_data)

    fig_uam = go.Figure()

    # Draw corridors
    for u, v, data in G_uam.edges(data=True):
        vp_u = VERTIPORTS[u]
        vp_v = VERTIPORTS[v]
        color = "#aaa" if data["corridor"].avoids_icn_ctr else "#e07b39"
        fig_uam.add_trace(go.Scattermapbox(
            lon=[vp_u.position.lon, vp_v.position.lon],
            lat=[vp_u.position.lat, vp_v.position.lat],
            mode="lines",
            line=dict(width=2, color=color),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Draw vertiports
    fig_uam.add_trace(go.Scattermapbox(
        lon=vp_df["lon"],
        lat=vp_df["lat"],
        mode="markers+text",
        marker=dict(size=14, color="#1f77b4"),
        text=vp_df["id"],
        textposition="top right",
        hovertext=vp_df.apply(
            lambda r: f"{r['id']}: {r['name']}<br>Pads: {r['pads']}", axis=1
        ),
        hoverinfo="text",
        showlegend=False,
    ))

    # ICN CTR circle (approximate — 5 NM radius markers)
    import math
    ctr_lats, ctr_lons = [], []
    for deg in range(0, 361, 10):
        rad = math.radians(deg)
        dlat = (5 / 60) * math.cos(rad)
        dlon = (5 / 60) * math.sin(rad) / math.cos(math.radians(37.47))
        ctr_lats.append(37.4691 + dlat)
        ctr_lons.append(126.4505 + dlon)
    fig_uam.add_trace(go.Scattermapbox(
        lon=ctr_lons, lat=ctr_lats,
        mode="lines",
        line=dict(width=1.5, color="red", dash="dot"),
        name="ICN CTR (5 NM)",
        showlegend=True,
    ))

    fig_uam.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=37.48, lon=126.85),
            zoom=8.5,
        ),
        height=480,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(x=0, y=1),
    )
    st.plotly_chart(fig_uam, use_container_width=True)

    st.caption(
        "Grey corridors avoid ICN CTR.  "
        "Orange corridors cross CTR boundary (require ATC coordination).  "
        "Red dashed circle = ICN CTR 5 NM boundary."
    )

    # ── ACROSS flight plan demo ────────────────────────────────────────────────
    st.divider()
    st.subheader("ACROSS Flight Plan Submission")

    col_a, col_b = st.columns(2)
    with col_a:
        origin_vp = st.selectbox("Origin Vertiport",  list(VERTIPORTS.keys()), index=0)
        dest_vp   = st.selectbox("Destination Vertiport", list(VERTIPORTS.keys()), index=3)
        dep_hour  = st.slider("Departure Hour (UTC)", 0, 23, 3)
        alt_ft    = st.slider("Cruise Altitude (ft AGL)", 300, 1500, 800, step=100)
        pax_count = st.slider("Passenger Count", 1, 4, 2)

    with col_b:
        G_route = build_uam_network()
        path = find_route(G_route, origin_vp, dest_vp)
        flight_min = 0.0

        if path and len(path) >= 2:
            from argos.uav.network import route_distance_nm
            dist = route_distance_nm(G_route, path)
            flight_min = (dist / (120 * 0.8)) * 60
            st.metric("Route", " -> ".join(path))
            st.metric("Distance", f"{dist:.1f} NM")
            st.metric("Est. Flight Time", f"{flight_min:.0f} min")
        else:
            st.warning("No UAM corridor connects these vertiports.")

    if st.button("Submit to ACROSS", type="primary"):
        if not path or len(path) < 2:
            st.error("No route available.")
        else:
            etd = datetime(2024, 6, 15, dep_hour, 0, 0, tzinfo=timezone.utc)
            eta = etd + timedelta(minutes=flight_min)
            origin_pos = VERTIPORTS[origin_vp].position
            dest_pos   = VERTIPORTS[dest_vp].position

            plan = UAMFlightPlan(
                plan_id=f"DEMO-{dep_hour:02d}{origin_vp[:3]}{dest_vp[:3]}",
                vehicle_id="KE-AAM-001",
                origin_id=origin_vp,
                dest_id=dest_vp,
                flight_rules=FlightRules.VFRC,
                etd_utc=etd,
                eta_utc=eta,
                cruise_alt_ft=float(alt_ft),
                trajectory=[
                    Waypoint4D(GeoPoint(origin_pos.lat, origin_pos.lon, float(alt_ft)), etd),
                    Waypoint4D(GeoPoint(dest_pos.lat,   dest_pos.lon,   float(alt_ft)), eta),
                ],
                pax_count=pax_count,
            )
            client = ACROSSClient()
            response = client.submit_plan(plan)

            if response.approved:
                st.success(
                    f"✅ **APPROVED** — Plan ID: {response.plan_id}  \n"
                    f"{response.message}"
                )
                if response.conditions:
                    st.info("Conditions:\n" + "\n".join(f"• {c}" for c in response.conditions))
            else:
                st.error(
                    f"❌ **DENIED** — Plan ID: {response.plan_id}  \n"
                    f"{response.message}"
                )
                for conflict in response.conflicts:
                    st.warning(
                        f"**{conflict.conflict_type.value}**: {conflict.description}"
                    )

    # ── Vertiport info table ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Vertiport Registry")
    st.dataframe(
        vp_df.rename(columns={"id": "ID", "name": "Name", "lat": "Lat", "lon": "Lon", "pads": "Pads"}),
        use_container_width=True,
        hide_index=True,
    )
