/* OCC Operations tab — KPI strip, route map, schedule, simulation, histogram */
const { useState: useStateOcc } = React;

/* Simple equirectangular projection into a 720×300 viewBox.
   Centered/zoomed on East-Asia-to-world so ICN traces read clearly. */
function project(lon, lat) {
  const x = (lon + 180) / 360 * 720;
  const y = (90 - lat) / 180 * 360 - 30; // crop top/bottom band
  return [x, y];
}

function RouteMap({ flights }) {
  const ICN = project(126.4505, 37.4691);
  return (
    <div className="map-frame">
      <svg viewBox="0 0 720 300" width="100%" height="100%" preserveAspectRatio="xMidYMid slice"
        style={{ background: "#EAF1FB" }}>
        {/* graticule */}
        {[...Array(7)].map((_, i) => (
          <line key={"v" + i} x1={i * 120} y1="0" x2={i * 120} y2="300" stroke="#D5E2F2" strokeWidth="1" />
        ))}
        {[...Array(4)].map((_, i) => (
          <line key={"h" + i} x1="0" y1={i * 80} x2="720" y2={i * 80} stroke="#D5E2F2" strokeWidth="1" />
        ))}
        {/* route traces */}
        {flights.map(f => {
          const r = ROUTES.find(r => r.id === f.route);
          if (!r) return null;
          const [x1, y1] = project(r.oLon, r.oLat);
          const [x2, y2] = project(r.dLon, r.dLat);
          // arc control point for a gentle great-circle feel
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - Math.abs(x2 - x1) * 0.12;
          const delayed = f.delay > 15;
          return (
            <path key={f.id} d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`}
              fill="none"
              stroke={delayed ? "var(--status-critical)" : "var(--status-info)"}
              strokeWidth={delayed ? 1.6 : 1.1}
              opacity={delayed ? 0.85 : 0.5} />
          );
        })}
        {/* destination dots */}
        {flights.map(f => {
          const r = ROUTES.find(r => r.id === f.route);
          if (!r) return null;
          const [x, y] = project(r.dLon, r.dLat);
          return <circle key={"d" + f.id} cx={x} cy={y} r="2.4" fill="var(--fg-3)" />;
        })}
        {/* ICN hub star */}
        <g transform={`translate(${ICN[0]} ${ICN[1]})`}>
          <circle r="6" fill="#F5C518" stroke="white" strokeWidth="1.5" />
          <text x="9" y="4" fontSize="11" fontWeight="700" fill="var(--fg-1)"
            fontFamily="var(--font-mono)">ICN</text>
        </g>
      </svg>
    </div>
  );
}

function ScheduleTable({ flights }) {
  return (
    <div className="scroll-y">
      <table className="schedule">
        <thead>
          <tr><th>Flight</th><th>Route</th><th>Dep(KST)</th><th>Delay</th><th>Status</th></tr>
        </thead>
        <tbody>
          {flights.map(f => (
            <tr key={f.id} className={f.status === "CNX" ? "cnx" : f.delay > 15 ? "dly" : ""}>
              <td>{f.num}</td>
              <td>{f.route}</td>
              <td>{f.dep}</td>
              <td>{f.status === "CNX" ? "—" : "+" + String(f.delay).padStart(2, "0")}</td>
              <td><Badge status={f.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Histogram({ data }) {
  const max = Math.max(...data);
  return (
    <div className="hist">
      {data.map((v, i) => (
        <div key={i} className="bar" style={{ height: `${(v / max) * 100}%`, opacity: 0.45 + 0.5 * (v / max) }} />
      ))}
    </div>
  );
}

function SimulationPanel({ ran, trigger, delay, scenarios, onApprove }) {
  if (!ran) {
    return (
      <div className="sim-panel">
        <h2>Delay propagation simulation</h2>
        <div className="sim-empty" style={{ marginTop: 14 }}>
          <Icon name="play" size={22} color="var(--fg-3)" style={{ margin: "0 auto 8px" }} />
          트리거 편을 선택하고 <b>▶ Run simulation</b> 을 눌러 시작하세요.
        </div>
      </div>
    );
  }
  const totalDelay = scenarios[0].residual.delay;
  return (
    <div className="sim-panel">
      <h2>Delay propagation simulation</h2>
      <p style={{ color: "var(--fg-2)", fontSize: 13, marginTop: 2 }}>
        Trigger <b style={{ fontFamily: "var(--font-mono)", color: "var(--fg-1)" }}>{trigger.num}</b> · +{delay} min
      </p>

      <div className="kpi-row" style={{ marginTop: 14, marginBottom: 0, gridTemplateColumns: "repeat(4,1fr)" }}>
        <KPICard label="Cascade depth" value="4" meta="legs affected" />
        <KPICard label="Total delay" value={`${delay * 4}`} meta="min" trend="up" />
        <KPICard label="PAX impacted" value="1,210" meta="+1,210" trend="up" />
        <KPICard label="Trigger delay" value={delay} meta="min" trend="flat" />
      </div>

      <div className="cascade-strip">
        <span style={{ fontWeight: 600, color: "var(--fg-2)" }}>Cascade chain</span>
        {CASCADE_CHAIN.map((leg, i) => (
          <React.Fragment key={leg}>
            <span className="leg">{leg}</span>
            {i < CASCADE_CHAIN.length - 1 && <span className="arrow">→</span>}
          </React.Fragment>
        ))}
      </div>

      <h3 style={{ fontSize: 15, marginTop: 6, marginBottom: 0 }}>Recovery scenarios</h3>
      <div className="scenarios">
        {scenarios.map(s => (
          <div key={s.id} className="scen-card">
            <span className="id">[{s.id}] · {s.enName}</span>
            <span className="name">{s.name}</span>
            <Feasibility level={s.feas} />
            <span className="desc">{s.desc}</span>
            <span className="metrics">
              <span>잔여 <b>{s.residual.legs}</b>편</span>
              <span><b>{s.residual.delay}</b> min</span>
              <span>PAX <b>{s.residual.pax.toLocaleString()}</b></span>
              <span>CI <b>{s.ci.toFixed(2)}</b></span>
            </span>
            <span className="action"><i>Action</i> · {s.action}</span>
            <PillButton size="sm" onClick={() => onApprove(s)}>시나리오 {s.id} 승인</PillButton>
          </div>
        ))}
      </div>
    </div>
  );
}

function TabOCC({ ran, trigger, delay, scenarios, onApprove }) {
  return (
    <div>
      <div className="kpi-row">
        <KPICard label="Total flights" value={KPIS.totalFlights} meta="대비 7일 평균 408" trend="flat" />
        <KPICard label="Delayed > 15m" value={KPIS.delayed} meta={"▲ " + KPIS.delayedDelta} trend="up" />
        <KPICard label="Cancelled" value={KPIS.cancelled} meta="▲ 1" trend="up" />
        <KPICard label="PAX today" value={KPIS.paxToday.toLocaleString()} meta={"▼ " + KPIS.paxDelta.replace("−", "")} trend="down" />
      </div>

      <div className="cols-3-2">
        <Surface title="Route map" style={{ padding: 0 }}>
          <div style={{ padding: "0 0 0 0" }}><RouteMap flights={FLIGHTS} /></div>
        </Surface>
        <Surface title="Departure schedule"><ScheduleTable flights={FLIGHTS} /></Surface>
      </div>

      <div style={{ marginBottom: 18 }}>
        <SimulationPanel ran={ran} trigger={trigger} delay={delay} scenarios={scenarios} onApprove={onApprove} />
      </div>

      <Surface title="Delay distribution"
        action={<span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>n = 161,868 · binned 0–300 min</span>}>
        <Histogram data={DELAY_HIST} />
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--fg-3)", marginTop: 4 }}>
          <span>0</span><span>departure delay (min)</span><span>300</span>
        </div>
      </Surface>
    </div>
  );
}

Object.assign(window, { TabOCC });
