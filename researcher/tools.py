import json
import httpx
from typing import Dict
from pathlib import Path
from pydantic import BaseModel, Field, validator
from requests_html import AsyncHTMLSession
from bs4 import BeautifulSoup
import markdownify


session = AsyncHTMLSession()


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchQuery(BaseModel):
    query: str = Field(..., description="Exact search query string")
    num_results: int = Field(
        8, ge=1, le=15, description="Number of results, max 15")


class ReadUrl(BaseModel):
    url: str = Field(...,
                     description="Full URL to fetch and extract clean text from")


class WriteFile(BaseModel):
    path: str = Field(..., description="Relative or absolute path to write")
    content: str = Field(..., description="Full content to write")

    @validator("path")
    def prevent_path_traversal(cls, v):
        if ".." in Path(v).parts or Path(v).is_absolute() and not str(Path(v).resolve()).startswith(str(Path.cwd().resolve())):
            raise ValueError("Path traversal attempt blocked")
        return v


async def search_web(query: str, num_results: int = 8) -> list[SearchResult]:
    params = {"q": query, "format": "json", "engines": "ddg"}
    try:
        resp = httpx.get(f"http://127.0.0.1:8081/search",
                         params=params, timeout=20.0)
    except:
        return []
    data = resp.json()
    results = data.get("results", [])[:num_results]
    formatted = []
    for r in results:
        formatted.append(SearchResult(
            title=r["title"], url=r["url"], snippet=r.get("content", "")))
    return formatted


async def fetch_page(url: str) -> str:
    try:
        r = await session.get(url, timeout=30.0)
        await r.html.arender(sleep=2, keep_page=True)
        soup = BeautifulSoup(r.html.raw_html, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        markdown = markdownify.markdownify(text, heading_style="ATX")
        return markdown[:120000]  # truncae to roughly 30k tokens
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"


async def execute_tool(tool_call: Dict) -> Dict:
    func_name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    if func_name == "search_web":
        query = SearchQuery(**args)
        result = await search_web(query.query, query.num_results)
    elif func_name == "read_url":
        url = ReadUrl(**args)
        result = await fetch_page(url.url)
    elif func_name == "write_file":
        file = WriteFile(**args)
        Path(file.path).write_text(file.content, encoding="utf-8")
        result = f"File written to {file.path}"
    else:
        result = "Unknown tool"
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
            "name": "search_web",
            "description": "Search the internet via local SearxNG instance and return title+url+snippet.",
            "parameters": SearchQuery.model_json_schema()
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Fetch a webpage and return clean markdown body.",
            "parameters": ReadUrl.model_json_schema()
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file inside the current working directory only.",
            "parameters": WriteFile.model_json_schema()
        }
    }
]
