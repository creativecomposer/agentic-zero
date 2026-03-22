import httpx
from requests_html import AsyncHTMLSession
from bs4 import BeautifulSoup
import markdownify

SEARXNG_URL = "http://127.0.0.1:8081"

session = AsyncHTMLSession()


async def search_web(query: str, num_results: int = 8) -> str:
    params = {"q": query, "format": "json", "engines": "ddg"}
    resp = httpx.get(f"{SEARXNG_URL}/search", params=params, timeout=20.0)
    data = resp.json()
    results = data.get("results", [])[:num_results]
    formatted = []
    for r in results:
        formatted.append(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {
            r.get('content', '')[:300]}...")
    return "\n\n".join(formatted)


async def read_url(url: str) -> str:
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
