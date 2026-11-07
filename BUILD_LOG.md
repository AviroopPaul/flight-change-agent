# Build Log

Plan: [docs/superpowers/plans/2026-11-07-flight-change-agent.md](docs/superpowers/plans/2026-11-07-flight-change-agent.md)
Spec: [docs/superpowers/specs/2026-11-07-flight-change-agent-design.md](docs/superpowers/specs/2026-11-07-flight-change-agent-design.md)

## Status

| # | Task | Status | Commit |
|---|---|---|---|
| 1 | Repo scaffold, Postgres, backend skeleton | done | (see git log) |
| 2 | Catalog, flights, fare math | todo | |
| 3 | Field validators | todo | |
| 4 | Session engine | todo | |
| 5 | Outcome, record, pricing | todo | |
| 6 | Store, outbox, delivery | todo | |
| 7 | Public API, chat socket, rate limits | todo | |
| 8 | LiveKit bridge, internal API | todo | |
| 9 | Sweep, startup recovery | todo | |
| 10 | Voice agent | todo | |
| 11 | Web app | todo | |
| 12 | Deploy | todo | |
| 13 | Latency report, README | todo | |

## Commits

- `chore: scaffold backend, postgres, schema` (Task 1)

## Decisions made during the build

- **Local Postgres:** Docker Desktop did not start from the shell. Tests use Homebrew `postgresql@16` on port 5433 (db `flight`, user `dev`/`dev`), the same URL as `docker-compose.yml`.
  - Start it: `LC_ALL=en_US.UTF-8 /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D /opt/homebrew/var/postgresql@16 -o "-p 5433" -l /opt/homebrew/var/log/pg16-5433.log start`
- **Commits:** local only, on `main`. Nothing is pushed.

## Left to do

- Tasks 2 to 13 (see the table).
- Needs you later: Neon project (Task 12), at least 10 real test calls for latency numbers (Task 13).
