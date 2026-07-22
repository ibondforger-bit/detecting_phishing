from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal["safe", "suspicious", "unknown"]


class CheckRequest(BaseModel):
    url_hash: str = Field(min_length=32)
    url: str | None = None
    source: str | None = "direct"


class CheckResponse(BaseModel):
    result: Literal["safe", "suspicious"]
    reason: str
    cached: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class DeepScanRequest(BaseModel):
    url: str
    source: str | None = "direct"


class DeepScanResponse(BaseModel):
    scan_id: str
    status: str


class ToolResult(BaseModel):
    status: Literal["ok", "error"]
    data: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class UpdateKeysRequest(BaseModel):
    google_safe_browsing_api_key: str | None = None
    virustotal_api_key: str | None = None
    phishtank_api_key: str | None = None
    spamhaus_api_key: str | None = None
    cloudflare_api_key: str | None = None



