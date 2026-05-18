import asyncio
import json
from typing import Annotated, Any, List, Literal, TypedDict
import httpx
from langgraph.checkpoint import memory
from rich.console import Console
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from prompts import PLAN_PROMPT, EXTRACT_CLAIMS_PROMPT, CRITIC_PROMPT
from tools import search_web, fetch_page

console = Console()

client = httpx.Client(base_url="http://127.0.0.1:8080/v1", timeout=None)


class AgentState(TypedDict):
    messages: Annotated[List[Any], "append"]
    question: str
    plan_steps: List[str]
    search_results: List[dict]
    source_texts: List[dict]
    extracted_claims: List[dict]
    conflicts: List[dict]
    final_report: str
    needs_human_approval: bool


def call_model(state: AgentState, config: RunnableConfig) -> dict:
    messages = state["messages"]
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 8192
    }
    resp = client.post("/chat/completions", json=payload).json()
    msg = resp["choices"][0]["message"]
    return {"messages": [msg]}


def plan_research(state: AgentState):
    console.print("[grey]--- Planning the research ---[/grey]")
    messages = [
        {"role": "system", "content": PLAN_PROMPT.format(
            question=state["question"])},
        {"role": "user", "content": "Create the research plan."}
    ]
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.0
    }
    resp = client.post("/chat/completions", json=payload).json()
    plan_json = resp["choices"][0]["message"]["content"] or "{}"
    console.print(f"Research plan: {plan_json}")
    match = plan_json.find("{", 0)
    if match == -1:
        console.print("\n[bold red]No research plan received![/bold red]")
        return {"plan_steps": [""], "messages": [AIMessage(content=plan_json)]}
    decoder = json.JSONDecoder()
    try:
        result, index = decoder.raw_decode(plan_json[match:])
    except ValueError:
        return {"plan_steps": [""], "messages": [AIMessage(content=plan_json)]}
    plan_steps = result["plan_steps"]
    return {"plan_steps": plan_steps, "messages": [AIMessage(content=plan_json)]}


async def execute_search(state: AgentState):
    console.print("[grey]--- Executing search ---[/grey]")
    tasks = [search_web(step) for step in state["plan_steps"][:5]]
    all_results = await asyncio.gather(*tasks)
    flat_results = [item.model_dump()
                    for sublist in all_results for item in sublist]
    console.print(f"Search results: {flat_results}")
    return {"search_results": flat_results}


async def fetch_sources(state: AgentState):
    console.print("[grey]--- Fetching sources ---[/grey]")
    urls = [r["url"] for r in state["search_results"][:8]]
    pages = [fetch_page(url) for url in urls]
    texts = await asyncio.gather(*pages, return_exceptions=True)
    source_texts = []
    for url, text in zip(urls, texts):
        if isinstance(text, Exception):
            continue
        source_texts.append({"url": url, "text": str(text)})
    console.print(f"Source texts: {source_texts}")
    return {"source_texts": source_texts}


def extract_claims(state: AgentState):
    console.print("[grey]--- Extracting the claims ---[/grey]")
    claims = []
    for i, src in enumerate(state["source_texts"]):
        messages = [{"role": "system", "content": EXTRACT_CLAIMS_PROMPT.format(text=src["text"])},
                    {"role": "user", "content": "Extract claims from the text"}]
        payload = {
            "model": "local",
            "messages": messages,
            "temperature": 0.0
        }
        resp = client.post("/chat/completions", json=payload).json()
        try:
            console.print(f"Extracted claims: {
                          resp['choices'][0]['message']['content']}")
            data = json.loads(resp["choices"][0]["message"]["content"])
            for c in data:
                c["source_id"] = i
                c["page_url"] = src["url"]
            claims.extend(data)
        except:
            pass
    console.print(f"Extracted claims: {claims}")
    return {"extracted_claims": claims}


def check_conflicts(state: AgentState) -> Literal["verify_claims", "synthesize_report"]:
    console.print("[grey]--- Checking for conflicts ---[/grey]")
    # Simplified conflict detection
    if len(state["extracted_claims"]) > 8:
        return "verify_claims"
    console.print(
        "Extracted claims is less than 8, so no conflicts. Synthesize the report")
    return "synthesize_report"


async def synthesize_report(state: AgentState):
    console.print("[grey]--- Sythesizeing report ---[/grey]")
    context = "\n\n".join([
        "Sources:", *[f"{i}: {s['url']}" for i,
                      s in enumerate(state["source_texts"])],
        "\nClaims:", json.dumps(state["extracted_claims"], indent=2)
    ])
    console.print(f"Context for final report: {context}")
    messages = [
        {"role": "system", "content": "Write a clear, cited report. Use markdown footnotes for sources."},
        {"role": "user", "content": f"Question: {
            state['question']}\n\n{context}"}
    ]
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.3
    }
    resp = client.post("/chat/completions", json=payload).json()
    report = resp["choices"][0]["message"]["content"]
    return {"final_report": report}


async def fact_check_report(state: AgentState):
    console.print("[grey]--- Fact checking the report ---[/grey]")
    messages = [
        {"role": "system", "content": CRITIC_PROMPT},
        {"role": "user", "content": f"Report:\n{state['final_report']}\n\nSources:\n{
            json.dumps(state['source_texts'], indent=2)}"}
    ]
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.0
    }
    resp = client.post("/chat/completions", json=payload).json()
    criticism = resp["choices"][0]["message"]["content"].strip()
    if criticism == "ALL_CLAIMS_SUPPORTED":
        return {"messages": [AIMessage(content="Fact-check passed")]}
    # In real system, loop back to verification
    return {"messages": [AIMessage(content=f"Fact-check failed:\n{criticism}")]}


# Build the graph
builder = StateGraph(AgentState)
builder.add_node("plan_research", plan_research)
builder.add_node("execute_search", execute_search)
builder.add_node("fetch_sources", fetch_sources)
builder.add_node("extract_claims", extract_claims)
builder.add_node("synthesize_report", synthesize_report)
builder.add_node("fact_check_report", fact_check_report)
builder.add_edge(START, "plan_research")
builder.add_edge("plan_research", "execute_search")
builder.add_edge("execute_search", "fetch_sources")
builder.add_edge("fetch_sources", "extract_claims")
builder.add_conditional_edges("extract_claims", check_conflicts, {
                              "verify_claims": "synthesize_report", "synthesize_report": "synthesize_report"})
builder.add_edge("synthesize_report", "fact_check_report")
builder.add_edge("fact_check_report", END)

# memory = SqliteSaver.from_conn_string("research_checkpoints.db")
memory = MemorySaver()

graph = builder.compile(checkpointer=memory)


async def run_research(question: str, thread_id: str = "default"):
    config = {"configurable": {"thread_id": thread_id}}
    async for step in graph.astream({"question": question, "messages": [HumanMessage(content=question)]}, config, stream_mode="values"):
        if "final_report" in step and step["final_report"]:
            console.print("\n[bold green]Final Report:[/bold green]")
            console.print(step["final_report"])
            return step["final_report"]


if __name__ == "__main__":
    q = "What is the best way to configure opencode with llama.cpp?"
    asyncio.run(run_research(q))
