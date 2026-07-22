from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from server.config import get_settings


async def run(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=get_settings().request_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        forms = []
        page_host = urlparse(str(response.url)).hostname
        for form in soup.find_all("form"):
            action = form.get("action") or str(response.url)
            action_url = urljoin(str(response.url), action)
            action_host = urlparse(action_url).hostname
            inputs = [item.get("type", "text").lower() for item in form.find_all("input")]
            forms.append(
                {
                    "action": action_url,
                    "cross_domain": bool(action_host and page_host and action_host != page_host),
                    "has_password": "password" in inputs,
                    "hidden_fields": inputs.count("hidden"),
                    "credential_like_inputs": sum(1 for item in inputs if item in {"password", "email", "tel", "number"}),
                }
            )
        suspicious = [form for form in forms if form["cross_domain"] or form["has_password"] or form["hidden_fields"] > 2]
        return {
            "status": "ok",
            "data": {
                "final_url": str(response.url),
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "forms": forms,
                "suspicious_form_count": len(suspicious),
            },
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "data": {}}
