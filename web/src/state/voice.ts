import type { AgentState } from "@livekit/components-react";
import type { LocalAudioTrack, RemoteAudioTrack } from "livekit-client";
import { Role } from "../protocol";
import { CallState, ThreadItemKind, type CallStatus, type ThreadItem } from "./conversation";

/** What the orb and the call controls need to draw the live call. */
export interface VoiceState {
  /** The agent's own state, from its `lk.agent.state` attribute. */
  agentState: AgentState | null;
  agentTrack?: RemoteAudioTrack;
  micTrack?: LocalAudioTrack;
  muted: boolean;
}

export const idleVoice: VoiceState = { agentState: null, muted: false };

/** The orb state: the agent's own state while it is on the call, otherwise one derived from the call. */
export function orbState(call: CallStatus, voice: VoiceState, items: readonly ThreadItem[]): AgentState {
  switch (call.state) {
    case CallState.IDLE:
    case CallState.ENDED:
      return "idle";
    case CallState.ERROR:
      return "failed";
    case CallState.CONNECTING:
    case CallState.RECONNECTING:
      return "connecting";
    case CallState.CONNECTED:
      if (voice.agentState) return voice.agentState;
      // The demo has no agent participant, so read the state from the transcript.
      return lastSpoken(items)?.role === Role.AGENT && !lastSpoken(items)?.final ? "speaking" : "listening";
  }
}

export function lastSpoken(items: readonly ThreadItem[]) {
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    if (item.kind === ThreadItemKind.TRANSCRIPT) return item;
  }
  return undefined;
}

export const ORB_LABELS: Partial<Record<AgentState, string>> = {
  idle: "Ready",
  failed: "Call failed",
  connecting: "Connecting",
  "pre-connect-buffering": "Connecting",
  initializing: "Agent joining",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  disconnected: "Ready",
};
