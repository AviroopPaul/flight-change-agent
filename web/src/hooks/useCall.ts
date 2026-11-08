import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AgentState } from "@livekit/components-react";
import {
  ConnectionState,
  type LocalAudioTrack,
  type Participant,
  ParticipantKind,
  type RemoteAudioTrack,
  type RemoteParticipant,
  type RemoteTrack,
  Room,
  RoomEvent,
  Track,
} from "livekit-client";
import type { Server } from "../config";
import { errorMessage } from "../lib/errors";
import { Role } from "../protocol";
import { CallState } from "../state/conversation";
import type { CallControls, Ui } from "../state/ui";
import { idleVoice, type VoiceState } from "../state/voice";

const TRANSCRIPTION_TOPIC = "lk.transcription";
const AGENT_STATE_ATTR = "lk.agent.state";
const MIC_OPTIONS = { echoCancellation: true, noiseSuppression: true, autoGainControl: true };

interface TokenResponse {
  token?: string;
  url?: string;
  error?: string;
}

export interface VoiceCall extends CallControls {
  voice: VoiceState;
  setMuted(muted: boolean): void;
  /** Switches the live call to another microphone. Before a call, the next call uses it. */
  switchMic(deviceId: string): void;
}

const isAgent = (p: Participant): boolean => p.kind === ParticipantKind.AGENT;
const agentStateOf = (p: Participant): AgentState | null =>
  (p.attributes?.[AGENT_STATE_ATTR] as AgentState | undefined) ?? null;

/** The call runs over LiveKit (WebRTC). The backend mints a token; the voice agent joins the same room. */
export function useCall(ui: Ui, server: Server | null, sessionId: string | null, micDeviceId: string): VoiceCall {
  const roomRef = useRef<Room | null>(null);
  const audioEls = useRef<HTMLMediaElement[]>([]);
  const userHungUp = useRef(false);
  const deviceRef = useRef(micDeviceId);
  const [voice, setVoice] = useState<VoiceState>(idleVoice);
  deviceRef.current = micDeviceId;

  const cleanup = useCallback(() => {
    audioEls.current.forEach((el) => el.remove());
    audioEls.current = [];
    setVoice(idleVoice);
  }, []);

  useEffect(() => () => {
    roomRef.current?.disconnect();
    cleanup();
  }, [cleanup]);

  const start = useCallback(async () => {
    if (!server || !sessionId || roomRef.current) return;
    userHungUp.current = false;
    ui.setCall(CallState.CONNECTING, "connecting…");

    let auth: TokenResponse;
    try {
      const res = await fetch(`${server.http}/sessions/${encodeURIComponent(sessionId)}/call-token`, { method: "POST" });
      auth = await res.json().catch(() => ({}));
      if (!res.ok || !auth.token || !auth.url) {
        ui.setCall(CallState.ERROR, auth.error ?? "Could not start the call.");
        return;
      }
    } catch (err) {
      ui.setCall(CallState.ERROR, errorMessage(err, `Could not reach ${server.http}`));
      return;
    }

    const room = new Room({ adaptiveStream: true, dynacast: true });
    roomRef.current = room;
    const agentHere = () => [...room.remoteParticipants.values()].some(isAgent);
    const markLive = () => ui.setCall(CallState.CONNECTED, "on call");
    const readAgentState = (p: Participant) => {
      if (isAgent(p)) setVoice((v) => ({ ...v, agentState: agentStateOf(p) }));
    };

    // Speech-to-text sends a caller's turn as several segments. Keep them in one bubble until the agent speaks.
    let userTurn: { id: string; done: string } | null = null;
    room.registerTextStreamHandler(TRANSCRIPTION_TOPIC, async (reader, from) => {
      const attrs = reader.info.attributes ?? {};
      const segmentId = attrs["lk.segment_id"] ?? reader.info.id;
      const role = from.identity === room.localParticipant.identity ? Role.USER : Role.AGENT;
      if (role === Role.AGENT) userTurn = null;
      const turn = role === Role.USER ? (userTurn ??= { id: segmentId, done: "" }) : null;
      const prefix = turn?.done ? `${turn.done} ` : "";
      const id = turn ? turn.id : segmentId;
      let text = "";
      for await (const chunk of reader) {
        text += chunk;
        ui.addTranscript({ role, text: prefix + text, final: false, id });
      }
      const final = role === Role.AGENT || attrs["lk.transcription_final"] === "true";
      if (turn && final && userTurn === turn) turn.done = prefix + text;
      ui.addTranscript({ role, text: prefix + text, final, id });
    });

    room
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _pub, participant: RemoteParticipant) => {
        if (track.kind !== Track.Kind.Audio) return;
        const el = track.attach();
        el.style.display = "none";
        document.body.appendChild(el);
        audioEls.current.push(el);
        if (isAgent(participant)) setVoice((v) => ({ ...v, agentTrack: track as RemoteAudioTrack }));
      })
      .on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
        setVoice((v) => (v.agentTrack === track ? { ...v, agentTrack: undefined } : v));
      })
      .on(RoomEvent.ParticipantAttributesChanged, (_changed, p: Participant) => readAgentState(p))
      .on(RoomEvent.ParticipantConnected, (p: Participant) => {
        if (isAgent(p)) {
          readAgentState(p);
          markLive();
          ui.addNote("Call started");
        }
      })
      .on(RoomEvent.ParticipantDisconnected, (p: Participant) => {
        if (isAgent(p)) setVoice((v) => ({ ...v, agentState: null, agentTrack: undefined }));
      })
      .on(RoomEvent.Reconnecting, () => ui.setCall(CallState.RECONNECTING, "reconnecting…"))
      .on(RoomEvent.Reconnected, () => (agentHere() ? markLive() : ui.setCall(CallState.CONNECTING, "connecting…")))
      .on(RoomEvent.Disconnected, () => {
        roomRef.current = null;
        cleanup();
        ui.setCall(CallState.ENDED, "call ended");
        ui.addNote(userHungUp.current ? "You hung up" : "Call ended");
      });

    try {
      await room.connect(auth.url, auth.token);
      const device = deviceRef.current;
      await room.localParticipant.setMicrophoneEnabled(true, device ? { ...MIC_OPTIONS, deviceId: device } : MIC_OPTIONS);
      await room.startAudio();
    } catch (err) {
      room.disconnect();
      roomRef.current = null;
      cleanup();
      ui.setCall(CallState.ERROR, errorMessage(err, "Could not start the call or the microphone."));
      return;
    }
    const micTrack = room.localParticipant.getTrackPublication(Track.Source.Microphone)?.track as LocalAudioTrack | undefined;
    setVoice((v) => ({ ...v, micTrack, muted: false }));
    const agent = [...room.remoteParticipants.values()].find(isAgent);
    if (room.state === ConnectionState.Connected && agent) {
      readAgentState(agent);
      markLive();
      ui.addNote("Call started");
    } else {
      ui.setCall(CallState.CONNECTING, "waiting for the agent…");
    }
  }, [ui, server, sessionId, cleanup]);

  const hangUp = useCallback(() => {
    userHungUp.current = true;
    const room = roomRef.current;
    if (room) room.disconnect();
    else ui.setCall(CallState.ENDED, "call ended");
  }, [ui]);

  const setMuted = useCallback((muted: boolean) => {
    const room = roomRef.current;
    if (!room) return;
    setVoice((v) => ({ ...v, muted }));
    room.localParticipant.setMicrophoneEnabled(!muted).catch((err: unknown) => {
      setVoice((v) => ({ ...v, muted: !muted }));
      ui.setNotice(errorMessage(err, "Could not change the microphone."));
    });
  }, [ui]);

  const switchMic = useCallback((deviceId: string) => {
    deviceRef.current = deviceId;
    const room = roomRef.current;
    if (!room) return;
    room
      .switchActiveDevice("audioinput", deviceId || "default")
      // The same track object now carries a new MediaStreamTrack; copy the state so the meters re-read it.
      .then(() => setVoice((v) => ({ ...v })))
      .catch((err: unknown) => ui.setNotice(errorMessage(err, "Could not switch to that microphone.")));
  }, [ui]);

  return useMemo(() => ({ start, hangUp, voice, setMuted, switchMic }), [start, hangUp, voice, setMuted, switchMic]);
}
