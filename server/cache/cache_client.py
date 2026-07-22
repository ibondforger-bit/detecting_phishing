from pathlib import Path
from typing import Any
import diskcache
from server.config import get_settings, ROOT_DIR

_cache_instance = None


def _get_cache() -> diskcache.Cache:
    global _cache_instance
    if _cache_instance is None:
        settings = get_settings()
        data_dir = Path(settings.data_dir)
        if not data_dir.is_absolute():
            data_dir = ROOT_DIR / data_dir
        cache_dir = data_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_instance = diskcache.Cache(str(cache_dir))
    return _cache_instance


def get_json(key: str) -> dict[str, Any] | None:
    try:
        return _get_cache().get(key)
    except Exception:
        return None


def set_json(key: str, value: dict[str, Any], ttl_seconds: int = 86400) -> None:
    try:
        _get_cache().set(key, value, expire=ttl_seconds)
    except Exception:
        pass
