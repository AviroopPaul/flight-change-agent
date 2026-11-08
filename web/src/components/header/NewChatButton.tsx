import { newChatUrl } from "../../config";
import { NewChatIcon } from "../icons";

interface Props {
  inCall: boolean;
}

/**
 * Starts a fresh session with an empty thread. A full page load resets the chat socket,
 * the call and the thread in one step. The old session stays on the server; its URL still opens it.
 */
export function NewChatButton({ inCall }: Props) {
  const onClick = () => {
    if (inCall && !window.confirm("End the call and start a new chat?")) return;
    location.assign(newChatUrl());
  };
  return (
    <button className="icon-btn" type="button" onClick={onClick} aria-label="New chat" title="New chat">
      <NewChatIcon />
    </button>
  );
}
