import { useFollowBottom } from "../../hooks/useFollowBottom";
import type { Answer, CardEntry, OpenCard, ThreadItem } from "../../state/conversation";
import { Composer } from "../cards/Composer";
import { ThreadEntry } from "./ThreadEntry";

interface Props {
  serverLabel: string;
  sessionId: string;
  items: ThreadItem[];
  cards: Record<string, CardEntry>;
  barCard: OpenCard | null;
  onAnswer: (card: OpenCard, answer: Answer) => void;
}

export function Thread({ serverLabel, sessionId, items, cards, barCard, onAnswer }: Props) {
  useFollowBottom(items, cards);
  return (
    <main className="thread">
      <div className="log" role="log" aria-label="Conversation">
        <p className="note">
          {serverLabel} · session <code>{sessionId}</code>
        </p>
        {!items.length && (
          <p className="note empty">Tap the phone icon to start the call. The agent will ask for details here.</p>
        )}
        {items.map((item, i) => (
          <ThreadEntry key={item.key} item={item} prev={items[i - 1]} cards={cards} onAnswer={onAnswer} />
        ))}
      </div>
      <Composer card={barCard} onAnswer={(answer) => barCard && onAnswer(barCard, answer)} />
    </main>
  );
}
