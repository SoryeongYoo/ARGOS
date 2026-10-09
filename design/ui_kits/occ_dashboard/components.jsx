/* OCC kit — shared atoms. Exported to window for cross-file use. */
const { useState } = React;

/* Lucide-style 1.5px outline icons (paths lifted from lucide.dev) */
const ICON_PATHS = {
  plane: <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />,
  clock: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>,
  alert: <><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></>,
  check: <path d="M20 6 9 17l-5-5" />,
  close: <><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>,
  play: <polygon points="6 3 20 12 6 21 6 3" />,
  graph: <><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="m8.59 13.51 6.83 3.98" /><path d="m15.41 6.51-6.82 3.98" /></>,
  pin: <><circle cx="12" cy="10" r="3" /><path d="M12 2a8 8 0 0 0-8 8c0 1.892.402 3.13 1.5 4.5L12 22l6.5-7.5c1.098-1.37 1.5-2.608 1.5-4.5a8 8 0 0 0-8-8Z" /></>,
  trend: <><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></>,
  calendar: <><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4" /><path d="M8 2v4" /><path d="M3 10h18" /></>,
  arrowRight: <><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
};

function Icon({ name, size = 16, color = "currentColor", strokeWidth = 1.5, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      style={{ display: "block", flexShrink: 0, ...style }}>
      {ICON_PATHS[name]}
    </svg>
  );
}

function PillButton({ children, variant = "ink", size, disabled, onClick }) {
  const cls = ["pill-btn", variant === "violet" ? "violet" : "", size === "sm" ? "sm" : ""]
    .filter(Boolean).join(" ");
  return <button className={cls} disabled={disabled} onClick={onClick}>{children}</button>;
}

function Badge({ status, children }) {
  return (
    <span className={`badge ${status}`}>
      <span className="dot"></span>{children || status}
    </span>
  );
}

function Feasibility({ level }) {
  return <span className={`feas ${level}`}>{level}</span>;
}

function KPICard({ label, value, meta, trend }) {
  return (
    <div className="kpi">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      {meta && <span className={`meta ${trend || "flat"}`}>{meta}</span>}
    </div>
  );
}

function Surface({ title, children, style, action }) {
  return (
    <div className="surface" style={style}>
      {(title || action) && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          {title && <h2 style={{ margin: 0 }}>{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

function Toast({ title, detail, onDone }) {
  React.useEffect(() => {
    const t = setTimeout(onDone, 4200);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="toast fade-up">
      <span className="check"><Icon name="check" size={18} color="var(--status-ontime)" strokeWidth={2.5} /></span>
      <div className="body">{title}<small>{detail}</small></div>
    </div>
  );
}

Object.assign(window, { Icon, PillButton, Badge, Feasibility, KPICard, Surface, Toast });
