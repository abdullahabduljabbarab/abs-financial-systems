import { useState } from "react";
import { api, type Trace } from "../api";
import { Panel, Pill, useAsync } from "../ui";

function stateKind(state: string): "ok" | "bad" | "warn" | "neutral" {
  if (state === "settled") return "ok";
  if (state === "failed" || state === "rejected") return "bad";
  if (state === "unknown" || state === "risk_review") return "warn";
  return "neutral";
}

function txCell(id: string | null) {
  return id ? <span className="gold mono">{id}</span> : <span className="dim">—</span>;
}

function TraceBody({ t }: { t: Trace }) {
  return (
    <>
      <div className="grid cols-2">
        <Panel title="Payment">
          <dl className="kv">
            <dt>id</dt><dd>{t.payment.id}</dd>
            <dt>state</dt><dd><Pill kind={stateKind(t.payment.state)}>{t.payment.state}</Pill></dd>
            <dt>amount</dt><dd className="teal">{t.payment.amount}</dd>
            <dt>destination</dt><dd>{t.payment.destination}</dd>
            <dt>provider</dt><dd>{t.payment.provider ?? <span className="dim">none</span>}</dd>
            <dt>correlation_id</dt><dd className="teal">{t.payment.correlation_id}</dd>
            <dt>created_at</dt><dd className="dim">{t.payment.created_at ?? "—"}</dd>
          </dl>
        </Panel>
        <Panel title="Ledger effect">
          <dl className="kv">
            <dt>reserve_tx_id</dt><dd>{txCell(t.ledger_effect.reserve_tx_id)}</dd>
            <dt>capture_tx_id</dt><dd>{txCell(t.ledger_effect.capture_tx_id)}</dd>
            <dt>release_tx_id</dt><dd>{txCell(t.ledger_effect.release_tx_id)}</dd>
          </dl>
          <p className="muted" style={{ fontSize: 11.5, marginTop: 14 }}>
            The ledger transaction carries no correlation id; the financial effect is reached
            through the orchestrator's recorded transaction ids.
          </p>
        </Panel>
      </div>

      <div className="spacer-lg" />
      <div className="grid cols-2">
        <Panel title="Lifecycle">
          <ul className="timeline">
            {t.timeline.map((e, i) => (
              <li key={i}>
                <div className="state">
                  {e.from_state ? <span className="dim">{e.from_state} → </span> : null}
                  {e.to_state}
                </div>
                <div className="at">{e.at ?? ""}{e.detail ? ` · ${e.detail}` : ""}</div>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Notifications">
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
      <Panel title="Event trace (analytics)">
        {t.event_trace.length === 0 ? (
          <p className="muted">No events ingested for this correlation id yet.</p>
        ) : (
          <table>
            <thead><tr><th>event_type</th><th>producer</th><th className="mono">occurred_at</th></tr></thead>
            <tbody>
              {t.event_trace.map((e) => (
                <tr key={e.event_id}>
                  <td className="mono teal">{e.event_type}</td>
                  <td className="mono">{e.producer ?? "—"}</td>
                  <td className="mono dim">{e.occurred_at ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
      <form
        className="field"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(input.trim());
        }}
      >
        <input
          placeholder="payment id (uuid)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          spellCheck={false}
        />
        <button type="submit">Trace</button>
      </form>
      {submitted ? <Result paymentId={submitted} /> : <p className="muted">Enter a payment id to trace it.</p>}
    </div>
  );
}
