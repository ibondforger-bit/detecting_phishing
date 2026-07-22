from __future__ import annotations

from urllib.parse import urlparse

import dns.resolver


def run(url: str) -> dict:
    try:
        host = urlparse(url if "://" in url else f"http://{url}").hostname or url
        records = {}
        for record_type in ("A", "AAAA", "MX", "NS", "TXT"):
            try:
                answers = dns.resolver.resolve(host, record_type, lifetime=4)
                records[record_type] = [str(answer).rstrip(".") for answer in answers]
            except Exception:
                records[record_type] = []
        anomalies = []
        if not records["A"] and not records["AAAA"]:
            anomalies.append("No A or AAAA records found")
        if not records["NS"]:
            anomalies.append("No nameserver records found")
        return {"status": "ok", "data": {"domain": host, "records": records, "anomalies": anomalies}}
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "data": {}}
