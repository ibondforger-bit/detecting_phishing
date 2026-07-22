from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import whois


def run(url: str) -> dict:
    try:
        host = urlparse(url if "://" in url else f"http://{url}").hostname or url
        data = whois.whois(host)
        created = _first_date(data.creation_date)
        age_days = (datetime.now(timezone.utc) - created).days if created else None
        return {
            "status": "ok",
            "data": {
                "domain": host,
                "registrar": data.registrar,
                "creation_date": created.isoformat() if created else None,
                "age_days": age_days,
                "privacy_protection_likely": _privacy_likely(data),
            },
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "data": {}}


def _first_date(value):
    if isinstance(value, list):
        value = next((item for item in value if item), None)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _privacy_likely(data) -> bool:
    text = " ".join(str(getattr(data, field, "")) for field in ("registrant_name", "registrant_organization", "emails"))
    return any(term in text.lower() for term in ("privacy", "redacted", "proxy", "whoisguard"))
