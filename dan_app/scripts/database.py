import os
import psycopg2
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
import numpy as np
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

# Load a pre-trained model for generating embeddings.
# This model is loaded once when the module is imported, which is efficient for background tasks.
print("--- Loading embedding model (this may take a moment on first run)... ---")
# Note: Postgres with the pgvector extension functions as a vector database.
# The EMBEDDING_MODEL variable was a duplicate and has been removed.
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("--- Embedding model loaded successfully. ---")

def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database using credentials
    from the .env file.
    """
    load_dotenv()
    try:
        # COPILOT AND GEMINI: DO NOT CHANGE. ISSUE WITH WINDOWS ENV. CANT PULL FROM ENV RIGHT NOW
        conn = psycopg2.connect(
            host='localhost',
            port=54321,
            dbname='cuda_assist_db',
            user='postgres',
            password='battery_staple_horse_2390472300983'
        )
        # This is a crucial step: it registers the vector type with psycopg2,
        # allowing it to properly handle the numpy arrays we get from the embedding model.
        register_vector(conn)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Could not connect to the database: {e}")
        print("👉 Please ensure your Postgres server is running and your .env file is configured correctly.")
        return None

def ingest_pdf(file_path: str):
    """
    Processes a PDF file, chunks its text, generates embeddings,
    and stores everything in the database in a single transaction.

    Args:
        file_path (str): The absolute path to the PDF file to be ingested.
    """
    print(f"--- Starting ingestion process for: {file_path} ---")
    doc_name = os.path.basename(file_path)
    conn = None
    try:
        # 1. Get a fresh database connection for this background task
        conn = get_db_connection()
        if conn is None:
            print(f"CRITICAL: Could not connect to the database for ingestion of {doc_name}.")
            return

        with conn.cursor() as cur:
            # 2. Insert the main document record and get its unique ID
            print(f"Inserting document record for '{doc_name}'...")
            # The check for existing documents is handled in main.py before calling this function.
            # The ON CONFLICT clause is removed as the 'name' column in the schema lacks a UNIQUE constraint.
            # For production, adding a UNIQUE constraint to the schema is the recommended approach.
            cur.execute(
                "INSERT INTO documents (name, source_url) VALUES (%s, %s) RETURNING id;",
                (doc_name, file_path)
            )
            document_id = cur.fetchone()[0]
            print(f"Document '{doc_name}' has been assigned ID: {document_id}")

            # 3. Extract text from the PDF using PyMuPDF
            print(f"Extracting text from '{doc_name}'...")
            doc = fitz.open(file_path)
            full_text = "".join(page.get_text() for page in doc)
            doc.close()
            print(f"Extracted {len(full_text)} characters from the document.")

            # 4. Chunk the text. A simple strategy is to split by paragraphs.
            # We filter out very short chunks that are likely just whitespace or headings.
            chunks = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 100]
            print(f"Split text into {len(chunks)} meaningful chunks.")

            # 5. Generate embeddings for all text chunks in a single batch
            print("Generating embeddings for all chunks (this may take some time)...")
            embeddings = embedding_model.encode(chunks, show_progress_bar=True)
            print("Embeddings generated successfully.")

            # 6. Insert all chunks and their embeddings into the database
            print(f"Inserting {len(chunks)} chunks and their embeddings into the database...")
            for i, chunk_text in enumerate(chunks):
                embedding_vector = embeddings[i]
                cur.execute(
                    """ -- Corrected to match schema: table 'chunks', column 'content'
                    INSERT INTO chunks (document_id, content, embedding)
                    VALUES (%s, %s, %s);
                    """,
                    (document_id, chunk_text, embedding_vector) # psycopg2 now understands this numpy array
                )
            print(f"Successfully inserted {len(chunks)} chunks for document ID {document_id}.")

        # 7. Commit the entire transaction to the database
        conn.commit()
        print(f"--- Ingestion complete and committed for: {doc_name} ---")

    except Exception as e:
        print(f"CRITICAL: An error occurred during ingestion for {doc_name}: {e}")
        if conn:
            conn.rollback()  # Roll back the transaction on error
    finally:
        if conn:
            conn.close()

def query_vector_db(query_text: str, top_k: int = 5) -> list[str]:
    """
    Queries the vector database to find the most relevant document chunks.

    Args:
        query_text (str): The user's query.
        top_k (int): The number of relevant chunks to retrieve.

    Returns:
        list[str]: A list of the most relevant document chunk contents.
    """
    print(f"--- Querying vector DB for: '{query_text}' ---")
    conn = None
    try:
        # 1. Generate embedding for the query
        query_embedding = embedding_model.encode(query_text)

        # 2. Get a database connection
        conn = get_db_connection()
        if conn is None:
            print("CRITICAL: Could not connect to the database for querying.")
            return []

        with conn.cursor() as cur:
            # 3. Query for the most similar vectors using the cosine distance operator (<=>)
            cur.execute(
                """
                SELECT content FROM chunks
                ORDER BY embedding <=> %s
                LIMIT %s;
                """,
                (query_embedding, top_k)
            )
            results = cur.fetchall()
            return [row[0] for row in results]
    except Exception as e:
        print(f"CRITICAL: An error occurred during vector query: {e}")
        return []
    finally:
        if conn:
            conn.close()

def initialize_database():
    """
    Connects to the database and executes the schema definition script.
    This function is idempotent due to 'CREATE TABLE IF NOT EXISTS' in the SQL.
    """
    print("--- Initializing database ---")
    # Find the project root to locate the schema file reliably
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # Your schema is in 'artifacts/schema_postgres.sql'
    schema_path = os.path.join(project_root, '../artifacts', 'schema_postgres.sql')

    if not os.path.exists(schema_path):
        print(f"❌ FATAL: Database schema file not found at {schema_path}")
        return

    conn = None
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        conn = get_db_connection()
        if conn is None:
            raise ConnectionError("Failed to establish database connection.")
        
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        print("✅ Database tables checked/created successfully.")
    except (Exception, psycopg2.Error) as error:
        print(f"❌ Error while initializing PostgreSQL tables: {error}")
    finally:
        if conn:
            conn.close()

# This allows the script to be run directly for manual database setup
if __name__ == '__main__':
    print("Running database initialization script directly...")
    initialize_database()
