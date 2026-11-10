import { useRef, useState, type FormEvent } from "react";
import { ArrowUp, CalendarCheck, Check, Forward, Plane, X } from "lucide-react";
import { choiceAnswer, multiSelectAnswer, singleChoices, SKIPPED_DISPLAY, textAnswer } from "../../lib/answers";
import { fareLines, optionParts } from "../../lib/cardView";
import { INPUT_TYPES, inputId, labelId } from "../../lib/inputs";
import { InputKind } from "../../protocol";
import type { Answer, OpenCard } from "../../state/conversation";
import { cn } from "@/lib/utils";
import { CalendarPicker } from "./CalendarPicker";
import { ErrorLine } from "./ErrorLine";

const OPTION =
  "well group flex w-full items-center justify-between gap-3 rounded-[1.15rem] px-4 py-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring";
const FIELD =
  "well h-11 min-w-0 flex-1 rounded-full px-4 text-[15px] outline-none placeholder:text-muted-foreground [color-scheme:dark]";
const ACT =
  "inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none";
const PRIMARY = cn(ACT, "btn-glow");
const SECONDARY = cn(ACT, "well text-foreground");
const CHIP = "rounded-full px-2 py-0.5 text-[11.5px] font-semibold whitespace-nowrap";

interface Props {
  card: OpenCard;
  onAnswer: (answer: Answer) => void;
}

/** The answer controls inside an agent card: options, flights, the fare, a date, or an optional field. */
export function InlineCard({ card, onAnswer }: Props) {
  switch (card.spec.kind) {
    case InputKind.CONFIRM:
      return <ConfirmControls card={card} onAnswer={onAnswer} />;
    case InputKind.SELECT:
      return <SelectControls card={card} onAnswer={onAnswer} />;
    case InputKind.MULTI_SELECT:
      return <MultiSelectControls card={card} onAnswer={onAnswer} />;
    case InputKind.DATE:
      return <DateControls card={card} onAnswer={onAnswer} />;
    default:
      return <OptionalTextControls card={card} onAnswer={onAnswer} />;
  }
}

/** The fare card's text as a small table, when it has that shape. */
export function FareTable({ label }: { label: string }) {
  const fare = fareLines(label);
  if (!fare) return null;
  return (
    <div className="flex flex-col text-sm">
      {fare.lines.filter((line) => !line.total).map((line) => (
        <div key={line.label} className="flex items-baseline gap-2 py-[3px] text-muted-foreground">
          <span>{line.label}</span>
          <span aria-hidden="true" className="mb-1 flex-1 border-b border-dotted border-white/15" />
          <span className="text-foreground tabular-nums">{line.amount}</span>
        </div>
      ))}
      {fare.other.map((text) => (
        <p key={text} className="mt-0.5 text-[13px] text-muted-foreground">{text}</p>
      ))}
      {fare.lines.filter((line) => line.total).map((line) => (
        <div key={line.label} className="well mt-2.5 flex items-center justify-between gap-3 rounded-[1.15rem] px-4 py-2.5">
          <span className="text-[15px] font-medium">{line.label}</span>
          <span className="text-gradient-glow text-2xl font-semibold tracking-tight tabular-nums">{line.amount}</span>
        </div>
      ))}
      {fare.question && <p className="mt-3 text-[15px] font-medium">{fare.question}</p>}
    </div>
  );
}

function ConfirmControls({ card, onAnswer }: Props) {
  return (
    <>
      <div className="mt-3 flex gap-2.5" role="group" aria-labelledby={labelId(card.spec)}>
        {singleChoices(card.spec).map((choice) => (
          <button
            key={choice.label}
            type="button"
            className={choice.value === true ? PRIMARY : SECONDARY}
            onClick={() => onAnswer(choiceAnswer(choice))}
          >
            {choice.value === true ? <Check className="size-4" strokeWidth={2.6} /> : <X className="size-4" strokeWidth={2.2} />}
            {choice.label}
          </button>
        ))}
      </div>
      <ErrorLine message={card.error} />
    </>
  );
}

function SelectControls({ card, onAnswer }: Props) {
  const choices = singleChoices(card.spec);
  return (
    <>
      <div className="stagger mt-3.5 flex flex-col gap-2" role="group" aria-labelledby={labelId(card.spec)}>
        {choices.map((choice, i) => {
          if (choice.value === null) return null;
          const parts = optionParts(choice.label);
          return (
            <button key={`${i}:${choice.label}`} type="button" className={OPTION} onClick={() => onAnswer(choiceAnswer(choice))}>
              {parts ? (
                <>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <FlightTimes title={parts.title} />
                    <span className="text-xs text-muted-foreground">{parts.subtitle}</span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1 text-right">
                    <span className="text-xs text-muted-foreground tabular-nums">{parts.price}</span>
                    {parts.note && (
                      <span className={cn(CHIP, /^you pay/i.test(parts.note) ? "bg-glow/18 text-glow-2" : "bg-success/12 text-success")}>
                        {parts.note}
                      </span>
                    )}
                  </span>
                </>
              ) : (
                <span className="text-[15px] font-medium">{choice.label}</span>
              )}
            </button>
          );
        })}
      </div>
      <SkipLink card={card} onAnswer={onAnswer} />
      <ErrorLine message={card.error} />
    </>
  );
}

function MultiSelectControls({ card, onAnswer }: Props) {
  const { spec, previous } = card;
  const [checked, setChecked] = useState<string[]>(Array.isArray(previous?.value) ? previous.value : []);
  const [error, setError] = useState(card.error);
  const toggle = (value: string, on: boolean) =>
    setChecked((prev) => (on ? [...prev, value] : prev.filter((v) => v !== value)));
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const result = multiSelectAnswer(spec, checked);
    if (typeof result === "string") setError(result);
    else onAnswer(result);
  };
  return (
    <form className="mt-4 flex flex-col gap-2.5" noValidate onSubmit={onSubmit} onChange={() => setError(null)}>
      <div className="stagger flex flex-col gap-2" role="group" aria-labelledby={labelId(spec)}>
        {(spec.options ?? []).map(({ value, label }) => (
          <label key={value} className={cn(OPTION, "cursor-pointer justify-start has-[:checked]:bg-glow/10 has-[:checked]:shadow-[inset_0_0_0_1px_color-mix(in_oklch,var(--glow-2)_55%,transparent)]")}>
            <input type="checkbox" checked={checked.includes(value)} onChange={(e) => toggle(value, e.target.checked)} className="peer sr-only" />
            <span aria-hidden="true" className="grid size-5 shrink-0 place-items-center rounded-full text-transparent shadow-[inset_0_0_0_1.5px_oklch(1_0_0/0.3)] transition-all peer-checked:bg-primary peer-checked:text-primary-foreground peer-checked:shadow-none peer-focus-visible:ring-2 peer-focus-visible:ring-ring">
              <Check className="size-3.5" strokeWidth={3} />
            </span>
            <span className="text-[15px] font-medium">{label || value}</span>
          </label>
        ))}
      </div>
      <div className="flex">
        <button type="submit" className={PRIMARY}><ArrowUp className="size-4" strokeWidth={2.6} /> Send</button>
      </div>
      <ErrorLine message={error} />
    </form>
  );
}

function DateControls({ card, onAnswer }: Props) {
  const { spec, previous } = card;
  const [value, setValue] = useState(typeof previous?.value === "string" ? previous.value : "");
  const [error, setError] = useState(card.error);
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!value) return setError("Please pick a date.");
    onAnswer({ value, display: longDate(value) });
  };
  return (
    <form id={inputId(spec)} className="mt-4 flex flex-col gap-2" noValidate onSubmit={onSubmit}>
      <CalendarPicker
        value={value}
        min={today()}
        onChange={(next) => {
          setValue(next);
          setError(null);
        }}
      />
      <button type="submit" className={PRIMARY} disabled={!value}>
        <CalendarCheck className="size-4" strokeWidth={2.3} />
        {value ? `Use ${longDate(value)}` : "Pick a day"}
      </button>
      <ErrorLine message={error} />
    </form>
  );
}

function OptionalTextControls({ card, onAnswer }: Props) {
  const { spec, previous } = card;
  const [text, setText] = useState(previous?.value != null ? String(previous.value) : "");
  const [error, setError] = useState(card.error);
  const inputRef = useRef<HTMLInputElement>(null);
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const result = textAnswer(spec, text, inputRef.current);
    if (typeof result === "string") setError(result);
    else onAnswer(result);
  };
  return (
    <form className="mt-4 flex flex-col gap-1" noValidate onSubmit={onSubmit}>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          id={inputId(spec)}
          className={FIELD}
          type={INPUT_TYPES[spec.kind] ?? "text"}
          placeholder={spec.placeholder || "Type here"}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setError(null);
          }}
        />
        <button type="submit" className={cn(PRIMARY, "flex-none")} disabled={!text.trim()}><Check className="size-4" strokeWidth={2.6} /> Save</button>
      </div>
      <SkipLink card={card} onAnswer={onAnswer} />
      <ErrorLine message={error} />
    </form>
  );
}

function SkipLink({ card, onAnswer }: Props) {
  if (card.spec.required !== false) return null;
  return (
    <button type="button" className="mt-3 -ml-1 inline-flex items-center gap-1.5 self-start rounded-full px-2.5 py-1 text-[13px] text-muted-foreground transition-colors outline-none hover:bg-white/[0.07] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onAnswer({ value: null, display: SKIPPED_DISPLAY })}>
      <Forward className="size-3.5" /> Skip
    </button>
  );
}

/** "17:45 → 20:30" as two times with a small flight path between them. */
function FlightTimes({ title }: { title: string }) {
  const [from, to] = title.split(/\s*→\s*/);
  if (!to) return <span className="text-[15px] font-medium">{title}</span>;
  return (
    <span className="flex items-center gap-2 text-base font-semibold tracking-tight tabular-nums">
      {from}
      <span aria-hidden="true" className="flex items-center gap-1 text-muted-foreground transition-colors group-hover:text-glow-2">
        <span className="h-px w-3 bg-current opacity-50" />
        <Plane className="size-3.5 rotate-45 transition-transform duration-300 group-hover:translate-x-0.5" />
        <span className="h-px w-3 bg-current opacity-50" />
      </span>
      <span className="sr-only">to</span>
      {to}
    </span>
  );
}

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function longDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}
