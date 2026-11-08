import { useState } from "react";
import { useTrackVolume } from "@livekit/components-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import * as config from "./config";
import { ChatPanel } from "./components/chat/ChatPanel";
import { Stage } from "./components/stage/Stage";
import { createDemo } from "./demo/demo";
import { useCall } from "./hooks/useCall";
import { useChat } from "./hooks/useChat";
import { useConversation } from "./hooks/useConversation";
import { useMicDevices } from "./hooks/useMicDevices";
import { useMicLevel } from "./hooks/useMicLevel";
import { useSession } from "./hooks/useSession";
import { initialState, isInCall, ThreadItemKind } from "./state/conversation";
import { lastSpoken, orbState } from "./state/voice";

// Speech RMS rarely passes 0.25, so the demo's raw mic level is scaled up to fill the meters.
const DEMO_GAIN = 4;

export function App() {
  const { state, barCard, ui, submit } = useConversation(() =>
    config.setupProblem ? initialState({ text: "no server configured", disabled: true }, config.setupProblem) : initialState(),
  );
  const session = useSession(config.backend);
  const mics = useMicDevices();
  const call = useCall(ui, config.backend, session.sessionId, mics.deviceId);
  const chat = useChat(ui, config.backend, session.sessionId);
  const notice = state.notice ?? session.error;
  const submitted = state.items.some((item) => item.kind === ThreadItemKind.RECORD);
  const [demo] = useState(() => (config.demo ? createDemo(ui, config.demoPace) : null));

  const controls = demo ?? call;
  const sendInput = demo?.sendInput ?? chat.sendInput;
  const inCall = isInCall(state.call.state);
  const onCall = () => (inCall ? controls.hangUp() : controls.start());

  // The demo has no LiveKit room, so its mute is a local flag that just silences the meters.
  const [demoMuted, setDemoMuted] = useState(false);
  const voice = demo ? { ...call.voice, muted: demoMuted && inCall } : call.voice;
  const onMute = demo ? setDemoMuted : call.setMuted;

  const orb = orbState(state.call, voice, state.items);
  const liveMicLevel = useTrackVolume(voice.micTrack, { fftSize: 512, smoothingTimeConstant: 0.6 });
  const rawDemoLevel = useMicLevel();
  const demoMicLevel = voice.muted ? 0 : Math.min(1, rawDemoLevel * DEMO_GAIN);
  const micLevel = demo ? demoMicLevel : liveMicLevel;
  const caption = lastSpoken(state.items);

  const pickMic = (deviceId: string) => {
    mics.select(deviceId);
    call.switchMic(deviceId);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className="app-bg relative flex h-dvh flex-col overflow-hidden lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(420px,520px)]">
        <Stage
          call={state.call}
          orb={orb}
          voice={voice}
          caption={caption}
          micLevel={micLevel}
          orbVolume={demo && orb === "listening" ? demoMicLevel : undefined}
          mics={mics}
          onCall={onCall}
          onMute={onMute}
          onPickMic={pickMic}
          onStop={chat.optOut}
          stopDisabled={!session.sessionId || submitted || Boolean(demo)}
        />
        <ChatPanel
          serverLabel={config.serverLabel}
          sessionId={session.sessionId}
          notice={notice}
          inCall={inCall}
          items={state.items}
          cards={state.cards}
          barCard={barCard}
          onAnswer={(open, answer) => submit(open.spec, answer, sendInput)}
        />
      </div>
    </TooltipProvider>
  );
}
