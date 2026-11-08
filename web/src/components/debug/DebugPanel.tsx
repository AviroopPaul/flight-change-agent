import { useEffect, useMemo, useState } from "react";
import { Activity, Check, ExternalLink, RefreshCw, TriangleAlert, X } from "lucide-react";
import { useTimeline } from "@/hooks/useTimeline";
import { cn } from "@/lib/utils";
import {
  clock,
  LANES,
  seconds,
  shortValue,
  timelineUrl,
  type Lane,
  type TimelineEntry,
  type TimelineSummary,
} from "@/lib/timeline";

interface Props {
  open: boolean;
  onClose: () => void;
  http: string | null;
  sessionId: string | null;
}

const LANE_BY_ID = Object.fromEntries(LANES.map((l) => [l.lane, l])) as Record<Lane, (typeof LANES)[number]>;

/**
 * The debug view: everything that happened in this session, from the backend's timeline.
 * Both channels, the agent's tool calls and replies, state changes, latency, cost and records.
 */
export function DebugPanel({ open, onClose, http, sessionId }: Props) {
  const { timeline, error, refresh } = useTimeline(http, sessionId, open);
  const [hidden, setHidden] = useState<Set<Lane>>(new Set());

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const counts = useMemo(() => {
    const c: Partial<Record<Lane, number>> = {};
    for (const e of timeline?.entries ?? []) c[e.lane] = (c[e.lane] ?? 0) + 1;
    return c;
  }, [timeline]);

  if (!open) return null;
  const entries = (timeline?.entries ?? []).filter((e) => !hidden.has(e.lane));
  const toggle = (lane: Lane) =>
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(lane)) next.delete(lane);
      else next.add(lane);
      return next;
    });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Session timeline"
      className="fixed inset-0 z-[60] flex flex-col bg-[oklch(0.15_0.02_264/0.98)] backdrop-blur-xl"
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-white/[0.07] px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3 lg:px-8">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/[0.06] ring-1 ring-white/10">
          <Activity className="size-4 text-glow" />
        </span>
        <div className="min-w-0 flex-1 leading-tight">
          <h2 className="text-sm font-medium">Session timeline</h2>
          <p className="truncate font-mono text-[10.5px] text-muted-foreground">
            {sessionId ?? "no session"} · refreshes every few seconds
          </p>
        </div>
        <IconButton label="Refresh" onClick={refresh}>
          <RefreshCw className="size-4" />
        </IconButton>
        {http && sessionId && (
          <a
            href={timelineUrl(http, sessionId)}
            target="_blank"
            rel="noreferrer"
            aria-label="Open raw JSON"
            className="hidden h-9 items-center gap-1.5 rounded-xl px-3 text-sm text-muted-foreground ring-1 ring-white/10 transition-colors hover:bg-white/[0.06] hover:text-foreground sm:flex"
          >
            <ExternalLink className="size-4" /> JSON
          </a>
        )}
        <IconButton label="Close timeline" onClick={onClose}>
          <X className="size-4" />
        </IconButton>
      </header>

      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-4 py-5 lg:px-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-5">
          {error && (
            <p className="flex items-center gap-2 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <TriangleAlert className="size-4" /> {error}
            </p>
          )}
          {!timeline && !error && <p className="text-sm text-muted-foreground">Loading the timeline…</p>}
          {timeline && (
            <>
              <Stats s={timeline.summary} />
              <Fields s={timeline.summary} />
              <div className="flex flex-wrap gap-2" role="group" aria-label="Show lanes">
                {LANES.map((l) => (
                  <button
                    key={l.lane}
                    type="button"
                    aria-pressed={!hidden.has(l.lane)}
                    onClick={() => toggle(l.lane)}
                    className="flex h-8 items-center gap-2 rounded-full px-3 text-xs text-muted-foreground ring-1 ring-white/10 transition-colors hover:text-foreground aria-pressed:bg-white/[0.07] aria-pressed:text-foreground"
                  >
                    <span className={cn("size-2 rounded-full", l.dot, hidden.has(l.lane) && "opacity-30")} />
                    {l.label}
                    <span className="tabular-nums opacity-60">{counts[l.lane] ?? 0}</span>
                  </button>
                ))}
              </div>
              <ol className="flex flex-col" aria-label="Timeline">
                {entries.map((e, i) => (
                  <Row key={`${e.at}-${i}`} e={e} />
                ))}
                {!entries.length && <li className="py-6 text-sm text-muted-foreground">Nothing to show yet.</li>}
              </ol>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="grid size-9 shrink-0 place-items-center rounded-xl text-muted-foreground ring-1 ring-white/10 transition-colors outline-none hover:bg-white/[0.06] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
    </button>
  );
}

function Stats({ s }: { s: TimelineSummary }) {
  const mins = Math.floor(s.callSeconds / 60);
  const tiles = [
    { label: "Outcome", value: s.outcome ?? "open", sub: s.outcome ? `revision ${s.revision}` : s.openCard ? `waiting on ${s.openCard}` : s.requestType },
    { label: "Calls", value: String(s.calls), sub: `${mins} min ${s.callSeconds % 60} s talked` },
    { label: "Chat answers", value: String(s.chatMessages), sub: `${s.requestType} request` },
    { label: "Voice latency p50", value: seconds(s.latency.p50Ms), sub: `p95 ${seconds(s.latency.p95Ms)} · ${s.latency.turns} turns` },
    { label: "Agent tools", value: String(s.toolCalls), sub: s.toolErrors ? `${s.toolErrors} returned an error` : "no errors" },
    { label: "Cost", value: `$${s.costUsd.toFixed(4)}`, sub: "STT + TTS + LLM" },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-2xl bg-white/[0.04] px-3 py-2.5 ring-1 ring-white/[0.08]">
          <p className="text-[11px] text-muted-foreground">{t.label}</p>
          <p className="truncate text-lg font-medium tabular-nums">{t.value}</p>
          <p className="truncate text-[11px] text-muted-foreground">{t.sub}</p>
        </div>
      ))}
    </div>
  );
}

const STATUS_DOT: Record<string, string> = { valid: "bg-success", invalid: "bg-destructive", missing: "bg-white/25" };

function Fields({ s }: { s: TimelineSummary }) {
  return (
    <div className="grid gap-x-6 gap-y-1.5 rounded-2xl bg-white/[0.03] p-3 ring-1 ring-white/[0.08] sm:grid-cols-2">
      {Object.entries(s.fields).map(([name, f]) => (
        <div key={name} className="flex min-w-0 items-center gap-2 text-sm">
          <span className={cn("size-2 shrink-0 rounded-full", STATUS_DOT[f.status] ?? "bg-warning")} title={f.status} />
          <span className="shrink-0 font-mono text-[12px] text-muted-foreground">{name}</span>
          {f.source && (
            <span className="shrink-0 rounded-md bg-white/[0.06] px-1.5 text-[10.5px] text-muted-foreground">{f.source}</span>
          )}
          <span className="min-w-0 truncate" title={shortValue(f.value)}>
            {f.status === "valid" && f.value === null ? "skipped" : shortValue(f.value) || f.status}
          </span>
        </div>
      ))}
    </div>
  );
}

function Row({ e }: { e: TimelineEntry }) {
  const lane = LANE_BY_ID[e.lane];
  const args = e.kind === "tool" && e.data?.args ? JSON.stringify(e.data.args) : null;
  const record = e.kind === "record" ? e.data?.record : null;
  return (
    <li className="grid grid-cols-[4.5rem_1fr] gap-3 border-b border-white/[0.05] py-2.5 sm:grid-cols-[4.5rem_7.5rem_1fr]">
      <time dateTime={e.at} className="pt-0.5 font-mono text-[11px] text-muted-foreground tabular-nums">
        {clock(e.at)}
      </time>
      <span className="hidden items-start gap-2 pt-0.5 text-xs text-muted-foreground sm:flex">
        <span className={cn("mt-1 size-2 shrink-0 rounded-full", lane?.dot)} />
        {lane?.label ?? e.lane}
      </span>
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-sm">
          <span className={cn("size-2 shrink-0 rounded-full sm:hidden", lane?.dot)} />
          <span className={cn("font-medium", e.kind === "tool" && "font-mono text-[13px]")}>{e.title}</span>
          {e.ok === true && e.kind === "tool" && <Check className="size-3.5 text-success" aria-label="ok" />}
          {e.ok === false && <TriangleAlert className="size-3.5 text-destructive" aria-label="error" />}
        </p>
        {args && <p className="font-mono text-[11.5px] [overflow-wrap:anywhere] text-glow-2/90">{args}</p>}
        {e.detail && (
          <p className={cn("text-[13px] [overflow-wrap:anywhere] text-muted-foreground", e.ok === false && "text-destructive/90")}>
            {e.detail}
          </p>
        )}
        {record != null && (
          <details className="mt-1">
            <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">View record JSON</summary>
            <pre className="thin-scroll mt-1 max-h-80 overflow-auto rounded-lg bg-black/30 p-2 font-mono text-[11px]">
              {JSON.stringify(record, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </li>
  );
}
