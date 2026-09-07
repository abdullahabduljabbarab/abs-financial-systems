import { api } from "../api";
import { Panel, useAsync } from "../ui";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "accent" | "gold" }) {
  return (
    <Panel>
      <div className="stat">
        <span className={`value ${tone ?? ""}`}>{value}</span>
        <span className="label">{label}</span>
      </div>
    </Panel>
  );
}

export function AnalyticsView() {
  const { data, error, loading } = useAsync(() => api.analytics("overview"), []);

  const wm = (data?.watermark ?? {}) as { raw_event_count?: number; as_of?: string };
  const ov = (data?.overview ?? {}) as Record<string, unknown>;
  const num = (k: string) => (ov[k] === undefined ? "—" : String(ov[k]));
  const pct = (k: string) => (ov[k] === undefined ? "—" : `${(Number(ov[k]) * 100).toFixed(1)}%`);

  return (
    <div>
      <h2 className="view-title">Analytics</h2>
      <p className="view-note">
        The event-sourced read model. Every figure is materialized from raw history; the
        watermark shows exactly which events it reflects.
      </p>
      {loading && <p className="muted">Loading projections…</p>}
      {error && <p className="error">Error: {error}</p>}
      {data && (
        <>
          <p className="muted mono" style={{ fontSize: 12, marginBottom: 16 }}>
            watermark · {wm.raw_event_count ?? "—"} raw events · as of {wm.as_of ?? "—"}
          </p>
          <p className="section-title">Payments</p>
          <div className="grid cols-3" style={{ marginBottom: 18 }}>
            <Stat label="payments" value={num("payments")} tone="accent" />
            <Stat label="settled" value={num("settled")} />
            <Stat label="settlement rate" value={pct("settlement_success_rate")} tone="gold" />
            <Stat label="failed" value={num("failed")} />
            <Stat label="rejected" value={num("rejected")} />
            <Stat label="total value" value={num("total_value")} tone="accent" />
          </div>
          <p className="section-title">Risk</p>
          <div className="grid cols-3">
            <Stat label="allow" value={num("risk_allow")} />
            <Stat label="review" value={num("risk_review")} />
            <Stat label="block" value={num("risk_block")} />
            <Stat label="avg risk score" value={num("average_risk_score")} tone="gold" />
            <Stat label="provider failures" value={num("provider_failures")} />
            <Stat label="events ingested" value={num("events")} tone="accent" />
          </div>
        </>
      )}
    </div>
  );
}
