import httpx
from typing import TypedDict
from crewai import Agent, Crew, Process, Task
from qdrant_client import QdrantClient
from langgraph.graph import StateGraph, END
from rich.console import Console
from rich.prompt import Prompt


console = Console()

# Run qdrant server
# docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant:latest
qdrant_client = QdrantClient(url="http://127.0.0.1:6333")

# Run llama.cpp with an embedding model
# ./build/bin/llama-server --model /home/anthony/.cache/llama.cpp/nomic-embed-text-v1.5.Q8_0.gguf --port 8081 --host 0.0.0.0 --embedding --pooling cls -ub 8192
embed_client = httpx.Client(base_url="http://127.0.0.1:8081/v1", timeout=None)
COLLECTION_NAME = "second_brain"


def get_embedding(text: str):
    resp = embed_client.post(
        "/embeddings", json={"input": [text], "model": "nomic"})
    return resp.json()["data"][0]["embedding"] or ""


def retrieve(query: str, limit: int = 5):
    if not qdrant_client.collection_exists(COLLECTION_NAME):
        console.print(f"[red]The collection {
                      COLLECTION_NAME} does not exist :([/red]")
        return None
    console.print(f"[blue]Retrieving relevant results for {query}...[/blue]")
    vector = get_embedding(query)
    search_results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME, query=vector, with_payload=True, limit=limit)
    if len(search_results.points) <= 0:
        return None
    formatted = []
    for hit in search_results.points:
        payload = hit.model_dump()["payload"]
        # snippet = payload["text"][:800] + "..." if len(payload["text"]) > 800 else payload["text"]
        snippet = payload["text"]
        formatted.append(f"Source: {payload["source"]}\n{snippet}\n")
    return "\n\n".join(formatted)


def local_llm(temp=0.3, max_tokens=8192):
    return {
        "model": "llama.cpp",
        "base_url": "http://127.0.0.1:8080/v1",
        "temperature": temp,
        "max_tokens": max_tokens,
        "llm_type": "openai",
        "api_key": "na"
    }


writer = Agent(
    role="Experienced synopsis summary writer",
    goal="Write a clear summary without sacrificing accuracy.",
    backstory="""You excel at reading through the given text and pick out the relevant sections in order to accurately answer the user's question.
    You always site sources with exact file paths. If you are unsure, you say so.""",
    verbose=True,
    allow_delegration=False,
    llm=local_llm(temp=0.2)
)


class AgentState(TypedDict):
    query_topic: str
    retrieved_knowledge: str
    draft_summary: str


def knowledge_retrieval_node(state: AgentState):
    console.print(
        f"--- Memory: Searching database for {state['query_topic']} ---")
    knowledge = retrieve(state['query_topic'])
    return {"retrieved_knowledge": knowledge if knowledge is not None else "No text found"}


def summary_writer_node(state: AgentState):
    console.print("--- Writer: Drafting the summary ---")
    knowledge = state["retrieved_knowledge"]
    question = state["query_topic"]
    prompt = f"Given reference text: {
        knowledge}.\n---\nUser's question: {question}. Write a summary."
    summary_task = Task(
        description=prompt,
        expected_output="Answer with clear summay for the given question.",
        agent=writer
    )
    writer_crew = Crew(
        agents=[writer],
        tasks=[summary_task],
        process=Process.sequential,
        verbose=True
    )
    result = writer_crew.kickoff()
    return {"draft_summary": str(result)}


builder = StateGraph(AgentState)
builder.add_node("memory_lookup", knowledge_retrieval_node)
builder.add_node("writer", summary_writer_node)
builder.set_entry_point("memory_lookup")
builder.add_edge("memory_lookup", "writer")
builder.add_edge("writer", END)
app = builder.compile()


def chat_loop():
    while True:
        user_question = Prompt.ask("Your question please :smiley:? ")
        console.print(f"[bold green]User:[/bold green] {user_question}")
        with console.status("Getting a reply from agent...", spinner="monkey"):
            final_result = app.invoke(
                {"query_topic": user_question, "retrieved_knowledge": "", "draft_summary": ""})


if __name__ == "__main__":
    try:
        chat_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
        exit(0)
    except Exception as e:
        console.print(f"[bold red]Exception {e}[/bold red]")
        exit(1)
