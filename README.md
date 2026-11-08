# Flight Change Agent

A voice + chat agent that helps an airline customer change an existing flight booking. The user talks on a web call and types awkward details (booking reference, names, flight choice, fare consent) in a web chat. Both channels share one session. The session ends in one sanitized, versioned record.

- **Public URL:** https://flight-change-agent.vercel.app (backend: https://flight-backend-820256992821.asia-south1.run.app)
- **Brief:** [Hunar.ai AI Engineer assignment](https://github.com/Hunar-ai/ai-engineer-assignment)
- **Design spec:** [docs/superpowers/specs/2026-11-07-flight-change-agent-design.md](docs/superpowers/specs/2026-11-07-flight-change-agent-design.md)
- **Build log:** [BUILD_LOG.md](BUILD_LOG.md)

**Try it with these seeded bookings** (dates move with today):

| PNR | What it shows |
|---|---|
| `ABC123` | 1 passenger, `RAHUL SHARMA`, saver fare (₹3,000 change fee) |
| `PQR456` | 2 passengers, `ANANYA IYER` and `KARTIK IYER` |
| `FLX789` | flex fare, `MEERA NAIR`: a cheaper flight gives a refund |
| `CNX111` | cancelled booking (rejected) |
| `OLD222` | already flown (rejected) |
| `SON333` | departs in under 3 hours (rejected) |

## Architecture and shared state

```
Browser (Vercel)
  ├─ chat WebSocket ───────────────► Backend (Cloud Run, FastAPI)
  │                                    ├─ Postgres (Neon): all state
  ├─ POST /sessions/{id}/call-token ─►│  └─ LiveKit server API: token, dispatch, room data
  │                                    ▲
  └─ WebRTC audio + transcript ─► LiveKit Cloud room ◄─► Voice agent (LiveKit Agents)
                                                           └─ HTTP to backend /internal/*
```

- **The backend is the single source of truth.** Each session is one JSONB state row in Postgres.
- **One pure function changes state.** Every change is an engine command, `(state, input, now) -> (state, events, reply)`. It does no I/O and never reads the clock.
- **One transaction per change.** `apply` locks the row (`SELECT ... FOR UPDATE`), runs the command, decides the outcome, writes events, the record (if any) and the new state, then commits.
- **The event log drives the chat.** Each event has an id. The chat socket replays events after `?after=<id>`, so a reload or reconnect shows the same thread without duplicates.
- **Chat to call.** When the user answers in chat during a call, the backend sends a LiveKit data message (topic `session-events`) into the room. The agent adds a note to its context and acknowledges at once if nobody is speaking, or at its next turn.
- **Call to chat.** The agent calls backend tools (`/internal/sessions/{id}/*`). They run the same engine and push the result to the chat socket.
- **The agent holds no state it cannot rebuild.** On start it reads `/context` (field status, open card, focus, last 20 transcript turns, no passenger names).
- **During a call, the chat keeps going on its own.** The agent opens the first box (the booking reference); the other typed fields then follow in order, so a missed request cannot leave a field unasked.
- **One input at a time, on both channels.** The engine opens the next card only when the current one is answered (the optional e-ticket email too: type it or tap Skip), and cancels a stale card (`inputCancel`), for example when the date changes after flights were listed. While a card is open the call agent asks no new spoken question: each chat answer forwarded to the call names the next open card, so the agent prompts for it once and waits.
- **Chat UI.** Every question is an agent message in the thread. Dates, choices, flights, the fare and the optional email are answered inside that message; the bottom bar is for typed answers only. Answers show as the user's messages. The final record is a summary card (trip, payment, request, with call/chat source tags) and keeps a "View JSON" toggle.
- **Code layout.** The backend is split by domain (`catalog`, `sessions`, `chat`, `calls`, `records`, `telemetry`, `jobs`). Only a domain's `repository.py` has SQL for its tables.

## How the record is built and sanitized

**Fields** (8; all times ISO 8601 with `+05:30`):

| Field | Channel | Required | Validation and normalization |
|---|---|---|---|
| `changeReason` | call | yes | 3 to 500 characters, not a bare greeting ("hey", "okay"). A small LLM call sets a category: `schedule`, `personal`, `medical`, `missedFlight` or `other`. |
| `newTravelDate` | call | yes | ISO date only. The agent looks dates up in a 2-week calendar in its prompt and reads back the backend's wording ("Friday 13 November 2026"). Not past, at most 330 days ahead, not the current flight's day. |
| `timeFlexibility` | call | yes | `morning`, `afternoon`, `evening` or `any` ("any time", "flexible" map to `any`). |
| `pnr` | chat | yes | Uppercased, spaces removed, 6 letters or digits. Must exist, be `confirmed`, not flown, and depart in more than 3 hours. |
| `passengerNames` | chat | yes | One card per passenger. Uppercased, punctuation and titles (MR, MRS, DR...) removed. Each must match a different name on the booking. Errors never show the real names. |
| `contactEmail` | chat | no | Lowercased, basic pattern with a dotted domain. Skip is allowed. |
| `selectedFlight` | chat | yes | Must be one of the offered flight ids. Options come from the route, date and time window. |
| `fareAcceptance` | chat | yes | A yes/no card with the full breakdown. An expired quote (10 minutes) is re-priced; if the amount changed, the user is asked again. |

**Fare math:** `net = (newFare - oldFare) x passengers + changeFee x passengers`. A positive net is paid. A negative net is refunded to the original payment method.

**Conflicts** (the call and the chat give different values for one field):
- **Chat-native fields** (`pnr`, `passengerNames`, `contactEmail`): the typed value wins at once. STT mangles letters and digits. Logged as `resolution: "chatValue"`, `reason: "typed value preferred over spoken"`.
- **Call-native fields** (`changeReason`, `newTravelDate`, `timeFlexibility`): the field becomes `invalid` until the user picks one (by voice, or a select card in chat). If the session goes idle with it open, the outcome is `needsReview`.
- **Every conflict is listed in the record,** resolved or not.

**Sanitization:** the record holds normalized values only. Passenger names appear only in `fields.passengerNames`. The booking block has the route, original flight, fare class and the masked payment method. The agent's context never contains names.

## Outcomes, delivery and revisions

| Outcome | When |
|---|---|
| `completed` | A change request with every required field valid and the fare accepted. Built at once. |
| `needsReview` | The user asked for a refund instead (built once PNR, names and reason are valid), or the session went idle with an unresolved call-native conflict. |
| `optedOut` | The user confirmed "stop" by voice or with the chat's Stop button (a confirm card first). |
| `partial` | No call is connected, no user activity for 30 minutes, and required fields are missing or invalid. Set by the sweep. |

- **Precedence:** `optedOut` > `needsReview` > `completed` > `partial`.
- **Revisions:** every record has `revision`, starting at 1. `partial` is not final: if the user comes back and answers, the session reopens and the next end state is revision N+1. The other outcomes lock the session; the chat then shows the record and accepts no input.
- **Exactly once:** the record is written to an outbox table with key `(sessionId, revision)` in the same transaction as the state. Delivery POSTs it to a stub endpoint on the backend (`/stub/records`) with `Idempotency-Key: {sessionId}:{revision}`. The stub ignores a repeated key. Delivery runs right after the write, on every sweep (every 5 minutes) and on startup, so a restart between write and delivery still delivers once. It is also logged as one JSON line and shown in the chat.
- **If the call is live** when the record is built, the agent reads a short summary and hangs up.
- **Seeing a delivered record:** `GET /stub/records?sessionId=<id>` (the list without `sessionId` shows only keys and outcomes).

The JSON Schema of the record is in [docs/record.schema.json](docs/record.schema.json).

## Stack and cost per session (150 words or fewer)

- **Voice:** LiveKit Cloud (free Build plan) and LiveKit Agents in Python. LiveKit handles WebRTC, barge-in, turn detection and call-drop reconnects, which saved the most work.
- **STT / TTS:** Deepgram Nova-3 streaming and Aura-2. Fast, cheap, good on Indian English.
- **LLM:** Gemini 3.5 Flash-Lite on Vertex AI (`asia-south1`, minimal thinking), with 3.1 Flash-Lite as fallback. 3.1 is about $0.002 cheaper per session, but Vertex serves it only from `global`, and live tool-chain turns took 7 to 9 s on it, against about 2 s. Auth: ADC locally; on LiveKit Cloud, a key for a service account with only the Vertex AI User role.
- **Backend:** FastAPI on Cloud Run (one instance, scales to zero) with Neon Postgres. Web: the starter UI on Vercel.
- **Cost:** about **$0.06 per completed session** (estimate for a 3-minute call: STT $0.023, TTS $0.030, LLM $0.009, hosting $0). Measured numbers: see below.

## Cost and latency

- **How cost is measured:** the agent reports STT audio seconds, TTS characters and LLM tokens from LiveKit metrics to `/usage`. The backend prices them with a table in [backend/app/telemetry/pricing.py](backend/app/telemetry/pricing.py) and writes `costUsd` into each record.
- **How latency is measured:** for each agent turn, the agent joins three LiveKit metrics by speech id: end-of-utterance delay + LLM time to first token + TTS time to first byte. Their sum is the time from the user stopping to the first agent audio. `scripts/latency_report.py` prints p50 and p95.
- **Numbers:** _pending 10+ test calls on the deployed system._ A local smoke run (3 turns, synthesized speech) gave a mean of 2.9 s, most of it LLM time to first token (1.9 s) on turns that called tools.

```bash
cd backend && uv run python ../scripts/latency_report.py --database-url "$NEON_DATABASE_URL"
```

## Product decisions where the brief was vague

- **Scenario: flight change.** Almost every check can be done by machine, so a human is needed only for refunds and unresolved conflicts.
- **The agent never books or charges.** It collects, validates, quotes and gets consent. The downstream service executes.
- **Typed wins for letters and digits.** Spoken PNRs and names are only hints.
- **Email before the fare.** Fare acceptance is the last step, so it can close the session at once.
- **Declining the fare does not end the session.** The flight list is offered again.
- **Three failed tries** on a field: the agent offers to stop. No `needsReview` for this.
- **30 minutes idle** before `partial`. The sweep runs every 5 minutes.
- **No calls after 10 minutes,** at most 5 calls at once, 10 new sessions per network per hour, and a daily session cap.
- **If nobody calls within 20 seconds,** the chat starts asking on its own (no LLM), including the call fields as cards.

## Edge cases

**Handled**
- A double-clicked Submit, an answer to a cancelled card, or two tabs answering one card: the first wins, the rest get "This question is no longer open." (row lock + card id check).
- Messy values from the LLM (`"Dec 13th"`, a lowercase PNR with spaces, an unknown field): the tool gets HTTP 200 `{ok:false, error}` with a sentence it can say.
- A restart after a record is written but before delivery: delivered once on startup.
- The sweep never marks a session `partial` while a call is live or the user was active in the last 30 minutes. A stale call flag (no agent signal for 15 minutes) is reset.
- The date or time window changes after flights were listed: the open flight or fare card is cancelled and a new list is offered.
- No flights match (or all are sold out): no empty select card. The user is asked for another date or a wider window.
- Tab reload during a call: the room stays for 2 minutes and the same agent continues. Agent restart: the new agent rebuilds context and says "Sorry, we got cut off" before asking again.
- The LLM writes an em dash: removed before TTS and the transcript.

**Not handled**
- Round trips, multi-segment bookings, changing only some passengers.
- Languages other than English.
- A user who never accepts the mic permission gets only the chat (which still works end to end).
- Barge-in was tested with synthesized speech, not by a person on a real mic in every browser.
- More than one backend instance (the chat hub is in-process; `--max-instances=1`).

## What I trust least

- **LLM quotas.** The first live test on Groq's free tier hit its 8,000 tokens per minute limit within a few turns, and the fallback model then got a date wrong. The agent now runs Gemini on Vertex AI in a billed project, so free-tier quotas do not apply.
- **LLM tool discipline.** The prompt asks the model to save focus, read dates back and request one chat card at a time. The backend enforces the rules that matter (validation, one card, no names), but the conversation quality still depends on the model following the prompt.
- **The in-process chat hub.** It is correct only with one backend instance.

## Next week

- Measure real p50/p95 and cost over 20+ calls; then tune endpointing delay and try preemptive generation.
- A session timeline page from the event log (transcript, tool calls, timings, costs, errors).
- "Call me back" from the chat, reusing the same room and context.
- Hindi and one more Indian language (Deepgram multilingual + a multilingual turn detector).
- Load the chat hub through Postgres `LISTEN/NOTIFY` so the backend can scale past one instance.

## AI tools

- **Helped:** writing the plan and spec as a checklist, test-first work on the engine and outcome rules, and reading the installed LiveKit Agents API instead of guessing.
- **Misled:** the plan assumed `openai.LLM.with_groq`, which does not exist in LiveKit Agents 1.8; a union of two `Literal` types made a tool schema Groq rejects; and the LLM skipped an "optional" tool in a live run, so the backend now classifies the reason itself. Each was caught by a test or a live smoke run.

## Run locally

Needs Python 3.12 with `uv`, Node 20+, Postgres 16 on port 5433 (`docker compose up -d db`, or a local install with db `flight`, user/pass `dev`/`dev`), keys for LiveKit Cloud, Deepgram and Groq in your environment, and `gcloud auth application-default login` for Gemini on Vertex AI.

```bash
cd backend && uv sync && SERVICE_TOKEN=dev-token uv run uvicorn app.main:app --port 8080
```

```bash
cd agent && uv sync && uv run python agent.py download-files && BACKEND_URL=http://localhost:8080 SERVICE_TOKEN=dev-token uv run python agent.py dev
```

```bash
cd web && npm install && echo "VITE_SERVER_URL=http://localhost:8080" > .env.local && npm run dev
```

Tests (the backend tests use a `flight_test` database on port 5433):

```bash
cd backend && uv run pytest -q
```

```bash
cd agent && uv run pytest -q
```

## HTTP endpoints

- **Public:** `POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/call-token`, `WS /chat?sessionId=&after=`, `GET /stub/records?sessionId=`, `GET /health`.
- **Internal** (header `Authorization: Bearer $SERVICE_TOKEN`): `GET /internal/sessions/{id}/context`, and `POST` to `.../fields`, `.../chat-input`, `.../conflicts/{field}/resolve`, `.../refund-instead`, `.../opt-out`, `.../focus`, `.../reason-category`, `.../call`, `.../transcript`, `.../usage`, `.../metrics`, plus `POST /internal/sweep` and `POST /stub/records`.

## Deploy

- **Backend:** `gcloud run deploy flight-backend --source=. --region=asia-south1 --max-instances=1 --timeout=3600 --allow-unauthenticated` from `backend/`, with secrets from Secret Manager.
- **Agent:** `lk agent create` / `lk agent deploy` from `agent/`, with `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `BACKEND_URL`, `SERVICE_TOKEN` as agent secrets.
- **Web:** `vercel --prod` from `web/`. `VITE_SERVER_URL` (the backend URL) is a Vercel production env var. Then set the backend's `ALLOWED_ORIGINS` to the Vercel URL.
- **Sweep:** a Cloud Scheduler job every 5 minutes: `POST /internal/sweep` with the service token.

## Later (bonus list)

- Session timeline and debug view (the event log already supports it)
- "Call me back" from chat
- Vision checks on uploads (needs an upload field)
- Language switching (English only for now)
