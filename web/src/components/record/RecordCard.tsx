import {
  CalendarDays,
  CircleAlert,
  CircleCheckBig,
  CircleX,
  Clock,
  CreditCard,
  Mail,
  MessageCircle,
  MessageSquareText,
  Mic,
  Plane,
  Ticket,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import { isPlainObject } from "../../lib/record";
import { engagementLine, recordSections, type RowIcon } from "../../lib/recordView";
import { Outcome, type FinalRecord } from "../../protocol";
import { cn } from "@/lib/utils";

const ROW_ICONS: Record<RowIcon, LucideIcon> = {
  plane: Plane,
  ticket: Ticket,
  user: User,
  calendar: CalendarDays,
  clock: Clock,
  reason: MessageSquareText,
  mail: Mail,
  card: CreditCard,
  check: CircleCheckBig,
};

interface Heading {
  title: string;
  icon: LucideIcon;
  /** Text color, ring and glow for the outcome. */
  tone: string;
}

const HEADINGS: Record<string, Heading> = {
  [Outcome.COMPLETED]: { title: "Flight change confirmed", icon: CircleCheckBig, tone: "text-success ring-white/10" },
  [Outcome.NEEDS_REVIEW]: { title: "Sent for review", icon: CircleAlert, tone: "text-warning ring-white/10" },
  [Outcome.PARTIAL]: { title: "Saved for later", icon: Clock, tone: "text-muted-foreground ring-white/10" },
  [Outcome.OPTED_OUT]: { title: "Request stopped", icon: CircleX, tone: "text-destructive ring-white/10" },
};

const FALLBACK: Heading = { title: "Final record", icon: CircleAlert, tone: "text-muted-foreground ring-white/10" };

const OUTCOME_TEXT: Record<string, string> = {
  [Outcome.COMPLETED]: "completed",
  [Outcome.NEEDS_REVIEW]: "needs review",
  [Outcome.PARTIAL]: "partial",
  [Outcome.OPTED_OUT]: "opted out",
};

const TAG = "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10.5px] whitespace-nowrap";

function Source({ source }: { source?: string }) {
  if (!source) return null;
  const call = source === "call";
  const Icon = call ? Mic : MessageCircle;
  return (
    <span className={cn(TAG, "bg-white/[0.06] text-muted-foreground")} title={call ? "Said on the call" : "Typed in the chat"}>
      <Icon className="size-3" />
      {call ? "call" : "chat"}
    </span>
  );
}

interface Props {
  record: FinalRecord;
  /** Shows a close button (the floating copy). */
  onClose?: () => void;
  className?: string;
}

export function RecordCard({ record, onClose, className }: Props) {
  const rec: Record<string, unknown> = isPlainObject(record) ? record : {};
  const outcome = String(rec.outcome ?? "");
  const heading = HEADINGS[outcome] ?? FALLBACK;
  const HeadIcon = heading.icon;
  const conflicts = Array.isArray(rec.conflicts) ? rec.conflicts.length : 0;
  const footer = engagementLine(rec);

  return (
    <section aria-label="Final record" className={cn("my-2 overflow-hidden rounded-2xl bg-white/[0.03] ring-1", heading.tone, className)}>
      <header className="flex items-start gap-3 border-b border-white/[0.07] px-4 py-3.5">
        <HeadIcon className="mt-0.5 size-6 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] tracking-[0.16em] uppercase opacity-80">Final record</p>
          <h2 className="text-base font-semibold text-foreground">{heading.title}</h2>
          {typeof rec.outcomeReason === "string" && <p className="mt-0.5 text-[12.5px] text-muted-foreground">{rec.outcomeReason}</p>}
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close final record"
            className="order-last -mt-1 -mr-1 grid size-8 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors outline-none hover:bg-white/10 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" />
          </button>
        )}
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className="rounded-full bg-current/10 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/25">{OUTCOME_TEXT[outcome] ?? outcome}</span>
          {rec.revision !== undefined && <span className="font-mono text-[10.5px] text-muted-foreground">rev {String(rec.revision)}</span>}
        </div>
      </header>

      {recordSections(rec).map((section) => (
        <div key={section.title} className="border-t border-white/[0.06] px-4 pt-3 pb-1 first-of-type:border-t-0">
          <h3 className="mb-1 font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">{section.title}</h3>
          {section.rows.map((r) => {
            const Icon = ROW_ICONS[r.icon];
            return (
              <div key={r.key} className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-start gap-3 py-2">
                <Icon className="mt-1 size-4 text-muted-foreground" />
                <div className="flex min-w-0 flex-col">
                  <span className="text-[11.5px] text-muted-foreground">{r.label}</span>
                  <span
                    className={cn(
                      "text-sm [overflow-wrap:anywhere] text-foreground",
                      r.emphasis && "text-[15px] font-semibold",
                      r.flagged && "text-destructive",
                    )}
                  >
                    {r.value}
                    {r.chip && <span className={cn(TAG, "ml-1.5 bg-glow/10 font-medium text-glow")}>{r.chip}</span>}
                  </span>
                  {r.detail && <span className="text-[12.5px] text-muted-foreground">{r.detail}</span>}
                </div>
                <div className="flex flex-col items-end gap-1 pt-0.5">
                  {r.flagged && <span className={cn(TAG, "bg-destructive/15 text-destructive")}>{r.flagged}</span>}
                  <Source source={r.source} />
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {conflicts > 0 && (
        <p className="px-4 py-1.5 text-xs text-muted-foreground">{conflicts} conflict(s) between call and chat were resolved. See the JSON.</p>
      )}
      {footer && <p className="border-t border-white/[0.06] px-4 py-2 text-xs text-muted-foreground">{footer}</p>}
      <details className="group px-4 pt-1 pb-3">
        <summary className="cursor-pointer text-[12.5px] text-glow/90 hover:text-glow">View JSON</summary>
        <pre className="thin-scroll mt-2 max-h-64 overflow-auto rounded-lg bg-black/30 p-3 font-mono text-[11px] text-foreground/85 ring-1 ring-white/[0.06]">
          {JSON.stringify(record, null, 2)}
        </pre>
      </details>
    </section>
  );
}
