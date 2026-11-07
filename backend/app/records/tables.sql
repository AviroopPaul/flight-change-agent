CREATE TABLE IF NOT EXISTS records (
    session_id text NOT NULL,
    revision int NOT NULL,
    outcome text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    attempts int NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, revision)
);

CREATE TABLE IF NOT EXISTS stub_records (
    id bigserial PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now()
);
