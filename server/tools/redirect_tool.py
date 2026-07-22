from __future__ import annotations

import httpx

from server.config import get_settings


async def run(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=get_settings().request_timeout_seconds, follow_redirects=True, max_redirects=5) as client:
            response = await client.get(url)
        chain = [
            {"status_code": item.status_code, "url": str(item.url), "location": item.headers.get("location")}
            for item in response.history
        ]
        chain.append({"status_code": response.status_code, "url": str(response.url), "location": None})
        return {"status": "ok", "data": {"chain": chain, "hop_count": max(len(chain) - 1, 0)}}
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "data": {}}
