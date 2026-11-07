CREATE TABLE IF NOT EXISTS transcript (
    id bigserial PRIMARY KEY,
    session_id text NOT NULL,
    role text NOT NULL,
    text text NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS transcript_session ON transcript (session_id, id);

CREATE TABLE IF NOT EXISTS usage (
    id bigserial PRIMARY KEY,
    session_id text NOT NULL,
    kind text NOT NULL,
    quantity numeric NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_session ON usage (session_id);

CREATE TABLE IF NOT EXISTS turn_metrics (
    id bigserial PRIMARY KEY,
    session_id text NOT NULL,
    eou_ms numeric,
    llm_ttft_ms numeric,
    tts_ttfb_ms numeric,
    total_ms numeric,
    at timestamptz NOT NULL DEFAULT now()
);
