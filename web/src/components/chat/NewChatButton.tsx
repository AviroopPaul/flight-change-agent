import { SquarePen } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { newChatUrl } from "../../config";
import { TOP_BUTTON } from "../stage/topButton";

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
        <button type="button" onClick={onClick} aria-label="New chat" className={TOP_BUTTON}>
          <SquarePen className="size-4" />
          <span className="hidden sm:inline">New chat</span>
        </button>
      </TooltipTrigger>
      <TooltipContent>Start a new session</TooltipContent>
    </Tooltip>
  );
}
