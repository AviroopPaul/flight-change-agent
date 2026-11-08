import { MessagesSquare } from "lucide-react";

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
      className="relative flex h-9 shrink-0 items-center gap-2 rounded-xl px-3 text-sm text-muted-foreground ring-1 ring-white/10 transition-colors outline-none hover:bg-white/[0.06] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring aria-expanded:bg-white/[0.08] aria-expanded:text-foreground"
    >
      <MessagesSquare className="size-4" />
      <span className="hidden sm:inline">Conversation</span>
      {unread > 0 && (
        <span className="absolute -top-1.5 -right-1.5 grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1 text-[10.5px] font-semibold text-primary-foreground tabular-nums">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </button>
  );
}
