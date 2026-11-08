import { TriangleAlert } from "lucide-react";
import type { Answer, CardEntry, OpenCard, ThreadItem } from "../../state/conversation";
import { Thread } from "../thread/Thread";
import { NewChatButton } from "./NewChatButton";

interface Props {
  serverLabel: string;
  sessionId: string | null;
  notice: string | null;
  inCall: boolean;
  items: ThreadItem[];
  cards: Record<string, CardEntry>;
  barCard: OpenCard | null;
  onAnswer: (card: OpenCard, answer: Answer) => void;
}

/** The chat side: transcript, agent cards and the typing bar, all tied to the same session as the call. */
export function ChatPanel({ serverLabel, sessionId, notice, inCall, items, cards, barCard, onAnswer }: Props) {
  return (
    <section
      aria-label="Chat"
      className="glass relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-t-3xl border-b-0 lg:m-4 lg:ml-0 lg:rounded-3xl lg:border-b"
    >
      <header className="flex shrink-0 items-center gap-3 border-b border-white/[0.07] px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-medium">Conversation</h2>
          <p className="truncate font-mono text-[10.5px] text-muted-foreground" title={serverLabel}>
            session {sessionId ?? "starting…"}
          </p>
        </div>
        <NewChatButton inCall={inCall} />
      </header>
      {notice && (
        <p role="status" className="mx-3 mt-3 flex items-start gap-2 rounded-xl bg-warning/10 px-3 py-2 text-[13px] text-warning ring-1 ring-warning/25">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span className="min-w-0 [overflow-wrap:anywhere]">{notice}</span>
        </p>
      )}
      <Thread items={items} cards={cards} barCard={barCard} onAnswer={onAnswer} />
    </section>
  );
}
