"""LiveKit voice agent for the flight-change session. All state lives in the backend."""

import asyncio
import json
import logging
import os
import time

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import FallbackAdapter
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.english import EnglishModel

from backend_client import BackendClient
from prompts import GREETING, TIME_LIMIT, event_note, resume_line, system_prompt
from tools import FlightAgent
from turns import TurnTracker

load_dotenv()
log = logging.getLogger("flight-agent")

AGENT_NAME = "flight-agent"
EVENT_TOPIC = "session-events"
MAX_CALL_SECONDS = 10 * 60
USER_GONE_SECONDS = 90
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def groq_llm(model: str) -> openai.LLM:
    return openai.LLM(model=model, base_url=GROQ_BASE_URL, api_key=os.environ["GROQ_API_KEY"],
                      reasoning_effort="low", max_retries=1)


def build_session(vad) -> AgentSession:
    return AgentSession(
        stt=deepgram.STT(model="nova-3", language=os.getenv("STT_LANGUAGE", "en-IN")),
        # Groq's free tier allows 8k tokens/min per model; fall back to the 20b model's separate quota.
        llm=FallbackAdapter([groq_llm(os.getenv("LLM_MODEL", "openai/gpt-oss-120b")),
                             groq_llm(os.getenv("LLM_FALLBACK_MODEL", "openai/gpt-oss-20b"))]),
        tts=deepgram.TTS(model=os.getenv("TTS_VOICE", "aura-2-thalia-en")),
        vad=vad,
        turn_handling={"turn_detection": EnglishModel()},
        max_tool_steps=4,
    )


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    session_id = json.loads(ctx.job.metadata or "{}").get("sessionId")
    if not session_id:
        log.error("job without sessionId metadata")
        return
    client = BackendClient(os.environ["BACKEND_URL"], os.environ["SERVICE_TOKEN"], session_id)
    started = time.monotonic()
    bg: set[asyncio.Task] = set()

    def spawn(coro) -> None:
        t = asyncio.create_task(coro)
        bg.add(t)
        t.add_done_callback(bg.discard)

    async def on_shutdown() -> None:
        await client.call_status(False, seconds=int(time.monotonic() - started))
        await client.aclose()

    ctx.add_shutdown_callback(on_shutdown)
    await ctx.connect()
    await client.call_status(True)
    context = await client.context()
    agent = FlightAgent(client, instructions=system_prompt(context))
    session = build_session(ctx.proc.userdata["vad"])
    turns = TurnTracker()

    @session.on("conversation_item_added")
    def _on_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        text = getattr(item, "text_content", None)
        if text and getattr(item, "role", None) in ("user", "assistant"):
            spawn(client.transcript("user" if item.role == "user" else "agent", text))

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent) -> None:
        m = ev.metrics
        done = None
        if isinstance(m, metrics.STTMetrics) and m.audio_duration:
            spawn(client.usage("stt_seconds", m.audio_duration))
        elif isinstance(m, metrics.TTSMetrics):
            if m.characters_count:
                spawn(client.usage("tts_chars", m.characters_count))
            done = turns.add(m.speech_id, tts_ttfb_ms=m.ttfb * 1000)
        elif isinstance(m, metrics.LLMMetrics):
            spawn(client.usage("llm_in_tokens", m.prompt_tokens))
            spawn(client.usage("llm_out_tokens", m.completion_tokens))
            done = turns.add(m.speech_id, llm_ttft_ms=m.ttft * 1000)
        elif isinstance(m, metrics.EOUMetrics):
            done = turns.add(m.speech_id, eou_ms=m.end_of_utterance_delay * 1000)
        if done:
            spawn(client.metrics(done["eouMs"], done["llmTtftMs"], done["ttsTtfbMs"]))

    async def hang_up(line: str) -> None:
        handle = session.say(line, allow_interruptions=False)
        await handle
        await asyncio.sleep(0.5)
        await ctx.delete_room()

    async def on_event(kind: str, payload: dict) -> None:
        if kind == "outcome":
            await session.interrupt()
            await hang_up(f"{payload.get('summary', '')} Goodbye.")
            return
        note = event_note(kind, payload)
        chat_ctx = agent.chat_ctx.copy()
        chat_ctx.add_message(role="system", content=note)
        await agent.update_chat_ctx(chat_ctx)
        if kind == "fieldUpdate" and session.user_state != "speaking" and session.agent_state != "speaking":
            session.generate_reply(instructions=f"{note} Acknowledge it in one short sentence and continue.")

    def _on_data(packet: rtc.DataPacket) -> None:
        if packet.topic != EVENT_TOPIC:
            return
        try:
            msg = json.loads(packet.data.decode())
        except ValueError:
            return
        spawn(on_event(msg.get("kind", ""), msg.get("payload") or {}))

    ctx.room.on("data_received", _on_data)

    gone_timer: dict[str, asyncio.Task | None] = {"t": None}

    async def end_if_gone() -> None:
        await asyncio.sleep(USER_GONE_SECONDS)
        log.info("caller did not come back; ending")
        ctx.shutdown("caller left")

    def _on_left(p: rtc.RemoteParticipant) -> None:
        if p.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            gone_timer["t"] = asyncio.create_task(end_if_gone())

    def _on_joined(p: rtc.RemoteParticipant) -> None:
        if gone_timer["t"]:
            gone_timer["t"].cancel()
            gone_timer["t"] = None
            session.generate_reply(instructions="The caller reconnected after a drop. Say welcome back in a few "
                                                "words and ask again for what you were discussing.")

    ctx.room.on("participant_disconnected", _on_left)
    ctx.room.on("participant_connected", _on_joined)

    await session.start(agent, room=ctx.room, room_options=room_io.RoomOptions(close_on_disconnect=False))

    if (context.get("state") or {}).get("locked"):
        await hang_up("This request is already submitted. You can see the details in the chat. Goodbye.")
        return
    session.say(resume_line(context) or GREETING)

    async def time_limit() -> None:
        await asyncio.sleep(MAX_CALL_SECONDS)
        await session.interrupt()
        await hang_up(TIME_LIMIT)

    spawn(time_limit())


if __name__ == "__main__":
    cli.run_app(server)
