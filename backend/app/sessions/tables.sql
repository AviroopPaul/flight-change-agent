CREATE TABLE IF NOT EXISTS sessions (
    id text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    ip_hash text,
    last_user_activity_at timestamptz,
    chat_connected_at timestamptz,
    call_active bool NOT NULL DEFAULT false,
    call_seen_at timestamptz,
    locked bool NOT NULL DEFAULT false,
    state jsonb NOT NULL,
    version int NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sessions_ip_created ON sessions (ip_hash, created_at);

CREATE TABLE IF NOT EXISTS events (
    id bigserial PRIMARY KEY,
    session_id text NOT NULL REFERENCES sessions(id),
    at timestamptz NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS events_session ON events (session_id, id);
