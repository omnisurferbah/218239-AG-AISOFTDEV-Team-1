import os
import sys
from typing import List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from contextlib import asynccontextmanager

# Add project root to the Python path to allow importing from sibling directories
# This is necessary because the 'app' and 'scripts' directories are siblings.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dan_app.scripts.database import initialize_database, get_db_connection, ingest_pdf
from dan_app.rag_workflow import runnable_graph

def generate_database():
    """
    Calls the database initialization logic from database.py.
    This function ensures the database and tables are created as per the schema.
    """
    print("--- Manually generating database schema ---")
    initialize_database()
    print("--- Database generation complete ---")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    A context manager to handle application startup and shutdown events.
    On startup, it ensures the database schema is created. This is the
    recommended approach for FastAPI applications.
    """
    print("--- Application starting up... ---")
    initialize_database() # Automatically initializes DB on app start
    yield
    print("--- Application shutting down... ---")

app = FastAPI(
    title="CUDA-Assist API",
    description="API for the RAG-powered CUDA documentation chatbot.",
    version="1.0.0",
    lifespan=lifespan
)

class IngestRequest(BaseModel):
    """Request model for the /ingest endpoint."""
    file_path: str

class ChatRequest(BaseModel):
    """Request model for the /chat endpoint."""
    question: str = Field(..., min_length=3, max_length=300, description="The user's question for the chatbot.")

class ChatResponse(BaseModel):
    """Response model for the /chat endpoint."""
    answer: str
    retrieved_documents: List[str]

@app.get("/", summary="Root Endpoint")
async def read_root():
    """
    A simple root endpoint to confirm the API is running.
    """
    return {"message": "Welcome to the CUDA-Assist API. The database has been initialized."}

@app.post("/ingest", status_code=202, summary="Trigger PDF Ingestion")
async def trigger_ingestion(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Accepts a file path and triggers the document ingestion process in the background,
    if the document has not already been ingested.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"File not found at: {request.file_path}")

    doc_name = os.path.basename(request.file_path)
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection could not be established.")

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM documents WHERE name = %s", (doc_name,))
            if cur.fetchone():
                return JSONResponse(status_code=200, content={"message": "Document has already been ingested."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database check failed: {e}")
    finally:
        conn.close()

    background_tasks.add_task(ingest_pdf, request.file_path)
    return {"message": "Document ingestion process started in the background.", "file_path": request.file_path}

@app.post("/chat", response_model=ChatResponse, summary="Chat with the RAG system")
async def chat_with_rag(request: ChatRequest):
    """
    Receives a user question, runs it through the RAG workflow,
    and returns the generated answer along with the source documents.
    """
    try:
        # The input to our graph is a dictionary with the key "question"
        inputs = {"question": request.question}
        
        # Invoke the LangGraph runnable
        result = runnable_graph.invoke(inputs)

        answer = result.get("generation")
        documents = result.get("documents", [])

        if not answer:
            answer = "I could not find relevant information in the documentation to answer your question."

        return ChatResponse(answer=answer, retrieved_documents=documents)
    except Exception as e:
        # ERROR HERE
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

def main():
    """
    Main entry point for running the FastAPI application.
    The database is initialized automatically on startup via the lifespan manager.
    """
    print("--- Starting FastAPI application ---")
    # This will start the Uvicorn server programmatically.
    uvicorn.run("dan_app.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    # The script can now be run directly to start the server.
    main()
