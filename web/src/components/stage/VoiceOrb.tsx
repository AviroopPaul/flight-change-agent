import type { AgentState } from "@livekit/components-react";
import { useTrackVolume } from "@livekit/components-react";
import type { LocalAudioTrack, RemoteAudioTrack } from "livekit-client";
import { AgentAudioVisualizerAura } from "@/components/agents-ui/agent-audio-visualizer-aura";
import { cn } from "@/lib/utils";

interface Props {
  state: AgentState;
  audioTrack?: LocalAudioTrack | RemoteAudioTrack;
  /** Overrides the level read from the track (the demo feeds the mic level). */
  volume?: number;
  live: boolean;
}

const CORE_GLOW =
  "radial-gradient(circle, color-mix(in oklch, var(--glow) 60%, transparent) 0%, color-mix(in oklch, var(--glow-2) 32%, transparent) 45%, transparent 72%)";

/** The agent's presence: LiveKit's Aura shader around a glowing core, inside two slow HUD rings. */
export function VoiceOrb({ state, audioTrack, volume, live }: Props) {
  const trackLevel = useTrackVolume(audioTrack, { fftSize: 512, smoothingTimeConstant: 0.7 });
  const level = Math.min(1, volume ?? trackLevel);
  const speaking = state === "speaking";

  return (
    <div className="relative grid place-items-center" aria-hidden="true">
      <svg
        viewBox="0 0 200 200"
        className={cn(
          "pointer-events-none absolute inset-[-6%] size-[112%] transition-opacity duration-700",
          live ? "opacity-100" : "opacity-40",
        )}
      >
        <defs>
          <linearGradient id="orb-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--glow)" stopOpacity="0.7" />
            <stop offset="100%" stopColor="var(--glow-2)" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <circle className="orb-ring" cx="100" cy="100" r="97" fill="none" stroke="url(#orb-ring)" strokeWidth="0.5" strokeDasharray="1 5" />
        <circle className="orb-ring reverse" cx="100" cy="100" r="90" fill="none" stroke="url(#orb-ring)" strokeWidth="0.8" strokeDasharray="40 120 6 120" strokeLinecap="round" />
      </svg>

      {/* The core breathes slowly and swells with whoever is talking. */}
      <span className={cn("orb-breathe pointer-events-none absolute size-[52%]", !live && "opacity-50")}>
        <span
          className="block size-full rounded-full blur-2xl transition-transform duration-100 ease-out"
          style={{ background: CORE_GLOW, transform: `scale(${1 + level * (speaking ? 0.55 : 0.3)})` }}
        />
      </span>

      <AgentAudioVisualizerAura
        state={state}
        audioTrack={audioTrack}
        volume={volume}
        color="#1FD5F9"
        colorShift={0.35}
        themeMode="dark"
        className={cn("relative transition-[height] duration-500", live ? "h-60 sm:h-72 lg:h-[22rem] xl:h-[26rem]" : "h-48 sm:h-60 lg:h-72 xl:h-80")}
      />
    </div>
  );
}
