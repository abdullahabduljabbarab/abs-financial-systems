import { api } from "../api";
import { AreaChart } from "../chart";
import { Panel, useAsync } from "../ui";

function Stat({ label, value, tone, big }: { label: string; value: string; tone?: string; big?: boolean }) {
  return (
    <Panel>
      <div className={`stat ${big ? "big" : ""}`}>
        <span className={`value ${tone ?? ""}`}>{value}</span>
        <span className="label">{label}</span>
      </div>
    </Panel>
  );
}

function Bars({ rows }: { rows: { k: string; n: number; fill: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  return (
    <div className="bars">
      {rows.map((r) => (
        <div className="row" key={r.k}>
          <span className="k">{r.k}</span>
          <span className="track"><span className={r.fill} style={{ width: `${(r.n / max) * 100}%` }} /></span>
          <span className="n">{r.n}</span>
        </div>
      ))}
    </div>
  );
}

interface Bucket { date: string; payments: number; settled: number; value: string; }

export function AnalyticsView() {
  const { data, error, loading } = useAsync(() => api.analytics("overview"), []);
  const series = useAsync(() => api.analytics("timeseries"), []);
  const buckets = (series.data?.timeseries ?? []) as Bucket[];
  const wm = (data?.watermark ?? {}) as { raw_event_count?: number; as_of?: string };
  const ov = (data?.overview ?? {}) as Record<string, unknown>;
  const n = (k: string) => Number(ov[k] ?? 0);
  const s = (k: string) => (ov[k] === undefined ? "—" : String(ov[k]));
  const rate = ov["settlement_success_rate"] === undefined ? "—" : `${(n("settlement_success_rate") * 100).toFixed(1)}%`;

  return (
    <div>
      <h2 className="view-title">Analytics</h2>
      <p className="view-note">
        The event-sourced read model. Every figure is materialized deterministically from raw
        history; the watermark shows exactly which events it reflects.
      </p>
      {loading && <p className="muted">Loading projections…</p>}
      {error && <p className="error">Error: {error}</p>}
      {data && (
        <>
          <div className="watermark">
            <span className="lbl">analytical watermark</span>
            <span><span className="big">{wm.raw_event_count ?? "—"}</span> events materialized</span>
            <span>as of {wm.as_of ?? "—"}</span>
            <span className="faint">derived from immutable raw event history</span>
          </div>

          <div className="grid cols-4">
            <Stat big label="payments" value={s("payments")} tone="teal" />
            <Stat big label="total value" value={s("total_value")} tone="gold" />
            <Stat big label="settlement rate" value={rate} tone="ok" />
            <Stat big label="events ingested" value={s("events")} tone="teal" />
          </div>

          <div className="spacer-lg" />
          <div className="grid cols-2">
            <Panel><p className="panel-head">Payment outcomes</p>
              <Bars rows={[
                { k: "settled", n: n("settled"), fill: "fill-green" },
                { k: "failed", n: n("failed"), fill: "fill-red" },
                { k: "rejected", n: n("rejected"), fill: "fill-amber" },
              ]} />
            </Panel>
            <Panel><p className="panel-head">Risk distribution</p>
              <Bars rows={[
                { k: "allow", n: n("risk_allow"), fill: "fill-green" },
                { k: "review", n: n("risk_review"), fill: "fill-amber" },
                { k: "block", n: n("risk_block"), fill: "fill-red" },
              ]} />
              <div className="foot" style={{ display: "flex", justifyContent: "space-between", marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border-soft)", fontFamily: "var(--mono)", fontSize: 13 }}>
                <span className="faint">avg risk score</span>
                <span className="gold">{s("average_risk_score")}</span>
              </div>
            </Panel>
          </div>

          <div className="spacer-lg" />
          <Panel><p className="panel-head">Payment volume over time</p>
            {series.loading ? (
              <p className="muted">Loading trend…</p>
            ) : (
              <AreaChart points={buckets.map((b) => ({ label: b.date, value: b.payments }))} />
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
