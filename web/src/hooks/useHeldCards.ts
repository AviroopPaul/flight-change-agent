import { useEffect, useRef, useState } from "react";
import { Role } from "../protocol";
import { ThreadItemKind, type CardEntry, type ThreadItem } from "../state/conversation";

/** If the agent never speaks (no transcript, a stalled turn), show the card anyway after this long. */
export const HOLD_MAX_MS = 6000;

/** Who said the newest line of the call transcript, if anyone has spoken yet. */
function lastSpeaker(items: readonly ThreadItem[]): Role | null {
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    if (item.kind === ThreadItemKind.TRANSCRIPT) return item.role;
  }
  return null;
}

export interface HoldInput {
  card: CardEntry | undefined;
  items: readonly ThreadItem[];
  inCall: boolean;
  agentSpeaking: boolean;
  waitedMs: number;
}

/**
 * On a call, the agent often opens a card (a tool call) a moment before it answers the caller.
 * A card that pops up before the agent says anything feels out of order, so it waits while the
 * agent has not yet answered the caller's last turn.
 *
 * A card shows once any of these holds:
 * - there is no live call (chat only, or the call ended);
 * - the agent is speaking, or the newest spoken line is the agent's (it asked, then opened the card);
 * - the card is back after a rejected answer (the user is mid-task);
 * - it has waited HOLD_MAX_MS.
 */
export function cardReady({ card, items, inCall, agentSpeaking, waitedMs }: HoldInput): boolean {
  return (
    !inCall ||
    agentSpeaking ||
    Boolean(card?.error) ||
    (card?.version ?? 0) > 0 ||
    lastSpeaker(items) === Role.AGENT ||
    waitedMs >= HOLD_MAX_MS
  );
}

/** The open cards that may float now, in order. Once shown, a card stays shown until it closes. */
export function useHeldCards(
  ids: readonly string[],
  items: readonly ThreadItem[],
  cards: Record<string, CardEntry>,
  inCall: boolean,
  agentSpeaking: boolean,
): string[] {
  const shown = useRef(new Set<string>());
  const firstSeen = useRef(new Map<string, number>());
  const [, wake] = useState(0);
  const now = Date.now();

  for (const id of ids) {
    if (!firstSeen.current.has(id)) firstSeen.current.set(id, now);
    if (shown.current.has(id)) continue;
    const waitedMs = now - (firstSeen.current.get(id) ?? now);
    if (cardReady({ card: cards[id], items, inCall, agentSpeaking, waitedMs })) shown.current.add(id);
  }

  const waiting = ids.filter((id) => !shown.current.has(id));
  const waitKey = waiting.join(",");
  useEffect(() => {
    if (!waiting.length) return;
    // Re-check when the oldest waiting card hits the time limit.
    const due = Math.min(...waiting.map((id) => (firstSeen.current.get(id) ?? Date.now()) + HOLD_MAX_MS));
    const timer = setTimeout(() => wake((n) => n + 1), Math.max(0, due - Date.now()) + 20);
    return () => clearTimeout(timer);
  }, [waitKey]);

  return ids.filter((id) => shown.current.has(id));
}
