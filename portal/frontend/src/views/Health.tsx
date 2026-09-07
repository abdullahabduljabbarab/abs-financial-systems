import { api, type ServiceHealth } from "../api";
import { Panel, Pill, useAsync } from "../ui";

function detailLine(detail: Record<string, unknown>): string {
  const parts: string[] = [];
  if (typeof detail.database === "string") parts.push(`db ${detail.database}`);
  if (typeof detail.backend === "string") parts.push(`store ${detail.backend}`);
  if (typeof detail.db_latency_ms === "number") parts.push(`${detail.db_latency_ms}ms db`);
  if (typeof detail.error === "string") parts.push(detail.error);
  return parts.join(" · ") || "ok";
}

function ServiceCard({ s }: { s: ServiceHealth }) {
  const width = Math.min(100, (s.latency_ms / 400) * 100);
  return (
    <Panel>
      <div className="svc">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="name">{s.service}</span>
          <Pill kind={s.healthy ? "ok" : "bad"}>{s.healthy ? "healthy" : "down"}</Pill>
        </div>
        <div className="bar">
          <span style={{ width: `${s.healthy ? width : 100}%`, background: s.healthy ? undefined : "var(--red)" }} />
        </div>
        <div className="meta">
          <span>{detailLine(s.detail)}</span>
          <span>{s.status_code ?? "—"} · {s.latency_ms}ms</span>
        </div>
      </div>
    </Panel>
  );
}

export function HealthView() {
  const { data, error, loading } = useAsync(() => api.health(), []);

  return (
    <div>
      <h2 className="view-title">System health</h2>
      <p className="view-note">
        Live liveness of every service, probed through the portal. The portal reads only; a
        service being down here never affects the others.
      </p>
      {loading && <p className="muted">Probing services…</p>}
      {error && <p className="error">Portal error: {error}</p>}
      {data && (
        <div className="grid cols-3">
          {data.services.map((s) => (
            <ServiceCard key={s.service} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}
