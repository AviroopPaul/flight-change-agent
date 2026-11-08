import { useEffect, useState } from "react";
import { useTrackVolume } from "@livekit/components-react";
import { TriangleAlert } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import * as config from "./config";
import { ChatPanel } from "./components/chat/ChatPanel";
import { ConversationButton } from "./components/chat/ConversationButton";
import { FloatingCards } from "./components/float/FloatingCards";
import { Stage } from "./components/stage/Stage";
import { createDemo } from "./demo/demo";
import { useCall } from "./hooks/useCall";
import { useChat } from "./hooks/useChat";
import { useConversation } from "./hooks/useConversation";
import { useMicDevices } from "./hooks/useMicDevices";
import { useMicLevel } from "./hooks/useMicLevel";
import { useSession } from "./hooks/useSession";
import { initialState, isInCall, ThreadItemKind, type Answer, type OpenCard, type ThreadItem } from "./state/conversation";
import { lastSpoken, orbState } from "./state/voice";

// Speech RMS rarely passes 0.25, so the demo's raw mic level is scaled up to fill the meters.
const DEMO_GAIN = 4;

type RecordItem = Extract<ThreadItem, { kind: ThreadItemKind.RECORD }>;

const latestRecord = (items: ThreadItem[]): RecordItem | undefined =>
  items.findLast((item): item is RecordItem => item.kind === ThreadItemKind.RECORD);

export function App() {
  const { state, barCard, ui, submit } = useConversation(() =>
    config.setupProblem ? initialState({ text: "no server configured", disabled: true }, config.setupProblem) : initialState(),
  );
  const session = useSession(config.backend);
  const mics = useMicDevices();
  const call = useCall(ui, config.backend, session.sessionId, mics.deviceId);
  const chat = useChat(ui, config.backend, session.sessionId);
  const notice = state.notice ?? session.error;
  const record = latestRecord(state.items);
  const [demo] = useState(() => (config.demo ? createDemo(ui, config.demoPace) : null));

  const controls = demo ?? call;
  const sendInput = demo?.sendInput ?? chat.sendInput;
  const inCall = isInCall(state.call.state);
  const onCall = () => (inCall ? controls.hangUp() : controls.start());
  const onAnswer = (open: OpenCard, answer: Answer) => submit(open.spec, answer, sendInput);

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

  // Voice first: the conversation drawer starts closed and counts what arrives while it is shut.
  const [paneOpen, setPaneOpen] = useState(false);
  const [seen, setSeen] = useState(0);
  const itemCount = state.items.length;
  useEffect(() => {
    if (paneOpen) setSeen(itemCount);
  }, [paneOpen, itemCount]);
  useEffect(() => {
    if (!paneOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setPaneOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paneOpen]);
  const unread = paneOpen ? 0 : Math.max(0, itemCount - seen);

  // The final record floats until closed; a new revision has a new key, so it floats again.
  const [closedRecord, setClosedRecord] = useState<string | null>(null);
  const floatingRecord = record && record.key !== closedRecord ? record.record : null;

  const pickMic = (deviceId: string) => {
    mics.select(deviceId);
    call.switchMic(deviceId);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className="app-bg relative h-dvh overflow-hidden">
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
          stopDisabled={!session.sessionId || Boolean(record) || Boolean(demo)}
          conversationButton={<ConversationButton open={paneOpen} unread={unread} onToggle={() => setPaneOpen((o) => !o)} />}
        />

        {notice && (
          <p
            role="status"
            className="fixed top-[calc(4.5rem+env(safe-area-inset-top))] left-1/2 z-50 flex w-[min(92vw,560px)] -translate-x-1/2 items-start gap-2 rounded-xl bg-[oklch(0.22_0.04_80/0.95)] px-3 py-2 text-[13px] text-warning ring-1 ring-warning/30 backdrop-blur-xl"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            <span className="min-w-0 [overflow-wrap:anywhere]">{notice}</span>
          </p>
        )}

        {!paneOpen && (
          <FloatingCards
            items={state.items}
            cards={state.cards}
            onAnswer={onAnswer}
            record={floatingRecord}
            onCloseRecord={() => record && setClosedRecord(record.key)}
          />
        )}

        <ChatPanel
          serverLabel={config.serverLabel}
          sessionId={session.sessionId}
          inCall={inCall}
          open={paneOpen}
          onClose={() => setPaneOpen(false)}
          items={state.items}
          cards={state.cards}
          barCard={barCard}
          onAnswer={onAnswer}
        />
      </div>
    </TooltipProvider>
  );
}
