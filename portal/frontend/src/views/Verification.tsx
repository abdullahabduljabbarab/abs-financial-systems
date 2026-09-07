import { useState } from "react";
import { api, type Matrix, type Scenario } from "../api";
import { Panel, useAsync } from "../ui";

function ScenarioDrawer({ scenario, onClose }: { scenario: Scenario; onClose: () => void }) {
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer">
        <button className="close" onClick={onClose} aria-label="close">×</button>
        <div className="eyebrow">{scenario.id}</div>
        <h3>{scenario.title}</h3>
        <p className="subtitle">Black-box scenario, driven against the live services.</p>

        <div className="eyebrow" style={{ marginBottom: 8 }}>Requirements</div>
        <div>{scenario.covers.map((c) => <span key={c} className="tag" style={{ cursor: "default" }}>{c}</span>)}</div>

        {scenario.assertions && (
          <>
            <div className="eyebrow" style={{ margin: "20px 0 4px" }}>Assertions</div>
            <ul className="assert-list">
              {scenario.assertions.map((a, i) => (
                <li key={i}><span className="ck">✓</span><span>{a}</span></li>
              ))}
            </ul>
          </>
        )}
        <p className="muted" style={{ fontSize: 11.5, marginTop: 20 }}>
          Each run writes an immutable evidence file (ids, revisions, and per-assertion results)
          produced by the verification harness.
        </p>
      </aside>
    </>
  );
}

function Header({ m }: { m: Matrix }) {
  const covered = m.requirements.filter((r) => r.scenarios.length > 0 || r.note).length;
  const pct = Math.round((covered / m.totals.requirements) * 100);
  return (
    <>
      <div className="grid cols-3" style={{ marginBottom: 4 }}>
        <Panel><div className="stat"><span className="value teal">{m.totals.requirements}</span><span className="label">requirements</span></div></Panel>
        <Panel><div className="stat"><span className="value gold">{m.totals.scenarios}</span><span className="label">scenarios</span></div></Panel>
        <Panel><div className="stat"><span className="value ok">{covered}<small> / {m.totals.requirements}</small></span><span className="label">traceability · mapped</span></div></Panel>
      </div>
      <div className="coverage">
        <div className="eyebrow">Requirement coverage · {pct}%</div>
        <div className="bar"><span style={{ width: `${pct}%` }} /></div>
      </div>
    </>
  );
}

export function VerificationView() {
  const { data, error, loading } = useAsync(() => api.verification(), []);
  const [openId, setOpenId] = useState<string | null>(null);
  const byId = data ? Object.fromEntries(data.scenarios.map((s) => [s.id, s])) : {};
  const open = openId ? byId[openId] : null;

  return (
    <div>
      <h2 className="view-title">System verification</h2>
      <p className="view-note">
        Every system-level requirement and the black-box scenario that proves it. The harness
        drives the live services and records immutable evidence per run. Click a scenario to see
        what it asserts.
      </p>
      {loading && <p className="muted">Loading matrix…</p>}
      {error && <p className="error">Error: {error}</p>}
      {data && (
        <>
          <Header m={data} />
          <Panel><p className="panel-head">Requirements</p>
            <table>
              <thead><tr><th className="mono">id</th><th>requirement</th><th>verified by</th></tr></thead>
              <tbody>
                {data.requirements.map((r) => (
                  <tr key={r.id}>
                    <td className="mono teal">{r.id}</td>
                    <td>{r.requirement}</td>
                    <td>
                      {r.scenarios.map((s) => (
                        <span className="tag" key={s} title={byId[s]?.title} onClick={() => setOpenId(s)}>{s}</span>
                      ))}
                      {r.scenarios.length === 0 && r.note && <span className="muted" style={{ fontSize: 12 }}>{r.note}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          {open && <ScenarioDrawer scenario={open} onClose={() => setOpenId(null)} />}
        </>
      )}
    </div>
  );
}
