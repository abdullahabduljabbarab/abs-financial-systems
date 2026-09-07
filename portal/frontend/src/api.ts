// Thin typed client for the portal BFF. All reads, all relative paths: in
// production the BFF serves this app from the same origin.

export interface ServiceHealth {
  service: string;
  healthy: boolean;
  status_code: number | null;
  latency_ms: number;
  detail: Record<string, unknown>;
}

export interface Health {
  healthy: boolean;
  services: ServiceHealth[];
}

export interface Payment {
  id: string;
  account_id: string;
  amount: string;
  destination: string;
  state: string;
  provider: string | null;
  correlation_id: string;
  created_at: string | null;
}

export interface LedgerEffect {
  reserve_tx_id: string | null;
  capture_tx_id: string | null;
  release_tx_id: string | null;
}

export interface TimelineEntry {
  from_state: string | null;
  to_state: string;
  detail: string | null;
  at: string | null;
}

export interface Delivery {
  channel: string;
  status: string;
  attempt_count: number;
  destination: string;
  correlation_id: string | null;
}

export interface TraceEvent {
  event_id: string;
  event_type: string;
  occurred_at: string | null;
  producer: string | null;
  payment_id: string | null;
  account_id: string | null;
  correlation_id: string | null;
}

export interface Trace {
  payment: Payment;
  ledger_effect: LedgerEffect;
  timeline: TimelineEntry[];
  notifications: Delivery[];
  event_trace: TraceEvent[];
}

export interface Requirement {
  id: string;
  requirement: string;
  scenarios: string[];
  note: string | null;
}

export interface Scenario {
  id: string;
  title: string;
  covers: string[];
}

export interface Matrix {
  requirements: Requirement[];
  scenarios: Scenario[];
  totals: { requirements: number; scenarios: number };
}

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: { Accept: "application/json" } });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => getJSON<Health>("/api/health"),
  verification: () => getJSON<Matrix>("/api/verification"),
  analytics: (view: string) => getJSON<Record<string, unknown>>(`/api/analytics/${view}`),
  trace: (paymentId: string) => getJSON<Trace>(`/api/trace/${encodeURIComponent(paymentId)}`),
};
