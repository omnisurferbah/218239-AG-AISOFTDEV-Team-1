import os
import sys
from typing import List, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

# Add project root to the Python path to allow importing from sibling directories
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dan_app.scripts.database import query_vector_db
from dan_app.utils import load_environment

# --- 1. Define the state for our graph ---
class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: The user's question.
        documents: A list of documents retrieved from the vector database.
        generation: The LLM-generated answer.
    """
    question: str
    documents: List[str]
    generation: str

# --- 2. Define the nodes for our graph ---

def retrieve_node(state: GraphState) -> GraphState:
    """
    Retrieves documents from the vector database based on the user's question.
    """
    print("--- NODE: RETRIEVE ---")
    question = state["question"]
    documents = query_vector_db(question, top_k=5)
    print(f"Retrieved {len(documents)} documents.")
    return {"documents": documents, "question": question}

def generate_node(state: GraphState) -> GraphState:
    """
    Generates an answer using the retrieved documents and the user's question.
    """
    print("--- NODE: GENERATE ---")
    question = state["question"]
    documents = state["documents"]

    prompt_template = """You are an expert assistant for the NVIDIA CUDA C++ Programming Guide.
    Your task is to answer the user's question based *only* on the following context retrieved from the documentation.
    If the context does not contain the answer, state that you cannot answer the question with the provided information.
    Do not make up information. Be concise and clear.

    CONTEXT:
    {context}

    QUESTION:
    {question}

    ANSWER:
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)

    # not working...
    load_environment()
    hard_coded_api_key = 'api key here'

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=hard_coded_api_key)

    context_str = "\n\n---\n\n".join(documents)

    print(f"Given question: {question}")
    print(f"Retrieved Context: {context_str}")

    rag_chain = prompt | llm
    generation = rag_chain.invoke({"context": context_str, "question": question}).content
    print(f"--- Generated Answer: {generation[:100]}... ---")
    return {"generation": generation}

# --- 3. Define the conditional edge ---

def decide_to_generate(state: GraphState) -> str:
    """
    Determines whether to generate an answer or end the process if no documents are found.
    """
    print("--- CONDITIONAL EDGE: DECIDE TO GENERATE ---")
    if state["documents"]:
        print("Decision: Documents found, proceeding to generation.")
        return "generate"
    else:
        print("Decision: No documents found, ending process.")
        return "end"

# --- 4. Assemble the graph ---

def build_graph():
    """
    Builds and compiles the LangGraph workflow.
    """
    workflow = StateGraph(GraphState)

    # Add the nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)

    # Set the entry point
    workflow.set_entry_point("retrieve")

    # Add the edges
    workflow.add_conditional_edges(
        "retrieve",
        decide_to_generate,
        {
            "generate": "generate",
            "end": END,
        },
    )
    workflow.add_edge("generate", END)

    # Compile the graph into a runnable
    app_graph = workflow.compile()
    print("--- RAG Graph Compiled ---")
    return app_graph

# Create a single instance of the compiled graph to be used by the API
runnable_graph = build_graph()