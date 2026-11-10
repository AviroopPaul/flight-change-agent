import { MessagesSquare } from "lucide-react";
import { TOP_BUTTON } from "../stage/topButton";

interface Props {
  open: boolean;
  /** Thread entries added since the drawer was last open. */
  unread: number;
  onToggle: () => void;
}

export function ConversationButton({ open, unread, onToggle }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-controls="conversation"
      aria-label={unread ? `Conversation, ${unread} new` : "Conversation"}
      className={TOP_BUTTON}
    >
      <MessagesSquare className="size-4" />
      <span className="hidden sm:inline">Conversation</span>
      {unread > 0 && (
        <span className="btn-glow absolute -top-1.5 -right-1.5 z-10 grid h-5 min-w-5 place-items-center rounded-full px-1 text-[10.5px] font-bold tabular-nums">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </button>
  );
}
