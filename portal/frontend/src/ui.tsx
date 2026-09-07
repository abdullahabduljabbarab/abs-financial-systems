// Small shared presentational bits and a minimal data-fetch hook.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

export function Pill({ kind, children }: { kind: "ok" | "bad" | "warn" | "neutral"; children: ReactNode }) {
  return (
    <span className={`pill ${kind}`}>
      {kind !== "neutral" && <span className="dot" />}
      {children}
    </span>
  );
}

export function Panel({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="panel">
      {title && <p className="section-title">{title}</p>}
      {children}
    </section>
  );
}

export interface AsyncState<T> {
  data?: T;
  error?: string;
  loading: boolean;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ loading: true });
  useEffect(() => {
    let live = true;
    setState({ loading: true });
    fn()
      .then((data) => live && setState({ data, loading: false }))
      .catch((e) => live && setState({ error: String(e?.message ?? e), loading: false }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
