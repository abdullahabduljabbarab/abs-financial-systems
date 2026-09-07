import { useState } from "react";
import { api } from "./api";
import { Pill, useAsync } from "./ui";
import { HealthView } from "./views/Health";
import { TraceView } from "./views/Trace";
import { VerificationView } from "./views/Verification";
import { AnalyticsView } from "./views/Analytics";

type Tab = "health" | "trace" | "verification" | "analytics";

const TABS: { id: Tab; label: string }[] = [
  { id: "health", label: "System" },
  { id: "trace", label: "Payment Trace" },
  { id: "verification", label: "Verification" },
  { id: "analytics", label: "Analytics" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("health");
  const health = useAsync(() => api.health(), []);

  return (
    <div className="app">
      <header className="masthead">
        <div className="mark">
          <span className="abs">A<b>·</b>B<b>·</b>S</span>
          <span className="title">Engineering Portal</span>
        </div>
        <span className="sub">read-only observation surface</span>
        <span className="spacer" />
        {health.loading ? (
          <Pill kind="neutral">probing</Pill>
        ) : health.error ? (
          <Pill kind="bad">portal error</Pill>
        ) : health.data?.healthy ? (
          <Pill kind="ok">all systems nominal</Pill>
        ) : (
          <Pill kind="warn">degraded</Pill>
        )}
      </header>

      <nav className="nav">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "health" && <HealthView />}
      {tab === "trace" && <TraceView />}
      {tab === "verification" && <VerificationView />}
      {tab === "analytics" && <AnalyticsView />}
    </div>
  );
}
