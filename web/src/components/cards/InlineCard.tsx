import { useRef, useState, type FormEvent } from "react";
import { choiceAnswer, multiSelectAnswer, singleChoices, SKIPPED_DISPLAY, textAnswer } from "../../lib/answers";
import { fareLines, optionParts } from "../../lib/cardView";
import { INPUT_TYPES, inputId, labelId } from "../../lib/inputs";
import { InputKind } from "../../protocol";
import type { Answer, OpenCard } from "../../state/conversation";
import { ErrorLine } from "./ErrorLine";

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
    <div className="fare">
      {fare.lines.filter((line) => !line.total).map((line) => (
        <div key={line.label} className="fare-row">
          <span>{line.label}</span>
          <span>{line.amount}</span>
        </div>
      ))}
      {fare.other.map((text) => (
        <p key={text} className="fare-note">{text}</p>
      ))}
      {fare.lines.filter((line) => line.total).map((line) => (
        <div key={line.label} className="fare-row total">
          <span>{line.label}</span>
          <span>{line.amount}</span>
        </div>
      ))}
      {fare.question && <p className="fare-question">{fare.question}</p>}
    </div>
  );
}

function ConfirmControls({ card, onAnswer }: Props) {
  return (
    <>
      <div className="actions" role="group" aria-labelledby={labelId(card.spec)}>
        {singleChoices(card.spec).map((choice) => (
          <button
            key={choice.label}
            type="button"
            className={`act${choice.value === true ? " primary" : ""}`}
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
      <div className="options" role="group" aria-labelledby={labelId(card.spec)}>
        {choices.map((choice, i) => {
          if (choice.value === null) return null;
          const parts = optionParts(choice.label);
          return (
            <button key={`${i}:${choice.label}`} type="button" className="option" onClick={() => onAnswer(choiceAnswer(choice))}>
              {parts ? (
                <>
                  <span className="opt-main">
                    <span className="opt-title">{parts.title}</span>
                    <span className="opt-sub">{parts.subtitle}</span>
                  </span>
                  <span className="opt-side">
                    <span className="opt-price">{parts.price}</span>
                    {parts.note && <span className="opt-note">{parts.note}</span>}
                  </span>
                </>
              ) : (
                <span className="opt-title">{choice.label}</span>
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
    <form className="inline-form" noValidate onSubmit={onSubmit} onChange={() => setError(null)}>
      <div className="options" role="group" aria-labelledby={labelId(spec)}>
        {(spec.options ?? []).map(({ value, label }) => (
          <label key={value} className="option check">
            <input type="checkbox" checked={checked.includes(value)} onChange={(e) => toggle(value, e.target.checked)} />
            <span className="opt-title">{label || value}</span>
          </label>
        ))}
      </div>
      <div className="actions">
        <button type="submit" className="act primary">Send</button>
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
    <form className="inline-form" noValidate onSubmit={onSubmit}>
      <div className="row">
        <input
          id={inputId(spec)}
          className="field"
          type="date"
          min={today()}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setError(null);
          }}
        />
        <button type="submit" className="act primary" disabled={!value}>Use date</button>
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
    <form className="inline-form" noValidate onSubmit={onSubmit}>
      <div className="row">
        <input
          ref={inputRef}
          id={inputId(spec)}
          className="field"
          type={INPUT_TYPES[spec.kind] ?? "text"}
          placeholder={spec.placeholder || "Type here"}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setError(null);
          }}
        />
        <button type="submit" className="act primary" disabled={!text.trim()}>Save</button>
      </div>
      <SkipLink card={card} onAnswer={onAnswer} />
      <ErrorLine message={error} />
    </form>
  );
}

function SkipLink({ card, onAnswer }: Props) {
  if (card.spec.required !== false) return null;
  return (
    <button type="button" className="skip" onClick={() => onAnswer({ value: null, display: SKIPPED_DISPLAY })}>
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
