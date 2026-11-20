CREATE TABLE IF NOT EXISTS youtube_oauth_states (
    state_hash VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_youtube_oauth_states_expires_at
    ON youtube_oauth_states (expires_at);

CREATE TABLE IF NOT EXISTS youtube_connections (
    user_id VARCHAR(36) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    channel_id VARCHAR(255) NOT NULL,
    channel_title VARCHAR(255) NOT NULL,
    refresh_token_encrypted TEXT NOT NULL,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
