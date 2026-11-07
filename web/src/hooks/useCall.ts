import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ConnectionState,
  type Participant,
  ParticipantKind,
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

const TRANSCRIPTION_TOPIC = "lk.transcription";

interface TokenResponse {
  token?: string;
  url?: string;
  error?: string;
}

/** The call runs over LiveKit (WebRTC). The backend mints a token; the voice agent joins the same room. */
export function useCall(ui: Ui, server: Server | null, sessionId: string | null): CallControls {
  const roomRef = useRef<Room | null>(null);
  const audioEls = useRef<HTMLMediaElement[]>([]);
  const stopMeter = useRef<(() => void) | null>(null);
  const userHungUp = useRef(false);

  const cleanup = useCallback(() => {
    stopMeter.current?.();
    stopMeter.current = null;
    audioEls.current.forEach((el) => el.remove());
    audioEls.current = [];
    ui.setLevel(0);
  }, [ui]);

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
    const agentHere = () => [...room.remoteParticipants.values()].some((p) => p.kind === ParticipantKind.AGENT);
    const markLive = () => ui.setCall(CallState.CONNECTED, "on call");

    room.registerTextStreamHandler(TRANSCRIPTION_TOPIC, async (reader, from) => {
      const attrs = reader.info.attributes ?? {};
      const id = attrs["lk.segment_id"] ?? reader.info.id;
      const role = from.identity === room.localParticipant.identity ? Role.USER : Role.AGENT;
      let text = "";
      for await (const chunk of reader) {
        text += chunk;
        ui.addTranscript({ role, text, final: false, id });
      }
      const final = role === Role.AGENT || attrs["lk.transcription_final"] === "true";
      ui.addTranscript({ role, text, final, id });
    });

    room
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind !== Track.Kind.Audio) return;
        const el = track.attach();
        el.style.display = "none";
        document.body.appendChild(el);
        audioEls.current.push(el);
      })
      .on(RoomEvent.ParticipantConnected, (p: Participant) => {
        if (p.kind === ParticipantKind.AGENT) {
          markLive();
          ui.addNote("Call started");
        }
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
      await room.localParticipant.setMicrophoneEnabled(true, {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      });
      await room.startAudio();
    } catch (err) {
      room.disconnect();
      roomRef.current = null;
      cleanup();
      ui.setCall(CallState.ERROR, errorMessage(err, "Could not start the call or the microphone."));
      return;
    }
    stopMeter.current = startMeter(room, ui.setLevel);
    if (room.state === ConnectionState.Connected && agentHere()) {
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

  return useMemo(() => ({ start, hangUp }), [start, hangUp]);
}

/** Feeds the starter's mic meter from the local mic track. Returns a stop function. */
function startMeter(room: Room, setLevel: (level: number) => void): () => void {
  const track = room.localParticipant.getTrackPublication(Track.Source.Microphone)?.track?.mediaStreamTrack;
  if (!track) return () => {};
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  ctx.createMediaStreamSource(new MediaStream([track])).connect(analyser);
  const buf = new Float32Array(analyser.fftSize);
  let raf = 0;
  const tick = () => {
    analyser.getFloatTimeDomainData(buf);
    let energy = 0;
    for (const v of buf) energy += v * v;
    setLevel(Math.sqrt(energy / buf.length));
    raf = requestAnimationFrame(tick);
  };
  tick();
  return () => {
    cancelAnimationFrame(raf);
    void ctx.close();
  };
}
