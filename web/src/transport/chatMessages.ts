import { ChatServerMessageType, type ChatServerMessage } from "../protocol";
import type { Ui } from "../state/ui";
import { parseMessage } from "./socket";

export function handleChatMessage(ui: Ui, data: unknown): void {
  const msg = parseMessage<ChatServerMessage>(data);
  switch (msg?.type) {
    case ChatServerMessageType.MESSAGE:
      if (msg.spoken) ui.addTranscript({ role: msg.role, text: msg.text, final: true, id: msg.id });
      else ui.addMessage(msg);
      break;
    case ChatServerMessageType.INPUT_REQUEST:
      ui.showInputCard(msg);
      break;
    case ChatServerMessageType.INPUT_ERROR:
      ui.rejectInputCard(msg.requestId, msg.message);
      break;
    case ChatServerMessageType.INPUT_CANCEL:
      ui.cancelInputCard(msg.requestId, msg.reason);
      break;
    case ChatServerMessageType.RECORD:
      ui.showRecord(msg.record);
      break;
    case undefined:
      break;
    default:
      // Unknown types are ignored at runtime; this makes the compiler flag a known type left unhandled.
      msg satisfies never;
  }
}
