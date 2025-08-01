from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from db import SessionLocal, Base, engine
import models
import rag
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Load environment variables at startup
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_environment
load_environment()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    citations: List[int]
    session_id: int
    interaction_id: int

class FeedbackRequest(BaseModel):
    interaction_id: int
    rating: int  # 1 for thumbs up, -1 for thumbs down
    feedback_text: Optional[str] = None

class FeedbackResponse(BaseModel):
    message: str

class SessionResponse(BaseModel):
    session_id: int
    created_at: datetime

class InteractionHistoryResponse(BaseModel):
    interactions: List[dict]

class CitationResponse(BaseModel):
    chunk_id: int
    content: str
    metadata: dict
    document_name: str
    source_url: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        # Create or get session
        if req.session_id:
            session = db.query(models.ChatSession).filter(models.ChatSession.id == req.session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            session = models.ChatSession()
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # Retrieve relevant chunks
        chunks = rag.retrieve_relevant_chunks(db, req.query, k=5)
        
        # Generate response
        response_text = rag.generate_response(req.query, chunks)
        
        # Create interaction record
        interaction = models.Interaction(
            session_id=session.id,
            query_text=req.query,
            response_text=response_text
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        
        # Create citation records
        citations = []
        for chunk_data in chunks:
            chunk_id = chunk_data[0]  # row[0] is the id column
            citations.append(chunk_id)
            
            # Create citation record
            citation = models.InteractionCitation(
                interaction_id=interaction.id,
                chunk_id=chunk_id
            )
            db.add(citation)
        
        db.commit()
        
        return ChatResponse(
            response=response_text,
            citations=citations,
            session_id=session.id,
            interaction_id=interaction.id
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    """Submit feedback (thumbs up/down) for an interaction"""
    try:
        # Verify interaction exists
        interaction = db.query(models.Interaction).filter(models.Interaction.id == req.interaction_id).first()
        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found")
        
        # Check if feedback already exists
        existing_feedback = db.query(models.Feedback).filter(models.Feedback.interaction_id == req.interaction_id).first()
        if existing_feedback:
            # Update existing feedback
            existing_feedback.rating = req.rating
            existing_feedback.feedback_text = req.feedback_text
        else:
            # Create new feedback
            feedback = models.Feedback(
                interaction_id=req.interaction_id,
                rating=req.rating,
                feedback_text=req.feedback_text
            )
            db.add(feedback)
        
        db.commit()
        return FeedbackResponse(message="Feedback submitted successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions", response_model=SessionResponse)
def create_session(db: Session = Depends(get_db)):
    """Create a new chat session"""
    try:
        session = models.ChatSession()
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return SessionResponse(
            session_id=session.id,
            created_at=session.created_at
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/history", response_model=InteractionHistoryResponse)
def get_session_history(session_id: int, db: Session = Depends(get_db)):
    """Get interaction history for a session"""
    try:
        session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        interactions = db.query(models.Interaction).filter(
            models.Interaction.session_id == session_id
        ).order_by(models.Interaction.created_at).all()
        
        interaction_data = []
        for interaction in interactions:
            citations = db.query(models.InteractionCitation).filter(
                models.InteractionCitation.interaction_id == interaction.id
            ).all()
            
            interaction_data.append({
                "id": interaction.id,
                "query": interaction.query_text,
                "response": interaction.response_text,
                "created_at": interaction.created_at.isoformat(),
                "citations": [c.chunk_id for c in citations]
            })
        
        return InteractionHistoryResponse(interactions=interaction_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/citations/{chunk_id}", response_model=CitationResponse)
def get_citation_details(chunk_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a cited chunk"""
    try:
        chunk = db.query(models.Chunk).filter(models.Chunk.id == chunk_id).first()
        if not chunk:
            raise HTTPException(status_code=404, detail="Citation not found")
        
        document = db.query(models.Document).filter(models.Document.id == chunk.document_id).first()
        
        return CitationResponse(
            chunk_id=chunk.id,
            content=chunk.content,
            metadata=chunk.meta or {},
            document_name=document.name if document else "Unknown",
            source_url=document.source_url if document else None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now()
    )
