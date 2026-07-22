from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from server.config import get_settings
from server.tools.url_heuristics import analyze_url


async def run(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=get_settings().request_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
        page_host = urlparse(str(response.url)).hostname
        soup = BeautifulSoup(response.text, "html.parser")
        domains = set()
        for tag, attr in (("script", "src"), ("img", "src"), ("iframe", "src"), ("link", "href")):
            for item in soup.find_all(tag):
                value = item.get(attr)
                if not value:
                    continue
                host = urlparse(urljoin(str(response.url), value)).hostname
                if host and host != page_host:
                    domains.add(host)
        scanned = [{"domain": domain, "heuristics": analyze_url(f"https://{domain}")} for domain in sorted(domains)[:25]]
        return {"status": "ok", "data": {"page_domain": page_host, "connected_domains": scanned, "limit": 25}}
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "data": {}}
