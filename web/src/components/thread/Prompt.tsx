import { fareLines } from "../../lib/cardView";
import { inputId, isChoiceKind, labelId } from "../../lib/inputs";
import { InputKind } from "../../protocol";
import { CardStatus, toOpenCard, usesTextBar, type Answer, type CardEntry, type OpenCard } from "../../state/conversation";
import { FareTable, InlineCard } from "../cards/InlineCard";

interface Props {
  id: string;
  entry: CardEntry;
  onAnswer: (card: OpenCard, answer: Answer) => void;
}

/** A question from the agent, in the thread. Its answer controls sit inside it, except typed answers (text bar). */
export function Prompt({ id, entry, onAnswer }: Props) {
  const { spec, status } = entry;
  const open = status === CardStatus.OPEN;
  const inline = open && !usesTextBar(spec);
  const isFare = spec.kind === InputKind.CONFIRM && fareLines(spec.label) !== null;
  const text = spec.label || spec.field || "Input";
  const card = toOpenCard(id, entry);
  const labelled = isChoiceKind(spec.kind) || !inline;

  return (
    <div className={`bubble agent prompt${inline ? " asking" : ""}${status === CardStatus.CANCELLED ? " closed" : ""}`}>
      {isFare ? (
        <div className="card-label" id={labelId(spec)}><FareTable label={spec.label} /></div>
      ) : labelled ? (
        <span className="card-label" id={labelId(spec)}>{text}</span>
      ) : (
        <label className="card-label" id={labelId(spec)} htmlFor={inputId(spec)}>{text}</label>
      )}
      {spec.help && <p className="card-help">{spec.help}</p>}
      {open && usesTextBar(spec) && <p className="card-hint">Type your answer below.</p>}
      {inline && <InlineCard key={card.key} card={card} onAnswer={(answer) => onAnswer(card, answer)} />}
    </div>
  );
}
