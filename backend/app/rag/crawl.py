"""Crawl client — turns URLs into markdown via the on-demand Crawl4AI service.

Crawl4AI runs headless Chromium and returns cleaned markdown. Its `/crawl` endpoint
wants configs in crawl4ai's "dump" format ({"type","params"}); it also blocks setting
raw request headers from an untrusted caller, so we pass `locale` (Playwright derives
Accept-Language from it) rather than an explicit header.

Only used during ingest — the crawler service is off unless started with the `crawl` profile.
"""
import httpx

from app.config import settings


async def crawl_to_markdown(urls: list[str]) -> list[dict]:
    body = {
        "urls": urls,
        "browser_config": {"type": "BrowserConfig", "params": {"locale": "en-US"}},
        "crawler_config": {"type": "CrawlerRunConfig", "params": {"cache_mode": "bypass"}},
    }
    headers = {"Authorization": f"Bearer {settings.crawl4ai_token}"}
    async with httpx.AsyncClient(timeout=240) as client:
        resp = await client.post(f"{settings.crawl4ai_url}/crawl", json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    out: list[dict] = []
    for res in data.get("results", []):
        if not res.get("success"):
            continue
        md = res.get("markdown")
        if isinstance(md, dict):
            text = md.get("fit_markdown") or md.get("raw_markdown") or ""
        else:
            text = md or ""
        text = (text or "").strip()
        if not text:
            continue
        meta = res.get("metadata") or {}
        out.append({"url": res.get("url"), "title": meta.get("title"), "markdown": text})
    return out
