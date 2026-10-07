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

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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

_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = str((_ROOT / "data" / "db" / "argos.duckdb").resolve())
KST = timezone(timedelta(hours=9))

# Static airport lat/lon for route map rendering (routes table has no geo columns)
AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    "ICN": (37.4691, 126.4505),
    "AKL": (-37.0082, 174.7917),
    "ALA": (43.3521, 77.0405),
    "AMS": (52.3086, 4.7639),
    "ATL": (33.6367, -84.4281),
    "AUH": (24.4330, 54.6511),
    "BKK": (13.6900, 100.7501),
    "BOM": (19.0896, 72.8656),
    "CAN": (23.3924, 113.2988),
    "CDG": (49.0097, 2.5479),
    "CGK": (-6.1256, 106.6558),
    "CMB": (7.1808, 79.8841),
    "CSX": (28.1892, 113.2200),
    "CTS": (42.7752, 141.6922),
    "CTU": (30.5785, 103.9470),
    "DEL": (28.5665, 77.1031),
    "DLC": (38.9657, 121.5386),
    "DOH": (25.2732, 51.6080),
    "DPS": (-8.7482, 115.1670),
    "DXB": (25.2532, 55.3657),
    "FCO": (41.8003, 12.2389),
    "FRA": (50.0379, 8.5622),
    "FUK": (33.5853, 130.4511),
    "HGH": (30.2295, 120.4341),
    "HIJ": (34.4361, 132.9194),
    "HND": (35.5494, 139.7798),
    "HNL": (21.3245, -157.9251),
    "JFK": (40.6413, -73.7781),
    "JNB": (-26.1367, 28.2411),
    "KIX": (34.4347, 135.2440),
    "KOJ": (31.8034, 130.7186),
    "KUL": (2.7456, 101.7072),
    "LAX": (33.9425, -118.4081),
    "LHR": (51.4700, -0.4543),
    "MAD": (40.4936, -3.5670),
    "MEL": (-37.6733, 144.8430),
    "MNL": (14.5086, 121.0197),
    "NGO": (34.8583, 136.8053),
    "NRT": (35.7720, 140.3929),
    "OKA": (26.1958, 127.6461),
    "ORD": (41.9742, -87.9073),
    "PEK": (40.0801, 116.5846),
    "PVG": (31.1443, 121.8083),
    "RGN": (16.9073, 96.1332),
    "RUH": (24.9576, 46.6988),
    "SDJ": (38.1397, 140.9169),
    "SEA": (47.4502, -122.3088),
    "SFO": (37.6213, -122.3790),
    "SGN": (10.8188, 106.6520),
    "SHA": (31.1980, 121.3360),
    "SIN": (1.3644, 103.9915),
    "SVO": (55.9726, 37.4146),
    "SYD": (-33.9399, 151.1753),
    "SZX": (22.6393, 113.8107),
    "ULN": (47.8431, 106.7669),
    "VIE": (48.1103, 16.5697),
    "VVO": (43.3989, 132.1483),
    "XIY": (34.4471, 108.7516),
    "YVR": (49.1947, -123.1792),
    "YYZ": (43.6777, -79.6248),
    "ZRH": (47.4647, 8.5492),
}

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
    day_end = day_start + timedelta(days=1)

    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute(
            """
            SELECT f.flight_id, f.flight_number, f.route_id,
                   f.origin_iata, f.dest_iata,
                   f.aircraft_registration, f.aircraft_type,
                   f.scheduled_dep_utc, f.scheduled_arr_utc,
                   f.block_time_minutes, f.dep_delay_minutes,
                   COALESCE(f.pax_boarded, 0) AS pax_boarded,
                   f.status
            FROM flights f
            WHERE f.scheduled_dep_utc >= ? AND f.scheduled_dep_utc < ?
            ORDER BY f.scheduled_dep_utc
        """,
            [day_start, day_end],
        ).df()
    finally:
        con.close()

    df["scheduled_dep_utc"] = pd.to_datetime(df["scheduled_dep_utc"], utc=True)
    df["dep_kst"] = df["scheduled_dep_utc"].dt.tz_convert("Asia/Seoul")
    df["origin_lat"] = df["origin_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[0])
    df["origin_lon"] = df["origin_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[1])
    df["dest_lat"] = df["dest_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[0])
    df["dest_lon"] = df["dest_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[1])
    return df


@st.cache_data(ttl=300)
def load_routes_latlon() -> pd.DataFrame:
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        df = con.execute("SELECT route_id, origin_iata, dest_iata FROM routes").df()
    finally:
        con.close()
    df["origin_lat"] = df["origin_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[0])
    df["origin_lon"] = df["origin_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[1])
    df["dest_lat"] = df["dest_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[0])
    df["dest_lon"] = df["dest_iata"].map(lambda x: AIRPORT_COORDS.get(x, (0.0, 0.0))[1])
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
    st.caption("항공 노선 및 지상 운항 관제 시스템")
    st.divider()

    dep_date = st.date_input(
        "운항 날짜",
        value=date(2024, 6, 15),
        min_value=date(2022, 1, 1),
        max_value=date(2024, 12, 31),
    )

    st.subheader("지연 시뮬레이션")
    flights_df = load_flights_for_day(str(dep_date))

    if flights_df.empty:
        st.warning("해당 날짜에 항공편이 없습니다.")
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
        "트리거 항공편",
        range(len(flight_labels)),
        format_func=lambda i: flight_labels[i],
    )
    selected_flight_id = flight_ids[selected_idx]

    delay_min = st.slider("출발 지연 (분)", 15, 300, 90, step=15)

    run_sim = st.button("▶ 시뮬레이션 실행", type="primary", use_container_width=True)
    st.divider()
    st.caption(f"DB: {flights_df.shape[0]:,}편 로드됨")


# ── Main tabs ─────────────────────────────────────────────────────────────────

tab_occ, tab_uam = st.tabs(["OCC 운항 관제", "UAM / ACROSS"])

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
    k1.metric("총 항공편", f"{total_flights:,}")
    k2.metric(
        "지연 (>15분)",
        f"{delayed:,}",
        delta=f"{delayed / total_flights:.1%}",
        delta_color="inverse",
    )
    k3.metric("결항", f"{cancelled:,}", delta_color="inverse")
    k4.metric("오늘 탑승객", f"{total_pax:,}")

    st.divider()

    # ── Flight map + schedule ──────────────────────────────────────────────────
    map_col, sched_col = st.columns([3, 2])

    with map_col:
        st.subheader("노선 지도")
        sample = flights_df.head(300)  # limit for rendering speed
        fig_map = go.Figure()
        for _, row in sample.iterrows():
            color = "red" if row["dep_delay_minutes"] > 15 else "#1f77b4"
            fig_map.add_trace(
                go.Scattergeo(
                    lon=[row["origin_lon"], row["dest_lon"]],
                    lat=[row["origin_lat"], row["dest_lat"]],
                    mode="lines",
                    line=dict(width=1, color=color),
                    opacity=0.5,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        fig_map.add_trace(
            go.Scattergeo(
                lon=[126.4505],
                lat=[37.4691],
                mode="markers+text",
                marker=dict(size=12, color="gold", symbol="star"),
                text=["ICN"],
                textposition="top center",
                showlegend=False,
            )
        )
        fig_map.update_geos(
            projection_type="natural earth",
            showcountries=True,
            countrycolor="lightgray",
            showland=True,
            landcolor="#f5f5f5",
            showocean=True,
            oceancolor="aliceblue",
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
        st.subheader("출발 스케줄")
        sched_display = flights_df[
            ["flight_number", "route_id", "dep_kst", "dep_delay_minutes", "status"]
        ].copy()
        sched_display["dep_kst"] = sched_display["dep_kst"].dt.strftime("%H:%M")
        sched_display.columns = ["항공편", "노선", "출발(KST)", "지연(분)", "상태"]
        sched_display = sched_display.head(20)

        def _color_row(row):
            if row["상태"] == "CNX":
                return ["background-color: #ffcccc"] * len(row)
            if row["지연(분)"] > 15:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            sched_display.style.apply(_color_row, axis=1),
            use_container_width=True,
            height=340,
        )

    # ── Simulation results ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("지연 전파 시뮬레이션")

    if run_sim or "sim_result" in st.session_state:
        if run_sim:
            with st.spinner("지연 전파 계산 중..."):
                result, scenarios, G, all_flights = run_propagation(
                    selected_flight_id, delay_min, dep_date
                )
            st.session_state["sim_result"] = result
            st.session_state["sim_scenarios"] = scenarios
            st.session_state["sim_flight_id"] = selected_flight_id
            st.session_state["sim_delay"] = delay_min

        result = st.session_state["sim_result"]
        scenarios = st.session_state["sim_scenarios"]

        # Cascade summary
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("연쇄 깊이", result.cascade_depth)
        c2.metric("총 지연", f"{result.total_delay_minutes}분")
        c3.metric("영향 탑승객", f"{result.total_pax_impacted:,}")
        c4.metric("트리거 지연", f"{result.initial_delay_minutes}분")

        # Cascade chain
        if result.cascade_chain:
            st.markdown(
                "**연쇄 체인:** "
                + " → ".join(result.cascade_chain[:6])
                + ("…" if len(result.cascade_chain) > 6 else "")
            )

        # Scenario cards
        st.markdown("### 회복 시나리오")
        scen_cols = st.columns(3)
        feasibility_color = {"HIGH": "green", "MEDIUM": "orange", "LOW": "red"}
        for i, s in enumerate(scenarios):
            with scen_cols[i]:
                fc = feasibility_color.get(s.feasibility, "gray")
                st.markdown(
                    f"**[{s.scenario_id}] {s.name}**  \n"
                    f":{fc}[{s.feasibility}]  |  Cost index: {s.cost_index:.1f}  \n"
                    f"{s.description}  \n"
                    f"*조치:* {s.action_required}  \n"
                    f"잔류: {s.residual.cascade_depth}편, "
                    f"{s.residual.total_delay_minutes}분, "
                    f"{s.residual.total_pax_impacted}명"
                )
                if st.button(f"시나리오 {s.scenario_id} 승인", key=f"approve_{i}"):
                    st.success(
                        f"✅ 시나리오 {s.scenario_id} 승인됨  \n"
                        f"조치 기록됨: {s.action_required}  \n"
                        "**[시뮬레이션]** 실제 운항에는 영향 없음."
                    )
    else:
        st.info("트리거 항공편을 선택하고 **▶ 시뮬레이션 실행**을 클릭하세요.")

    # ── Delay histogram ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("지연 분포")
    delayed_df = flights_df[flights_df["dep_delay_minutes"] > 0]
    if not delayed_df.empty:
        fig_hist = px.histogram(
            delayed_df,
            x="dep_delay_minutes",
            nbins=40,
            labels={"dep_delay_minutes": "출발 지연 (분)"},
            color_discrete_sequence=["#1f77b4"],
        )
        fig_hist.update_layout(height=250, margin=dict(t=10))
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("해당 날짜에 지연 항공편이 없습니다.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: UAM / ACROSS
# ══════════════════════════════════════════════════════════════════════════════
with tab_uam:
    st.subheader("UAM 버티포트 네트워크 — 인천 허브 권역")

    G_uam = build_uam_network()

    # Vertiport map
    vp_data = []
    for vid, vp in VERTIPORTS.items():
        vp_data.append(
            {
                "id": vid,
                "name": vp.name_en,
                "lat": vp.position.lat,
                "lon": vp.position.lon,
                "pads": vp.pad_count,
            }
        )
    vp_df = pd.DataFrame(vp_data)

    fig_uam = go.Figure()

    # Draw corridors
    for u, v, data in G_uam.edges(data=True):
        vp_u = VERTIPORTS[u]
        vp_v = VERTIPORTS[v]
        color = "#aaa" if data["corridor"].avoids_icn_ctr else "#e07b39"
        fig_uam.add_trace(
            go.Scattermapbox(
                lon=[vp_u.position.lon, vp_v.position.lon],
                lat=[vp_u.position.lat, vp_v.position.lat],
                mode="lines",
                line=dict(width=2, color=color),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Draw vertiports
    fig_uam.add_trace(
        go.Scattermapbox(
            lon=vp_df["lon"],
            lat=vp_df["lat"],
            mode="markers+text",
            marker=dict(size=14, color="#1f77b4"),
            text=vp_df["id"],
            textposition="top right",
            hovertext=vp_df.apply(lambda r: f"{r['id']}: {r['name']}<br>패드: {r['pads']}", axis=1),
            hoverinfo="text",
            showlegend=False,
        )
    )

    # ICN CTR circle (approximate — 5 NM radius markers)
    import math

    ctr_lats, ctr_lons = [], []
    for deg in range(0, 361, 10):
        rad = math.radians(deg)
        dlat = (5 / 60) * math.cos(rad)
        dlon = (5 / 60) * math.sin(rad) / math.cos(math.radians(37.47))
        ctr_lats.append(37.4691 + dlat)
        ctr_lons.append(126.4505 + dlon)
    fig_uam.add_trace(
        go.Scattermapbox(
            lon=ctr_lons,
            lat=ctr_lats,
            mode="lines",
            line=dict(width=1.5, color="red"),
            name="ICN CTR (5 NM)",
            showlegend=True,
        )
    )

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
        "회색 회랑은 ICN CTR을 우회합니다.  "
        "주황색 회랑은 CTR 경계를 통과합니다 (ATC 협조 필요).  "
        "빨간 원 = ICN CTR 5 NM 경계."
    )

    # ── ACROSS flight plan demo ────────────────────────────────────────────────
    st.divider()
    st.subheader("ACROSS 비행 계획 제출")

    col_a, col_b = st.columns(2)
    with col_a:
        origin_vp = st.selectbox("출발 버티포트", list(VERTIPORTS.keys()), index=0)
        dest_vp = st.selectbox("도착 버티포트", list(VERTIPORTS.keys()), index=3)
        dep_hour = st.slider("출발 시각 (UTC)", 0, 23, 3)
        alt_ft = st.slider("순항 고도 (ft AGL)", 300, 1500, 800, step=100)
        pax_count = st.slider("탑승객 수", 1, 4, 2)

    with col_b:
        G_route = build_uam_network()
        path = find_route(G_route, origin_vp, dest_vp)
        flight_min = 0.0

        if path and len(path) >= 2:
            from argos.uav.network import route_distance_nm

            dist = route_distance_nm(G_route, path)
            flight_min = (dist / (120 * 0.8)) * 60
            st.metric("경로", " -> ".join(path))
            st.metric("거리", f"{dist:.1f} NM")
            st.metric("예상 비행 시간", f"{flight_min:.0f}분")
        else:
            st.warning("연결되는 UAM 회랑이 없습니다.")

    if st.button("ACROSS에 제출", type="primary"):
        if not path or len(path) < 2:
            st.error("이용 가능한 경로가 없습니다.")
        else:
            etd = datetime(2024, 6, 15, dep_hour, 0, 0, tzinfo=timezone.utc)
            eta = etd + timedelta(minutes=flight_min)
            origin_pos = VERTIPORTS[origin_vp].position
            dest_pos = VERTIPORTS[dest_vp].position

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
                    Waypoint4D(GeoPoint(dest_pos.lat, dest_pos.lon, float(alt_ft)), eta),
                ],
                pax_count=pax_count,
            )
            client = ACROSSClient()
            response = client.submit_plan(plan)

            if response.approved:
                st.success(f"✅ **승인됨** — 계획 ID: {response.plan_id}  \n{response.message}")
                if response.conditions:
                    st.info("조건:\n" + "\n".join(f"• {c}" for c in response.conditions))
            else:
                st.error(f"❌ **거부됨** — 계획 ID: {response.plan_id}  \n{response.message}")
                for conflict in response.conflicts:
                    st.warning(f"**{conflict.conflict_type.value}**: {conflict.description}")

    # ── Vertiport info table ───────────────────────────────────────────────────
    st.divider()
    st.subheader("버티포트 목록")
    st.dataframe(
        vp_df.rename(
            columns={"id": "ID", "name": "이름", "lat": "위도", "lon": "경도", "pads": "패드 수"}
        ),
        use_container_width=True,
        hide_index=True,
    )
