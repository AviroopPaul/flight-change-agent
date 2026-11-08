import { SquarePen } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { newChatUrl } from "../../config";

/**
 * Starts a fresh session with an empty thread. A full page load resets the chat socket,
 * the call and the thread in one step. The old session stays on the server; its URL still opens it.
 */
export function NewChatButton({ inCall }: { inCall: boolean }) {
  const onClick = () => {
    if (inCall && !window.confirm("End the call and start a new chat?")) return;
    location.assign(newChatUrl());
  };
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          aria-label="New chat"
          className="grid size-9 place-items-center rounded-xl text-muted-foreground ring-1 ring-white/10 transition-colors outline-none hover:bg-white/[0.06] hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <SquarePen className="size-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent>New chat</TooltipContent>
    </Tooltip>
  );
}
