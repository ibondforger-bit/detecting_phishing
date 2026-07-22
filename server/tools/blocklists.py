from __future__ import annotations

import asyncio
import base64
from typing import Any
from urllib.parse import urlparse

import httpx

from server.config import get_settings, get_api_key


async def run_blocklist_checks(url: str) -> dict[str, Any]:
    settings = get_settings()
    timeout = settings.request_timeout_seconds

    keys = {
        "google_safe_browsing": get_api_key("google_safe_browsing"),
        "virustotal": get_api_key("virustotal"),
        "phishtank": get_api_key("phishtank"),
        "spamhaus": get_api_key("spamhaus"),
        "cloudflare": get_api_key("cloudflare"),
    }

    tasks = []
    if keys["google_safe_browsing"]:
        tasks.append(_check_google_safe_browsing(url, keys["google_safe_browsing"], timeout))
    if keys["virustotal"]:
        tasks.append(_check_virustotal(url, keys["virustotal"], timeout))
    if keys["phishtank"]:
        tasks.append(_check_phishtank(url, keys["phishtank"], timeout))
    if keys["spamhaus"]:
        tasks.append(_check_spamhaus(url, keys["spamhaus"], timeout))
    if keys["cloudflare"]:
        tasks.append(_check_cloudflare(url, keys["cloudflare"], timeout))

    if not tasks:
        # If no APIs are configured, runheuristics only (handled in fast_tier.py)
        return {
            "verdict": "safe",
            "results": [],
        }

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    parsed_results = []
    has_suspicious = False
    
    for i, res in enumerate(results):
        api_name = list(filter(lambda k: keys[k], keys.keys()))[i]
        display_name = {
            "google_safe_browsing": "Google Safe Browsing",
            "virustotal": "VirusTotal",
            "phishtank": "PhishTank",
            "spamhaus": "Spamhaus",
            "cloudflare": "Cloudflare"
        }.get(api_name, api_name)
        
        if isinstance(res, Exception):
            parsed_results.append({
                "api": api_name,
                "api_display_name": display_name,
                "verdict": "unknown",
                "reason": f"API request error: {str(res)}",
            })
        else:
            parsed_results.append(res)
            if res.get("verdict") == "suspicious":
                has_suspicious = True

    return {
        "verdict": "suspicious" if has_suspicious else "safe",
        "results": parsed_results,
    }


async def _check_google_safe_browsing(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"
    payload = {
        "client": {"clientId": "websense-dev", "clientVersion": "0.2.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        body = response.json()
    is_suspicious = bool(body.get("matches"))
    return {
        "api": "google_safe_browsing",
        "api_display_name": "Google Safe Browsing",
        "verdict": "suspicious" if is_suspicious else "safe",
        "reason": "Matches returned" if is_suspicious else "No matches",
    }


async def _check_virustotal(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    # VT URL ID is url-safe base64 without padding
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    endpoint = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    headers = {"x-apikey": api_key}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(endpoint, headers=headers)
        if response.status_code == 404:
            return {
                "api": "virustotal",
                "api_display_name": "VirusTotal",
                "verdict": "safe",
                "reason": "URL not found in VirusTotal database",
            }
        response.raise_for_status()
        body = response.json()
    
    stats = body.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    is_suspicious = (malicious > 0) or (suspicious > 0)
    return {
        "api": "virustotal",
        "api_display_name": "VirusTotal",
        "verdict": "suspicious" if is_suspicious else "safe",
        "reason": f"Malicious detections: {malicious}, suspicious: {suspicious}" if is_suspicious else "Clean score",
    }


async def _check_phishtank(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    endpoint = "https://checkurl.phishtank.com/checkurl/"
    headers = {"User-Agent": "phishtank/PhishGuard"}
    payload = {
        "url": url,
        "format": "json"
    }
    if api_key:
        payload["app_key"] = api_key
        
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(endpoint, data=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
    
    is_suspicious = False
    if isinstance(body, dict) and "results" in body:
        results = body["results"]
        if results and results.get("verified") and results.get("valid"):
            is_suspicious = True
    elif isinstance(body, list) and len(body) > 0:
        # Sometimes returns a list of result dicts
        res = body[0]
        if isinstance(res, dict) and "results" in res:
            res_inner = res["results"]
            if res_inner and res_inner.get("verified") and res_inner.get("valid"):
                is_suspicious = True
    
    return {
        "api": "phishtank",
        "api_display_name": "PhishTank",
        "verdict": "suspicious" if is_suspicious else "safe",
        "reason": "Verified phishing in PhishTank database" if is_suspicious else "Not listed",
    }


async def _check_spamhaus(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    parsed = urlparse(url)
    domain = parsed.netloc.removeprefix("www.")
    if not domain:
        return {
            "api": "spamhaus",
            "api_display_name": "Spamhaus",
            "verdict": "safe",
            "reason": "Invalid domain",
        }
    
    endpoint = f"https://apibl.spamhaus.net/lookup/v1/DBL/{domain}"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(endpoint, headers=headers)
        if response.status_code == 404:
            return {
                "api": "spamhaus",
                "api_display_name": "Spamhaus",
                "verdict": "safe",
                "reason": "Domain not listed in DBL",
            }
        response.raise_for_status()
        is_suspicious = response.status_code == 200
    
    return {
        "api": "spamhaus",
        "api_display_name": "Spamhaus",
        "verdict": "suspicious" if is_suspicious else "safe",
        "reason": "Listed in Spamhaus DBL" if is_suspicious else "Not listed",
    }


async def _check_cloudflare(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    parsed = urlparse(url)
    domain = parsed.netloc.removeprefix("www.")
    if not domain:
        return {
            "api": "cloudflare",
            "api_display_name": "Cloudflare",
            "verdict": "safe",
            "reason": "Invalid domain",
        }
    
    if ":" not in api_key:
        return {
            "api": "cloudflare",
            "api_display_name": "Cloudflare",
            "verdict": "unknown",
            "reason": "Cloudflare API key format must be 'account_id:api_token'",
        }
    
    account_id, token = api_key.split(":", 1)
    endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/intel/domain?domain={domain}"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(endpoint, headers=headers)
        response.raise_for_status()
        body = response.json()
    
    result = body.get("result", {})
    classification = result.get("classification", {}).get("type", "").lower()
    is_suspicious = classification in ["phishing", "malicious", "malware", "spam"]
    return {
        "api": "cloudflare",
        "api_display_name": "Cloudflare",
        "verdict": "suspicious" if is_suspicious else "safe",
        "reason": f"Cloudflare domain classification: {classification}" if is_suspicious else "Classified as clean",
    }

