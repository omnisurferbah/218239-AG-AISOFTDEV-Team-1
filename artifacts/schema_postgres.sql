-- Database Schema for CUDA-Assist Chatbot
-- Target RDBMS: PostgreSQL with pgvector
-- Description: This schema is designed to support a RAG (Retrieval-Augmented Generation)
--              chatbot as specified in the PRD. It is normalized to ensure data
--              integrity and leverages the 'vector' type for efficient similarity search.

-- Enable the vector extension. This must be run by a superuser.
CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------
-- Table: documents
-- Purpose: Stores metadata about the source documents (e.g., the CUDA Programming Guide).
-- Rationale: Normalizes document information, avoiding redundant storage of names/versions in every chunk.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    source_url TEXT,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Table: chunks
-- Purpose: Stores the individual text/code chunks extracted from documents, along with their vector embeddings.
-- Rationale: This is the core table for the RAG system. Using the 'vector' type is essential for pgvector.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL, -- Using the vector type with a dimension of 384 (for 'all-MiniLM-L6-v2' model)
    metadata JSONB, -- Using JSONB is more efficient for querying in Postgres. e.g., '{"page": 42, "section": "3.1"}'
    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
);

-- Index for faster lookup of chunks belonging to a specific document.
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);

-- Create an HNSW index for fast approximate nearest neighbor search.
-- This is crucial for the performance of the RAG retrieval step.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_l2_ops);

-- -----------------------------------------------------
-- Table: chat_sessions
-- Purpose: Represents a single user conversation session.
-- Rationale: Groups interactions together, allowing for session-based analysis and context management.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------
-- Table: interactions
-- Purpose: Logs each question-and-answer pair within a chat session.
-- Rationale: Captures the core user activity for analysis and for linking to feedback and source chunks.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS interactions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
);

-- Index for quickly retrieving all interactions in a session.
CREATE INDEX IF NOT EXISTS idx_interactions_session_id ON interactions (session_id);

-- -----------------------------------------------------
-- Table: interaction_citations
-- Purpose: A many-to-many link table connecting an interaction (response) to the source chunks used to generate it.
-- Rationale: Fulfills the requirement to cite sources (FR-3.3) and allows for traceability.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS interaction_citations (
    interaction_id INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    PRIMARY KEY (interaction_id, chunk_id),
    FOREIGN KEY (interaction_id) REFERENCES interactions (id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES chunks (id) ON DELETE CASCADE
);

-- -----------------------------------------------------
-- Table: feedback
-- Purpose: Stores user feedback (e.g., thumbs up/down) for a specific interaction.
-- Rationale: Fulfills user story US-08 and provides data for success metric 4.1.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    interaction_id INTEGER NOT NULL UNIQUE, -- An interaction can only have one feedback entry
    rating INTEGER NOT NULL, -- e.g., 1 for "thumbs up", -1 for "thumbs down"
    feedback_text TEXT, -- Optional qualitative feedback
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interaction_id) REFERENCES interactions (id) ON DELETE CASCADE
);