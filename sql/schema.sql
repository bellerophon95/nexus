CREATE EXTENSION IF NOT EXISTS vector;

-- Supabase Schema for Project Nexus

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source_path TEXT,
    doc_type TEXT,
    fingerprint BIGINT UNIQUE,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    header TEXT,
    token_count INTEGER,
    entities JSONB DEFAULT '[]',
    topics TEXT[] DEFAULT '{}',
    key_phrases TEXT[] DEFAULT '{}',
    sparse_tokens JSONB DEFAULT '{}',
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_text_search ON chunks USING gin(to_tsvector('english', text));
CREATE INDEX IF NOT EXISTS idx_chunks_topics ON chunks USING gin(topics);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);

-- Upgrade: Metadata-Aware Hybrid search function with Title Boosting
CREATE OR REPLACE FUNCTION match_hybrid_chunks(
  query_embedding vector(384),
  query_text TEXT,
  match_threshold FLOAT,
  match_count INT,
  full_text_weight FLOAT DEFAULT 1.0,
  vector_weight FLOAT DEFAULT 1.0,
  title_boost FLOAT DEFAULT 0.5
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  title TEXT,
  text TEXT,
  header TEXT,
  metadata JSONB,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
  final_similarity FLOAT;
BEGIN
  RETURN QUERY
  SELECT
    chunks.id,
    chunks.document_id,
    documents.title,
    chunks.text,
    chunks.header,
    jsonb_build_object(
      'entities', chunks.entities,
      'topics', chunks.topics,
      'key_phrases', chunks.key_phrases
    ) as metadata,
    (
      -- Dense Vector similarity
      (1 - (chunks.embedding <=> query_embedding)) * vector_weight +
      -- Full-text similarity on chunk content
      (ts_rank_cd(to_tsvector('english', chunks.text), plainto_tsquery('english', query_text))) * full_text_weight +
      -- Metadata boost: Title match (Fuzzy)
      (CASE 
        WHEN lower(regexp_replace(documents.title, '\.[^.]+$', '')) = any(string_to_array(lower(query_text), ' ')) THEN title_boost * 2.0
        WHEN lower(query_text) ILIKE '%' || lower(regexp_replace(documents.title, '\.[^.]+$', '')) || '%' THEN title_boost
        WHEN lower(regexp_replace(documents.title, '\.[^.]+$', '')) ILIKE '%' || lower(query_text) || '%' THEN title_boost
        ELSE 0
      END)
    ) as similarity
  FROM chunks
  JOIN documents ON chunks.document_id = documents.id
  WHERE (
    (1 - (chunks.embedding <=> query_embedding)) * vector_weight +
    (ts_rank_cd(to_tsvector('english', chunks.text), plainto_tsquery('english', query_text))) * full_text_weight +
    (CASE 
        WHEN lower(regexp_replace(documents.title, '\.[^.]+$', '')) = any(string_to_array(lower(query_text), ' ')) THEN title_boost * 2.0
        WHEN lower(query_text) ILIKE '%' || lower(regexp_replace(documents.title, '\.[^.]+$', '')) || '%' THEN title_boost
        WHEN lower(regexp_replace(documents.title, '\.[^.]+$', '')) ILIKE '%' || lower(query_text) || '%' THEN title_boost
        ELSE 0
    END)
  ) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;

-- Persistence Layer for Conversations and Feedback
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    user_id UUID, -- Optional for future auth
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    metrics JSONB DEFAULT '{}',
    trace_id TEXT,
    feedback INTEGER DEFAULT 0, -- 1 = Up, -1 = Down, 0 = Neutral
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Asynchronous Ingestion Task Tracking
CREATE TABLE IF NOT EXISTS ingestion_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'error', 'skipped')),
    progress FLOAT DEFAULT 0.0,
    filename TEXT,
    message TEXT,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_tasks_status ON ingestion_tasks(status);

