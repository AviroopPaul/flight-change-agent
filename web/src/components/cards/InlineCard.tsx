import { useRef, useState, type FormEvent } from "react";
import { choiceAnswer, multiSelectAnswer, singleChoices, SKIPPED_DISPLAY, textAnswer } from "../../lib/answers";
import { fareLines, optionParts } from "../../lib/cardView";
import { INPUT_TYPES, inputId, labelId } from "../../lib/inputs";
import { InputKind } from "../../protocol";
import type { Answer, OpenCard } from "../../state/conversation";
import { cn } from "@/lib/utils";
import { ErrorLine } from "./ErrorLine";

const OPTION =
  "group flex w-full items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3.5 py-3 text-left ring-1 ring-white/10 transition-all outline-none hover:bg-white/[0.06] hover:ring-white/25 focus-visible:ring-2 focus-visible:ring-ring";
const FIELD =
  "h-10 min-w-0 flex-1 rounded-xl bg-white/[0.04] px-3 text-[15px] ring-1 ring-white/12 outline-none placeholder:text-muted-foreground focus:ring-white/35 [color-scheme:dark]";
const ACT =
  "inline-flex min-h-10 flex-1 items-center justify-center rounded-xl px-4 text-sm font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40";
const PRIMARY = cn(ACT, "bg-primary text-primary-foreground hover:brightness-110");
const SECONDARY = cn(ACT, "bg-white/[0.05] text-foreground ring-1 ring-white/12 hover:bg-white/10");

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
        <div key={line.label} className="flex justify-between gap-3 py-0.5 text-muted-foreground">
          <span>{line.label}</span>
          <span className="text-foreground tabular-nums">{line.amount}</span>
        </div>
      ))}
      {fare.other.map((text) => (
        <p key={text} className="mt-0.5 text-[13px] text-muted-foreground">{text}</p>
      ))}
      {fare.lines.filter((line) => line.total).map((line) => (
        <div key={line.label} className="mt-2 flex justify-between gap-3 border-t border-white/10 pt-2 text-[15px] font-semibold">
          <span>{line.label}</span>
          <span className="text-glow tabular-nums">{line.amount}</span>
        </div>
      ))}
      {fare.question && <p className="mt-3 font-medium">{fare.question}</p>}
    </div>
  );
}

function ConfirmControls({ card, onAnswer }: Props) {
  return (
    <>
      <div className="mt-4 flex gap-2" role="group" aria-labelledby={labelId(card.spec)}>
        {singleChoices(card.spec).map((choice) => (
          <button
            key={choice.label}
            type="button"
            className={choice.value === true ? PRIMARY : SECONDARY}
            onClick={() => onAnswer(choiceAnswer(choice))}
          >
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
      <div className="mt-3 flex flex-col gap-2" role="group" aria-labelledby={labelId(card.spec)}>
        {choices.map((choice, i) => {
          if (choice.value === null) return null;
          const parts = optionParts(choice.label);
          return (
            <button key={`${i}:${choice.label}`} type="button" className={OPTION} onClick={() => onAnswer(choiceAnswer(choice))}>
              {parts ? (
                <>
                  <span className="flex min-w-0 flex-col">
                    <span className="text-[15px] font-medium">{parts.title}</span>
                    <span className="text-xs text-muted-foreground">{parts.subtitle}</span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end text-right">
                    <span className="text-xs text-muted-foreground tabular-nums">{parts.price}</span>
                    {parts.note && <span className="text-[13px] font-semibold text-success">{parts.note}</span>}
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
    <form className="mt-3 flex flex-col gap-2" noValidate onSubmit={onSubmit} onChange={() => setError(null)}>
      <div className="flex flex-col gap-2" role="group" aria-labelledby={labelId(spec)}>
        {(spec.options ?? []).map(({ value, label }) => (
          <label key={value} className={cn(OPTION, "cursor-pointer justify-start has-[:checked]:bg-white/[0.07] has-[:checked]:ring-white/30")}>
            <input type="checkbox" checked={checked.includes(value)} onChange={(e) => toggle(value, e.target.checked)} className="size-4 accent-[var(--glow)]" />
            <span className="text-[15px] font-medium">{label || value}</span>
          </label>
        ))}
      </div>
      <div className="flex">
        <button type="submit" className={PRIMARY}>Send</button>
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
    <form className="mt-3 flex flex-col gap-1" noValidate onSubmit={onSubmit}>
      <div className="flex items-center gap-2">
        <input
          id={inputId(spec)}
          className={FIELD}
          type="date"
          min={today()}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setError(null);
          }}
        />
        <button type="submit" className={cn(PRIMARY, "flex-none")} disabled={!value}>Use date</button>
      </div>
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
    <form className="mt-3 flex flex-col gap-1" noValidate onSubmit={onSubmit}>
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
        <button type="submit" className={cn(PRIMARY, "flex-none")} disabled={!text.trim()}>Save</button>
      </div>
      <SkipLink card={card} onAnswer={onAnswer} />
      <ErrorLine message={error} />
    </form>
  );
}

function SkipLink({ card, onAnswer }: Props) {
  if (card.spec.required !== false) return null;
  return (
    <button type="button" className="mt-2 self-start text-[13px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline" onClick={() => onAnswer({ value: null, display: SKIPPED_DISPLAY })}>
      Skip
    </button>
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
