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
| 12 | Deploy | blocked (needs your OK for secrets) | config only |
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

- **Task 12 deploy (blocked):** the permission classifier denied writing the API keys to GCP Secret Manager. Needs your OK. After that: Cloud Run backend, LiveKit Cloud agent (`lk project add` + `lk agent create`), Vercel web, Cloud Scheduler sweep, prod smoke.
- **Task 13 numbers:** at least 10 real calls on the deployed system, then paste p50/p95 latency and cost per completed session into the README.
- **Your choice:** Groq Dev tier (paid, per use) to lift the 8k tokens/min limit before reviewers call.
- **Deferred minors:** chat autostart can race a cold-starting agent; no timeout on "waiting for the agent"; a PNR change does not re-check the date's same-day rule; the sweep re-advances idle chat sessions (no-op writes).
