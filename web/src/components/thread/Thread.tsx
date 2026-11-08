import { useRef } from "react";
import { MessagesSquare } from "lucide-react";
import { useFollowBottom } from "../../hooks/useFollowBottom";
import type { Answer, CardEntry, OpenCard, ThreadItem } from "../../state/conversation";
import { Composer } from "../cards/Composer";
import { ThreadEntry } from "./ThreadEntry";

interface Props {
  items: ThreadItem[];
  cards: Record<string, CardEntry>;
  barCard: OpenCard | null;
  onAnswer: (card: OpenCard, answer: Answer) => void;
}

export function Thread({ items, cards, barCard, onAnswer }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useFollowBottom(scrollRef, items, cards);
  return (
    <>
      <div ref={scrollRef} className="thin-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5">
        <div className="mx-auto flex max-w-2xl flex-col gap-3" role="log" aria-label="Conversation">
          {!items.length && <EmptyThread />}
          {items.map((item, i) => (
            <ThreadEntry key={item.key} item={item} prev={items[i - 1]} cards={cards} onAnswer={onAnswer} />
          ))}
        </div>
      </div>
      <Composer card={barCard} onAnswer={(answer) => barCard && onAnswer(barCard, answer)} />
    </>
  );
}

function EmptyThread() {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <span className="grid size-11 place-items-center rounded-2xl bg-white/[0.05] ring-1 ring-white/10">
        <MessagesSquare className="size-5 text-glow" />
      </span>
      <p className="max-w-xs text-sm text-balance text-muted-foreground">
        The live transcript appears here. The agent also asks for things like your booking reference here.
      </p>
    </div>
  );
}
