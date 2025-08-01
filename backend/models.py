from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from db import Base

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String)
    source_url = Column(String)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    chunks = relationship("Chunk", back_populates="document")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    meta = Column("metadata", JSON)  # Map 'meta' attribute to 'metadata' column
    document = relationship("Document", back_populates="chunks")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    interactions = relationship("Interaction", back_populates="session")

class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    session = relationship("ChatSession", back_populates="interactions")
    citations = relationship("InteractionCitation", back_populates="interaction")
    feedback = relationship("Feedback", uselist=False, back_populates="interaction")

class InteractionCitation(Base):
    __tablename__ = "interaction_citations"
    interaction_id = Column(Integer, ForeignKey("interactions.id", ondelete="CASCADE"), primary_key=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    interaction = relationship("Interaction", back_populates="citations")
    chunk = relationship("Chunk")

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    interaction_id = Column(Integer, ForeignKey("interactions.id", ondelete="CASCADE"), unique=True, nullable=False)
    rating = Column(Integer, nullable=False)
    feedback_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    interaction = relationship("Interaction", back_populates="feedback")
