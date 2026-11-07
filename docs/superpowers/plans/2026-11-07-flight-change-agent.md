# Flight Change Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a voice + chat agent that collects a flight-change request across a LiveKit call and a web chat, and produces one sanitized, versioned record per session.

**Architecture:**
- **The backend owns all state.** A FastAPI backend holds each session as one JSONB state row in Postgres.
- **One pure function changes state.** Every change goes through a pure engine, `apply(state, command) -> (state, events)`. The backend persists the state, events and records in one transaction.
- **The voice agent holds no state.** It is a LiveKit Agents worker that reads and writes only through backend HTTP tools. The backend pushes chat events into the LiveKit room as data messages.
- **The web app is the starter UI,** with its call transport swapped to `livekit-client`.

**Tech Stack:**
- **Backend:** Python 3.12, FastAPI, asyncpg, pydantic v2, `livekit-api`, httpx, pytest + pytest-asyncio.
- **Agent:** LiveKit Agents 1.x (Deepgram, Silero, turn-detector, OpenAI-compatible plugin pointed at Groq).
- **Web:** React + Vite (starter), `livekit-client`.
- **Data and hosting:** Postgres 16 (Docker locally, Neon in prod), Cloud Run, LiveKit Cloud, Vercel.

**Spec:** `docs/superpowers/specs/2026-11-07-flight-change-agent-design.md`. Read it before any task. Section numbers below (§) refer to it.

## Global Constraints

- **Python:** 3.12 for `backend/` and `agent/`, managed with `uv`.
- **Node:** whatever the starter needs (Node 20.19+ or 22.12+). Local Node is 26.
- **Secrets:** never in the repo, in `VITE_*` or in logs. Locally, they come from env vars loaded by `~/.config/zsh/secrets.zsh`:
  - `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
  - `DATABASE_URL`, `SERVICE_TOKEN`
- **`.env*` is git-ignored.** Each package has a `.env.example` with names only.
- **Time:** all user-facing times are in `Asia/Kolkata`. All timestamps in records and events are ISO 8601 with `+05:30`.
- **Injected clock:** every engine, catalog and validator function takes `now: datetime` as a parameter. Modules marked `[pure]` in the File Structure do no I/O and never read the clock.
- **Domain-led layout:** each domain folder owns its `models.py`, `repository.py`, `service.py`, `schemas.py`, `router.py` and `tables.sql`, where it has them.
  - **`models`:** domain types.
  - **`schemas`:** HTTP and WebSocket bodies.
  - **`repository`:** the only place with SQL for that domain's tables.
  - **`service`:** the use cases.
  - **`router`:** thin. It parses input, calls the service and maps the result.
- **Cross-domain imports** go only through another domain's `service`, `models` or pure modules, never its `repository` or `router`. `core/` imports no domain.
- **Currency:** INR, whole rupees, as `int`.
- **Field names are exact.** They match the spec §6:
  `changeReason`, `newTravelDate`, `timeFlexibility`, `pnr`, `passengerNames`, `selectedFlight`, `fareAcceptance`, `contactEmail`.
- **Outcome strings are exact:** `completed`, `partial`, `optedOut`, `needsReview`.
- **Record JSON is camelCase.** Python code is snake_case. Pydantic models use `alias_generator=to_camel` and `populate_by_name=True`.
- **Spend caps:**
  - 10 session creations per IP per hour
  - calls of 10 minutes max
  - a daily session cap from env `DAILY_SESSION_CAP` (default 200)
- **Idle threshold:** 30 minutes for `partial`. The sweep runs every 5 minutes.
- **Deploy:**
  - Backend: `gcloud run deploy <service> --source=.`, never `gcloud builds submit`. Project `my-stuff-ai`, `--max-instances=1`, `--timeout=3600`.
  - Agent: `lk agent deploy`.
- **Browser checks:** use Playwright with headless Chromium only. Never `open <url>` and never the user's browser. Put this rule in any sub-agent prompt that does browser checks.
- **Git:** run `git init` in the repo root. Per-task local commits are allowed only if the user approves them when execution starts. Never push, open a PR or create the GitHub repo without the user asking.
- **Copy, no em dashes:** user-facing copy (UI text, agent lines) must have no em dashes.

## Review Focus

1. **A stale or duplicate chat answer.** The user double-clicks Submit, or answers a card that was cancelled (old `requestId`), or two tabs answer the same card. Expected: the first answer wins, later ones get `inputError` with "This question is no longer open." No crash, no double write. Test in Task 4 and Task 7.
2. **Messy values from the LLM.** For example `"Dec 13th"`, `"13/12"`, `"tmrw"`, a lowercase PNR with spaces, or an unknown field name. Expected: the backend returns `{ok:false, error:"<sentence the agent can say>"}` with HTTP 200, never a 500. Test in Task 3 and Task 8.
3. **A restart or sweep at the wrong moment.** The server restarts after the record is written but before delivery, or the sweep runs while the user is answering. Expected: exactly one record per `(sessionId, revision)`, delivered once (idempotency key), and no `partial` for an active user. Test in Task 6 and Task 9.
4. **The date changes after flights were offered.** Expected: the open `selectedFlight` or `fareAcceptance` card gets `inputCancel`, the quote is cleared and a new list is offered. Test in Task 4.
5. **No flights match.** The date and flexibility give zero options, or every option is sold out. Expected: no empty select card. The agent (or chat) asks for another date or a wider time window. Test in Task 2 and Task 4.

---

## File Structure

```
.gitignore
docker-compose.yml                 # postgres:16 for dev + tests
README.md                          # Task 13
backend/
  pyproject.toml  Dockerfile  .env.example
  app/
    main.py                        # app factory: mounts each domain router; startup: migrate + sweep
    core/                          # shared plumbing, no business rules
      config.py                    # Settings (env)
      clock.py                     # now_ist(): the only place that reads the clock
      db.py                        # asyncpg pool; migrate() runs each domain's tables.sql in DOMAIN_ORDER
      auth.py                      # require_service_token FastAPI dependency
      ratelimit.py                 # per-ip-hash and daily caps
      result.py                    # Ok / Err
    catalog/                       # bookings, flights, fares (no DB: JSON + generator)
      models.py                    # Booking, Flight, Quote
      repository.py                # load_bookings(now), get_booking(pnr, now)
      service.py                   # flights_for, get_flight, make_quote, CHANGE_FEE, WINDOWS   [pure]
      data/bookings.json
    sessions/                      # session lifecycle + the conversation engine
      models.py                    # SessionState, FieldState, Conflict, InputCard, Event, Result
      fields.py                    # field defs + validators/normalizers                         [pure]
      engine.py                    # commands -> Result; advance(); conflicts                     [pure]
      repository.py                # sessions + events tables
      service.py                   # create_session, apply (one transaction), load, events_since
      effects.py                   # after_apply: hub publish, call events, delivery kick
      classify.py                  # classify_reason via Groq
      schemas.py                   # API request/response bodies
      router.py                    # POST /sessions, GET /sessions/{id}
      tables.sql
    chat/                          # browser chat channel
      hub.py                       # in-process fan-out
      schemas.py                   # starter wire messages
      service.py                   # event -> wire message; client message -> engine command
      router.py                    # WS /chat
    calls/                         # LiveKit + the agent's internal API
      livekit.py                   # mint_token, ensure_dispatch, send_event
      schemas.py
      service.py                   # call status, context for the agent
      router.py                    # POST /sessions/{id}/call-token, /internal/sessions/{id}/*
    records/                       # outcome, final record, outbox, delivery
      models.py                    # FinalRecord (camelCase) + JSON Schema export
      outcome.py                   # decide_outcome, is_final                                     [pure]
      builder.py                   # build_record                                                 [pure]
      repository.py                # records + stub_records tables
      service.py                   # deliver_pending
      router.py                    # /stub/records
      tables.sql
    telemetry/                     # transcript, usage, latency, cost
      pricing.py                   # PRICES, cost_usd                                             [pure]
      repository.py                # transcript, usage, turn_metrics tables
      schemas.py
      router.py                    # /internal/sessions/{id}/transcript|usage|metrics
      tables.sql
    jobs/                          # scheduled work
      service.py                   # sweep
      router.py                    # POST /internal/sweep
  tests/                           # mirrors app/ by domain: tests/catalog/, tests/sessions/, ...; conftest.py gives db + client fixtures
agent/
  pyproject.toml  Dockerfile  livekit.toml  .env.example
  agent.py                         # entrypoint, session wiring, events
  backend_client.py                # typed httpx client for /internal/*
  tools.py                         # @function_tool definitions
  prompts.py                       # system prompt + resume prompt from context
  tests/
web/                               # copy of starter/ from the brief repo
  src/hooks/useCall.ts             # rewritten: livekit-client
  src/hooks/useSession.ts          # new: create/resolve sessionId
  src/components/header/StopButton.tsx   # new
  src/components/thread/Banner.tsx       # new: Connecting / Reconnecting
scripts/latency_report.py
```

---

### Task 1: Repo scaffold, Postgres and backend skeleton

**Files:**
- Create: `.gitignore`, `docker-compose.yml`, `backend/pyproject.toml`, `backend/.env.example`, `backend/app/main.py`, `backend/app/core/{config,clock,db,auth,result}.py`, `backend/app/{sessions,records,telemetry}/tables.sql` (plus empty `__init__.py` in every domain folder), `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings) with `database_url`, `service_token`, `livekit_url`, `livekit_api_key`, `livekit_api_secret`, `groq_api_key`, `allowed_origins: list[str]`, `daily_session_cap: int = 200`, `stub_url: str | None` (default: own `/stub/records`)
  - `get_pool() -> asyncpg.Pool`, `migrate(pool) -> None` (runs `app/<domain>/tables.sql` for `DOMAIN_ORDER = ["sessions", "records", "telemetry"]`), `require_service_token` dependency (401 unless `Authorization: Bearer {SERVICE_TOKEN}`), `Ok(value)` / `Err(message)` in `core/result.py`
  - `now_ist() -> datetime`
  - `create_app(settings) -> FastAPI`
  - Fixtures: `pool` (fresh schema per test), `client` (httpx `AsyncClient` on the app)
- **Tables, split by owning domain** (`sessions/tables.sql`: `sessions`, `events`; `records/tables.sql`: `records`, `stub_records`; `telemetry/tables.sql`: `transcript`, `usage`, `turn_metrics`):

| Table | Columns |
|---|---|
| `sessions` | `id text pk`, `created_at`, `updated_at`, `ip_hash text`, `last_user_activity_at timestamptz`, `call_active bool default false`, `locked bool default false`, `state jsonb`, `version int` |
| `events` | `id bigserial pk`, `session_id`, `at`, `kind text`, `payload jsonb` |
| `records` | `session_id`, `revision int`, `outcome`, `payload jsonb`, `created_at`, `delivered_at null`, `attempts int default 0`, **pk (session_id, revision)** |
| `transcript` | `id`, `session_id`, `role`, `text`, `at` |
| `usage` | `id`, `session_id`, `kind text`, `quantity numeric`, `at` |
| `turn_metrics` | `id`, `session_id`, `eou_ms`, `llm_ttft_ms`, `tts_ttfb_ms`, `total_ms`, `at` |
| `stub_records` | `id`, `idempotency_key text unique`, `payload jsonb`, `received_at` |

  Use `CREATE TABLE IF NOT EXISTS`.

- [ ] **Step 1:** `git init`. Write `.gitignore` covering `.env*` (except `.env.example`), `.venv`, `node_modules`, `dist`, `__pycache__`. Write `docker-compose.yml` with service `db` (`postgres:16`, port 5433:5432, db `flight`, user/pass `dev`/`dev`).
- [ ] **Step 2:** `cd backend && uv init --python 3.12`. Add deps: `fastapi uvicorn[standard] asyncpg pydantic pydantic-settings livekit-api httpx`. Dev deps: `pytest pytest-asyncio`.
- [ ] **Step 3: Write the failing test** `tests/test_health.py::test_health_ok`. It asserts that `GET /health` returns 200 `{"ok": true, "db": true}`.
- [ ] **Step 4:** `docker compose up -d db`, then `uv run pytest -q`. Expected: FAIL (no app).
- [ ] **Step 5:** Implement `core/config.py`, `core/clock.py`, `core/db.py`, `core/auth.py`, `core/result.py`, the three `tables.sql` files, and `main.py`:
  - `create_app`: CORS from `allowed_origins`, `/health` does `select 1`, startup runs migrate.
  - `conftest.py`: `TEST_DATABASE_URL` defaults to `postgresql://dev:dev@localhost:5433/flight`. Each test drops and recreates the `public` schema.
- [ ] **Step 6:** `uv run pytest -q`. Expected: PASS.
- [ ] **Step 7: Commit** (if approved): `chore: scaffold backend, postgres, schema`

---

### Task 2: Catalog, flights and fare math (pure)

**Files:**
- Create: `backend/app/catalog/data/bookings.json`, `backend/app/catalog/models.py` (`Booking`, `Flight`, `Quote`), `backend/app/catalog/repository.py` (`load_bookings`, `get_booking`), `backend/app/catalog/service.py` (everything else below)
- Test: `backend/tests/catalog/test_catalog.py`

**Interfaces:**
- Produces:
  - `Passenger`, `Booking(pnr, status: Literal["confirmed","cancelled"], fare_class: Literal["saver","flex"], passengers: list[str], origin, destination, flight_no, departure: datetime, fare_per_pax: int, payment_method: str)`
  - `load_bookings(now) -> dict[str, Booking]`. Seed dates are offsets: `"departure": {"days": 5, "time": "07:05"}` or `{"hours": 2}`.
  - `Flight(id, flight_no, origin, destination, departure, arrival, fare: int, sold_out: bool)`
  - `flights_for(origin, destination, day: date, window: str) -> list[Flight]`. Sold-out flights are excluded. `id = f"{flight_no}-{day:%Y%m%d}"`.
  - `get_flight(flight_id) -> Flight | None`
  - `Quote(id, pnr, flight_id, pax, old_fare, new_fare, change_fee_per_pax, net: int, amount_due: int, refund_due: int, refund_to: str | None, expires_at)`
  - `make_quote(booking, flight, now) -> Quote`. The id is `q_` + 8 hex characters, derived deterministically from (pnr, flight_id, now minute).
  - `CHANGE_FEE = {"saver": 3000, "flex": 0}`
  - `QUOTE_TTL = timedelta(minutes=10)`
  - `WINDOWS = {"morning": (5,12), "afternoon": (12,17), "evening": (17,24), "any": (0,24)}`
- **Seed values (spec §5).** All passenger names are uppercase in the seed. The fictional airline code is `AQ`.

| PNR | Status | Class | Passengers | Route | Departure | Fare/pax | Payment |
|---|---|---|---|---|---|---|---|
| `ABC123` | confirmed | saver | `RAHUL SHARMA` | BLR-DEL | +5 days, 07:05 | 5400 | Visa •• 4242 |
| `PQR456` | confirmed | saver | `ANANYA IYER`, `KARTIK IYER` | BOM-DEL | +9 days, 18:40 | 6100 | Mastercard •• 1881 |
| `FLX789` | confirmed | flex | `MEERA NAIR` | BLR-BOM | +12 days, 09:35 | 8900 | UPI •• kotak |
| `CNX111` | cancelled | saver | `ARJUN MEHTA` | DEL-CCU | +6 days | 5000 | — |
| `OLD222` | confirmed | saver | `SNEHA RAO` | HYD-DEL | −2 days | 4900 | — |
| `SON333` | confirmed | saver | `VIKRAM SINGH` | BLR-DEL | +2 hours | 5200 | — |

- **Flight generator.** Routes and base fares:
  - BLR-DEL: 165 minutes, ₹5,200
  - BOM-DEL: 130 minutes, ₹4,800
  - BLR-BOM: 100 minutes, ₹3,900
  - CCU-BLR: 160 minutes, ₹5,600
  - DEL-CCU: 135 minutes, ₹5,000
  - HYD-DEL: 140 minutes, ₹4,900

  Departure slots: `06:10, 09:35, 13:20, 17:45, 21:05`. Flight number: `AQ{100*route_idx + slot_idx + 1}`.

  ```python
  h = int(sha256(f"{route}|{day}|{slot}".encode()).hexdigest(), 16)
  fare = round(base * (0.8 + 0.6 * (h % 1000) / 1000) / 50) * 50
  sold_out_slot = int(sha256(f"{route}|{day}".encode()).hexdigest(), 16) % 5
  ```

- [ ] **Step 1: Write the failing tests:**
  - `test_load_bookings_offsets`: with `now=2026-11-07T10:00+05:30`, `ABC123.departure == 2026-11-12T07:05+05:30` and `SON333.departure == now + 2h`.
  - `test_flights_deterministic`: two calls with the same arguments are equal.
  - `test_flights_exclude_sold_out_and_respect_window`: `"morning"` returns only departures with hour in [5,12), and there is never more than 4 per day.
  - `test_unknown_route_returns_empty`.
  - `test_quote_saver_pay_more`: old 5400, new 6200, 1 pax gives `net=3800, amount_due=3800, refund_due=0`.
  - `test_quote_saver_cheaper_still_pays_fee`: old 5400, new 4200 gives `net=1800`.
  - `test_quote_flex_refund`: old 8900, new 7400 gives `net=-1500, refund_due=1500, refund_to="UPI •• kotak"`.
  - `test_quote_two_pax`: PQR456, new 6500 gives `net=(6500-6100)*2+3000*2=6800`.
  - `test_quote_expiry`: `expires_at == now + 10min`.
- [ ] **Step 2:** `uv run pytest tests/catalog -q`. Expected: FAIL.
- [ ] **Step 3:** Implement the `catalog/` files and `bookings.json` to the interfaces above.
- [ ] **Step 4:** Run again. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: seeded bookings, flight generator, fare quotes`

---

### Task 3: Field definitions and validators (pure)

**Files:**
- Create: `backend/app/sessions/fields.py`
- Test: `backend/tests/sessions/test_fields.py`

**Interfaces:**
- Consumes: `Booking`, `load_bookings`, `get_flight` (Task 2).
- Produces (`Ok`/`Err` come from `core/result.py`):
  - `FieldName = Literal[...]` (the 8 names)
  - `CALL_NATIVE = {"changeReason","newTravelDate","timeFlexibility"}`
  - `CHAT_NATIVE = {"pnr","passengerNames","contactEmail","selectedFlight","fareAcceptance"}`
  - `REQUIRED_CHANGE = [changeReason,newTravelDate,timeFlexibility,pnr,passengerNames,selectedFlight,fareAcceptance]`
  - `REQUIRED_REFUND = [pnr,passengerNames,changeReason]`
  - `OPTIONAL = ["contactEmail"]`
  - `CHAT_ORDER = ["pnr","passengerNames","contactEmail","selectedFlight","fareAcceptance"]`
  - `normalize_pnr(raw, bookings, now) -> Ok|Err`
  - `normalize_name(raw) -> str` (uppercase, drop punctuation, collapse spaces, strip leading `MR|MRS|MS|MISS|DR|MASTER`)
  - `match_passenger(raw, booking, already: list[str]) -> Ok|Err`
  - `normalize_date(raw, now, current_departure: datetime | None) -> Ok|Err` accepts ISO `YYYY-MM-DD` only. The LLM resolves relative dates, and the date card sends ISO.
  - `normalize_flex(raw) -> Ok|Err` (one of the `WINDOWS` keys, lowercased and trimmed; `"any time"`, `"anytime"` and `"flexible"` map to `any`)
  - `normalize_reason(raw) -> Ok|Err` (text 3 to 500 characters; category is set separately)
  - `normalize_email(raw) -> Ok|Err`
  - `REASON_CATEGORIES = ["schedule","personal","medical","missedFlight","other"]`
- **Exact error copy** (the agent reads these aloud and the chat shows them; no em dashes):
  - PNR format: `"A booking reference has 6 letters or digits, like ABC123."`
  - PNR not found: `"I can't find a booking with that reference. Please check it."`
  - Cancelled: `"That booking is cancelled, so it can't be changed."`
  - Flown or under 3 hours: `"That flight has already left or leaves in under 3 hours, so it can't be changed here."`
  - Name: `"That name doesn't match a passenger on this booking. Please type it exactly as on the ID."`
  - Duplicate name: `"You've already given that passenger."`
  - Date format: `"Please give the date as a day, month and year."`
  - Past date: `"That date has passed. Please pick a future date."`
  - Too far: `"We can only book up to 330 days ahead."`
  - Same day as the current flight: `"That's the same day as your current flight. Please pick a different date."`
  - Flex: `"Please choose morning, afternoon, evening or any time."`
  - Email: `"That email address doesn't look right."`

- [ ] **Step 1: Write the failing tests** (`now = 2026-11-07T10:00+05:30`):
  - `test_pnr_normalizes_case_and_spaces`: `" abc 123 "` gives `Ok("ABC123")`.
  - `test_pnr_errors`: parametrize over `"AB12"`, `"ZZZ999"`, `"CNX111"`, `"OLD222"`, `"SON333"`, each giving the exact copy above.
  - `test_name_match_ignores_titles_case_punct`: `"mr. rahul  sharma"` against ABC123 gives `Ok("RAHUL SHARMA")`.
  - `test_name_mismatch_hides_real_names`: the Err message contains no booking name.
  - `test_name_duplicate_rejected`.
  - `test_date_rules`: parametrize over `"2026-11-06"` (past), `"2027-10-04"` (more than 330 days), `"2026-11-12"` with ABC123's departure (same day), `"13/12"` (format), each giving the exact copy. `"2026-12-13"` gives `Ok(date(2026,12,13))`.
  - `test_flex_aliases`: `"Any time"` gives `Ok("any")`, and `"night"` gives Err.
  - `test_email`: `"A@B.co"` gives `Ok("a@b.co")`, and `"a@b"` gives Err.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `sessions/fields.py`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: field validators and normalizers`

---

### Task 4: Session state and engine (pure)

**Files:**
- Create: `backend/app/sessions/models.py`, `backend/app/sessions/engine.py`
- Test: `backend/tests/sessions/test_engine.py`

**Interfaces:**
- Consumes: Task 2 and Task 3.
- Produces (`sessions/models.py`, camelCase aliases):

  ```python
  class FieldState(BaseModel): value: Any = None; source: Literal["call","chat"] | None = None
      collected_at: datetime | None = None; status: Literal["valid","missing","invalid"] = "missing"
      error: str | None = None; attempts: int = 0
  class Conflict(BaseModel): field: str; call_value: Any; chat_value: Any
      resolution: Literal["callValue","chatValue"] | None = None; reason: str | None = None
  class InputCard(BaseModel): id: str; field: str; kind: str; label: str; help: str | None = None
      placeholder: str | None = None; required: bool = True; pattern: str | None = None
      options: list[dict] | None = None; index: int | None = None   # passenger index
  class SessionState(BaseModel):
      session_id: str; request_type: Literal["change","refund"] = "change"
      fields: dict[str, FieldState]; candidates: dict[str, dict[str, Any]] = {}
      conflicts: list[Conflict] = []; open_card: InputCard | None = None
      requested: list[str] = []          # agent-requested chat fields, in order
      quote: Quote | None = None; offered_flight_ids: list[str] = []
      focus: str | None = None; opted_out: bool = False
      revision: int = 0; last_outcome: str | None = None; locked: bool = False
      calls: int = 0; call_seconds: int = 0; chat_messages: int = 0
      reason_category: str | None = None
  def new_state(session_id: str) -> SessionState
  ```

- Produces (`sessions/engine.py`). `Result` and `Event` are defined in `sessions/models.py`. Every command returns `Result(state: SessionState, events: list[Event], reply: Ok|Err)`. `Event(kind: str, payload: dict)` uses these kinds:
  - `message` (`{role:"agent", text}`)
  - `inputRequest` (InputCard payload)
  - `inputError` (`{requestId, message}`)
  - `inputCancel` (`{requestId, reason}`)
  - `answer` (`{field, value}`)
  - `fieldUpdate` (`{field, status, summary}`). This kind is also sent to the call.

  Commands:
  - `submit_call_value(state, field, raw, now, call_active) -> Result`
    - For a CALL_NATIVE field: validate and set with `source="call"`.
    - For a CHAT_NATIVE field: store as `candidates[field]["call"]` only, and reply `Ok`.
  - `request_chat_input(state, field, now, call_active) -> Result` appends to `requested` and calls `advance`.
  - `answer_card(state, request_id, value, now, call_active) -> Result`
    - A stale or closed `request_id` gives `inputError "This question is no longer open."`
    - A validation error gives `inputError` with the copy and `attempts += 1`.
    - `passengerNames` takes one card per passenger and stays `missing` until all are matched.
  - `resolve_conflict(state, field, choice: Literal["callValue","chatValue"], now) -> Result`
  - `refund_instead(state, now) -> Result` sets `request_type="refund"` and cancels open flight or fare cards.
  - `opt_out(state, now) -> Result`
  - `set_focus(state, field) -> Result`
  - `set_reason_category(state, category) -> Result`
  - `advance(state, now, call_active) -> Result` (public; Tasks 7, 8 and 9 call it): if no card is open, pick the next field to show:
    - If `call_active`: the first field in `requested` that is still not `valid`.
    - If not: the first non-valid field among `CHAT_ORDER` + CALL_NATIVE (asked last, as chat cards), skipping fields that don't apply. Refund requests skip `selectedFlight`, `fareAcceptance` and `contactEmail`.
    - `selectedFlight` is eligible only when `pnr`, `newTravelDate` and `timeFlexibility` are valid.
    - Builds the card (rules below).
- **Card rules:**
  - **`pnr`:** kind `text`, pattern `^[A-Za-z0-9]{6}$`, label `"Booking reference (PNR)"`.
  - **`passengerNames`:** kind `text`, label `"Passenger {i+1} of {n}: full name as on ID"`.
  - **`contactEmail`:** kind `email`, `required=False`, label `"Email for your new e-ticket (optional)"`. Skip value is `null`, and it becomes `status="valid", value=None`.
  - **`selectedFlight`:** kind `select`. Options come from `flights_for`, and each label reads `"AQ512 · 13 Dec 06:10 → 08:55 · ₹6,200/person · you pay ₹3,800"` (or `"refund ₹1,500"`). It sets `offered_flight_ids`.
    - **If there are no options:** the engine emits a `message` `"No seats match that date and time. Please pick another date or a wider time window."`, sets `newTravelDate` to `invalid`, and skips the card.
  - **`fareAcceptance`:** kind `confirm`. The label is the breakdown text from the quote. Accepting sets `value={accepted:true, quoteId, amountDue|refundDue, currency:"INR"}`.
    - **Declining** clears `selectedFlight`, `quote` and `offered_flight_ids` and re-offers the list.
    - **Accepting an expired quote** re-quotes. If `net` changed, the card is re-asked with the new amount.
  - **Call-native fields as chat cards:**
    - `changeReason`: kind `text`
    - `newTravelDate`: kind `date`
    - `timeFlexibility`: kind `select`, options from `WINDOWS`
- **Changing `newTravelDate` or `timeFlexibility` after a flight was offered:** emit `inputCancel` for any open flight or fare card, clear the quote and selection, then `advance`.
- **Conflicts (spec §8):** a value arrives from the other source and differs from the current value or candidate.
  - **CHAT_NATIVE:** auto-resolve with `resolution="chatValue", reason="typed value preferred over spoken"`. The field keeps the chat value.
  - **CALL_NATIVE:** record an unresolved conflict and set the field `status="invalid"` with `error="conflict"`. If not on a call, open a `select` card listing both values. `resolve_conflict` sets the chosen value and makes the field valid.
- **Locked state:** every command returns `Err("This request is already submitted.")` and no events.
- **Counting:** each `answer` increments `chat_messages`.

- [ ] **Step 1: Write the failing tests** (a helper builds a state with given valid fields):
  - `test_first_card_after_call_is_pnr`: no call, new state, `advance` opens a `pnr` card.
  - `test_one_card_at_a_time`: two `request_chat_input` calls give exactly one `inputRequest` event. The second appears only after the first is answered.
  - `test_stale_request_id_rejected`: answering an old id twice gives `inputError "This question is no longer open."` and the state is unchanged.
  - `test_passenger_cards_per_pax`: on PQR456, two cards in sequence. After both, `passengerNames.value == ["ANANYA IYER","KARTIK IYER"]`.
  - `test_attempts_increment_on_error`.
  - `test_flight_card_waits_for_date_and_flex`.
  - `test_no_flights_message_and_date_invalid` (Review Focus 5). Monkeypatch `flights_for` to return `[]`.
  - `test_date_change_cancels_open_flight_card` (Review Focus 4): an `inputCancel` with the old id, and `quote is None`.
  - `test_decline_fare_reoffers_list`.
  - `test_expired_quote_requotes_on_accept`.
  - `test_spoken_pnr_then_typed_differs_auto_resolves_chat`: the conflict has `resolution=="chatValue"` and the field value is the typed PNR.
  - `test_call_native_conflict_unresolved_marks_invalid`, then `resolve_conflict(...,"chatValue")` makes it valid.
  - `test_refund_instead_skips_flight_and_cancels_card`.
  - `test_email_skip_is_valid_none`.
  - `test_locked_rejects_everything`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `sessions/models.py` and `sessions/engine.py`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: pure session engine with chat queue and conflicts`

---

### Task 5: Outcome, record and pricing (pure)

**Files:**
- Create: `backend/app/records/outcome.py`, `backend/app/records/builder.py`, `backend/app/records/models.py` (`FinalRecord` pydantic model; `build_record` returns `FinalRecord.model_dump(by_alias=True)`), `backend/app/telemetry/pricing.py`
- Test: `backend/tests/records/test_outcome_builder.py`, `backend/tests/telemetry/test_pricing.py`

**Interfaces:**
- Consumes: `SessionState`, `REQUIRED_*`, `load_bookings`.
- Produces:
  - `decide_outcome(state, *, idle: bool) -> tuple[str, str] | None`. It returns `(outcome, outcomeReason)` or None. Precedence: `optedOut` > `needsReview` > `completed` > `partial`.

    | Outcome | Condition | Reason text |
    |---|---|---|
    | `optedOut` | `state.opted_out` | `"user asked to stop"` |
    | `needsReview` | `request_type=="refund"` and all `REQUIRED_REFUND` valid | `"refund requested instead of change"` |
    | `needsReview` | `idle` and any unresolved conflict | `"unresolved conflict on <field>"` |
    | `completed` | `request_type=="change"` and all `REQUIRED_CHANGE` valid and `fareAcceptance.value.accepted` | `"all required fields valid, fare accepted"` |
    | `partial` | `idle` and anything required not valid | `"user stopped responding with <comma list> missing"` |

  - `is_final(outcome) -> bool` (True for every outcome except `partial`).
  - `build_record(state, outcome, reason, *, now, cost_usd, ended_at) -> dict`. It returns camelCase JSON matching spec §9:
    - `sessionId`, `revision` (= `state.revision + 1`), `requestType`, `outcome`, `outcomeReason`
    - `fields`: all 8 keys, each `{value, source, collectedAt, status}`. `changeReason.value = {text, category}`.
    - `conflicts`
    - `booking`: `{pnr, route, originalFlight, originalDeparture, fareClass, paymentMethod}`. Present only if the PNR is valid.
    - `quote`: present only if the fare was accepted.
    - `engagement`: `{calls, callSeconds, chatMessages}`
    - `costUsd`, `endedAt`
  - `PRICES` (config dict, verify against vendor pages when deploying):

    | Key | Price |
    |---|---|
    | `deepgram_stt_per_min` | 0.0077 |
    | `deepgram_tts_per_1k_chars` | 0.030 |
    | `groq_in_per_m` | 0.15 |
    | `groq_out_per_m` | 0.60 |
    | `livekit_per_min` | 0.0 |

  - `cost_usd(usage_rows: list[tuple[str, float]]) -> float`. The kinds are `stt_seconds`, `tts_chars`, `llm_in_tokens`, `llm_out_tokens` and `call_seconds`. The result is rounded to 4 decimal places.

- [ ] **Step 1: Write the failing tests:**
  - `test_precedence_optout_beats_completed`.
  - `test_refund_needs_review_without_flight`.
  - `test_idle_with_conflict_is_needs_review_not_partial`.
  - `test_completed_requires_acceptance`.
  - `test_partial_reason_lists_missing`: the reason is `"user stopped responding with pnr, selectedFlight, fareAcceptance missing"`.
  - `test_not_idle_and_incomplete_returns_none`.
  - `test_record_has_all_fields_and_iso_offsets`: every `collectedAt` ends with `+05:30`, and missing fields have `value None, source None, status "missing"`.
  - `test_record_revision_increments`.
  - `test_record_has_no_passenger_names_outside_fields`.
  - `test_cost_usd`: 240 s STT, 2000 TTS chars, 20k in, 3k out gives `0.0308 + 0.06 + 0.003 + 0.0018 = 0.0956`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement the four modules.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: outcome rules, record builder, pricing`

---

### Task 6: Store, outbox and exactly-once delivery

**Files:**
- Create: `backend/app/sessions/repository.py`, `backend/app/sessions/service.py` (`create_session`, `apply`, `load`, `events_since`), `backend/app/records/repository.py`, `backend/app/records/service.py` (`deliver_pending`), `backend/app/records/router.py` (stub), `backend/app/telemetry/repository.py` (`usage_rows(session_id)` only, for now)
- Test: `backend/tests/sessions/test_apply.py`, `backend/tests/records/test_delivery.py`

**Interfaces:**
- Consumes: the engine (Task 4), `decide_outcome`, `build_record`, `cost_usd` (Task 5), `pool` (Task 1).
- Produces:
  - `create_session(pool, ip_hash, now) -> str`. The id is `"s_" + secrets.token_hex(5)`.
  - `apply(pool, session_id, fn: Callable[[SessionState], Result], *, now, user_activity: bool, idle: bool = False) -> ApplyOutcome(state, events, reply, record: dict | None)`. In **one transaction** it:
    1. `SELECT ... FOR UPDATE` the session row.
    2. Runs `fn`.
    3. Runs `decide_outcome(state, idle=idle)`. If it returns an outcome different from `last_outcome`, or a new state after a `partial`, it builds the record (with `cost_usd` from this session's `usage` rows), bumps `revision`, sets `last_outcome` and sets `locked = is_final(...)`.
    4. Inserts the events and the `records` row (`ON CONFLICT DO NOTHING`).
    5. Saves the state, `version+1` and `last_user_activity_at` if `user_activity`.
  - **A `partial` session that receives a new user answer is re-opened** (not locked), and the next record gets revision+1.
  - `load(pool, session_id) -> SessionState`
  - `events_since(pool, session_id, after_id: int) -> list[(id, kind, payload)]`
  - `deliver_pending(pool, http: httpx.AsyncClient, stub_url) -> int`. It POSTs each undelivered record with header `Idempotency-Key: {sessionId}:{revision}`, sets `delivered_at` on 2xx, and otherwise `attempts += 1`. It also logs `json.dumps(record)` as one line.
  - `POST /stub/records`: inserts into `stub_records` with `ON CONFLICT (idempotency_key) DO NOTHING` and returns `{"ok":true, "duplicate": bool}`. `GET /stub/records` lists the newest first.

- [ ] **Step 1: Write the failing tests** (they use the real Postgres fixture):
  - `test_apply_persists_state_and_events`.
  - `test_completed_writes_one_record_and_locks`.
  - `test_record_written_once_even_if_apply_repeats`: running the same final transition twice gives `count(records) == 1`.
  - `test_restart_between_write_and_delivery` (Review Focus 3): write the record, build a **new** pool, run `deliver_pending` twice, and assert `stub_records` has 1 row and `records.delivered_at` is not null.
  - `test_stub_dedupes_idempotency_key`.
  - `test_partial_then_return_creates_revision_2`.
  - `test_concurrent_answers_one_wins` (Review Focus 1): two concurrent `apply` calls answering the same card give one `answer` event and one `inputError`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: transactional store, record outbox, idempotent delivery`

---

### Task 7: Public API, chat socket and rate limits

**Files:**
- Create: `backend/app/core/ratelimit.py`, `backend/app/sessions/{schemas,router,effects,classify}.py`, `backend/app/chat/{hub,schemas,service,router}.py`
- Test: `backend/tests/sessions/test_router.py`, `backend/tests/chat/test_chat_ws.py`

**Interfaces:**
- Consumes: `sessions.service` (Task 6), the engine commands (Task 4).
- Produces:
  - `Hub.publish(session_id, event_id, kind, payload)`, `Hub.subscribe(session_id) -> AsyncIterator`. This is in-process, which is fine with `max-instances=1`.
  - `after_apply(app, session_id, outcome: ApplyOutcome) -> None`. It lives in `sessions/effects.py`, and every caller of `sessions.service.apply` uses it. It:
    - publishes the events to the hub
    - forwards `fieldUpdate`, `answer` and `message` events to the call via `calls.livekit.send_event` when `call_active`. Task 8 adds this branch. In Task 7 it is absent.
    - schedules `deliver_pending` when a record was written
    - publishes `{type:"record", record}` to the chat
  - `POST /sessions` returns `{sessionId}`.
    - It returns 429 with `{"error":"Too many sessions from this network. Try again later."}` after 10 per `ip_hash` per hour.
    - It returns 503 when the `DAILY_SESSION_CAP` is reached.
    - `ip_hash = sha256(ip + service_token)[:16]`. The IP comes from `X-Forwarded-For` (first entry) on Cloud Run.
  - `GET /sessions/{id}` returns `{sessionId, locked, outcome, callActive}`, or 404.
  - `WS /chat?sessionId=&after=<eventId>`. On connect, it replays `events_since(after)` as starter messages:
    - `message` → `{type:"message", role, text, id}`
    - `inputRequest` → `{type:"inputRequest", ...card}`
    - `inputError`, `inputCancel`, `record`
    - `answer` → `{type:"message", role:"user", text:<display value>}`
    - Every message also carries `eventId`.

    Then it streams live events. Client messages:
    - `{type:"inputResponse", requestId, field, value}` → `answer_card`
    - `{type:"optOut"}` → opens a `confirm` card `"Stop this request? Nothing will be changed."` (field `__optOut`). Accepting it runs `opt_out`.
  - **First chat connect on a new session:** the backend emits the welcome `message`: `"Hi! I can help you change your flight. Tap the call button above to start, or answer the questions here."` Then `advance(call_active=False)` is called **only if** no call has started within 20 seconds of the first chat connect. This is a one-shot delayed task, and it is also re-checked by the sweep.
  - **Reason typed in chat:** when `changeReason` is answered in chat, `classify_reason(text) -> str` makes one Groq call (`openai/gpt-oss-20b`, low reasoning effort). It returns one of `REASON_CATEGORIES`, then `set_reason_category` runs. On any error or unknown label, the category is `"other"`. The function lives in `backend/app/sessions/classify.py`.

- [ ] **Step 1: Write the failing tests** (using `httpx` + `asgi-lifespan`, and Starlette's `TestClient` for the WebSocket):
  - `test_chat_reason_gets_category`: Groq is mocked with `respx`. A reply of `"medical"` gives category `medical`. A 500 error or a reply of `"banana"` gives `other`.
  - `test_create_session_and_rate_limit`: the 11th call from the same IP gets 429.
  - `test_ws_replays_history_after_reconnect`: answer the PNR card, disconnect, reconnect with `after=<first id>`, and receive only the later events.
  - `test_ws_input_flow_pnr_ok_then_names_card`.
  - `test_ws_stale_answer_gets_error` (Review Focus 1).
  - `test_ws_optout_confirm_produces_record`: the last message is `type=="record"` with `outcome=="optedOut"`.
  - `test_locked_session_rejects_answers`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: public API, chat websocket with replay, rate limits`

---

### Task 8: LiveKit bridge and internal API for the agent

**Files:**
- Create: `backend/app/calls/{livekit,schemas,service,router}.py`, `backend/app/telemetry/{schemas,router}.py` (transcript, usage, metrics endpoints), and extend `backend/app/telemetry/repository.py`
- Test: `backend/tests/calls/test_internal.py`, `backend/tests/calls/test_livekit.py`, `backend/tests/telemetry/test_router.py`

**Interfaces:**
- Consumes: `sessions.service`, `sessions.engine`, `sessions.effects.after_apply` (Task 7).
- Modify: `backend/app/sessions/effects.py` (add the call-forwarding branch).
- Produces:
  - `room_name(session_id) -> f"call-{session_id}"`
  - `AGENT_NAME = "flight-agent"`
  - `mint_token(session_id, identity) -> str`: room join for this room only, `can_publish` (mic), `can_subscribe`, `can_publish_data=False`, TTL 15 min.
  - `ensure_dispatch(session_id) -> None`:
    1. Creates the room if it is missing, with `departure_timeout=120` and `empty_timeout=120`. This lets a closed or reloaded tab rejoin the same agent (spec §10).
    2. Creates an explicit agent dispatch with `metadata=json.dumps({"sessionId": ...})`. It skips this if a dispatch already exists for the room.
  - `send_event(session_id, kind, payload) -> None`: `RoomService.send_data` with topic `session-events`, reliable. It logs failures and never raises.
  - `POST /sessions/{id}/call-token` returns `{token, url: LIVEKIT_URL, room}`. It returns 409 if the session is locked.
  - `/internal/*` requires `Authorization: Bearer {SERVICE_TOKEN}`, else 401. **Every endpoint returns HTTP 200 with `{ok: bool, error?: str, ...}` for domain errors** (Review Focus 2). An unknown field gives `ok:false, error:"Unknown field."`.
  - Endpoints (path prefix `/internal/sessions/{id}`):

    | Method | Path | Body | Action |
    |---|---|---|---|
    | GET | `/context` | — | Returns `{state, openCard, focus, transcript: last 20 [{role,text}], today: "YYYY-MM-DD", bookingSummary \| null}`. `bookingSummary` (route, original date and time, pax count) is present only if the PNR is valid. No names. |
    | POST | `/fields` | `{field, value}` | `submit_call_value` |
    | POST | `/chat-input` | `{field}` | `request_chat_input` |
    | POST | `/conflicts/{field}/resolve` | `{choice}` | `resolve_conflict` |
    | POST | `/refund-instead` | — | `refund_instead` |
    | POST | `/opt-out` | — | `opt_out` |
    | POST | `/focus` | `{field}` | `set_focus` |
    | POST | `/reason-category` | `{category}` | `set_reason_category` |
    | POST | `/call` | `{active: bool, seconds?: int}` | Sets `call_active`. `active=true` increments `calls`. `active=false` adds `call_seconds` and calls `advance(call_active=False)` so the chat takes over. |
    | POST | `/transcript` | `{role, text}` | Appends to the table. Counts as user activity when the role is user. |
    | POST | `/usage` | `{kind, quantity}` | Appends usage. |
    | POST | `/metrics` | `{eouMs, llmTtftMs, ttsTtfbMs}` | Appends turn metrics (`total_ms` = the sum). |

  - `POST /internal/sweep` is in Task 9.

- [ ] **Step 1: Write the failing tests** (`livekit-api` is mocked):
  - `test_internal_requires_token`.
  - `test_fields_messy_date_returns_speakable_error` (Review Focus 2): `{"field":"newTravelDate","value":"Dec 13th"}` gives 200 `{ok:false, error:"Please give the date as a day, month and year."}`.
  - `test_unknown_field_ok_false`.
  - `test_chat_answer_during_call_sends_room_event`: `send_event` is called with `kind="fieldUpdate"` and `field="pnr"`.
  - `test_call_end_hands_over_to_chat`: after `/call {active:false}`, the chat gets the next card.
  - `test_context_has_no_passenger_names`.
  - `test_call_token_scoped_to_room`: decode the JWT and assert the `video.room == "call-<id>"` grant and that `exp - iat == 900`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit:** `feat: livekit token/dispatch/data bridge and internal agent API`

---

### Task 9: Sweep and startup recovery

**Files:**
- Create: `backend/app/jobs/service.py` (`sweep`), `backend/app/jobs/router.py` (`POST /internal/sweep`)
- Modify: `backend/app/main.py` (startup calls `sweep`)
- Test: `backend/tests/jobs/test_sweep.py`

**Interfaces:**
- Consumes: `sessions.service.apply`, `records.service.deliver_pending`, `records.outcome.decide_outcome`.
- Produces: `sweep(pool, http, now) -> {"closed": int, "delivered": int, "chatStarted": int}`. It:
  - For each unlocked session with `call_active=false` and `last_user_activity_at < now - 30min`, whose last outcome is not already `partial` at the same `version`: runs `apply(..., fn=identity, idle=True, user_activity=False)`.
  - Starts the chat flow for sessions where the chat connected but no call started for over 20 seconds and no card is open.
  - Runs `deliver_pending`.
  - **A stale `call_active`** (no transcript or metrics for 15 minutes, which covers a crashed agent) is reset to false.

- [ ] **Step 1: Write the failing tests:**
  - `test_idle_incomplete_becomes_partial`.
  - `test_recent_activity_not_partial` (Review Focus 3).
  - `test_active_call_not_partial`.
  - `test_sweep_idempotent`: a second run writes no new record.
  - `test_idle_with_conflict_needs_review`.
  - `test_stale_call_flag_reset`.
  - `test_sweep_endpoint_requires_token`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Run the full backend suite: `uv run pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit:** `feat: idle sweep, startup recovery`

---

### Task 10: Voice agent

**Files:**
- Create: `agent/pyproject.toml`, `agent/agent.py`, `agent/backend_client.py`, `agent/tools.py`, `agent/prompts.py`, `agent/.env.example`, `agent/Dockerfile`, `agent/livekit.toml`
- Test: `agent/tests/test_tools.py`, `agent/tests/test_prompts.py`

**Interfaces:**
- Consumes: the `/internal/*` contract (Task 8). Room data topic `session-events` with payload `{kind, payload}`.
- **Dependencies:** `livekit-agents[deepgram,silero,turn-detector,openai]` (latest 1.x), `httpx`. Dev: `pytest pytest-asyncio respx`. **Before writing the code, check the installed package's API names** (`AgentSession`, `function_tool`, `RoomInputOptions`, agent-name dispatch, `metrics_collected`, `conversation_item_added`). Follow the installed version where it differs from this plan.
- Produces:
  - `BackendClient(base_url, token)` with async methods matching each internal endpoint: `context`, `submit_field`, `request_chat_input`, `resolve_conflict`, `refund_instead`, `opt_out`, `set_focus`, `set_reason_category`, `call_status`, `transcript`, `usage`, `metrics`. Each returns a dict.
  - `tools.py`: a `FlightAgent(Agent)` with `@function_tool`s. Each returns the backend's `error` string on `ok:false`, so the LLM can say it.

    | Tool | Backend call |
    |---|---|
    | `record_answer(field, value)` | `/fields` |
    | `send_chat_request(field)` | `/chat-input` |
    | `note_spoken_value(field, value)` | `/fields` for chat-native fields |
    | `resolve_conflict(field, choice)` | `/conflicts/{field}/resolve` |
    | `set_reason_category(category)` | `/reason-category` |
    | `switch_to_refund()` | `/refund-instead` |
    | `stop_request()` | `/opt-out`, only after the user confirms |
    | `check_status()` | `/context`, summarized |
    | `end_call()` | ends the call |

  - `prompts.py`:
    - `system_prompt(ctx: dict) -> str`. It includes: today's date (IST), the field rules, the "never invent flights or fares" rule, "never read passenger names", "one chat request at a time", "confirm dates by reading them back", "short replies, 1 to 2 sentences", and "no em dashes" (TTS).
    - `resume_line(ctx) -> str | None`. When the transcript is non-empty, it returns `"Sorry, we got cut off. "` + the question for `ctx["focus"]` (or the next missing field). Otherwise None.
    - `event_note(kind, payload) -> str`. Turns a `fieldUpdate` into a context note, for example `"The user just submitted pnr in chat. It is valid. Route BLR to DEL on 12 Nov."`
- **Wiring in `agent.py`:**
  - Register with `agent_name="flight-agent"`.
  - Read `sessionId` from the job metadata.
  - `stt=deepgram.STT(model="nova-3", language="en-IN" if supported else "en")`
  - `llm=openai.LLM.with_groq(model="openai/gpt-oss-120b")` with reasoning effort `low` (use the plugin's parameter, or extra body)
  - `tts=deepgram.TTS(model="aura-2-<voice>-en")`
  - `vad=silero.VAD.load()`, turn detector `EnglishModel`
  - Room input with `close_on_disconnect=False`
  - On start: `call_status(active=True)`, load the context, then either say `resume_line` or greet. Greeting: `"Hi, I can help you change your flight. What's the reason for the change?"`
  - On `data_received` with topic `session-events`: add an `event_note` to the chat context. If neither side is speaking, `generate_reply` so the agent acknowledges at once. Otherwise the note is used at the next turn.
  - On `conversation_item_added`: POST the transcript.
  - On `metrics_collected`: POST usage (STT seconds, TTS characters, LLM tokens) and per-turn metrics.
  - Hang up after 10 minutes: say `"We're at the time limit for this call. You can finish in the chat."` and end.
  - On shutdown or disconnect: `call_status(active=False, seconds=...)`.
  - When the backend replies with an outcome (`check_status` shows locked), say the summary line from spec §9 and `end_call`.

- [ ] **Step 1: Write the failing tests** (`respx` mocks the backend):
  - `test_record_answer_returns_backend_error_text`.
  - `test_tools_send_bearer_token`.
  - `test_resume_line_when_transcript_exists`: `focus="pnr"` gives text that starts with `"Sorry, we got cut off."`.
  - `test_no_resume_line_on_fresh_session`.
  - `test_system_prompt_has_rules_and_today`: it contains the IST date and `"never"` + `"fare"` rule text, and has no `"—"`.
  - `test_event_note_for_valid_pnr`.
- [ ] **Step 2:** `cd agent && uv run pytest -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `backend_client.py`, `prompts.py`, `tools.py`, `agent.py`. Generate `Dockerfile` and `livekit.toml` with `lk agent create` (or by hand from LiveKit's Python template).
- [ ] **Step 4:** `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Local smoke:**
  - Run the backend with `uv run uvicorn app.main:app --port 8080` (with the env from secrets and `DATABASE_URL` pointing at Docker).
  - Run the agent with `uv run python agent.py dev`.
  - Mint a token with `curl -XPOST localhost:8080/sessions` and `.../call-token`.
  - Join the room with the LiveKit Agents Playground (or the web app after Task 11).
  - Expected: you hear the greeting, interrupting stops the agent's speech, and transcript rows appear in the `transcript` table.
- [ ] **Step 6: Commit:** `feat: livekit voice agent with backend tools and resume`

---

### Task 11: Web app

**Files:**
- Create: `web/` (copy of `starter/` from `https://github.com/Hunar-ai/ai-engineer-assignment`, copied, not forked), `web/src/hooks/useSession.ts`, `web/src/components/header/StopButton.tsx`, `web/src/components/thread/Banner.tsx`
- Modify: `web/src/hooks/useCall.ts` (rewrite), `web/src/hooks/useChat.ts` (`after` param, `optOut` send, handle `eventId`), `web/src/protocol/types.ts` (add `OptOut` client message and `eventId?`), `web/src/App.tsx`, `web/src/config.ts`, `web/package.json` (add `livekit-client`)

**Interfaces:**
- Consumes: `POST /sessions`, `POST /sessions/{id}/call-token`, `WS /chat`, the starter `Ui` interface (`addTranscript`, `addMessage`, `showInputCard`, `rejectInputCard`, `cancelInputCard`, `showRecord`).
- Produces:
  - **`useSession()`:** returns `sessionId`. If `?sessionId=` is missing, it calls `POST /sessions` and `history.replaceState`s the id into the URL. It shows an error line on 429 or 503.
  - **`useCall`:**
    - Fetches a token, then `new Room({adaptiveStream:true})`, `room.connect(url, token)`, `setMicrophoneEnabled(true)`, and attaches remote audio.
    - Registers a text-stream handler for `lk.transcription` that calls `ui.addTranscript(role, text, final, id)`.
    - Room events drive a call state: `RoomEvent.Reconnecting` → `"reconnecting"`, `Reconnected` → `"live"`, `Disconnected` → `"ended"`.
    - Shows `"connecting"` until the agent participant joins.
    - The mic meter keeps working through the starter's `micLevel` store, fed from the local track's analyser.
  - **`Banner`:** shows "Connecting to the agent…" or "Reconnecting…" from the call state (no em dashes).
  - **`StopButton`:** in the header. It sends `{type:"optOut"}`.
  - **`useChat`:** remembers the last `eventId` and reconnects with `after=`. Chat state survives a page reload because the server replays everything.
  - **Config:** only `VITE_SERVER_URL`.

- [ ] **Step 1:** Copy the starter, `npm install`, `npm i livekit-client`. Check that `npm run build` passes before any change.
- [ ] **Step 2:** Implement the changes above.
- [ ] **Step 3:** `npm run build`. Expected: the type-check and build pass.
- [ ] **Step 4: Headless check.** Use a Playwright script with headless Chromium, `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`, against local backend + agent + `npm run dev`:
  - The page loads and the URL gets `?sessionId=s_…`.
  - The welcome message shows.
  - Click call; the banner shows and then clears.
  - Within 15 seconds, an agent transcript row appears.
  - Type `ABC123` into the PNR card when it shows; a user bubble appears.

  Report pass or fail with console errors. **Use one ≤1000px screenshot only if a check fails.**
- [ ] **Step 5: Commit:** `feat: web app on livekit-client with session, stop, banners`

---

### Task 12: Deploy

**Files:**
- Create: `backend/Dockerfile` (python:3.12-slim, `uv sync --frozen`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`), `web/vercel.json` (SPA rewrite)
- Modify: `README.md` (deploy section)

**Interfaces:**
- Consumes: everything above.
- Produces: public URLs. Record them in the README:
  - `https://<vercel-app>.vercel.app` (web)
  - `https://<service>-<hash>.a.run.app` (backend)

- [ ] **Step 1: Neon.** Ask the user to create a free Neon project, or use the Neon CLI if it is installed and logged in. Get `DATABASE_URL` (pooled, `sslmode=require`) and store it in `~/.config/zsh/secrets.zsh` as `export NEON_DATABASE_URL=...`. Never print it.
- [ ] **Step 2: Secrets.** Generate `SERVICE_TOKEN` (`openssl rand -hex 32`) and store it in the same file. Create Secret Manager secrets in `my-stuff-ai`:
  - `groq-api-key`, `deepgram-api-key`, `livekit-api-key`, `livekit-api-secret`
  - `database-url`, `service-token`
- [ ] **Step 3: Backend.** From `backend/`, run:
  ```bash
  gcloud run deploy flight-backend --source=. --region=asia-south1 --allow-unauthenticated --max-instances=1 --timeout=3600 --set-secrets=...
  ```
  Set env `LIVEKIT_URL` and `ALLOWED_ORIGINS` (filled in after Step 5). Verify `curl https://.../health` gives `{"ok":true,"db":true}`.
- [ ] **Step 4: Agent.** From `agent/`, run `lk agent create` (first time) or `lk agent deploy`, with secrets `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `BACKEND_URL`, `SERVICE_TOKEN`. LiveKit credentials come from the CLI's project. Verify `lk agent status` shows it running or sleeping.
- [ ] **Step 5: Web.** Run `vercel --prod` from `web/` with `VITE_SERVER_URL=<backend url>`. Then update the backend `ALLOWED_ORIGINS` to the Vercel URL and redeploy (Step 3).
- [ ] **Step 6: Scheduler.** Create a Cloud Scheduler job: `*/5 * * * *`, POST `<backend>/internal/sweep`, header `Authorization: Bearer <SERVICE_TOKEN>`.
- [ ] **Step 7: Prod smoke.** Re-run the Task 11 Playwright check against the Vercel URL. Then run one full session by hand (the user, with headphones):
  - ABC123 with an afternoon flight should end in a `completed` record that is visible in chat and at `GET /stub/records`.
  - Restart the backend (`gcloud run services update flight-backend --update-env-vars=RESTART=$(date +%s)`) mid-session. Expected: the chat resumes, and no duplicate record appears.
- [ ] **Step 8: Commit:** `chore: deploy config`

---

### Task 13: Latency report and README

**Files:**
- Create: `scripts/latency_report.py`, `README.md`

**Interfaces:**
- Consumes: the `turn_metrics` and `usage` tables, the record `costUsd`.
- Produces:
  - `latency_report.py --database-url $NEON_DATABASE_URL [--since 2026-11-07]` prints `n`, then p50 and p95 of `total_ms`, and p50 of each part. Percentiles use `statistics.quantiles(..., n=100)`.
  - `README.md` with every section the brief requires (§ "What to submit"):
    - architecture and shared state, with the diagram from spec §4
    - record sanitization: the validators, normalization and conflict rules
    - outcomes, delivery and revisions
    - stack and cost (150 words or fewer)
    - product decisions (the **[call]** items from the spec)
    - edge cases handled and not handled
    - what I trust least
    - cost and latency, with the numbers from real test calls
    - next week
    - AI-tool notes
    - local run steps
    - the JSON Schema of the record
    - the bonus list as "Later"
    - the public URL

    Writing style: plain short sentences and bulleted bold leads.

- [ ] **Step 1: Write the failing test** `backend/tests/telemetry/test_latency_report.py::test_percentiles`: seeded metrics `[800, 900, 1000, 1100, 3000]` give `p50 == 1000`. Import the function from `scripts/latency_report.py` via the path.
- [ ] **Step 2:** Run. Expected: FAIL. Implement. Run. Expected: PASS.
- [ ] **Step 3:** After at least 10 real test calls, run the script against prod. Paste the p50 and p95 into the README, with how it was measured (the agent's per-turn metrics: end-of-utterance delay + LLM time to first token + TTS time to first byte).
- [ ] **Step 4:** Compute the cost per completed session as the mean `costUsd` of the `completed` records in `stub_records`. Show the per-vendor breakdown in the README.
- [ ] **Step 5: Commit:** `docs: README, latency and cost report`
