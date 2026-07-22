from functools import lru_cache
from pathlib import Path
import keyring
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent

SERVICE_NAME = "PhishGuard"
API_KEYS = ["google_safe_browsing", "phishtank", "cloudflare", "spamhaus", "virustotal"]


class Settings(BaseSettings):
    server_port: int = 5000
    server_host: str = "127.0.0.1"
    request_timeout: float = 5.0
    cache_expiry_seconds: int = 86400
    data_dir: str = "./data"
    whitelist_dir: str = "./whitelist"
    outputs_dir: str = "./data/outputs"
    logs_file: str = "./data/logs/browsing_log.json"

    @property
    def request_timeout_seconds(self) -> float:
        return self.request_timeout

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")



@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_api_key(name: str) -> str:
    if name not in API_KEYS:
        return ""
    try:
        return keyring.get_password(SERVICE_NAME, name) or ""
    except Exception:
        return ""


def set_api_key(name: str, value: str) -> None:
    if name not in API_KEYS:
        return
    val = value.strip()
    try:
        if val:
            keyring.set_password(SERVICE_NAME, name, val)
        else:
            try:
                keyring.delete_password(SERVICE_NAME, name)
            except Exception:
                pass
    except Exception:
        pass

