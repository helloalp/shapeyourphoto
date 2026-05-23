from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app_metadata import APP_VERSION, APP_VERSION_ID


OFFICIAL_SITE_URL = "https://helloalp.top/tools/shapeyourphoto"
RULE_RECOMMEND_OFFICIAL = "recommend_official_download"
RULE_BLOCK_IN_APP_UPDATE = "block_in_app_update"


@dataclass(frozen=True)
class UpdateLagDecision:
    rule: str
    count: int
    latest_version: str
    latest_version_id: int
    published_at: str

    @property
    def blocks_in_app_update(self) -> bool:
        return self.rule == RULE_BLOCK_IN_APP_UPDATE


def _parse_remote_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def evaluate_update_lag(manifest: dict, *, now: datetime | None = None) -> UpdateLagDecision | None:
    try:
        latest_id = int(manifest.get("version_id") or manifest.get("build_id") or 0)
    except (TypeError, ValueError):
        return None
    count = latest_id - int(APP_VERSION_ID)
    if count < 2:
        return None
    latest_version = str(manifest.get("version") or manifest.get("latest_version") or "latest")
    published = str(manifest.get("date") or manifest.get("published_at") or manifest.get("release_date") or "")
    if count >= 10:
        return UpdateLagDecision(RULE_BLOCK_IN_APP_UPDATE, count, latest_version, latest_id, published)
    published_dt = _parse_remote_date(published)
    if published_dt is None:
        return None
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    if (now_dt - published_dt).days >= 3:
        return UpdateLagDecision(RULE_RECOMMEND_OFFICIAL, count, latest_version, latest_id, published)
    return None


def _app_identity(app_dir: Path) -> str:
    return hashlib.sha256(str(app_dir.resolve()).casefold().encode("utf-8", errors="replace")).hexdigest()[:16]


def update_policy_state_path(app_dir: Path | None = None) -> Path:
    root = (app_dir or Path.cwd()).resolve()
    return root / "data" / "update_state" / "policy_state.json"


def state_key(app_dir: Path, decision: UpdateLagDecision) -> str:
    return "|".join([_app_identity(app_dir), str(APP_VERSION_ID), str(decision.latest_version_id), decision.rule])


def remember_update_policy_ack(decision: UpdateLagDecision, app_dir: Path | None = None) -> None:
    root = (app_dir or Path.cwd()).resolve()
    path = update_policy_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload[state_key(root, decision)] = {
        "app_version": APP_VERSION,
        "current_version_id": APP_VERSION_ID,
        "latest_version_id": decision.latest_version_id,
        "rule": decision.rule,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def has_acknowledged_update_policy(decision: UpdateLagDecision, app_dir: Path | None = None) -> bool:
    path = update_policy_state_path(app_dir)
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return state_key((app_dir or Path.cwd()).resolve(), decision) in payload


def latest_block_state(app_dir: Path | None = None) -> dict | None:
    root = (app_dir or Path.cwd()).resolve()
    path = update_policy_state_path(root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    prefix = f"{_app_identity(root)}|{APP_VERSION_ID}|"
    for key, value in payload.items():
        if key.startswith(prefix) and isinstance(value, dict) and value.get("rule") == RULE_BLOCK_IN_APP_UPDATE:
            return value
    return None
