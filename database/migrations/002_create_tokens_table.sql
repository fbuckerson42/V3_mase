CREATE TABLE IF NOT EXISTS tokens (
    id SERIAL PRIMARY KEY,
    token_type VARCHAR(100) NOT NULL UNIQUE,
    token_value TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_tokens_type ON tokens(token_type);
CREATE INDEX IF NOT EXISTS idx_tokens_active ON tokens(is_active);
CREATE INDEX IF NOT EXISTS idx_tokens_updated ON tokens(updated_at DESC);

COMMENT ON TABLE tokens IS 'API tokens storage (JWT, bearer tokens)';
COMMENT ON COLUMN tokens.token_type IS 'Token type identifier (e.g., "bearer_token", "access_token")';
COMMENT ON COLUMN tokens.token_value IS 'Token value (JWT or other token string)';
COMMENT ON COLUMN tokens.expires_at IS 'Token expiration time (nullable)';
COMMENT ON COLUMN tokens.created_at IS 'When token was first stored';
COMMENT ON COLUMN tokens.updated_at IS 'When token was last updated';
COMMENT ON COLUMN tokens.is_active IS 'Whether token is currently active';

DO $$
BEGIN
    RAISE NOTICE 'Migration 002 completed successfully!';
    RAISE NOTICE 'Table "tokens" created with indexes.';
END $$;