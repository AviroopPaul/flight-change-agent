import type { ReactNode } from "react";
import type { AgentState } from "@livekit/components-react";
import { Headphones, Loader2, OctagonX, Phone, PhoneCall, PhoneOff, Plane } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { MicDevices } from "@/hooks/useMicDevices";
import { cn } from "@/lib/utils";
import { Role } from "@/protocol";
import { CallState, isInCall, type CallStatus, type ThreadItem } from "@/state/conversation";
import { ORB_LABELS, type VoiceState } from "@/state/voice";
import { MicControl } from "./MicControl";
import { VoiceOrb } from "./VoiceOrb";

type Spoken = Extract<ThreadItem, { role: Role; final: boolean }>;

interface Props {
  call: CallStatus;
  orb: AgentState;
  voice: VoiceState;
  /** The newest line of the call transcript, shown as a live caption under the orb. */
  caption?: Spoken;
  micLevel: number;
  orbVolume?: number;
  mics: MicDevices;
  onCall: () => void;
  onMute: (muted: boolean) => void;
  onPickMic: (deviceId: string) => void;
  onStop: () => void;
  stopDisabled: boolean;
  /** The top bar buttons: New chat, Debug and Conversation. */
  actions: ReactNode;
  /** A call happened earlier and the request is still open: the call button offers to call back. */
  callBack: boolean;
}

export function Stage({ call, orb, voice, caption, micLevel, orbVolume, mics, onCall, onMute, onPickMic, onStop, stopDisabled, actions, callBack }: Props) {
  const inCall = isInCall(call.state);
  const live = call.state === CallState.CONNECTED;
  const orbTrack = orb === "speaking" ? voice.agentTrack : orb === "listening" && !voice.muted ? voice.micTrack : undefined;
  const statusText =
    call.state === CallState.ERROR ? call.text
    : call.state === CallState.RECONNECTING ? "Reconnecting"
    : voice.muted && live ? "Muted"
    : ORB_LABELS[orb] ?? call.text;

  return (
    <section
      aria-label="Voice call"
      className="relative flex h-full flex-col items-center px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1.25rem,env(safe-area-inset-bottom))] lg:px-8 lg:pt-6"
    >
      <div className="flex w-full items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="glass grid size-9 shrink-0 place-items-center rounded-[0.8rem]">
            <Plane className="size-[17px] text-glow-2" />
          </span>
          <div className="min-w-0 leading-tight">
            <p className="text-sm font-medium tracking-tight">Flight change</p>
            <p className="text-[11px] text-muted-foreground">AI voice agent</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      </div>

      {/* The orb shows the call state. Words appear only when something is wrong; screen readers always get them. */}
      <p
        role="status"
        aria-live="polite"
        className={cn(
          "mt-3 text-center text-[13px] lg:mt-0",
          call.state === CallState.ERROR ? "text-destructive" : call.state === CallState.RECONNECTING ? "text-muted-foreground" : "sr-only",
        )}
      >
        {statusText}
      </p>

      {/* The orb and caption take the free space; the dock stays at the bottom like a phone call. */}
      <div className="flex min-h-0 w-full flex-1 flex-col items-center justify-center gap-5 lg:gap-7">
        <VoiceOrb state={orb} audioTrack={orbTrack} volume={orbVolume} live={inCall} />
        <Caption inCall={inCall} connecting={call.state === CallState.CONNECTING} caption={caption} callBack={callBack} />
      </div>

      <div className="glass flex items-center gap-2 rounded-full p-2">
        <MicControl inCall={live} muted={voice.muted} level={micLevel} mics={mics} onMute={onMute} onPick={onPickMic} />
        <CallButton call={call} onCall={onCall} callBack={callBack} />
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Stop request"
              disabled={stopDisabled}
              onClick={onStop}
              className="flex h-12 min-w-12 items-center justify-center gap-2 rounded-full px-3 text-sm text-muted-foreground transition-colors outline-none hover:bg-destructive/10 hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-35"
            >
              <OctagonX className="size-[18px]" />
              <span className="hidden pr-1 sm:inline">Stop request</span>
            </button>
          </TooltipTrigger>
          <TooltipContent>Stop this flight change request</TooltipContent>
        </Tooltip>
      </div>

      <p className="mt-3 hidden items-center gap-1.5 text-[11px] text-muted-foreground/70 lg:flex">
        <Headphones className="size-3.5" /> Headphones work best. You can talk over the agent at any time.
      </p>
    </section>
  );
}

function CallButton({ call, onCall, callBack }: { call: CallStatus; onCall: () => void; callBack: boolean }) {
  const inCall = isInCall(call.state);
  const connecting = call.state === CallState.CONNECTING || call.state === CallState.RECONNECTING;
  return (
    <button
      type="button"
      onClick={onCall}
      disabled={call.disabled}
      aria-label={inCall ? "End call" : callBack ? "Call me back" : "Start call"}
      className={cn(
        "flex h-12 items-center justify-center gap-2 rounded-full px-5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40",
        inCall
          ? "btn-danger min-w-12"
          : "btn-glow min-w-40 font-semibold",
      )}
    >
      {connecting ? <Loader2 className="size-5 animate-spin" /> : inCall ? <PhoneOff className="size-5" /> : callBack ? <PhoneCall className="size-[18px]" strokeWidth={2.3} /> : <Phone className="size-[18px]" strokeWidth={2.3} />}
      <span className={cn(inCall && "sr-only sm:not-sr-only")}>{inCall ? (connecting ? "Cancel" : "End") : callBack ? "Call me back" : "Start call"}</span>
    </button>
  );
}

function Caption({ inCall, connecting, caption, callBack }: { inCall: boolean; connecting: boolean; caption?: Spoken; callBack: boolean }) {
  if (!inCall && callBack) {
    return (
      <p className="max-w-sm text-center text-sm text-balance text-muted-foreground">
        The call ended. Tap Call me back and the agent picks up where you left off, or keep going in the cards.
      </p>
    );
  }
  if (!inCall) {
    return (
      <p className="max-w-sm text-center text-sm text-balance text-muted-foreground">
        Start a call and talk to the agent. Anything hard to say, it asks for in a card here.
      </p>
    );
  }
  if (connecting || !caption) {
    return (
      <p className="min-h-10 max-w-sm text-center text-sm text-muted-foreground">
        {connecting ? "Connecting to the agent. This can take a few seconds." : "Say hello to begin."}
      </p>
    );
  }
  const you = caption.role === Role.USER;
  return (
    <div className="flex min-h-10 max-w-xl flex-col items-center gap-1 text-center">
      <span className={cn("font-mono text-[10px] tracking-[0.18em] uppercase", you ? "text-muted-foreground" : "text-glow")}>
        {you ? "You" : "Agent"}
      </span>
      <p
        className={cn(
          "line-clamp-2 text-base leading-snug font-light text-balance lg:line-clamp-3 lg:text-[1.375rem]",
          caption.final ? "text-foreground/90" : "shimmer",
        )}
      >
        {caption.text}
      </p>
    </div>
  );
}
