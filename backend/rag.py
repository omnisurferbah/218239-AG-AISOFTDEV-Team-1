from sqlalchemy import text
from sentence_transformers import SentenceTransformer
import numpy as np
import sys
import os
import torch

# Add the parent directory to the path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import setup_llm_client, get_completion

# Initialize the embedding model with CUDA support if available
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

# Initialize LLM client (you can change the model here)
llm_client, model_name, api_provider = setup_llm_client("gpt-4o")  # or "claude-3-5-sonnet-20241022"

print(f"🚀 RAG System initialized:")
print(f"   📊 Embedding model: all-MiniLM-L6-v2 on {device}")
print(f"   🤖 LLM: {model_name} via {api_provider}" if llm_client else "   ⚠️  LLM client not initialized")

def retrieve_relevant_chunks(db, query_text, k=5):
    # Generate embedding for the query
    embedding = model.encode(query_text)
    embedding_list = embedding.tolist()
    
    # Format embedding as PostgreSQL vector literal
    embedding_str = '[' + ','.join(map(str, embedding_list)) + ']'
    
    sql = text("""
        SELECT c.id, c.content, c.embedding, 1 - (c.embedding <=> :embedding) as similarity, d.name as document_name
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        ORDER BY c.embedding <=> :embedding
        LIMIT :k
    """)
    
    result = db.execute(sql, {"embedding": embedding_str, "k": k})
    return result.fetchall()

def generate_response(query, chunks):
    """Generate a response based on the query and retrieved chunks using LLM"""
    if not chunks:
        return "I couldn't find relevant information in the CUDA documentation to answer your question. Please try rephrasing your question or ask about a different CUDA topic."
    
    if not llm_client:
        # Fallback to simple response if LLM client is not available
        context = chunks[0][1]  # content from first chunk
        document_name = chunks[0][4] if len(chunks[0]) > 4 else "CUDA Documentation"
        fallback_response = f"⚠️ LLM not available. Based on the CUDA documentation: {context[:500]}..." if len(context) > 500 else f"⚠️ LLM not available. Based on the CUDA documentation: {context}"
        return fallback_response + f"\n\n*Source: {document_name}*"
    
    # Format the retrieved chunks as context and collect document names
    context_parts = []
    document_names = set()
    for i, chunk_data in enumerate(chunks, 1):
        chunk_id = chunk_data[0]
        content = chunk_data[1]
        similarity = chunk_data[3] if len(chunk_data) > 3 else 0
        document_name = chunk_data[4] if len(chunk_data) > 4 else "Unknown Document"
        
        document_names.add(document_name)
        context_parts.append(f"[Context {i}] (Relevance: {similarity:.3f})\n{content}\n")
    
    context_text = "\n".join(context_parts)
    
    # Create the prompt for the LLM
    prompt = f"""You are a CUDA expert. Answer the user's question concisely based on the provided documentation context.

CONTEXT FROM CUDA DOCUMENTATION:
{context_text}

USER QUESTION: {query}

INSTRUCTIONS:
- Give a direct, concise answer (2-4 sentences max)
- Focus on the most important information only
- Include essential function names or concepts
- Skip lengthy explanations unless specifically asked
- Be precise and technical but brief

ANSWER:"""

    try:
        # Generate response using the LLM
        response = get_completion(
            prompt=prompt,
            client=llm_client,
            model_name=model_name,
            api_provider=api_provider,
            temperature=0.3  # Lower temperature for more consistent technical answers
        )
        
        if response:
            # Add source attribution line with actual document names
            doc_list = sorted(list(document_names))
            if len(doc_list) == 1:
                source_line = f"\n\n*Source: {doc_list[0]}*"
            else:
                # Show up to 3 document names, then "and X more" if there are many
                if len(doc_list) <= 3:
                    doc_names_str = ", ".join(doc_list)
                    source_line = f"\n\n*Sources: {doc_names_str}*"
                else:
                    first_docs = ", ".join(doc_list[:2])
                    remaining = len(doc_list) - 2
                    source_line = f"\n\n*Sources: {first_docs} and {remaining} more*"
            
            return response + source_line
        else:
            return "I encountered an issue generating a response. Please try again."
        
    except Exception as e:
        print(f"Error generating LLM response: {e}")
        # Fallback to simple response
        context = chunks[0][1]
        document_name = chunks[0][4] if len(chunks[0]) > 4 else "CUDA Documentation"
        fallback_response = f"⚠️ LLM error occurred. Based on the CUDA documentation: {context[:500]}..." if len(context) > 500 else f"⚠️ LLM error occurred. Based on the CUDA documentation: {context}"
        return fallback_response + f"\n\n*Source: {document_name}*"