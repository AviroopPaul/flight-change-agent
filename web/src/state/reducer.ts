import { Role } from "../protocol";
import { ActionType, type Action, type ActionOf } from "./actions";
import { CallState, CardStatus, ThreadItemKind, type CardEntry, type ConversationState, type ThreadItem } from "./conversation";

const DEFAULT_REJECT_MESSAGE = "Please check this value and try again.";

export function conversationReducer(state: ConversationState, action: Action): ConversationState {
  switch (action.type) {
    case ActionType.SET_CALL:
      return setCall(state, action);
    case ActionType.SET_NOTICE:
      return { ...state, notice: action.text };
    case ActionType.ADD_NOTE:
      return addNote(state, action);
    case ActionType.ADD_TRANSCRIPT:
      return addTranscript(state, action);
    case ActionType.ADD_MESSAGE:
      return addMessage(state, action);
    case ActionType.SHOW_RECORD:
      return showRecord(state, action);
    case ActionType.SHOW_CARD:
      return showCard(state, action);
    case ActionType.REJECT_CARD:
      return rejectCard(state, action);
    case ActionType.CANCEL_CARD:
      return cancelCard(state, action);
    case ActionType.SUBMIT_CARD:
      return submitCard(state, action);
    case ActionType.ACK_ANSWER:
      return ackAnswer(state, action);
  }
}

const toRole = (role: string): Role => (role === Role.USER ? Role.USER : Role.AGENT);

function setCall(state: ConversationState, { state: callState, text, now }: ActionOf<ActionType.SET_CALL>): ConversationState {
  const connectedAt = callState === CallState.CONNECTED ? now : null;
  return { ...state, call: { ...state.call, state: callState, text, connectedAt } };
}

function addNote(state: ConversationState, { text, key }: ActionOf<ActionType.ADD_NOTE>): ConversationState {
  return { ...state, items: [...state.items, { kind: ThreadItemKind.NOTE, key, text }] };
}

function addTranscript(state: ConversationState, { msg, key, time }: ActionOf<ActionType.ADD_TRANSCRIPT>): ConversationState {
  const { role, final, id } = msg;
  const text = msg.text || "";
  const lineKey = id ? `id:${id}` : `role:${role}`;
  const items = [...state.items];
  const transcripts = { ...state.transcripts };
  const index = items.findIndex((item) => item.key === transcripts[lineKey]);
  const existing = index >= 0 ? items[index] : undefined;
  if (existing?.kind === ThreadItemKind.TRANSCRIPT) {
    items[index] = { ...existing, text, final };
  } else {
    items.push({ kind: ThreadItemKind.TRANSCRIPT, key, role: toRole(role), text, final, time });
  }
  if (final && !id) delete transcripts[lineKey];
  else transcripts[lineKey] = existing?.key ?? key;
  return { ...state, items, transcripts };
}

function addMessage(state: ConversationState, { msg, key, time }: ActionOf<ActionType.ADD_MESSAGE>): ConversationState {
  const { id, role } = msg;
  if (id && state.items.some((item) => item.kind === ThreadItemKind.MESSAGE && item.id === id)) return state;
  const message: ThreadItem = { kind: ThreadItemKind.MESSAGE, key, id, role: toRole(role), text: msg.text || "", time };
  return { ...state, items: [...state.items, message] };
}

function showRecord(state: ConversationState, { record, key }: ActionOf<ActionType.SHOW_RECORD>): ConversationState {
  const index = state.items.findIndex((item) => item.kind === ThreadItemKind.RECORD);
  const items = [...state.items];
  if (index >= 0) items[index] = { kind: ThreadItemKind.RECORD, key: items[index].key, record };
  else items.push({ kind: ThreadItemKind.RECORD, key, record });
  return { ...state, items };
}

function ackAnswer(state: ConversationState, { key }: ActionOf<ActionType.ACK_ANSWER>): ConversationState {
  const index = state.items.findIndex((item) => item.key === key);
  const item = index >= 0 ? state.items[index] : undefined;
  if (item?.kind !== ThreadItemKind.ANSWER) return state;
  const items = [...state.items];
  items[index] = { ...item, acked: true };
  return { ...state, items };
}

function setCard(state: ConversationState, id: string, entry: CardEntry, items = state.items): ConversationState {
  return { ...state, items, cards: { ...state.cards, [id]: entry } };
}

/** A new question from the server: it shows at once, in the thread, wherever the conversation is. */
function showCard(state: ConversationState, { spec, key }: ActionOf<ActionType.SHOW_CARD>): ConversationState {
  if (!spec.id || state.cards[spec.id]) return state;
  const items: ThreadItem[] = [...state.items, { kind: ThreadItemKind.PROMPT, key: `${key}:prompt`, id: spec.id }];
  return setCard(state, spec.id, { spec, status: CardStatus.OPEN, error: null, version: 0 }, items);
}

/** The server (or the send) refused the answer: drop the answer bubble and reopen the card at the end. */
function rejectCard(state: ConversationState, { id, message }: ActionOf<ActionType.REJECT_CARD>): ConversationState {
  const entry = state.cards[id];
  if (entry?.status !== CardStatus.OPEN && entry?.status !== CardStatus.SUBMITTED) return state;
  const prompt = state.items.find((item) => item.kind === ThreadItemKind.PROMPT && item.id === id);
  const items = state.items.filter((item) => item.key !== entry.answerKey && item !== prompt);
  if (prompt) items.push(prompt);
  return setCard(
    state,
    id,
    { ...entry, status: CardStatus.OPEN, error: message || DEFAULT_REJECT_MESSAGE, version: entry.version + 1, answerKey: undefined },
    items,
  );
}

function cancelCard(state: ConversationState, { id, reason, key }: ActionOf<ActionType.CANCEL_CARD>): ConversationState {
  const entry = state.cards[id];
  if (!entry || entry.status === CardStatus.CANCELLED) return state;
  const items = [...state.items];
  if (entry.status === CardStatus.OPEN) {
    const suffix = reason ? ` (${reason})` : "";
    items.push({ kind: ThreadItemKind.NOTE, key, text: `${entry.spec.label}: no longer needed${suffix}` });
  }
  return setCard(state, id, { ...entry, status: CardStatus.CANCELLED }, items);
}

function submitCard(state: ConversationState, { id, answer, key, time }: ActionOf<ActionType.SUBMIT_CARD>): ConversationState {
  const entry = state.cards[id];
  if (entry?.status !== CardStatus.OPEN) return state;
  const items: ThreadItem[] = [...state.items, { kind: ThreadItemKind.ANSWER, key, spec: entry.spec, answer, acked: false, time }];
  return setCard(state, id, { ...entry, status: CardStatus.SUBMITTED, error: null, last: answer, answerKey: key }, items);
}
