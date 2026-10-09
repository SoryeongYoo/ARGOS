/* UAM / ACROSS tab — vertiport network map, ACROSS submission, registry */
const { useState: useStateUam } = React;

/* Project the ICN-region lat/lon box into a 640×440 viewBox. */
function projVP(lon, lat) {
  const lonMin = 126.35, lonMax = 127.20;
  const latMin = 37.18, latMax = 37.62;
  const x = (lon - lonMin) / (lonMax - lonMin) * 640;
  const y = (latMax - lat) / (latMax - latMin) * 440;
  return [x, y];
}

function VertiportMap({ activeRoute }) {
  const icn = projVP(126.4505, 37.4691);
  const routeSet = new Set();
  if (activeRoute && activeRoute.length >= 2) {
    for (let i = 0; i < activeRoute.length - 1; i++) {
      routeSet.add(activeRoute[i] + "|" + activeRoute[i + 1]);
      routeSet.add(activeRoute[i + 1] + "|" + activeRoute[i]);
    }
  }
  return (
    <div className="uam-map-frame">
      <div className="uam-legend">
        <div><span className="swatch" style={{ background: "#9AA3AE" }}></span>CTR 회피 코리도</div>
        <div><span className="swatch" style={{ background: "var(--module-uam)" }}></span>CTR 통과 (ATC 협조)</div>
        <div><span className="swatch" style={{ background: "var(--status-critical)", borderTop: "1.5px dashed" }}></span>ICN CTR 5 NM</div>
      </div>
      <svg viewBox="0 0 640 440" width="100%" height="100%" preserveAspectRatio="xMidYMid slice"
        style={{ background: "#EAF4F4" }}>
        {/* faint land texture grid */}
        {[...Array(9)].map((_, i) => <line key={"gx" + i} x1={i * 80} y1="0" x2={i * 80} y2="440" stroke="#D8E8E6" strokeWidth="1" />)}
        {[...Array(6)].map((_, i) => <line key={"gy" + i} x1="0" y1={i * 80} x2="640" y2={i * 80} stroke="#D8E8E6" strokeWidth="1" />)}

        {/* ICN CTR ring (5 NM) */}
        <circle cx={icn[0]} cy={icn[1]} r="58" fill="none" stroke="var(--status-critical)" strokeWidth="1.4" strokeDasharray="4 4" opacity="0.7" />

        {/* corridors */}
        {CORRIDORS.map((c, i) => {
          const a = VERTIPORTS.find(v => v.id === c.from);
          const b = VERTIPORTS.find(v => v.id === c.to);
          const [x1, y1] = projVP(a.lon, a.lat);
          const [x2, y2] = projVP(b.lon, b.lat);
          const onRoute = routeSet.has(c.from + "|" + c.to);
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={onRoute ? "var(--argos-violet-500)" : (c.avoidsCTR ? "#9AA3AE" : "var(--module-uam)")}
              strokeWidth={onRoute ? 3.4 : 2}
              opacity={onRoute ? 1 : 0.8} />
          );
        })}

        {/* vertiports */}
        {VERTIPORTS.map(v => {
          const [x, y] = projVP(v.lon, v.lat);
          const onR = activeRoute && activeRoute.includes(v.id);
          return (
            <g key={v.id} transform={`translate(${x} ${y})`}>
              <circle r={onR ? 8 : 6} fill={onR ? "var(--argos-violet-500)" : "var(--status-info)"} stroke="white" strokeWidth="2" />
              <text x="10" y="-6" fontSize="11" fontWeight="700" fontFamily="var(--font-mono)" fill="var(--fg-1)">{v.id}</text>
              <text x="10" y="7" fontSize="9.5" fontFamily="var(--font-sans)" fill="var(--fg-2)">{v.nameKo}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* Tiny graph routing: BFS over CORRIDORS */
function findRoute(from, to) {
  if (from === to) return null;
  const adj = {};
  CORRIDORS.forEach(c => {
    (adj[c.from] = adj[c.from] || []).push({ to: c.to, nm: c.nm });
    (adj[c.to] = adj[c.to] || []).push({ to: c.from, nm: c.nm });
  });
  const q = [[from]], seen = new Set([from]);
  while (q.length) {
    const path = q.shift();
    const last = path[path.length - 1];
    if (last === to) return path;
    for (const e of (adj[last] || [])) {
      if (!seen.has(e.to)) { seen.add(e.to); q.push([...path, e.to]); }
    }
  }
  return null;
}
function routeDistance(path) {
  if (!path) return 0;
  let d = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const c = CORRIDORS.find(c =>
      (c.from === path[i] && c.to === path[i + 1]) || (c.to === path[i] && c.from === path[i + 1]));
    if (c) d += c.nm;
  }
  return d;
}

function TabUAM({ onSubmit }) {
  const [origin, setOrigin] = useStateUam("ICN-T1");
  const [dest, setDest] = useStateUam("GMP");
  const [depHour, setDepHour] = useStateUam(3);
  const [alt, setAlt] = useStateUam(800);
  const [pax, setPax] = useStateUam(2);
  const [result, setResult] = useStateUam(null);

  const path = findRoute(origin, dest);
  const dist = routeDistance(path);
  const flightMin = path ? Math.round((dist / (120 * 0.8)) * 60) : 0;

  const submit = () => {
    if (!path) { setResult({ ok: false, msg: "연결된 UAM 코리도가 없습니다.", id: "—" }); return; }
    const crossesCTR = path.some((id, i) => {
      if (i === 0) return false;
      const c = CORRIDORS.find(c =>
        (c.from === path[i - 1] && c.to === id) || (c.to === path[i - 1] && c.from === id));
      return c && !c.avoidsCTR;
    });
    const id = `DEMO-${String(depHour).padStart(2, "0")}${origin.slice(0, 3)}${dest.slice(0, 3)}`;
    if (crossesCTR) {
      setResult({ ok: false, msg: "ICN CTR 통과 구간 포함 — ATC 사전 협조 미승인.", id, cond: ["경로를 CTR 회피 코리도로 재설정", "또는 ICN TWR 슬롯 예약 후 재제출"] });
    } else {
      setResult({ ok: true, msg: "VFRC 규칙 · 회랑 분리 충족 · 충돌 없음.", id, cond: [`순항 ${alt} ft AGL 유지`, `ETD ${String(depHour).padStart(2, "0")}:00 UTC ±5 min`] });
    }
    onSubmit && onSubmit(result);
  };

  return (
    <div>
      <h2 style={{ fontSize: 18, marginBottom: 4 }}>UAM vertiport network — ICN 허브 권역</h2>
      <p style={{ color: "var(--fg-2)", fontSize: 13, marginBottom: 14 }}>
        승인된 회랑(corridor) 그래프. 회색은 ICN CTR 회피, 주황은 CTR 경계 통과 — ATC 협조 필요.
      </p>

      <div className="uam-grid">
        <VertiportMap activeRoute={path} />

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="across-card">
            <h3>ACROSS flight plan</h3>
            <div className="field">
              <label>Origin vertiport</label>
              <select className="input mono" value={origin} onChange={e => { setOrigin(e.target.value); setResult(null); }}>
                {VERTIPORTS.map(v => <option key={v.id} value={v.id}>{v.id} · {v.nameKo}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Destination vertiport</label>
              <select className="input mono" value={dest} onChange={e => { setDest(e.target.value); setResult(null); }}>
                {VERTIPORTS.map(v => <option key={v.id} value={v.id}>{v.id} · {v.nameKo}</option>)}
              </select>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="field">
                <label>Dep hour (UTC) · {String(depHour).padStart(2, "0")}:00</label>
                <input type="range" min="0" max="23" value={depHour} onChange={e => setDepHour(+e.target.value)} />
              </div>
              <div className="field">
                <label>Cruise · {alt} ft</label>
                <input type="range" min="300" max="1500" step="100" value={alt} onChange={e => setAlt(+e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>PAX · {pax}</label>
              <input type="range" min="1" max="4" value={pax} onChange={e => setPax(+e.target.value)} />
            </div>

            <div style={{ display: "flex", gap: 16, padding: "10px 0", borderTop: "1px dashed var(--border-2)", borderBottom: "1px dashed var(--border-2)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              <div><div style={{ color: "var(--fg-3)", fontSize: 10 }}>ROUTE</div>{path ? path.join(" → ") : "—"}</div>
            </div>
            <div style={{ display: "flex", gap: 18, fontFamily: "var(--font-mono)", fontSize: 12 }}>
              <div><div style={{ color: "var(--fg-3)", fontSize: 10 }}>DIST</div><b>{dist.toFixed(1)}</b> NM</div>
              <div><div style={{ color: "var(--fg-3)", fontSize: 10 }}>EST TIME</div><b>{flightMin}</b> min</div>
              <div><div style={{ color: "var(--fg-3)", fontSize: 10 }}>RULES</div>VFRC</div>
            </div>

            <PillButton variant="violet" onClick={submit}>
              <Icon name="plane" size={14} color="white" /> Submit to ACROSS
            </PillButton>

            {result && (
              <div className={`across-result ${result.ok ? "ok" : "err"} fade-up`}>
                <b>{result.ok ? "✅ APPROVED" : "❌ DENIED"}</b> · Plan {result.id}<br />
                {result.msg}
                {result.cond && (
                  <ul style={{ margin: "6px 0 0", paddingLeft: 16 }}>
                    {result.cond.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 18 }}>
        <Surface title="Vertiport registry">
          <table className="vp-table">
            <thead><tr><th>ID</th><th>Name</th><th>Lat</th><th>Lon</th><th>Pads</th></tr></thead>
            <tbody>
              {VERTIPORTS.map(v => (
                <tr key={v.id}>
                  <td>{v.id}</td><td style={{ fontFamily: "var(--font-sans)" }}>{v.nameKo}</td>
                  <td>{v.lat.toFixed(4)}</td><td>{v.lon.toFixed(4)}</td><td>{v.pads}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Surface>
      </div>
    </div>
  );
}

Object.assign(window, { TabUAM });
