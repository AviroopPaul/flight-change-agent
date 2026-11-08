# Build Log

Plan: [docs/superpowers/plans/2026-11-07-flight-change-agent.md](docs/superpowers/plans/2026-11-07-flight-change-agent.md)
Spec: [docs/superpowers/specs/2026-11-07-flight-change-agent-design.md](docs/superpowers/specs/2026-11-07-flight-change-agent-design.md)

## Status

| # | Task | Status | Commit |
|---|---|---|---|
| 1 | Repo scaffold, Postgres, backend skeleton | done | `1fd02f4` |
| 2 | Catalog, flights, fare math | done | `9d3bc97` |
| 3 | Field validators | done | `2b8307a` |
| 4 | Session engine | done | `a9b51f9` |
| 5 | Outcome, record, pricing | done | `cd71b2d` |
| 6 | Store, outbox, delivery | done | `42db1ee` |
| 7 | Public API, chat socket, rate limits | done | `3355355` |
| 8 | LiveKit bridge, internal API | done | `02ce765` |
| 9 | Sweep, startup recovery | done | `b486d24` |
| 10 | Voice agent | done | `5b1e36f` |
| 11 | Web app | done | `1e53f78` |
| 12 | Deploy | done | see Commits |
| 13 | Latency report, README | done except real numbers (need deploy) | `455226b` |

## Commits
- `1fd02f4` chore: scaffold backend, postgres, schema (Task 1)
- `9d3bc97` feat: seeded bookings, flight generator, fare quotes (Task 2)
- `2b8307a` feat: field validators and normalizers (Task 3)
- `a9b51f9` feat: pure session engine with chat queue and conflicts (Task 4)
- `cd71b2d` feat: outcome rules, record builder, pricing (Task 5)
- `42db1ee` feat: transactional store, record outbox, idempotent delivery (Task 6)
- `3355355` feat: public API, chat websocket with replay, rate limits (Task 7)
- `02ce765` feat: livekit token/dispatch/data bridge and internal agent API (Task 8)
- `b486d24` feat: idle sweep, startup recovery (Task 9)
- `5b1e36f` feat: livekit voice agent with backend tools and resume (Task 10)
- `1e53f78` feat: web app on livekit-client with session, stop, banners (Task 11)
- `6b68ed4` chore: deploy config (backend Dockerfile, vercel.json, Neon-safe pool) (Task 12, partial)
- `455226b` docs: README, latency report, record schema (Task 13)
- `e1da6b0` fix: drop redundant agent notes, delete room when caller leaves (final review)
- `423b27b` fix: Gemini LLM, chat order during calls, spoken dates, speech timing, fewer tool round trips (after first live test)

## Decisions made during the build

- **Local Postgres:** Docker Desktop did not start from the shell. Homebrew `postgresql@16` runs on port 5433 (db `flight`, user `dev`/`dev`), the same URL as `docker-compose.yml`. Tests use a separate `flight_test` database.
  - Start it: `LC_ALL=en_US.UTF-8 /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D /opt/homebrew/var/postgresql@16 -o "-p 5433" -l /opt/homebrew/var/log/pg16-5433.log start`
- **Commits:** local only, on `main`. Nothing is pushed.
- **LiveKit Agents 1.8.11:** Groq goes through `openai.LLM(base_url=...)`; there is no `with_groq`.
- **Groq free tier:** 8,000 tokens per minute per model. A live test hit a 429 on the third turn. The agent now falls back from `gpt-oss-120b` to `gpt-oss-20b`.
- **Found in live smoke runs and fixed:** a tool schema Groq rejected (`anyOf`), em dashes from the LLM, and a reason category the LLM never set (the backend now classifies it).
- **Neon:** project `flight-change-agent` (Singapore). Its URL is `NEON_DATABASE_URL` in your secrets file. `SERVICE_TOKEN` is there too.
- **Final review:** a self-review (no sub-agents, as asked). Two Important fixes. Four minors deferred.

## Left to do

- **Live now (Task 12 done):** web https://flight-change-agent.vercel.app, backend https://flight-backend-820256992821.asia-south1.run.app (Cloud Run, `asia-south1`, max 1 instance), 5 secrets in Secret Manager, Cloud Scheduler job `flight-sweep` every 5 minutes. Prod chat check: 4/4 pass.
- **Agent:** hosted on a new LiveKit Cloud project (`hunar-yc8zto2u`, region `ap-south`, agent `CA_rkA3QfFypR48`), so `memoji` is untouched. Its keys are `FLIGHT_LIVEKIT_*` in `secrets.zsh`. Prod browser check: 6/6 pass, including the call.
- **Task 13 numbers:** at least 10 real calls on the deployed system, then paste p50/p95 latency and cost per completed session into the README.
- **LLM moved to Gemini 3.5 Flash-Lite** (fallback 3.5 Flash) after Groq's free tier rate-limited the first live test; Groq Dev upgrades were paused. Then moved from the AI Studio key (free tier, no billing) to **Vertex AI** in `my-stuff-ai`, `asia-south1`: ADC locally; on LiveKit Cloud a key for service account `flight-agent-llm` (Vertex AI User role only) in the `GOOGLE_CREDENTIALS_JSON` secret. `GOOGLE_API_KEY` removed from the agent secrets. Prod smoke `s_2362fc70dc`: LLM first token 0.6 s and 2.2 s.
- **LLM now Gemini 3.1 Flash-Lite** (`global`), fallback 3.5 Flash-Lite (`asia-south1`): cheapest live Gemini. Tool-call check on the real prompt (6 cases x 3): both 18/18; first token p50 1.07 s vs 0.51 s. 2.5 Flash-Lite returns 404 (retired). LLM cost about $0.0075 per session (25.8k in, 670 out tokens), vs $0.0094 on 3.5 Flash-Lite. Live smoke `s_8657e1514c`, `s_3d2aedd05c`: fields right, but tool-chain turns took 7.1 s and 9.4 s to first token (3.5 Flash-Lite: about 2 s). Service-account key now parsed in prewarm (it blocked the event loop ~200 ms).
- **Back to 3.5 Flash-Lite** (`asia-south1`) as the main LLM, 3.1 Flash-Lite (`global`) as fallback: the speed cost of 3.1 was not worth $0.002 per session. Prod smoke `s_2a5c0502d9` correct.
- **New chat button** in the header (pencil icon): loads the page without `?sessionId=`, so a new session starts; asks first during a call. Old session URLs still open. Prod checks: new-chat flow 2/2, web check 6/6. Header fits at 320/375/500 px (avatar hidden under 360 px).
- **Chat UI rework (after the second live test, `s_7cd7959fb2`):** every question is an agent message in the thread; dates, choices, flights, the fare and the optional email are answered inside it; the bottom bar is text only. The optional email now opens in an engine side slot (`side_card`), so the flights no longer wait for it; submit, refund and stop close it. New final record card (outcome header, trip / payment / request rows with icons and call/chat tags, engagement line). Also fixed from that run: the same date said on the call no longer changes its source from chat to call; the spoken summary reads the date in words; a record built mid-call counts the running call time (was 0); a StrictMode double-mount in dev wrote the wrong session id into the URL. Backend 144 tests; prod UI flow 12/12.
- **One input at a time again (brief, must-have 2):** removed the email side slot; the optional email blocks until it is typed or skipped. The call agent now waits too: the last chat fieldUpdate forwarded to the call carries `openCard`, the agent prompts for that card once and asks no new spoken question until it is submitted; a spoken save while a card is open returns a wait hint; a newer chat answer cancels a stale unspoken reply. Mixed voice+chat smoke `s_69a9026185`: agent named each card 4-5 s after the previous answer, held at the email box, asked the date 4 s after Skip. Backend 142, agent 23 tests; prod UI flow 12/12.
- **Vercel:** `VITE_SERVER_URL` is now a production env var. A deploy without it shipped a page with no backend for a few minutes.
- **Deferred minors:** chat autostart can race a cold-starting agent; no timeout on "waiting for the agent"; a PNR change does not re-check the date's same-day rule; the sweep re-advances idle chat sessions (no-op writes).
