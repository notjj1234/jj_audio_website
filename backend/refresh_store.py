"""Revoked refresh-token ids. A file, not a new database table."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.config import settings


def revoke_path() -> Path:
    override = os.environ.get("ATT_REFRESH_REVOKE_PATH", "").strip()
    if override:
        return Path(override)
    return Path(settings.data_dir) / "revoked_refresh.json"


def _load(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data if item}


def revoke_refresh_jti(jti: str) -> None:
    token_id = str(jti or "").strip()
    if not token_id:
        return
    path = revoke_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    found = _load(path)
    found.add(token_id)
    path.write_text(json.dumps(sorted(found)), encoding="utf-8")


def refresh_jti_revoked(jti: str) -> bool:
    token_id = str(jti or "").strip()
    if not token_id:
        return False
    return token_id in _load(revoke_path())
