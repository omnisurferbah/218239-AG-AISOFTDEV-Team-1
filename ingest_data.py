#!/usr/bin/env python3
"""
Data ingestion script for CUDA documentation RAG chatbot.
This script populates the database with sample CUDA documentation chunks.
"""

import sys
import os
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer

# Add backend directory to path
sys.path.append('backend')
from backend.db import engine, Base
from backend.models import Document, Chunk

# Initialize the embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Sample CUDA documentation content
CUDA_CONTENT = [
    {
        "title": "CUDA Kernels",
        "content": """A CUDA kernel is a function that executes on the GPU. Kernels are defined using the __global__ declaration specifier and the number of CUDA threads that execute that kernel for a given kernel launch is specified using the <<<>>> execution configuration syntax.

Example:
__global__ void VecAdd(float* A, float* B, float* C, int N)
{
    int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i < N)
        C[i] = A[i] + B[i];
}""",
        "meta": {"section": "3.2", "page": 15}
    },
    {
        "title": "Thread Hierarchy",
        "content": """CUDA threads are organized into a hierarchy of grids, blocks, and threads. A kernel is executed by a grid of thread blocks. Each block consists of multiple threads that can cooperate through shared memory and can synchronize their execution.

Built-in variables:
- threadIdx: Thread index within a block
- blockIdx: Block index within a grid
- blockDim: Block dimension
- gridDim: Grid dimension""",
        "meta": {"section": "3.3", "page": 18}
    },
    {
        "title": "Memory Management",
        "content": """CUDA provides several functions for memory management:

cudaMalloc(): Allocates memory on the device
cudaFree(): Frees memory on the device
cudaMemcpy(): Copies data between host and device
cudaMemcpyHostToDevice: Copy from host to device
cudaMemcpyDeviceToHost: Copy from device to host

Example:
float* d_A;
cudaMalloc(&d_A, size);
cudaMemcpy(d_A, h_A, size, cudaMemcpyHostToDevice);""",
        "meta": {"section": "3.4", "page": 22}
    },
    {
        "title": "Shared Memory",
        "content": """Shared memory is a form of memory that can be accessed by all threads in a block. It is much faster than global memory and can be used to optimize memory access patterns.

Shared memory is declared using the __shared__ qualifier:
__shared__ float sdata[256];

Threads in a block can cooperate by sharing data through shared memory and by synchronizing their execution to coordinate memory accesses using __syncthreads().""",
        "meta": {"section": "3.5", "page": 28}
    },
    {
        "title": "CUDA Streams",
        "content": """A CUDA stream is a sequence of operations that execute on the device in the order they are issued by the host code. Operations in different streams may execute concurrently.

Creating and using streams:
cudaStream_t stream1, stream2;
cudaStreamCreate(&stream1);
cudaStreamCreate(&stream2);

// Launch kernels in different streams
kernel1<<<grid, block, 0, stream1>>>(data1);
kernel2<<<grid, block, 0, stream2>>>(data2);

cudaStreamDestroy(stream1);
cudaStreamDestroy(stream2);""",
        "meta": {"section": "3.6", "page": 35}
    },
    {
        "title": "Error Handling",
        "content": """CUDA runtime functions return error codes that can be checked to ensure proper execution:

cudaError_t error = cudaMalloc(&d_data, size);
if (error != cudaSuccess) {
    printf("cudaMalloc failed: %s\\n", cudaGetErrorString(error));
    exit(1);
}

You can also use cudaGetLastError() to check for errors after kernel launches:
kernel<<<grid, block>>>(data);
cudaError_t error = cudaGetLastError();
if (error != cudaSuccess) {
    printf("Kernel launch failed: %s\\n", cudaGetErrorString(error));
}""",
        "meta": {"section": "3.7", "page": 42}
    },
    {
        "title": "Warp and Thread Execution",
        "content": """A warp is a collection of 32 threads that execute the same instruction at the same time. When threads in a warp follow different execution paths (diverge), the warp serializes the execution of each path.

Key concepts:
- Warp size is 32 threads
- All threads in a warp execute the same instruction
- Branch divergence reduces performance
- Use __syncthreads() to synchronize threads within a block""",
        "meta": {"section": "4.1", "page": 48}
    },
    {
        "title": "Memory Coalescing",
        "content": """Memory coalescing occurs when threads in a warp access consecutive memory locations. This allows the hardware to combine multiple memory requests into fewer transactions, improving performance.

Guidelines for coalesced access:
- Sequential threads should access sequential memory locations
- Align data structures to memory boundaries
- Avoid scattered memory access patterns
- Use array of structures (AoS) to structure of arrays (SoA) transformation when beneficial""",
        "meta": {"section": "5.3", "page": 67}
    }
]

def create_session():
    """Create a database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def ingest_documents():
    """Ingest sample CUDA documentation into the database."""
    session = create_session()
    
    try:
        # Create document record
        doc = Document(
            name="CUDA C++ Programming Guide",
            version="12.0",
            source_url="https://docs.nvidia.com/cuda/cuda-c-programming-guide/"
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        
        print(f"Created document: {doc.name} (ID: {doc.id})")
        
        # Process and insert chunks
        for i, content_item in enumerate(CUDA_CONTENT):
            print(f"Processing chunk {i+1}/{len(CUDA_CONTENT)}: {content_item['title']}")
            
            # Generate embedding for the content
            embedding = model.encode(content_item['content'])
            
            # Create chunk record
            chunk = Chunk(
                document_id=doc.id,
                content=content_item['content'],
                embedding=embedding.tolist(),
                meta=content_item['meta']
            )
            session.add(chunk)
        
        session.commit()
        print(f"Successfully ingested {len(CUDA_CONTENT)} chunks!")
        
        # Verify the data
        chunk_count = session.query(Chunk).count()
        print(f"Total chunks in database: {chunk_count}")
        
    except Exception as e:
        print(f"Error during ingestion: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    print("Starting CUDA documentation ingestion...")
    ingest_documents()
    print("Ingestion completed!")