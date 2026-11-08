import type { ReactNode } from "react";
import { isPlainObject } from "../../lib/record";
import { engagementLine, recordSections, type RowIcon } from "../../lib/recordView";
import { Outcome, type FinalRecord } from "../../protocol";
import {
  AlertCircleIcon,
  CalendarIcon,
  CardIcon,
  ChatIcon,
  CheckCircleIcon,
  ClockIcon,
  MailIcon,
  MicIcon,
  PlaneIcon,
  ReasonIcon,
  StopCircleIcon,
  TicketIcon,
  UserIcon,
} from "../icons";

const ROW_ICONS: Record<RowIcon, () => ReactNode> = {
  plane: PlaneIcon,
  ticket: TicketIcon,
  user: UserIcon,
  calendar: CalendarIcon,
  clock: ClockIcon,
  reason: ReasonIcon,
  mail: MailIcon,
  card: CardIcon,
  check: CheckCircleIcon,
};

const HEADINGS: Record<string, { title: string; icon: () => ReactNode }> = {
  [Outcome.COMPLETED]: { title: "Flight change confirmed", icon: CheckCircleIcon },
  [Outcome.NEEDS_REVIEW]: { title: "Sent for review", icon: AlertCircleIcon },
  [Outcome.PARTIAL]: { title: "Saved for later", icon: ClockIcon },
  [Outcome.OPTED_OUT]: { title: "Request stopped", icon: StopCircleIcon },
};

const OUTCOME_TEXT: Record<string, string> = {
  [Outcome.COMPLETED]: "completed",
  [Outcome.NEEDS_REVIEW]: "needs review",
  [Outcome.PARTIAL]: "partial",
  [Outcome.OPTED_OUT]: "opted out",
};

function Source({ source }: { source?: string }) {
  if (!source) return null;
  const call = source === "call";
  return (
    <span className={`src src-${source}`} title={call ? "Said on the call" : "Typed in the chat"}>
      {call ? <MicIcon /> : <ChatIcon />}
      {call ? "call" : "chat"}
    </span>
  );
}

export function RecordCard({ record }: { record: FinalRecord }) {
  const rec: Record<string, unknown> = isPlainObject(record) ? record : {};
  const outcome = String(rec.outcome ?? "");
  const heading = HEADINGS[outcome] ?? { title: "Final record", icon: AlertCircleIcon };
  const HeadIcon = heading.icon;
  const conflicts = Array.isArray(rec.conflicts) ? rec.conflicts.length : 0;
  const footer = engagementLine(rec);

  return (
    <section className={`record outcome-${outcome}`} aria-label="Final record">
      <header className="record-head">
        <span className="record-icon"><HeadIcon /></span>
        <div className="record-titles">
          <h2>{heading.title}</h2>
          {typeof rec.outcomeReason === "string" && <p className="record-reason">{rec.outcomeReason}</p>}
        </div>
        <div className="record-meta">
          <span className={`badge outcome-${outcome}`}>{OUTCOME_TEXT[outcome] ?? outcome}</span>
          {rec.revision !== undefined && <span className="rev">rev {String(rec.revision)}</span>}
        </div>
      </header>

      {recordSections(rec).map((section) => (
        <div key={section.title} className="record-section">
          <h3>{section.title}</h3>
          {section.rows.map((r) => {
            const RowIconC = ROW_ICONS[r.icon];
            return (
              <div key={r.key} className={`record-row${r.emphasis ? " emphasis" : ""}${r.flagged ? " flagged" : ""}`}>
                <span className="row-icon"><RowIconC /></span>
                <div className="row-body">
                  <span className="row-label">{r.label}</span>
                  <span className="row-value">
                    {r.value}
                    {r.chip && <span className="chip">{r.chip}</span>}
                  </span>
                  {r.detail && <span className="row-detail">{r.detail}</span>}
                </div>
                <div className="row-tags">
                  {r.flagged && <span className="status">{r.flagged}</span>}
                  <Source source={r.source} />
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {conflicts > 0 && <p className="record-note">{conflicts} conflict(s) between call and chat were resolved. See the JSON.</p>}
      {footer && <p className="record-foot">{footer}</p>}
      <details>
        <summary>View JSON</summary>
        <pre>{JSON.stringify(record, null, 2)}</pre>
      </details>
    </section>
  );
}
