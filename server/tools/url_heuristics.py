from __future__ import annotations

import ipaddress
from urllib.parse import unquote, urlparse

SUSPICIOUS_TLDS = {"xyz", "top", "click", "gq", "tk", "zip", "mov", "country", "kim"}
BRANDS = {"paypal", "google", "microsoft", "apple", "amazon", "facebook", "instagram", "netflix", "bankofamerica", "chase", "wellsfargo"}
KEYWORDS = {"verify", "secure", "update", "confirm", "login", "account", "suspended", "password", "billing"}
LOOKALIKE_REPLACEMENTS = {
    "0": "o",
    "1": "l",
    "3": "e",
    "5": "s",
    "@": "a",
}


def analyze_url(url: str) -> dict:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = (parsed.hostname or "").lower()
    decoded = unquote(url).lower()
    reasons: list[str] = []


    if _is_ip(host):
        reasons.append("URL uses a raw IP address as the domain")

    labels = host.split(".")
    tld = labels[-1] if labels else ""
    if tld in SUSPICIOUS_TLDS:
        reasons.append(f"Suspicious top-level domain .{tld}")

    if len(labels) > 4:
        reasons.append("Excessive subdomains")

    if "%" in url and decoded != url.lower():
        reasons.append("URL contains encoded characters")

    if len(url) > 100 and ("?" in url or "&" in url):
        reasons.append("Very long URL with query parameters")

    if parsed.scheme == "http" and any(word in decoded for word in ("login", "password", "account")):
        reasons.append("HTTP URL appears related to credentials")

    host_without_www = host.removeprefix("www.")
    registered = ".".join(labels[-2:]) if len(labels) >= 2 else host
    for brand in BRANDS:
        normalized_host = _normalize_lookalikes(host_without_www)
        brand_in_url = brand in decoded or brand in normalized_host
        brand_is_registered = registered.startswith(brand + ".") or registered == brand
        if brand_in_url and not brand_is_registered:
            reasons.append(f"Brand name appears outside the registered domain: {brand}")
            break
        if f"{brand}-" in host or f"-{brand}" in host:
            reasons.append(f"Hyphenated brand-like domain: {brand}")
            break

    if any(keyword in decoded for keyword in KEYWORDS) and any(brand in decoded for brand in BRANDS):
        reasons.append("Phishing keywords appear together with a known brand")

    return {
        "status": "suspicious" if reasons else "safe",
        "reasons": reasons,
        "parsed": {"scheme": parsed.scheme, "host": host, "registered_domain": registered, "path": parsed.path},
    }


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _normalize_lookalikes(value: str) -> str:
    return "".join(LOOKALIKE_REPLACEMENTS.get(char, char) for char in value)
