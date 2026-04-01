-- Phase 2 Ingestion: Supabase-Backed Queue
-- This table acts as the persistent broker for individual chunks
CREATE TABLE IF NOT EXISTS ingestion_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES ingestion_tasks(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'error')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for the worker to poll efficiently
CREATE INDEX IF NOT EXISTS idx_ingestion_chunks_task_id ON ingestion_chunks(task_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_chunks_status ON ingestion_chunks(status);

-- Add 'queued' to ingestion_tasks status if it doesn't exist (Manual check needed if using CHECK constraint)
-- For this MVP, we'll assume the worker will poll for 'pending' or 'processing' tasks.
