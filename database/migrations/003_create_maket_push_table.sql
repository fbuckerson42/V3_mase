CREATE TABLE IF NOT EXISTS maket_push (
    id BIGINT PRIMARY KEY,
    created_at DATE,
    closed_at DATE,
    status_id INTEGER NOT NULL,
    status_name VARCHAR(255),
    manager_id INTEGER,
    manager_name VARCHAR(255),
    tg_push BOOLEAN DEFAULT NULL,
    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_maket_push_status_id ON maket_push(status_id);
CREATE INDEX IF NOT EXISTS idx_maket_push_tg_push ON maket_push(tg_push);

DO $$
BEGIN
    RAISE NOTICE 'Migration 003 completed successfully!';
    RAISE NOTICE 'Table "maket_push" created with indexes.';
END $$;