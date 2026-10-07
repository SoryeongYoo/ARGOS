/* Sidebar — operating date, trigger flight combo, delay slider, run CTA */
const { useState: useStateSb } = React;

function Sidebar({ date, setDate, triggerId, setTriggerId, delay, setDelay, onRun, dbCount }) {
  // cascade candidates = flights whose registration appears >= 2 times
  const regCount = {};
  FLIGHTS.forEach(f => { regCount[f.reg] = (regCount[f.reg] || 0) + 1; });
  const candidates = FLIGHTS.filter(f => regCount[f.reg] >= 1); // demo: show all

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src={(window.__resources && window.__resources.glyph) || "../../assets/argos-glyph.svg"} width="36" height="36" alt="ARGOS" />
        <div>
          <div className="name">ARGOS OCC</div>
          <div className="tag">Route &amp; Ground Ops</div>
        </div>
      </div>

      <div className="sb-section">
        <h3>Operating date</h3>
        <div className="field">
          <input className="input mono" type="date" value={date}
            min="2022-01-01" max="2024-12-31"
            onChange={e => setDate(e.target.value)} />
          <span className="helper">데이터셋 범위 2022–2024 · UTC 기준</span>
        </div>
      </div>

      <div className="sb-section">
        <h3>Simulate delay</h3>
        <div className="field">
          <label>Trigger flight</label>
          <select className="input mono" value={triggerId}
            onChange={e => setTriggerId(e.target.value)}>
            {candidates.map(f => (
              <option key={f.id} value={f.id}>
                {f.num}  {f.route}  ({f.dep} KST)
              </option>
            ))}
          </select>
          <span className="helper">기재 회전이 있는 편만 표시</span>
        </div>
        <div className="field">
          <label>Departure delay · <span className="mono" style={{ color: "var(--fg-1)" }}>{delay} min</span></label>
          <input type="range" min="15" max="300" step="15" value={delay}
            onChange={e => setDelay(+e.target.value)} />
          <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--fg-3)" }}>
            <span>15</span><span>300</span>
          </div>
        </div>
        <PillButton onClick={onRun}>
          <Icon name="play" size={14} color="white" /> Run simulation
        </PillButton>
      </div>

      <div className="sidebar-footer">DB: {dbCount.toLocaleString()} flights loaded</div>
    </aside>
  );
}

Object.assign(window, { Sidebar });
