# Requirements Audit and Demo Script

This file checks every item in the [brief](https://github.com/Hunar-ai/ai-engineer-assignment) against the code, the tests and the build log (as of `main` at `ef9af05`, 2026-11-08). Then it gives a script for the screen recording.

**Status key:** **Done** = built, tested and live. **Partial** = built, with a gap that is named. **Not done** = not built.

## 1. Audit

### Scenario rules

| Requirement | Status | Evidence |
|---|---|---|
| A use case that needs both channels | **Done** | Flight change. This is one of the brief's own examples. |
| 3+ fields collected on the call | **Done** | `changeReason`, `newTravelDate`, `timeFlexibility` |
| 3+ fields better in chat | **Done** | `pnr`, `passengerNames`, `selectedFlight` (a list), `fareAcceptance` (a fare table) |
| 1+ optional field | **Done** | `contactEmail` (Save or Skip) |
| Clear rules for invalid inputs | **Done** | README "How the record is built", `backend/app/sessions/fields.py`, seeded bad PNRs `CNX111`, `OLD222`, `SON333` |

### Must-haves

| # | Requirement | Status | Evidence | How to show it |
|---|---|---|---|---|
| 1a | Web voice call | **Done** | LiveKit room, agent on LiveKit Cloud | Scene 1 |
| 1b | The user can interrupt the agent | **Done** | LiveKit barge-in (on by default). Only the goodbye line cannot be interrupted. Test 14. | Scene 1: talk over the greeting |
| 1c | Live transcript of both sides | **Done** | Live caption on the stage, and the full transcript in the Conversation pane | Scene 1: open Conversation |
| 2 | Chat on the same session, one input at a time (text, choices, files) | **Done** (no files) | The engine has one open card at a time. Card kinds: text, date, choice, flight list, fare confirm. There is no file input, because the flight-change scenario does not need one (the brief's flight example has none). | Scenes 1 and 2 |
| 3a | A chat answer during a call is acknowledged by the agent | **Done** | `session-events` data message, `event_note`, reply only when nobody speaks | Scene 1: type the PNR while on the call |
| 3b | When the call ends, the chat continues | **Done** | The next field opens as a chat card. Test 11 covers chat only. | Scene 3 |
| 4 | Final record, sanitized, structured, delivered | **Done** | `docs/record.schema.json`, outbox plus `POST /stub/records` with an idempotency key, one JSON log line, a record card in the UI | Scene 1 end, scene 6 |
| 5 | A restart loses nothing and does not produce the record twice | **Done** | All state in Neon. The outbox key is `(sessionId, revision)`. Delivery runs on startup and on every sweep. Tests in `backend/tests`. | Scene 5 |
| 6 | No leaked secrets | **Done** | The browser gets only a short-lived LiveKit room token from `/call-token`. The only web env var is `VITE_SERVER_URL`. Keys are in Secret Manager and LiveKit secrets. A grep for key patterns in git finds nothing. | Say it in scene 1. Optional: show DevTools Network. |
| 7 | Deployed on public HTTPS, with usage caps | **Done** | https://flight-change-agent.vercel.app (200) and the backend `/health` (200). Caps: 10 sessions per network per hour, 200 per day, calls end at 10 min, 5 calls at once. | Scene 1 |

### The final record

| Requirement | Status | Evidence |
|---|---|---|
| Define the shape (schema welcome) | **Done** | `docs/record.schema.json`, README field table |
| Deliver the record | **Done** | Outbox, POST to the stub, `GET /stub/records?sessionId=` |
| `completed` | **Done** | Every required field valid and the fare accepted |
| `partial` | **Done** | No call, 30 min idle, required fields missing. Set by the sweep every 5 min. |
| `optedOut` | **Done** | Stop by voice or with the Stop request button, after a confirm card |
| `needsReview` | **Done** | A refund request, or an unresolved call-vs-chat conflict at idle |
| Document triggers and new revisions | **Done** | README "Outcomes, delivery and revisions". `partial` reopens and gives revision N+1. |
| Conflicts resolved and listed | **Done** | Typed wins for chat-native fields. A choice card for call-native fields. All conflicts are in `conflicts[]`. |

### Cost and latency

| Requirement | Status | Evidence |
|---|---|---|
| Cost per completed session, and how it is worked out | **Done** | About $0.055 (3 sessions). Usage from LiveKit metrics, priced in `backend/app/telemetry/pricing.py`, written as `costUsd` into each record. |
| Voice latency p50 and p95, and how it is measured | **Partial** | p50 1.73 s, p95 7.6 s over 42 turns and 13 calls (EOU + LLM TTFT + TTS TTFB). Most calls used synthesized speech. The build log still asks for 10+ calls by real people. |
| Stack in 150 words or fewer | **Done** | README section |

### Bonus

| Bonus | Status | Evidence and gap |
|---|---|---|
| Call drop recovery | **Done** | The room stays 2 min after a drop. A new agent rebuilds context from `/context` and says "Sorry, we got cut off". An open chat card stays open. **Gap:** a sentence the caller was speaking at the moment of the drop is lost. |
| Logging and debuggability | **Done** (mostly) | The Debug view and `GET /sessions/{id}/timeline`: both channels, tool calls with arguments and replies, state changes, per-turn latency, cost, record revisions with delivery times. **Gap:** "why" is shown as the tool call and the backend's reply, not the model's reasoning. Agent errors appear only as tool errors. |
| Language switching (English, Hindi, 1 more) | **Not done** | English only |
| Call me back from chat | **Done** | The call button and a prompt in the thread read "Call me back". The new call opens with "Welcome back" and the current step. Test 20. |
| Checking uploads with a vision model | **Not done** | No uploads (the document upload is deferred) |
| HTTP access for testing | **Done** | `POST /sessions` creates a session. `POST /sessions/{id}/answers` answers the open chat card as the user, and `POST /sessions/{id}/stop` opens the stop confirm. `GET /sessions/{id}` shows the open card, and `/timeline` shows what happened. A test drives a whole session to `completed` over HTTP only. **Gap:** a page open on the same session shows HTTP answers only after a reload. |
| Good documentation | **Done** | README with all 10 sections, `docs/architecture.html`, `docs/TESTING.md`, record schema, build log |

### What to submit

| Item | Status | Note |
|---|---|---|
| Public HTTPS URL | **Done** | https://flight-change-agent.vercel.app |
| Own git repo with code and setup steps | **Done** | README "Run locally" |
| README, 10 required sections | **Done** | Architecture, record, outcomes, stack, decisions, edge cases, trust least, cost and latency, next week, AI tools |
| Reviewers can open the repo | **Not done** | The repo is **private**, and you are the only collaborator. Add the reviewers or make it public before you send it. |
| Screen recording (optional) | **Not done** | Use the script below |

## 2. What is left

In order of value to the review:

1. **Repo access.** The repo is private. Add the Hunar reviewers as collaborators, or make it public. Without this, nobody can read the code.
2. **Screen recording.** Optional, but it shows the voice flow better than any text. See the script below.
3. **Latency from real calls.** Make 10 or more calls yourself on a real mic, then run `scripts/latency_report.py` and update the README numbers.
4. **Language switching** (bonus, large). Needs a multilingual STT and TTS setup and prompt work. Skip it unless there is time.
5. **Document upload with a vision check** (bonus, deferred). The plan is ready: a medical note for medical reasons, a signed GCS URL, `document_id` in the record.
6. **Small items:**
   - A reloaded thread shows the reload time, not the original time.
   - The reason classifier still uses Groq. It could move to Gemini so there is one LLM provider.
   - The "Left to do" section in `BUILD_LOG.md` still asks for real latency numbers, which the README now has.
   - Deferred minors in the build log (an autostart race with a cold agent, no timeout on "waiting for the agent").

## 3. Demo script

**Goal:** one full session as the main take (4 to 5 min), then short clips for the other outcomes and for recovery. Talk while you click. Say each point in one sentence.

### Before you record

- **One day before, or 40+ min before:** open a new session, type `PQR456` only, then close the tab. Save the URL. This session will be `partial` (revision 1) when you record scene 6.
- Use Chrome with a headset, so the agent does not hear itself.
- Have these tabs ready:
  - The live site with `?guide=1`. A **Guide** pane opens on the left with the test bookings (tap a PNR to copy it) and the scenarios to tick off. It keeps the param across **New chat**.
  - `https://flight-backend-820256992821.asia-south1.run.app/stub/records?sessionId=<id>` (fill in the id during the take).
  - A terminal for the restart in scene 5.
- Make one warm-up call, so the agent is not cold.
- Keep this table at hand:

| PNR | Names | Use |
|---|---|---|
| `ABC123` | `RAHUL SHARMA` | main take |
| `PQR456` | `ANANYA IYER`, `KARTIK IYER` | partial, then revision 2 |
| `FLX789` | `MEERA NAIR` | refund on a cheaper flight (optional) |
| `CNX111` | | cancelled, rejected |

### Scene 1: the main take, a call and the chat together (`completed`)

| Step | Do | Say (points to cover) |
|---|---|---|
| 1 | Open the site. Show the `sessionId` in the URL. | "One session, two channels. The backend in Postgres holds the state." |
| 2 | Tap **Call**. While the agent greets you, start talking over it. | "I can interrupt it. It stops and listens." (must-have 1) |
| 3 | Say: "My work meeting was moved, so I need to change my flight." | "The reason is a call field." Open **Conversation** to show the live transcript of both sides. |
| 4 | The agent asks for the PNR in chat. First say aloud: "It is A B C 1 2 4." | "Letters and digits are bad on voice. A spoken PNR is only a hint." |
| 5 | Type `CNX111`. | "Validation: a cancelled booking is rejected with a clear reason." |
| 6 | Type `abc 123`. Wait for the agent. | "I typed it in chat while on the call. The agent heard about it and confirmed at a natural pause." (must-have 3a) "It was uppercased and the space was removed. The typed value won the conflict." |
| 7 | Type the name `Rahul Verma`, then `Mr. rahul sharma`. | "A wrong name is rejected without showing the real names. The title is removed." |
| 8 | Email card: type `Rahul@Example.COM` and **Save** (or **Skip**). | "The optional field. One card at a time: the agent waits until I answer." |
| 9 | Say: "The twentieth of December." Then: "Afternoon." | "Dates come by voice. The agent reads back the backend's wording." |
| 10 | Pick the first flight. On the fare table, tap **Yes**. | "Flights come from a list in chat. The fare breakdown needs consent." |
| 11 | The agent reads a summary, says goodbye and hangs up. The record card shows. | "End state reached, so the record was built and delivered once." (must-have 4) |
| 12 | Open the stub tab with this `sessionId`. | "Delivered to the stub with the key session plus revision." Point at `fields` with `source` call or chat, `conflicts` (pnr, chatValue), `engagement` and `costUsd`. |
| 13 | Tap **Debug**. Scroll the timeline. Toggle a lane chip. | "Every spoken line, chat answer, agent tool call with its arguments and reply, latency per turn, and the cost." (bonus: debuggability) |

### Scene 2: secrets and limits (20 s, no clicks needed)

- "The browser gets only a short-lived LiveKit token from the backend. No API keys are in the page or in the repo."
- "The URL is public, so there are caps: 10 sessions per network per hour, 200 per day, 10-minute calls."

### Scene 3: the call ends, the chat continues, then call me back

| Step | Do | Say |
|---|---|---|
| 1 | Tap **New chat**. Tap **Call**. Give a reason. Then end the call. | |
| 2 | The next question shows as a chat card. Type `ABC123`. | "The call ended, and the chat continues from the same step." (must-have 3b) |
| 3 | Wait about 2 min. Tap **Call me back**. | "Call me back from the chat." |
| 4 | The agent says "Welcome back" and asks the next step. | "It has full context. It does not ask again for the reason or the PNR." (bonus) |

### Scene 4: the call drops (keep the scene 3 session)

| Step | Do | Say |
|---|---|---|
| 1 | During the call, with a card open, reload the page. Tap **Call** again within 1 min. | |
| 2 | The thread comes back with the spoken lines. The agent continues where it was. | "Drop recovery: the thread, the open card and the agent's context all come back." (bonus) |

### Scene 5: the server restarts (keep the same session)

| Step | Do | Say |
|---|---|---|
| 1 | In the terminal, run the command below. It deploys a new revision, so the backend restarts. | "I restart the backend in the middle of a session." |
| 2 | Reload the page. | "Nothing is lost: every answer is still there." (must-have 5) |
| 3 | Finish the session, then open the stub tab for this session. | "One record per revision, even after a restart. The outbox and the idempotency key stop a second record." |

```bash
gcloud run services update flight-backend --region asia-south1 --project my-stuff-ai --update-env-vars RESTART_AT=$(date +%s)
```

### Scene 6: the other outcomes (short clips)

| Clip | Do | Expect | Say |
|---|---|---|---|
| `needsReview` | New chat, call, give a reason, type `ABC123` and the name. Say "Actually, I just want a refund instead." Then say "thanks, bye" before it is done. | The agent stays until the details are in, then the record shows `needsReview`. | "A refund is a decision a person makes, so the system does not make it." |
| `optedOut` | New chat. Tap **Stop request**, then **Yes**. | The record shows `optedOut`. The chat locks. | "The user asked to stop. It also works by voice." |
| `partial` then revision 2 | Open the `PQR456` session you saved. Show the stub: `partial`, revision 1. Finish the flow (`Ananya Iyer`, `Kartik Iyer`). | The stub shows revision 2 `completed`. | "The user left, so the record was partial. They came back, so the system made a new revision." |

### Scene 7: wrap up (30 s)

- Open `docs/architecture.html` or the README Mermaid diagram.
- **Points to say:**
  - "One pure engine with one transaction per change, used by both channels."
  - "About 5.5 cents per completed session. 1.7 s p50 voice latency."
  - "Not done: language switching, and file uploads with a vision check."

### Do not show

- The rate limit (it uses up your session quota).
- Internal endpoints or the service token.
- Any terminal output that prints an env value.

### Optional clip: HTTP access (30 s)

- In a terminal, run the `curl` lines from the README "HTTP endpoints" section.
- Then open the same `sessionId` in the browser, or tap **Debug**: the answers from the terminal are in the thread and the timeline.
- **Say:** "A tester can drive a whole session over HTTP, through the same engine as the chat."
