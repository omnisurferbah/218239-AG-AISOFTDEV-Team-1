# CUDA-Assist Backend

This is the backend server for the CUDA-Assist chatbot application.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your PostgreSQL database with pgvector extension:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

3. Update the database connection string in `db.py` or set the `DATABASE_URL` environment variable.

## Running the Server

### Option 1: Using the startup script (Recommended)
From the project root directory:
```bash
python run_backend.py
```

### Option 2: Running directly from backend directory
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `POST /chat` - Submit a chat query
- `POST /feedback` - Submit feedback for an interaction
- `POST /sessions` - Create a new chat session
- `GET /sessions/{session_id}/history` - Get session history
- `GET /citations/{chunk_id}` - Get citation details
- `GET /health` - Health check endpoint

## Database Models

The application uses the following database tables:
- `documents` - Source document metadata
- `chunks` - Text chunks with embeddings for RAG
- `chat_sessions` - User chat sessions
- `interactions` - Individual Q&A pairs
- `interaction_citations` - Links interactions to source chunks
- `feedback` - User feedback on responses
