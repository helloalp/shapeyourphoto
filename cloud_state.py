from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from paths import user_data_dir


STATE_FILE = user_data_dir() / "cloud_state.json"
SECRET_FILE = user_data_dir() / "cloud_state_secret.key"


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _state_secret() -> bytes:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()
    secret = secrets.token_bytes(32)
    SECRET_FILE.write_bytes(secret)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return secret


def _mac(payload: dict[str, Any]) -> str:
    return hmac.new(_state_secret(), _canonical(payload), hashlib.sha256).hexdigest()


def load_cloud_state() -> dict[str, Any]:
    default = {
        "declined_version_id": 0,
        "decline_auto_checks": 0,
        "last_seen_message_ids": [],
    }
    if not STATE_FILE.exists():
        return default
    try:
        wrapper = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        payload = wrapper.get("payload", {})
        digest = str(wrapper.get("hmac", ""))
        if not isinstance(payload, dict) or not hmac.compare_digest(digest, _mac(payload)):
            return default | {"integrity_error": "cloud state integrity check failed"}
        return default | payload
    except Exception as exc:
        return default | {"integrity_error": f"cloud state read failed: {exc}"}


def save_cloud_state(payload: dict[str, Any]) -> None:
    state = dict(payload)
    state.pop("integrity_error", None)
    wrapper = {"payload": state, "hmac": _mac(state)}
    STATE_FILE.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")


def record_temporary_decline(version_id: int) -> dict[str, Any]:
    state = load_cloud_state()
    current = int(state.get("declined_version_id") or 0)
    if current != int(version_id):
        state["declined_version_id"] = int(version_id)
        state["decline_auto_checks"] = 1
    else:
        state["decline_auto_checks"] = int(state.get("decline_auto_checks") or 0) + 1
    save_cloud_state(state)
    return state


def set_temporary_decline(version_id: int) -> dict[str, Any]:
    state = load_cloud_state()
    state["declined_version_id"] = int(version_id)
    state["decline_auto_checks"] = 0
    save_cloud_state(state)
    return state


def should_suppress_update_prompt(version_id: int) -> bool:
    state = load_cloud_state()
    if int(state.get("declined_version_id") or 0) != int(version_id):
        return False
    count = int(state.get("decline_auto_checks") or 0)
    if count < 5:
        state["decline_auto_checks"] = count + 1
        save_cloud_state(state)
        return True
    state["decline_auto_checks"] = 0
    save_cloud_state(state)
    return False


def remember_message(message_id: str) -> None:
    state = load_cloud_state()
    seen = [str(item) for item in state.get("last_seen_message_ids", []) if item]
    if message_id not in seen:
        seen.append(message_id)
    state["last_seen_message_ids"] = seen[-50:]
    save_cloud_state(state)
