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
| 10 | Voice agent | todo | |
| 11 | Web app | todo | |
| 12 | Deploy | todo | |
| 13 | Latency report, README | todo | |

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

## Decisions made during the build

- **Local Postgres:** Docker Desktop did not start from the shell. Tests use Homebrew `postgresql@16` on port 5433 (db `flight`, user `dev`/`dev`), the same URL as `docker-compose.yml`.
  - Start it: `LC_ALL=en_US.UTF-8 /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D /opt/homebrew/var/postgresql@16 -o "-p 5433" -l /opt/homebrew/var/log/pg16-5433.log start`
- **Commits:** local only, on `main`. Nothing is pushed.

## Left to do

- Tasks 2 to 13 (see the table).
- Needs you later: Neon project (Task 12), at least 10 real test calls for latency numbers (Task 13).
