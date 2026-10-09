/* Root app — tab state, sidebar wiring, simulation trigger, approval toast */
const { useState: useStateApp } = React;

function App() {
  const [tab, setTab] = useStateApp("occ");
  const [date, setDate] = useStateApp("2024-06-15");
  const [triggerId, setTriggerId] = useStateApp("f1");
  const [delay, setDelay] = useStateApp(90);
  const [ran, setRan] = useStateApp(false);
  const [scenarios, setScenarios] = useStateApp([]);
  const [toast, setToast] = useStateApp(null);

  const trigger = FLIGHTS.find(f => f.id === triggerId) || FLIGHTS[0];

  const onRun = () => {
    setScenarios(buildScenarios(trigger.num, delay));
    setRan(true);
    setTab("occ");
  };

  const onApprove = (s) => {
    setToast({
      title: `Scenario ${s.id} (${s.enName}) 승인됨`,
      detail: `Action logged · ${s.action}  ·  [Simulation] 실제 운항 영향 없음`,
    });
  };

  return (
    <div className="app">
      <Sidebar
        date={date} setDate={setDate}
        triggerId={triggerId} setTriggerId={setTriggerId}
        delay={delay} setDelay={setDelay}
        onRun={onRun} dbCount={161868}
      />
      <main className="main">
        <div className="app-header">
          <h1>인천 OCC · Operations Control</h1>
          <span className="crumb">{date} · KST 09:42 · live</span>
        </div>

        <div className="tabs">
          <button className={`tab ${tab === "occ" ? "active" : ""}`} onClick={() => setTab("occ")}>OCC Operations</button>
          <button className={`tab ${tab === "uam" ? "active" : ""}`} onClick={() => setTab("uam")}>UAM / ACROSS</button>
        </div>

        {tab === "occ"
          ? <TabOCC ran={ran} trigger={trigger} delay={delay} scenarios={scenarios} onApprove={onApprove} />
          : <TabUAM />}
      </main>

      {toast && <Toast title={toast.title} detail={toast.detail} onDone={() => setToast(null)} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
