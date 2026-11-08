import { InputKind, type FinalRecord, type InputRequest, type InputValue, type Role } from "../protocol";

export enum CallState {
  IDLE = "idle",
  CONNECTING = "connecting",
  CONNECTED = "connected",
  RECONNECTING = "reconnecting",
  ENDED = "ended",
  ERROR = "error",
}

export const isInCall = (state: CallState): boolean =>
  state === CallState.CONNECTING || state === CallState.CONNECTED || state === CallState.RECONNECTING;

export interface CallStatus {
  state: CallState;
  text: string;
  connectedAt: number | null;
  disabled: boolean;
}

export interface Answer {
  value: InputValue;
  display?: string;
  files?: File[];
}

export enum ThreadItemKind {
  NOTE = "note",
  TRANSCRIPT = "transcript",
  MESSAGE = "message",
  PROMPT = "prompt",
  ANSWER = "answer",
  RECORD = "record",
}

export type ThreadItem =
  | { kind: ThreadItemKind.NOTE; key: string; text: string }
  | { kind: ThreadItemKind.TRANSCRIPT; key: string; role: Role; text: string; final: boolean; time: string }
  | { kind: ThreadItemKind.MESSAGE; key: string; id?: string; role: Role; text: string; time: string }
  | { kind: ThreadItemKind.PROMPT; key: string; id: string }
  | { kind: ThreadItemKind.ANSWER; key: string; spec: InputRequest; answer: Answer; acked: boolean; time: string }
  | { kind: ThreadItemKind.RECORD; key: string; record: FinalRecord };

export enum CardStatus {
  QUEUED = "queued",
  OPEN = "open",
  SUBMITTED = "submitted",
  CANCELLED = "cancelled",
}

export interface CardEntry {
  spec: InputRequest;
  status: CardStatus;
  error: string | null;
  /** Bumped when the card reopens, so its form remounts with the last answer and the error. */
  version: number;
  last?: Answer;
  answerKey?: string;
}

export interface OpenCard {
  key: string;
  spec: InputRequest;
  error: string | null;
  previous?: Answer;
}

export interface ConversationState {
  call: CallStatus;
  notice: string | null;
  items: ThreadItem[];
  transcripts: Record<string, string>;
  cards: Record<string, CardEntry>;
}

export function initialState(call: Partial<CallStatus> = {}, notice: string | null = null): ConversationState {
  return {
    call: { state: CallState.IDLE, text: "online", connectedAt: null, disabled: false, ...call },
    notice,
    items: [],
    transcripts: {},
    cards: {},
  };
}

const BAR_KINDS: ReadonlySet<InputKind> = new Set([
  InputKind.TEXT, InputKind.EMAIL, InputKind.PHONE, InputKind.NUMBER, InputKind.FILE,
]);

/**
 * Required typed answers use the text bar at the bottom. Everything else (dates, choices, flights,
 * the fare, optional questions) is answered inside its card in the thread.
 */
export const usesTextBar = (spec: InputRequest): boolean => spec.required !== false && BAR_KINDS.has(spec.kind);

export function toOpenCard(id: string, entry: CardEntry): OpenCard {
  return { key: `${id}:${entry.version}`, spec: entry.spec, error: entry.error, previous: entry.last };
}

/** The open card that the text bar answers, if any (the server opens at most one required card). */
export function selectBarCard(cards: Record<string, CardEntry>): OpenCard | null {
  const found = Object.entries(cards).find(([, e]) => e.status === CardStatus.OPEN && usesTextBar(e.spec));
  return found ? toOpenCard(found[0], found[1]) : null;
}
