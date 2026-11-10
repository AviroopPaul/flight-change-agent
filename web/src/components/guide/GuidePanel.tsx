import { useState } from "react";
import { Check, Copy, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { BOOKINGS, CHANGE_FEE, SCENARIOS, type GuideBooking } from "./data";

const DONE_KEY = "guide.done";
const OUTCOME_TONE: Record<string, string> = {
  completed: "text-emerald-300 ring-emerald-400/30",
  needsReview: "text-amber-300 ring-amber-400/30",
  optedOut: "text-rose-300 ring-rose-400/30",
  partial: "text-sky-300 ring-sky-400/30",
};

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

function departs(b: GuideBooking): string {
  if ("hours" in b.departs) return `in ${b.departs.hours} h`;
  const day = new Date();
  day.setDate(day.getDate() + b.departs.days);
  const label = day.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  return `${label}, ${b.departs.time}`;
}

function loadDone(): string[] {
  try {
    return JSON.parse(localStorage.getItem(DONE_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function saveDone(ids: string[]) {
  try {
    localStorage.setItem(DONE_KEY, JSON.stringify(ids));
  } catch {
    // Ticks are a convenience; without storage they last until the next reload.
  }
}

function BookingRow({ b }: { b: GuideBooking }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(b.pnr).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };
  return (
    <li className={cn("rounded-xl bg-white/[0.03] px-3 py-2.5 ring-1 ring-white/[0.07]", b.blocked && "opacity-70")}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={copy}
          aria-label={`Copy ${b.pnr}`}
          className="flex items-center gap-1.5 rounded-md font-mono text-[13px] font-semibold tracking-wide outline-none hover:text-glow focus-visible:ring-2 focus-visible:ring-ring"
        >
          {b.pnr}
          {copied ? <Check className="size-3 text-emerald-300" /> : <Copy className="size-3 text-muted-foreground" />}
        </button>
        <span
          className={cn(
            "rounded-full px-1.5 py-px text-[10px] font-medium uppercase ring-1",
            b.fareClass === "flex" ? "text-emerald-300 ring-emerald-400/30" : "text-muted-foreground ring-white/15",
          )}
        >
          {b.fareClass}
        </span>
        {b.blocked && <span className="ml-auto text-[11px] text-rose-300">{b.blocked}</span>}
      </div>
      <p className="mt-1 text-[12.5px]">{b.passengers.join(", ")}</p>
      <p className="mt-0.5 text-[11.5px] text-muted-foreground">
        {b.route} · {b.flightNo} · {departs(b)}
      </p>
      {!b.blocked && <p className="mt-0.5 text-[11.5px] text-muted-foreground">
        {inr(b.farePerPax)} per person · {CHANGE_FEE[b.fareClass] ? `change fee ${inr(CHANGE_FEE[b.fareClass])}` : "no change fee"}
      </p>}
    </li>
  );
}

/** Presenter guide for recording the demo (?guide=1): the test bookings and the scenarios to show. */
export function GuidePanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [done, setDone] = useState<string[]>(loadDone);
  const toggle = (id: string) => {
    const next = done.includes(id) ? done.filter((d) => d !== id) : [...done, id];
    setDone(next);
    saveDone(next);
  };

  return (
    <aside
      aria-label="Demo guide"
      aria-hidden={!open}
      inert={!open}
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex w-full transition-transform duration-300 ease-out sm:w-[340px] lg:p-3 lg:pr-0",
        open ? "translate-x-0" : "-translate-x-full",
      )}
    >
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden border-r border-white/10 bg-[oklch(0.165_0.022_264/0.97)] shadow-[0_0_80px_-20px_rgb(0_0_0/0.9)] backdrop-blur-xl lg:rounded-3xl lg:border">
        <header className="flex shrink-0 items-center gap-2 border-b border-white/[0.07] px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-medium">Demo guide</h2>
            <p className="text-[11px] text-muted-foreground">Test bookings and scenarios</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close demo guide"
            className="grid size-9 place-items-center rounded-xl text-muted-foreground ring-1 ring-white/10 transition-colors outline-none hover:bg-white/[0.06] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-3 py-3">
          <h3 className="px-1 pb-2 text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">Bookings</h3>
          <ul className="flex flex-col gap-2">
            {BOOKINGS.map((b) => (
              <BookingRow key={b.pnr} b={b} />
            ))}
          </ul>

          <div className="flex items-baseline justify-between px-1 pt-5 pb-2">
            <h3 className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">Scenarios</h3>
            <span className="text-[11px] text-muted-foreground">
              {done.length}/{SCENARIOS.length}
              {done.length > 0 && (
                <button type="button" onClick={() => (setDone([]), saveDone([]))} className="ml-2 underline-offset-2 hover:text-foreground hover:underline">
                  Reset
                </button>
              )}
            </span>
          </div>
          <ol className="flex flex-col gap-1">
            {SCENARIOS.map((s, i) => {
              const ticked = done.includes(s.id);
              return (
                <li key={s.id}>
                  <label className="flex cursor-pointer items-start gap-2.5 rounded-lg px-2 py-1.5 hover:bg-white/[0.04]">
                    <input type="checkbox" checked={ticked} onChange={() => toggle(s.id)} className="mt-0.5 size-3.5 shrink-0 accent-glow" />
                    <span className="min-w-0 flex-1">
                      <span className={cn("flex items-center gap-2 text-[13px]", ticked && "text-muted-foreground line-through")}>
                        <span className="font-mono text-[11px] text-muted-foreground">{i + 1}</span>
                        {s.title}
                        {s.outcome && <span className={cn("rounded-full px-1.5 py-px font-mono text-[10px] ring-1", OUTCOME_TONE[s.outcome])}>{s.outcome}</span>}
                      </span>
                      <span className="block text-[11.5px] text-muted-foreground">{s.cue}</span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ol>
        </div>
      </section>
    </aside>
  );
}
