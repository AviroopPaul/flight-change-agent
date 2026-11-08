import { ThreadItemKind, type Answer, type CardEntry, type OpenCard, type ThreadItem } from "../../state/conversation";
import { RecordCard } from "../record/RecordCard";
import { AnswerBubble } from "./AnswerBubble";
import { Message } from "./Message";
import { Note } from "./Note";
import { Prompt } from "./Prompt";
import { Transcript } from "./Transcript";

interface Props {
  item: ThreadItem;
  prev?: ThreadItem;
  cards: Record<string, CardEntry>;
  onAnswer: (card: OpenCard, answer: Answer) => void;
}

export function ThreadEntry({ item, prev, cards, onAnswer }: Props) {
  switch (item.kind) {
    case ThreadItemKind.NOTE:
      return <Note text={item.text} />;
    case ThreadItemKind.TRANSCRIPT:
      return <Transcript role={item.role} text={item.text} final={item.final} time={item.time} />;
    case ThreadItemKind.MESSAGE:
      return <Message role={item.role} text={item.text} time={item.time} />;
    case ThreadItemKind.PROMPT:
      return cards[item.id] ? <Prompt id={item.id} entry={cards[item.id]} onAnswer={onAnswer} /> : null;
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
