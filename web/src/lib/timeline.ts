/** The session timeline from GET /sessions/{id}/timeline, used by the debug view. */

export type Lane = "call" | "chat" | "agent" | "system" | "record";

export interface TimelineEntry {
  at: string;
  lane: Lane;
  kind: string;
  title: string;
  detail: string | null;
  ok: boolean | null;
  data: Record<string, unknown> | null;
}

export interface FieldView {
  status: string;
  source: string | null;
  value: unknown;
}

export interface TimelineSummary {
  sessionId: string;
  createdAt: string;
  requestType: string;
  reasonCategory: string | null;
  outcome: string | null;
  locked: boolean;
  revision: number;
  openCard: string | null;
  fields: Record<string, FieldView>;
  conflicts: unknown[];
  calls: number;
  callSeconds: number;
  chatMessages: number;
  costUsd: number;
  latency: { turns: number; p50Ms?: number; p95Ms?: number; maxMs?: number };
  toolCalls: number;
  toolErrors: number;
  records: { revision: number; outcome: string; createdAt: string; deliveredAt: string | null }[];
}

export interface Timeline {
  summary: TimelineSummary;
  entries: TimelineEntry[];
}

export const LANES: { lane: Lane; label: string; dot: string }[] = [
  { lane: "call", label: "Call", dot: "bg-glow" },
  { lane: "chat", label: "Chat", dot: "bg-success" },
  { lane: "agent", label: "Agent tools", dot: "bg-glow-2" },
  { lane: "system", label: "State", dot: "bg-muted-foreground" },
  { lane: "record", label: "Record", dot: "bg-warning" },
];

export const timelineUrl = (http: string, sessionId: string): string =>
  `${http}/sessions/${encodeURIComponent(sessionId)}/timeline`;

export async function fetchTimeline(http: string, sessionId: string, signal?: AbortSignal): Promise<Timeline> {
  const res = await fetch(timelineUrl(http, sessionId), { signal });
  if (!res.ok) throw new Error(`Timeline request failed (${res.status}).`);
  return (await res.json()) as Timeline;
}

/** Local clock time with seconds, e.g. 14:23:05. */
export const clock = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const seconds = (ms?: number): string => (ms === undefined ? "n/a" : `${(ms / 1000).toFixed(2)} s`);

export function shortValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(shortValue).join(", ");
  if (typeof value === "object") {
    const v = value as Record<string, unknown>;
    if (typeof v.text === "string") return v.text;
    if (typeof v.flightNo === "string") return `${v.flightNo} ${String(v.departure ?? "")}`.trim();
    return JSON.stringify(value);
  }
  return String(value);
}
