import type { ReactNode } from "react";
import { X } from "lucide-react";
import type { Answer, CardEntry, OpenCard, ThreadItem } from "../../state/conversation";
import { Thread } from "../thread/Thread";

interface Props {
  serverLabel: string;
  sessionId: string | null;
  open: boolean;
  onClose: () => void;
  items: ThreadItem[];
  cards: Record<string, CardEntry>;
  barCard: OpenCard | null;
  onAnswer: (card: OpenCard, answer: Answer) => void;
  /** Shown after the last entry, e.g. the Call me back action. */
  footer?: ReactNode;
}

/**
 * The full conversation: transcript, agent cards and the typing bar. It is a drawer, closed by default;
 * the page is voice first and the floating cards collect input while it is closed.
 */
export function ChatPanel({ serverLabel, sessionId, open, onClose, items, cards, barCard, onAnswer, footer }: Props) {
  return (
    <aside
      id="conversation"
      aria-label="Conversation"
      aria-hidden={!open}
      inert={!open}
      className={`fixed inset-y-0 right-0 z-40 flex w-full transition-transform duration-300 ease-out sm:w-[440px] lg:p-3 ${open ? "translate-x-0" : "translate-x-full"}`}
    >
      <section className="glass-panel flex min-h-0 flex-1 flex-col overflow-hidden lg:rounded-[2rem]">
        <header className="flex shrink-0 items-center gap-2 border-b border-white/[0.07] px-5 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-medium">Conversation</h2>
            <p className="truncate font-mono text-[10.5px] text-muted-foreground" title={serverLabel}>
              session {sessionId ?? "starting…"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close conversation"
            className="well grid size-9 place-items-center rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" />
          </button>
        </header>
        <Thread items={items} cards={cards} barCard={barCard} onAnswer={onAnswer} interactive={open} footer={footer} />
      </section>
    </aside>
  );
}
