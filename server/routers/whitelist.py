import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from server.config import ROOT_DIR, get_settings

router = APIRouter(tags=["whitelist"])


def _get_whitelist_dir() -> Path:
    settings = get_settings()
    path = Path(settings.whitelist_dir)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


@router.get("/whitelist")
async def whitelist_fast() -> list[str]:
    path = _get_whitelist_dir() / "whitelist_fast.json"
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/whitelist/details")
async def whitelist_details() -> dict[str, Any]:
    path = _get_whitelist_dir() / "whitelist_details.json"
    return json.loads(path.read_text(encoding="utf-8"))

