import { api, type ServiceHealth } from "../api";
import { Panel, Pill, useAsync } from "../ui";

interface Meta {
  role: string;
  desc: string;
  tech: string;
  stream: string;
}

const META: Record<string, Meta> = {
  "ledger-api": { role: "Authoritative financial state", desc: "Double-entry ledger, tamper-evident chain", tech: "PostgreSQL · Cloud SQL", stream: "transaction-events" },
  "payment-orchestrator": { role: "Payment lifecycle authority", desc: "Risk → reserve → provider → capture", tech: "PostgreSQL · Cloud SQL", stream: "payment-events" },
  "risk-engine": { role: "Deterministic decision engine", desc: "Weighted rules, replayable, explainable", tech: "PostgreSQL · Cloud SQL", stream: "risk-events" },
  "notification-service": { role: "Strict downstream sink", desc: "Email + SMS fan-out, no outbound path", tech: "PostgreSQL · Cloud SQL", stream: "consumes payment · risk" },
  "analytics-service": { role: "Deterministic read model", desc: "Event-sourced CQRS projections", tech: "BigQuery", stream: "consumes all streams" },
};

function dbState(detail: Record<string, unknown>): string {
  if (typeof detail.database === "string") return `db ${detail.database}`;
  if (typeof detail.backend === "string") return `store ${detail.backend}`;
  if (typeof detail.error === "string") return String(detail.error);
  return "—";
}

function ServiceCard({ s }: { s: ServiceHealth }) {
  const m = META[s.service];
  return (
    <Panel>
      <div className="svc">
        <div className="top">
          <div>
            <div className="name">{s.service}</div>
            {m && <div className="role">{m.role}</div>}
          </div>
          <Pill kind={s.healthy ? "ok" : "bad"}>{s.healthy ? "healthy" : "down"}</Pill>
        </div>
        {m && <div className="desc">{m.desc}</div>}
        {m && (
          <div className="chips">
            <span className="chip">{m.tech}</span>
            <span className="chip topic">{m.stream}</span>
          </div>
        )}
        <div className="foot">
          <span>{dbState(s.detail)}</span>
          <span><b>{s.status_code ?? "—"}</b> · {s.latency_ms}ms</span>
        </div>
      </div>
    </Panel>
  );
}

export function HealthView() {
  const { data, error, loading } = useAsync(() => api.health(), []);
  const healthy = data ? data.services.filter((s) => s.healthy).length : 0;
  const total = data ? data.services.length : 5;

  return (
    <div>
      <section className="hero">
        <div className="eyebrow">A · B · S Financial Systems</div>
        <div className="lede">
          One <span className="accent">ledger</span>. Explicit <span className="gold">ownership</span>. Evidence under failure.
        </div>
        <div className="facts">
          <span><b>5</b> services</span><span className="sep">·</span>
          <span><b>3</b> event streams</span><span className="sep">·</span>
          <span><b>europe-west2</b></span><span className="sep">·</span>
          <span>read-only portal</span>
        </div>
      </section>

      <div className="pstate">
        <div className="cell">
          <span className={`big ${healthy === total ? "ok" : "teal"}`}>{healthy} / {total}</span>
          <span className="lbl">services healthy</span>
        </div>
        <div className="cell">
          <span className="big teal">ledger-api</span>
          <span className="lbl">authoritative state</span>
        </div>
        <div className="cell">
          <span className="big">Pub/Sub</span>
          <span className="lbl">event backbone</span>
        </div>
        <div className="cell">
          <span className="big">europe-west2</span>
          <span className="lbl">region · Cloud Run</span>
        </div>
      </div>

      <h2 className="view-title">System health</h2>
      <p className="view-note">
        Live liveness of every service, probed through the portal. The portal reads only; a
        service being down here never affects the others.
      </p>
      {loading && <p className="muted">Probing services…</p>}
      {error && <p className="error">Portal error: {error}</p>}
      {data && (
        <div className="grid auto">
          {data.services.map((s) => (
            <ServiceCard key={s.service} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}
