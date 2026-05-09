import os
from datetime import date
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import httpx
import json

app = FastAPI()

templates = Jinja2Templates(directory="templates")

LLAMA_CPP_URL = os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080/v1")
client = httpx.AsyncClient(base_url=LLAMA_CPP_URL, timeout=300.0)

today = date.today().strftime("%A %d. %B %Y")
SYSTEM_PROMPT = f"""You are a helpful, brilliant, and autonomous AI assistant running entirely on the user's local machine.
    Today's date is {today}. Be concise unless asked to elaborate."""


async def stream_completion(messages):
    payload = {
        "model": "local",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "stream": True
    }
    async with client.stream("POST", "/chat/completions", json=payload) as response:
        async for chunk in response.aiter_lines():
            if not chunk.strip():
                continue
            if chunk.startswith("data: "):
                data = chunk[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    json_data = json.loads(data.strip())
                    delta = json_data["choices"][0]["delta"]
                    print(delta)
                    if "content" in delta:
                        delta_to_yield = delta["content"] or ""
                        yield delta_to_yield
                except Exception as e:
                    print("Exception while parsing data: ", str(e))
                    continue


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.get_template("index.html").render({"request": request})


@app.post("/chat")
async def chat(request: Request, user_message: str = Form(...)):
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}]
    return StreamingResponse(stream_completion(messages), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
