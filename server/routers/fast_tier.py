from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from server.cache.cache_client import get_json, set_json
from server.config import ROOT_DIR, get_settings, get_api_key, set_api_key
from server.models import CheckRequest, CheckResponse, UpdateKeysRequest
from server.tools.blocklists import run_blocklist_checks
from server.tools.url_heuristics import analyze_url

router = APIRouter(tags=["fast-tier"])

# Protection status shared state (can be toggled by the PyQt6 GUI thread)
PROTECTION_ACTIVE = True
_log_lock = threading.Lock()


@router.get("/", response_class=HTMLResponse)
async def get_root_page() -> HTMLResponse:
    setup_path = ROOT_DIR / "server" / "templates" / "setup.html"
    if not setup_path.exists():
        return HTMLResponse(content="<h1>WebSense Backend Server is Running</h1><p>Go to <a href='/setup'>/setup</a> to configure API keys.</p>")
    return HTMLResponse(content=setup_path.read_text(encoding="utf-8"))


@router.get("/setup", response_class=HTMLResponse)
async def get_setup_page() -> HTMLResponse:
    setup_path = ROOT_DIR / "server" / "templates" / "setup.html"
    if not setup_path.exists():
        raise HTTPException(status_code=404, detail="Setup template not found")
    return HTMLResponse(content=setup_path.read_text(encoding="utf-8"))


@router.post("/check", response_model=CheckResponse)
async def check_url(payload: CheckRequest) -> CheckResponse:
    # If protection is paused, return safe immediately
    if not PROTECTION_ACTIVE:
        return CheckResponse(result="safe", reason="Protection is paused")

    cache_key = f"url:{payload.url_hash}"
    cached = get_json(cache_key)
    if cached:
        return CheckResponse(**cached, cached=True)

    if not payload.url:
        raise HTTPException(status_code=404, detail="Cache miss; raw URL required")

    whitelist = _load_whitelist()
    heuristics = analyze_url(payload.url)
    host = heuristics["parsed"]["host"].removeprefix("www.")

    if _is_whitelisted(host, whitelist):
        result = {"result": "safe", "reason": "Domain is on developer-maintained whitelist", "details": {"heuristics": heuristics}}
        set_json(cache_key, result)
        return CheckResponse(**result)

    blocklists = await run_blocklist_checks(payload.url)
    reasons: list[str] = []
    
    # 2.5 Blocklist API logic
    flagged_apis = []
    if blocklists["verdict"] == "suspicious":
        flagged_apis = [
            res["api_display_name"] 
            for res in blocklists["results"] 
            if res.get("verdict") == "suspicious"
        ]
        
    if flagged_apis:
        if len(flagged_apis) == 1:
            reasons.append(f"{flagged_apis[0]} is showing phishing")
        else:
            reasons.append(f"{', '.join(flagged_apis[:-1])} and {flagged_apis[-1]} are showing phishing")
    elif heuristics["status"] == "suspicious":
        reasons.extend(heuristics["reasons"])

    if reasons:
        verdict = "suspicious"
        reason = "; ".join(reasons)
    else:
        verdict = "safe"
        reason = "No suspicious signals found"

    result = {
        "result": verdict, 
        "reason": reason, 
        "details": {
            "heuristics": heuristics, 
            "blocklists": blocklists
        }
    }
    set_json(cache_key, result)
    return CheckResponse(**result)


@router.post("/logs")
async def add_log(log_entry: dict[str, Any]) -> dict[str, str]:
    settings = get_settings()
    log_file = Path(settings.logs_file)
    if not log_file.is_absolute():
        log_file = ROOT_DIR / log_file
    
    with _log_lock:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        existing_logs = []
        if log_file.exists():
            try:
                existing_logs = json.loads(log_file.read_text(encoding="utf-8"))
            except Exception:
                existing_logs = []
        existing_logs.append(log_entry)
        # Keep last 2000 logs to prevent file bloat
        log_file.write_text(json.dumps(existing_logs[-2000:], indent=2), encoding="utf-8")
        
    return {"status": "success"}


@router.get("/api-status")
async def api_status() -> dict[str, Any]:
    return {
        "google_safe_browsing": {"active": bool(get_api_key("google_safe_browsing")), "rate_limit": "provider account"},
        "virustotal": {"active": bool(get_api_key("virustotal")), "rate_limit": "provider account"},
        "phishtank": {"active": bool(get_api_key("phishtank")), "rate_limit": "provider account"},
        "spamhaus": {"active": bool(get_api_key("spamhaus")), "rate_limit": "provider account"},
        "cloudflare": {"active": bool(get_api_key("cloudflare")), "rate_limit": "provider account"},
    }


@router.post("/api-keys")
async def update_api_keys(payload: UpdateKeysRequest) -> dict[str, str]:
    if payload.google_safe_browsing_api_key is not None:
        set_api_key("google_safe_browsing", payload.google_safe_browsing_api_key)
    if payload.virustotal_api_key is not None:
        set_api_key("virustotal", payload.virustotal_api_key)
    if payload.phishtank_api_key is not None:
        set_api_key("phishtank", payload.phishtank_api_key)
    if payload.spamhaus_api_key is not None:
        set_api_key("spamhaus", payload.spamhaus_api_key)
    if payload.cloudflare_api_key is not None:
        set_api_key("cloudflare", payload.cloudflare_api_key)
    return {"status": "success", "message": "API keys updated successfully"}


def _load_whitelist() -> list[str]:
    settings = get_settings()
    whitelist_dir = Path(settings.whitelist_dir)
    if not whitelist_dir.is_absolute():
        whitelist_dir = ROOT_DIR / whitelist_dir
        
    path_fast = whitelist_dir / "whitelist_fast.json"
    path_user = whitelist_dir / "user_whitelist.json"
    
    whitelist = []
    try:
        if path_fast.exists():
            whitelist.extend(json.loads(path_fast.read_text(encoding="utf-8")))
    except Exception:
        pass
    try:
        if path_user.exists():
            data = json.loads(path_user.read_text(encoding="utf-8"))
            whitelist.extend(data.get("user_added_domains", []))
    except Exception:
        pass
    return list(set(whitelist))



def _is_whitelisted(host: str, whitelist: list[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in whitelist)

