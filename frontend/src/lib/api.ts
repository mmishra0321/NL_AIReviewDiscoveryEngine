// Typed API client. In dev, vite proxies /api -> :8000 (see vite.config.ts).
// In production, set VITE_API_BASE to the deployed backend origin.
import type {
  ActionsResponse,
  AskResponse,
  CanonicalDetail,
  CanonicalList,
  Health,
  Meta,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function jget<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

async function jpost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${path} → HTTP ${r.status} ${text}`);
  }
  return (await r.json()) as T;
}

export const api = {
  health:           () => jget<Health>("/api/health"),
  meta:             () => jget<Meta>("/api/meta"),
  canonical:        () => jget<CanonicalList>("/api/canonical"),
  canonicalDetail:  (qid: string) => jget<CanonicalDetail>(`/api/canonical/${encodeURIComponent(qid)}`),
  ask:              (question: string) => jpost<AskResponse>("/api/ask", { question }),
  actions:          (limit = 10) => jget<ActionsResponse>(`/api/actions?limit=${limit}`),
  exportUrl:        () => `${BASE}/api/export.xlsx`,
};
