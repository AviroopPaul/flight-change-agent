import { CallState, type CallStatus } from "../../state/conversation";

/** Shows while the agent is joining (it may be cold-starting) or while the call reconnects. */
export function Banner({ call }: { call: CallStatus }) {
  let text: string | null = null;
  if (call.state === CallState.CONNECTING) text = "Connecting to the agent… This can take a few seconds.";
  if (call.state === CallState.RECONNECTING) text = "Reconnecting…";
  if (!text) return null;
  return (
    <p className="banner" role="status" aria-live="polite">
      {text}
    </p>
  );
}
