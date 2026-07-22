from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from server.config import ROOT_DIR, get_settings
from server.models import DeepScanRequest, DeepScanResponse
from server.tools import dns_tool, dom_tool, network_tool, redirect_tool, whois_tool
from server.tools.nlp_tool import run_nlp_analysis

router = APIRouter(tags=["deep-scan"])


def _get_outputs_dir() -> Path:
    settings = get_settings()
    path = Path(settings.outputs_dir)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/deepscan", response_model=DeepScanResponse)
async def deep_scan(payload: DeepScanRequest) -> DeepScanResponse:
    scan_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    outputs_dir = _get_outputs_dir()

    whois_task = asyncio.to_thread(whois_tool.run, payload.url)
    dns_task = asyncio.to_thread(dns_tool.run, payload.url)
    dom_task = dom_tool.run(payload.url)
    redirect_task = redirect_tool.run(payload.url)
    network_task = network_tool.run(payload.url)
    nlp_task = run_nlp_analysis("")

    whois_result, dns_result, dom_result, redirect_result, network_result, nlp_result = await asyncio.gather(
        whois_task, dns_task, dom_task, redirect_task, network_task, nlp_task
    )

    document = {
        "scan_id": scan_id,
        "url": payload.url,
        "source": payload.source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tools": {
            "whois": whois_result,
            "dns": dns_result,
            "dom": dom_result,
            "nlp": nlp_result,
            "redirect_chain": redirect_result,
            "network_traffic": network_result,
        },
    }
    _write_scan(scan_id, document)
    return DeepScanResponse(scan_id=scan_id, status="complete")


@router.get("/reports/{scan_id}")
async def get_report(scan_id: str) -> dict[str, Any]:
    outputs_dir = _get_outputs_dir()
    path = outputs_dir / f"{scan_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scan not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/reports")
async def list_reports() -> list[dict[str, Any]]:
    outputs_dir = _get_outputs_dir()
    reports = []
    for path in sorted(outputs_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reports.append({"scan_id": data["scan_id"], "url": data["url"], "created_at": data["created_at"]})
        except Exception:
            continue
    return reports


def _write_scan(scan_id: str, document: dict[str, Any]) -> None:
    outputs_dir = _get_outputs_dir()
    path = outputs_dir / f"{scan_id}.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")

