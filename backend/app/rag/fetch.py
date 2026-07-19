"""Fetch client — turns URLs into markdown via direct HTTP + HTML→markdown.

Doc sites are server-rendered, so a plain HTTP GET + markdownify yields clean markdown and,
with `Accept-Language: en-US`, English content — no headless browser needed.

(A crawl4ai headless-browser crawler was evaluated but dropped: Stripe re-localizes via
client-side JS so the browser returned pt-BR, and its Chromium hangs behind a VPN. Plain HTTP
is simpler and robust here. See spec 02-rag.md.)
"""
import re

import httpx
from markdownify import markdownify as _to_md

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; support-triage-poc/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}


def _main_content(html: str) -> str:
    """Prefer <main>/<article>/<body> to drop head + chrome; fall back to full HTML."""
    for tag in ("main", "article"):
        m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html, re.S | re.I)
        if m:
            return m.group(1)
    m = re.search(r"<body\b[^>]*>(.*?)</body>", html, re.S | re.I)
    return m.group(1) if m else html


def _title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


async def fetch_to_markdown(urls: list[str]) -> list[dict]:
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception:
                continue  # skip unreachable pages; ingest continues with the rest
            md = _to_md(_main_content(resp.text), heading_style="ATX", strip=["script", "style"]).strip()
            md = re.sub(r"\n{3,}", "\n\n", md)  # collapse excess blank lines
            if not md:
                continue
            out.append({"url": url, "title": _title(resp.text), "markdown": md})
    return out
