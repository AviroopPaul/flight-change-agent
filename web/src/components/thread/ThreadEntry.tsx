import { Role } from "../../protocol";
import { ThreadItemKind, type Answer, type CardEntry, type OpenCard, type ThreadItem } from "../../state/conversation";
import { RecordCard } from "../record/RecordCard";
import { AnswerBubble } from "./AnswerBubble";
import { Message } from "./Message";
import { Note } from "./Note";
import { Prompt } from "./Prompt";

interface Props {
  item: ThreadItem;
  prev?: ThreadItem;
  cards: Record<string, CardEntry>;
  onAnswer: (card: OpenCard, answer: Answer) => void;
  interactive: boolean;
}

/** True when an entry is spoken or written by the agent, so it sits on the agent's side. */
const agentSide = (item?: ThreadItem): boolean =>
  item?.kind === ThreadItemKind.PROMPT ||
  ((item?.kind === ThreadItemKind.TRANSCRIPT || item?.kind === ThreadItemKind.MESSAGE) && item.role === Role.AGENT);

export function ThreadEntry({ item, prev, cards, onAnswer, interactive }: Props) {
  // Consecutive agent entries share one avatar, like one speaker continuing.
  const grouped = agentSide(item) && agentSide(prev);
  switch (item.kind) {
    case ThreadItemKind.NOTE:
      return <Note text={item.text} />;
    case ThreadItemKind.TRANSCRIPT:
      return <Message role={item.role} text={item.text} time={item.time} spoken partial={!item.final} grouped={grouped} />;
    case ThreadItemKind.MESSAGE:
      return <Message role={item.role} text={item.text} time={item.time} grouped={grouped} />;
    case ThreadItemKind.PROMPT:
      return cards[item.id] ? <Prompt id={item.id} entry={cards[item.id]} onAnswer={onAnswer} grouped={grouped} interactive={interactive} /> : null;
    case ThreadItemKind.ANSWER:
      return (
        <AnswerBubble
          spec={item.spec}
          answer={item.answer}
          acked={item.acked}
          time={item.time}
          caption={!(prev?.kind === ThreadItemKind.PROMPT && prev.id === item.spec.id)}
        />
      );
    case ThreadItemKind.RECORD:
      return <RecordCard record={item.record} />;
  }
}
