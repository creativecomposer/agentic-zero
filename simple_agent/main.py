import os
import asyncio
from datetime import date
import httpx
import json
from pydantic import BaseModel, Field, validator
from typing import Any, Dict, List
from rich.prompt import Prompt
from console import console


client = httpx.Client(base_url="http://127.0.0.1:8080/v1", timeout=None)

today = date.today().strftime("%A %d. %B %Y")
SYSTEM_PROMPT = f"""You are a helpful, brilliant, and autonomous AI assistant running entirely on the user's local machine.
You have access to the read_file tool to read the content of files on the user's local machine.
    Today's date is {today}. Be concise unless asked to elaborate."""


class ReadFile(BaseModel):
    path: str = Field(..., description="Relative or absolute path to read")

    @validator("path")
    def file_should_exist(cls, v):
        if not os.path.exists(v) or not os.path.isfile(v):
            raise ValueError(
                "Either the file does not exist or it is not a readable file")
        return v


def execute_tool(tool_call: Dict) -> Dict:
    func_name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    try:
        if func_name == "read_file":
            f = ReadFile(**args)
            with open(os.path.expanduser(f.path), "r") as f:
                result = f.read(20000)
        else:
            result = "Unknown tool"
    except:
        console.print(f"[bold red]!!! Exception while running the tool {
                      func_name}!!![/bold red]")
        result = "The given file does not exist"
    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "name": func_name,
        "content": result
    }


TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of the given local file path in the local computer only.",
            "parameters": ReadFile.model_json_schema()
        }
    }
]

message_history: List[Dict[str, Any]] = [
    {"role": "system", "content": SYSTEM_PROMPT}]


async def call_llm(messages):
    try:
        resp = client.post("/chat/completions", json={
            "model": "local",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 8192,
            "tools": TOOLS_SCHEMAS,
            "tool_choice": "auto"
        })
        data = resp.json()
        return data["choices"][0]["message"] or "No response"
    except:
        console.print(
            "[bold red]!!! Exception while calling LLM !!![/bold red]")
        return "No response"


async def chat_loop():
    while True:
        user_question = Prompt.ask("Your question please? :smiley: ")
        console.print(f"[bold green]User: [/bold green]{user_question}")
        message_history.append({"role": "user", "content": user_question})
        with console.status("Getting a reply from agent...", spinner="monkey"):
            for i in range(10):  # Max 10 tool cycles
                llm_response = await call_llm(messages=message_history)
                if llm_response == "No response":
                    console.print(
                        "[orange]The agent did not provide a response[/orange]")
                    break
                if "tool_calls" in llm_response:
                    for tool_call in llm_response.get("tool_calls", []):
                        console.print(
                            f"[bold blue]Calling: [/bold blue]{tool_call["function"]["name"]}, iteration {i}")
                        tool_response = execute_tool(tool_call)
                        message_history.append(tool_response)
                else:
                    message_history.append(llm_response)
                    console.print(
                        f"[bold cyan]Agent: [/bold cyan]{llm_response["content"]}")
                    break


if __name__ == "__main__":
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
        exit(0)
