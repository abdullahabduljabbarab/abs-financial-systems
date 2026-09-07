import { api } from "../api";
import { Panel, useAsync } from "../ui";

export function VerificationView() {
  const { data, error, loading } = useAsync(() => api.verification(), []);

  return (
    <div>
      <h2 className="view-title">Verification matrix</h2>
      <p className="view-note">
        Every system-level requirement and the black-box scenario that proves it. The harness
        drives the live services and records immutable evidence per run.
      </p>
      {loading && <p className="muted">Loading matrix…</p>}
      {error && <p className="error">Error: {error}</p>}
      {data && (
        <>
          <div className="grid cols-3" style={{ marginBottom: 18 }}>
            <Panel>
              <div className="stat">
                <span className="value accent">{data.totals.requirements}</span>
                <span className="label">requirements</span>
              </div>
            </Panel>
            <Panel>
              <div className="stat">
                <span className="value gold">{data.totals.scenarios}</span>
                <span className="label">scenarios</span>
              </div>
            </Panel>
            <Panel>
              <div className="stat">
                <span className="value">
                  {data.requirements.filter((r) => r.scenarios.length > 0 || r.note).length}
                  <span className="dim" style={{ fontSize: 15 }}>/{data.totals.requirements}</span>
                </span>
                <span className="label">covered</span>
              </div>
            </Panel>
          </div>

          <Panel title="Requirements">
            <table>
              <thead>
                <tr>
                  <th className="mono">id</th>
                  <th>requirement</th>
                  <th>verified by</th>
                </tr>
              </thead>
              <tbody>
                {data.requirements.map((r) => (
                  <tr key={r.id}>
                    <td className="mono teal">{r.id}</td>
                    <td>{r.requirement}</td>
                    <td>
                      {r.scenarios.map((s) => (
                        <span className="tag" key={s}>{s}</span>
                      ))}
                      {r.scenarios.length === 0 && r.note && <span className="muted" style={{ fontSize: 12 }}>{r.note}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </>
      )}
    </div>
  );
}
