# Flight Change Agent: Design

Date: 2026-11-07
Brief: https://github.com/Hunar-ai/ai-engineer-assignment (Hunar.ai AI Engineer assignment)

Items marked **[call]** are my decisions, not the user's. The user can change them.

## 1. Intent

- **What:** a voice + chat agent that helps an airline customer change an existing flight booking.
- **Why this scenario:** the user chose it because almost every check can be done by machine. A human is needed only in rare cases.
- **Flow:** the session starts on a web voice call. The user says what is easy to say. The agent asks for awkward details in a web chat during the call, notices when they arrive, and confirms them. If the call ends, the chat continues.
- **Output:** one sanitized, structured record per session. It must be ready for the airline's booking service to execute without a human, except for `needsReview` cases.
- **The agent does not rebook or take payment.** The downstream service does that. The agent only collects, validates, quotes and gets consent.

## 2. Goals, non-goals, anti-goals

**Goals**
- Meet every must-have in the brief: voice call with barge-in and live transcript, chat with one input at a time, shared state, final record, restart safety, no secrets in the browser, a public HTTPS deployment.
- Call-drop recovery (a bonus, but in the core build).
- Low cost per session. Report cost and voice latency (p50/p95).

**Non-goals (for now)**
- Languages other than English.
- Real booking, payment or ticketing.
- Round trips, multi-segment bookings, or changing only some passengers on a booking.
- File uploads. There is no file field in the core flow, so no upload storage is needed.
- Login.
- The other bonuses (see section 14). We revisit them after the core works.

**Anti-goals (a failure even if it "works")**
- Any secret reaches the browser or the repo.
- A record is produced twice for the same revision, or lost on restart.
- The agent says a flight, time or fare that did not come from a tool result.
- The agent reveals booking data, such as passenger names, to someone who only typed a PNR.
- The agent sends more than one chat input request at a time.

## 3. Stack (user decisions)

| Layer | Choice |
|---|---|
| Voice transport | LiveKit Cloud, Build plan (free) |
| Voice agent framework | LiveKit Agents (Python) |
| STT | Deepgram Nova-3, streaming |
| TTS | Deepgram Aura-2 |
| LLM | Groq `openai/gpt-oss-120b`, reasoning effort `low` |
| Language | English only |

**Hosting [call]** (all free tiers):
- **Frontend:** the starter UI, built as a static site on Vercel.
- **Backend:** FastAPI on Google Cloud Run, project `my-stuff-ai`.
  - Deploy with `gcloud run deploy <service> --source=.`, never via `cloudbuild.yaml`.
  - Request-based billing, scale to zero, `--max-instances=1`, `--timeout=3600`.
- **Voice agent:** hosted on LiveKit Cloud (`lk agent deploy`). It scales to zero on the free plan, so the first call after an idle spell has a cold start.
- **Database:** Neon Postgres (free).
- **Timers:** Cloud Scheduler job every 5 minutes calls `POST /internal/sweep`.

**Why `max-instances=1` [call]:** the chat socket and the agent's events must meet in one process. One instance handles the review traffic easily. This avoids a pub/sub layer. All state is still in Postgres, so a restart loses nothing.

## 4. Architecture

```
Browser (Vercel)
  ├─ chat WebSocket ───────────────► Backend (Cloud Run, FastAPI)
  │                                    ├─ Postgres (Neon): all state
  ├─ POST /sessions/{id}/call-token ─►│  └─ LiveKit server API: token, dispatch, room data
  │                                    ▲
  └─ WebRTC audio + transcript ─► LiveKit Cloud room ◄─► Voice agent (LiveKit Cloud)
                                                           └─ HTTP to backend /internal/*
```

- **The backend is the single source of truth.** It owns the field engine, validation, the chat input queue, quotes, outcomes and the record. The agent and the chat page are clients of it.
- **The agent holds no state of its own** that it cannot rebuild. Every read and write goes through backend tools.
- **Chat to call:** when a chat answer arrives, the backend sends a data message (topic `session-events`) into the LiveKit room `call-{sessionId}`. The agent receives it.
- **Call to chat:** the agent calls `/internal/...` tools. The backend updates state and pushes the change to the chat socket.
- **Agent auth to the backend:** a shared service token in the `Authorization` header. It is set as a secret in both Cloud Run and LiveKit Cloud.

## 5. Scenario data [call]

Seeded data is in the repo as JSON. Dates are offsets from "today" in Asia/Kolkata, so the demo always works.

**Bookings (about 6)**
- **Fields:** PNR, status, fare class, passengers (1 to 3, full names as on ID), one-way route, flight number, departure, fare paid per passenger, original payment method (for example "Visa •• 4242").
- **Fare classes:** `saver` has a ₹3,000 change fee per passenger. `flex` has no change fee.
- **Seed cases to cover:**
  - one normal 1-passenger booking
  - one 2-passenger booking
  - one `flex` booking
  - one `cancelled` booking
  - one already flown
  - one departing in under 3 hours

**Flights (generated, not stored)**
- About 6 domestic routes (for example BLR-DEL, BOM-DEL, BLR-BOM, CCU-BLR).
- Each route has 4 to 6 flights a day, for the next 330 days.
- Fares come from a deterministic function of (route, date, flight), so the same query always returns the same answer.
- One flight per route and day is sold out. It is never offered.

**Fare math (all passengers on the booking)**
- `net = (newFare - oldFare) × paxCount + changeFee × paxCount`
- **`net > 0`:** the user pays `net`.
- **`net < 0`:** a refund of `|net|` goes to the original payment method, automatically (user's "case A").
- **`net = 0`:** nothing is due.
- **A quote has an id and expires in 10 minutes [call].** On acceptance, the backend re-quotes if the quote expired. If the amount changed, the agent asks for acceptance again. With deterministic fares this rarely happens, but the path exists.

## 6. Fields, channels and validation

All times are ISO 8601 with a `+05:30` offset.

| # | Field | Channel | Kind (starter `InputKind`) | Required | Validation and normalization |
|---|---|---|---|---|---|
| 1 | `changeReason` | call | text, if asked in chat | yes | Non-empty. Stored as `{text, category}`. The LLM picks `category` from `schedule`, `personal`, `medical`, `missedFlight`, `other`. No fee waiver is ever applied. |
| 2 | `newTravelDate` | call | date | yes | The LLM resolves relative dates ("next Friday") using today's date in the prompt. The backend checks: a real date, at least today, at most 330 days ahead, and not the same flight as now. The agent reads the date back to confirm it. |
| 3 | `timeFlexibility` | call | select | yes | One of `morning` (05–12), `afternoon` (12–17), `evening` (17–24), `any`. |
| 4 | `pnr` | chat | text, pattern `^[A-Za-z0-9]{6}$` | yes | Uppercased, spaces trimmed. It must exist, have status `confirmed`, not be flown, and depart more than 3 hours from now. Each failure has its own error message. |
| 5 | `passengerNames` | chat | text, one card per passenger | yes | The passenger count comes from the booking. Matching is uppercase, ignores punctuation and repeated spaces, and strips titles (MR, MRS, MS, MISS, DR, MASTER). Each name must equal a distinct booking name. Errors never show the real names. |
| 6 | `selectedFlight` | chat | select | yes | Options are built from the route, date and flexibility. Each label shows flight number, times, new fare and the net amount. The value must be one of the offered flight ids. |
| 7 | `fareAcceptance` | chat | confirm | yes | Shows the breakdown: old fare, new fare, change fee, passengers, and the total to pay or the refund. Stored as `{accepted, quoteId, amountDue or refundDue, currency}`. |
| 8 | `contactEmail` | chat | email | **optional** | Lowercased. Checked against a basic email pattern and a domain with a dot. The user can skip it. |

**Rules from the brief, satisfied:** fields 1–3 are conversational, fields 4–7 are awkward by voice, field 8 is optional, and every field has invalid rules.

**Chat input order [call]:**
1. `pnr`
2. `passengerNames`
3. `contactEmail` (optional, with a Skip option)
4. `selectedFlight`, once the PNR, date and flexibility are valid
5. `fareAcceptance`

The email comes before the fare so that acceptance is the last step and can close the session at once.

**If the user declines the fare:** the backend clears `selectedFlight` and the quote. The agent offers the flight list again or asks for another date. Declining never ends the session by itself.

**Only one input card is open at a time.** The backend keeps a queue. It sends the next card when the current one is answered, and cancels a card (`inputCancel`) if it becomes stale, for example when the date changes after the flights were listed.

**Three failed tries on the same field [call]:** the agent offers to stop. The field stays `invalid` or `missing`. There is no `needsReview` for this.

## 7. Conversation behaviour

**Start**
- Opening the page with no `sessionId` calls `POST /sessions`. The page then puts `?sessionId=` in the URL.
- The chat shows a welcome message and asks the user to tap the call button.
- On the call, the agent greets the user, asks for the reason, and at once sends the PNR card to chat ("I've sent a box to your chat for your booking reference").

**While the call is on**
- The voice agent leads. It asks for fields 1–3 by voice. It triggers chat cards through the `request_chat_input` tool, which respects the queue.
- **Acknowledging chat answers:** when the agent gets a `session-events` message:
  - If neither side is speaking, it replies at once: "Got your booking reference, thanks. I can see a flight from Bengaluru to Delhi on the 12th."
  - Otherwise it adds a note to its context and mentions the answer at its next turn.
- **Barge-in:** LiveKit Agents interruption handling, on by default. Turn detection uses LiveKit's turn detector with Silero VAD (builder's choice of exact settings).
- **Live transcript:** LiveKit Agents publishes the transcription to the room, and the page shows both sides, interim and final. The agent also posts each final turn to the backend for the log.

**After the call ends (or if the user never calls)**
- The backend drives the chat on its own, with no LLM. It asks for every missing field as an input card. Call fields become chat cards too: reason as text, date as date, flexibility as select.
- The LLM is called only to set `changeReason.category` from typed text. This is cheap.

**User wants a refund instead (user's "case B")**
- A tool `request_refund_instead` sets `requestType = "refund"`.
- Then only `pnr`, `passengerNames` and `changeReason` are required. The flight and fare fields are skipped.
- The agent tells the user a person will process the refund. Outcome: `needsReview`.

**Opt-out**
- **By voice:** the user says they want to stop. The agent confirms once, then calls `opt_out`.
- **In chat:** a "Stop request" button in the chat header [call]. It shows a confirm card first.

**The agent must never**
- say flights, times or fares that were not in a tool result
- read booking passenger names aloud or show them in chat
- promise a fee waiver

## 8. Conflicts

A conflict is two different values for one field, one from the call and one from the chat. The agent may record a value heard on the call for a chat field (for example a spoken PNR) as a call candidate.

- **Chat-native fields (`pnr`, `passengerNames`, `contactEmail`): typed wins automatically [call].** STT mangles letters and digits. The conflict is logged with `resolution: "chatValue"` and `reason: "typed value preferred over spoken"`. It does not trigger review.
- **Call-native fields (`changeReason`, `newTravelDate`, `timeFlexibility`): the agent asks which is right.**
  - On the call, or with a select card in chat listing both values.
  - The confirmed value wins.
  - **If the user never confirms before the session ends, the outcome is `needsReview`** (user decision).
- **Every conflict is listed in the record,** whether it was resolved or not.
- **A field with an open conflict counts as `invalid`,** so the session cannot reach `completed` until it is resolved. If the sweep later ends the session, the outcome is `needsReview`, not `partial`.

## 9. Outcomes, records and revisions

| Outcome | Trigger |
|---|---|
| `completed` | `requestType = change`, every required field is `valid`, and the fare is accepted (pay, refund or zero). |
| `needsReview` | `requestType = refund` (user's case B), **or** an unresolved call-native conflict when the session ends. |
| `optedOut` | The user confirms they want to stop (voice or chat). |
| `partial` | No call is connected, the last user activity was more than 30 minutes ago [call], and required fields are missing or invalid. Set by the sweep. |

**Precedence when several apply:** `optedOut` > `needsReview` > `completed` > `partial`.

**When the record is built:**
- `completed`: as soon as the fare is accepted and every required field is valid.
- `needsReview` (refund): as soon as the refund fields are valid.
- `optedOut`: when the opt-out is confirmed.
- `partial`, or `needsReview` from an open conflict: when the sweep finds the session idle.

**If the call is live at that moment,** the agent reads a short summary (new flight and amount, or "a person will process your refund"), says goodbye and ends the call. The chat shows the record.

**Revisions**
- Each record has a `revision`, starting at 1.
- **`partial` is not final.** If the user comes back and continues, the session reopens. The next end state produces revision N+1.
- **`completed`, `needsReview` and `optedOut` lock the session.** After that, the chat shows "Your request is submitted" and accepts no new input.

**Restart safety and exactly-once records**
- Every state change is written to Postgres before it is acknowledged.
- Records go into an outbox table with a unique key `(sessionId, revision)`. A record is written once, then delivered.
- Delivery happens at once, and the sweep retries anything undelivered. The POST sends `Idempotency-Key: {sessionId}:{revision}`.
- The sweep also runs on backend startup.

**Delivery [call]**
- `POST` to a stub endpoint on our own backend, `POST /stub/records`. The stub stores what it gets, and `GET /stub/records` shows them.
- The record is also logged as one JSON line, and shown in the chat (the starter's record card).

**Record shape**
- It follows the starter's `FinalRecord`: `sessionId`, `revision`, `outcome`, `outcomeReason`, `fields`, `conflicts`, `engagement`, `costUsd`, `endedAt`.
- Each field is `{value, source, collectedAt, status}`.
- Extra top-level keys:
  - `requestType` (`change` or `refund`)
  - `booking`: PNR, route, original flight and fare class. No payment details beyond the masked method.
  - `quote`: id, fares, change fee, pax count, `amountDue` or `refundDue`, `refundTo`, currency `INR`.
- Write a JSON Schema for the record in the README.

## 10. Call-drop recovery

| Drop | Handling |
|---|---|
| Network blip | The LiveKit browser SDK resumes or fully reconnects by itself. The page shows a "Reconnecting…" banner. |
| Tab closed or reloaded | The agent session uses `close_on_disconnect=False`. The room keeps a departure timeout of about 2 minutes [call]. The room name is fixed per session (`call-{sessionId}`), so the user rejoins the same room and agent. |
| Agent or backend restart | A new agent job calls `GET /internal/sessions/{id}/context`. That returns the fields, the open chat card, `currentFocus` (the field being discussed) and the last 20 transcript turns. The agent rebuilds its prompt, says it got cut off and asks again for `currentFocus`. A half-spoken answer is lost and asked again. |

- **`currentFocus` is saved** whenever the agent asks for a field.
- **The chat socket reconnects by itself** (the starter already does this). On connect, the backend sends the thread history and the open card, from the event log.

## 11. Backend surface

**Public (browser)**
- `POST /sessions`: create a session. Rate-limited per IP.
- `GET /sessions/{id}`: current state, for the page on load.
- `POST /sessions/{id}/call-token`: mints a LiveKit token and dispatches the agent with `sessionId` in the metadata.
  - Token TTL is 15 minutes, for room `call-{sessionId}` only.
  - The agent is dispatched explicitly by name.
- `WS /chat?sessionId=`: chat. Server messages use the starter protocol (`message`, `inputRequest`, `inputError`, `inputCancel`, `record`). Client messages are `inputResponse`, plus a new `optOut`.

**Internal (agent and scheduler, service token)**
- `GET /internal/sessions/{id}/context`
- `POST /internal/sessions/{id}/fields`: record a call value, then validate and normalize. Returns ok or an error the agent can say.
- `POST /internal/sessions/{id}/chat-input`: queue a chat card for a field.
- `POST /internal/sessions/{id}/conflicts/{field}/resolve`
- `POST /internal/sessions/{id}/refund-instead`
- `POST /internal/sessions/{id}/opt-out`
- `POST /internal/sessions/{id}/focus`
- `POST /internal/sessions/{id}/transcript`
- `POST /internal/sessions/{id}/usage`: STT seconds, LLM tokens, TTS characters, and per-turn latency parts.
- `POST /internal/sweep`

**Stub**
- `POST /stub/records`, `GET /stub/records`

**Data (Postgres) [call]:** tables for sessions, field values, candidates and conflicts, chat input requests, quotes, an append-only event log (it replays the chat thread and can feed a timeline later), transcript turns, usage and turn metrics, and the record outbox. The exact schema is the builder's choice.

## 12. Cost, latency, limits

**Cost**
- The agent reports usage from LiveKit Agents metrics.
- The backend turns it into `costUsd` with a price table in config: Deepgram STT per minute, Aura-2 per character, Groq per token, and LiveKit (free, $0).
- The README reports cost per completed session from real test runs.

**Latency**
- Per agent turn, store: end-of-utterance delay, LLM time to first token and TTS time to first byte.
- **Voice latency = their sum** (user stops speaking → first agent audio).
- A script reports p50 and p95 over test calls.

**Spend caps [call]**
- Session creation: 10 per IP per hour.
- Calls: 10 minutes max, 5 at once (also the LiveKit free cap).
- A global daily session cap, set by an env var.

## 13. Frontend changes to the starter

- **Copy the starter** (`starter/` from the brief repo) into our repo. Copy it, never fork it.
- **Replace the call transport.** The WebSocket PCM in `useCall` becomes `livekit-client`:
  - Get a token from the backend and join the room.
  - Publish the mic and play the agent's audio.
  - Render transcription streams into the thread with the existing `addTranscript`.
  - The `audio/` capture and playback code is no longer used for the call.
- **Keep the chat flow** (`useChat`, cards, record view), pointed at the backend.
- **UI redesign (2026-11-08) [user]:** the WhatsApp-style page became a dark voice stage plus a chat panel. The stage has LiveKit's Aura orb (Agents UI, via shadcn), driven by the agent's `lk.agent.state` attribute and the live audio level. The dock has mute, a microphone picker (saved per browser, switched live with `switchActiveDevice`), and start or end call. Tailwind v4 and shadcn/ui replace the hand-written CSS. The brief allows this: the starter UI is optional.
- **Add:**
  - session creation on load
  - the "Stop request" button
  - the "Reconnecting…" banner
  - a "Connecting…" state while the agent cold-starts
- **Config:** only `VITE_SERVER_URL` (the Cloud Run URL). No secrets in `VITE_*`. The backend CORS allows only the Vercel domain and localhost.

## 14. Later (bonus list, revisit after the core works)

- Session timeline and debug view (the event log already supports it)
- "Call me back" from chat
- Vision checks on uploads (needs an upload field, such as an ID photo)
- Documented HTTP test endpoints (the internal API is most of it)
- A strong README (the brief's required README sections are written in any case)
- Language switching (parked: English only)

## 15. Constraints

- **Secrets:** Groq, Deepgram, LiveKit key and secret, the service token and the database URL. They live in Cloud Run env (Secret Manager) and LiveKit Cloud agent secrets only. `.env*` stays git-ignored. A `.env.example` lists the names only.
- **The deployment is public HTTPS** and stays up through review and interview.
- **Target browsers:** recent Chrome and Safari. Headphones are recommended.
- **Repo layout [call]:** one repo with `web/` (frontend), `backend/` (FastAPI) and `agent/` (LiveKit agent).

## 16. Left to the builder

- The exact Postgres schema, migrations tool and ORM.
- The agent prompt wording, the Aura-2 voice and the VAD and turn-detection settings.
- Seed names, routes and fare numbers.
- How tests are organized. **Must have tests for:** validators, fare math, the outcome rules, conflict rules, record building, and exactly-once delivery across a simulated restart.
- Whether the Groq call uses the LiveKit Groq plugin or the OpenAI plugin with Groq's base URL.

## 17. Open items for the user

- **Repo visibility:** the default is private, but Hunar's reviewers need access. Make it public at submission, or add them as collaborators.
- **Groq key tier:** check its rate limits before the review period.
- **Accounts needed:** LiveKit Cloud and Deepgram (sign up), Neon (free project).
