import { useState } from "react";
import { api, type Trace, type TimelineEntry } from "../api";
import { Panel, Pill, useAsync } from "../ui";

function stateKind(state: string): "ok" | "bad" | "warn" | "neutral" {
  if (state === "settled") return "ok";
  if (state === "failed" || state === "rejected") return "bad";
  if (state === "unknown" || state === "risk_review") return "warn";
  return "neutral";
}

const MILESTONES = [
  { label: "RECEIVED", states: ["received"] },
  { label: "RISK", states: ["risk_pending", "approved", "risk_review", "rejected"] },
  { label: "RESERVED", states: ["reserving", "funds_reserved"] },
  { label: "PROVIDER", states: ["provider_pending"] },
  { label: "CAPTURED", states: ["capturing"] },
  { label: "SETTLED", states: ["settled"] },
];

function LifecycleRail({ timeline, finalState }: { timeline: TimelineEntry[]; finalState: string }) {
  const seen = new Set(timeline.map((e) => e.to_state));
  const reached = MILESTONES.map((m) => m.states.some((s) => seen.has(s)));
  const lastDone = reached.lastIndexOf(true);
  const termClass =
    finalState === "settled" ? "term-ok" : finalState === "failed" || finalState === "rejected" ? "term-bad" : finalState === "unknown" || finalState === "risk_review" ? "term-warn" : "done";

  return (
    <div className="rail">
      {MILESTONES.map((m, i) => {
        const done = reached[i];
        const cls = i === lastDone ? termClass : done ? "done" : "";
        return (
          <div key={m.label} style={{ display: "contents" }}>
            {i > 0 && <span className={`link ${reached[i] && reached[i - 1] ? "done" : ""}`} />}
            <div className={`node ${cls}`}>
              <span className="disc" />
              <span className="lbl">{m.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function producerClass(producer: string | null): string {
  if (producer === "payment-orchestrator") return "prod-payment";
  if (producer === "risk-engine") return "prod-risk";
  if (producer === "ledger-api") return "prod-ledger";
  return "prod-other";
}

function TraceBody({ t }: { t: Trace }) {
  return (
    <>
      <div className="trace-hero">
        <div>
          <div className="amount">{t.payment.amount}</div>
          <div className="provider">{t.payment.provider ?? "no provider"} · {t.payment.destination}</div>
        </div>
        <span className="spacer" />
        <dl className="facts">
          <dt>payment</dt><dd>{t.payment.id}</dd>
          <dt>correlation</dt><dd className="teal">{t.payment.correlation_id}</dd>
          <dt>created</dt><dd className="dim">{t.payment.created_at ?? "—"}</dd>
        </dl>
        <Pill kind={stateKind(t.payment.state)}>{t.payment.state}</Pill>
      </div>

      <LifecycleRail timeline={t.timeline} finalState={t.payment.state} />

      <div className="grid cols-2">
        <Panel><p className="panel-head">Payment</p>
          <dl className="kv">
            <dt>state</dt><dd><Pill kind={stateKind(t.payment.state)}>{t.payment.state}</Pill></dd>
            <dt>amount</dt><dd className="gold">{t.payment.amount}</dd>
            <dt>provider</dt><dd>{t.payment.provider ?? <span className="dim">none</span>}</dd>
            <dt>destination</dt><dd>{t.payment.destination}</dd>
            <dt>account_id</dt><dd className="dim">{t.payment.account_id}</dd>
          </dl>
        </Panel>
        <Panel><p className="panel-head">Ledger effect</p>
          <dl className="kv">
            <dt>reserve_tx_id</dt><dd>{t.ledger_effect.reserve_tx_id ? <span className="gold">{t.ledger_effect.reserve_tx_id}</span> : <span className="dim">—</span>}</dd>
            <dt>capture_tx_id</dt><dd>{t.ledger_effect.capture_tx_id ? <span className="gold">{t.ledger_effect.capture_tx_id}</span> : <span className="dim">—</span>}</dd>
            <dt>release_tx_id</dt><dd>{t.ledger_effect.release_tx_id ? <span className="gold">{t.ledger_effect.release_tx_id}</span> : <span className="dim">—</span>}</dd>
          </dl>
          <p className="muted" style={{ fontSize: 11.5, marginTop: 14 }}>
            The ledger transaction carries no correlation id; the financial effect is reached
            through the orchestrator's recorded transaction ids.
          </p>
        </Panel>
      </div>

      <div className="spacer-lg" />
      <div className="grid cols-2">
        <Panel><p className="panel-head">Lifecycle</p>
          <ul className="timeline">
            {t.timeline.map((e, i) => (
              <li key={i}>
                <div className="state">{e.from_state ? <span className="dim">{e.from_state} → </span> : null}{e.to_state}</div>
                <div className="at">{e.at ?? ""}{e.detail ? ` · ${e.detail}` : ""}</div>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel><p className="panel-head">Notifications</p>
          {t.notifications.length === 0 ? (
            <p className="muted">No deliveries.</p>
          ) : (
            <table>
              <thead><tr><th>channel</th><th>status</th><th>attempts</th></tr></thead>
              <tbody>
                {t.notifications.map((n, i) => (
                  <tr key={i}>
                    <td className="mono">{n.channel}</td>
                    <td><Pill kind={n.status === "delivered" ? "ok" : n.status === "dead_lettered" ? "bad" : "warn"}>{n.status}</Pill></td>
                    <td className="mono">{n.attempt_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="spacer-lg" />
      <Panel><p className="panel-head">Event trace · analytics</p>
        {t.event_trace.length === 0 ? (
          <p className="muted">No events ingested for this correlation id yet.</p>
        ) : (
          <div className="events">
            {t.event_trace.map((e) => (
              <div key={e.event_id} className={`event-row ${producerClass(e.producer)}`}>
                <span className="rail-bar" />
                <div>
                  <div className="etype">{e.event_type}</div>
                  <div className="eprod">{e.producer ?? "—"}</div>
                </div>
                <div className="etime">{e.occurred_at ?? "—"}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}

function Result({ paymentId }: { paymentId: string }) {
  const { data, error, loading } = useAsync(() => api.trace(paymentId), [paymentId]);
  if (loading) return <p className="muted">Tracing {paymentId}…</p>;
  if (error) return <p className="error">{error.includes("404") ? "Payment not found." : `Error: ${error}`}</p>;
  return data ? <TraceBody t={data} /> : null;
}

export function TraceView() {
  const [input, setInput] = useState("");
  const [submitted, setSubmitted] = useState("");

  return (
    <div>
      <h2 className="view-title">Payment trace</h2>
      <p className="view-note">
        Follow one payment across every service, joined by its correlation id: its lifecycle,
        the ledger effect, the notifications it produced, and the analytics event trace.
      </p>
      <form className="field" onSubmit={(e) => { e.preventDefault(); setSubmitted(input.trim()); }}>
        <input placeholder="payment id (uuid)" value={input} onChange={(e) => setInput(e.target.value)} spellCheck={false} />
        <button type="submit">Trace</button>
      </form>
      {submitted ? <Result paymentId={submitted} /> : <p className="muted">Enter a payment id to trace it.</p>}
    </div>
  );
}
