from __future__ import annotations

import json
import platform
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app_metadata import APP_BUILD_ID, APP_UPDATE_CHANNEL, APP_VERSION, APP_VERSION_ID
from app_settings import FIXED_CLOUD_MESSAGES_URL, FIXED_UPDATE_MANIFEST_URL
from cloud_security import verify_signed_envelope
from ui.language import tr


DEFAULT_TIMEOUT = 8
USER_AGENT = f"ShapeYourPhotoUpdater/{APP_VERSION} (version_id={APP_VERSION_ID}; {platform.system() or 'Unknown'})"


@dataclass
class CloudResult:
    ok: bool
    payload: dict[str, Any] | None = None
    error: str = ""
    user_message: str = ""


def compare_builds(remote: dict[str, Any]) -> int:
    remote_id = int(remote.get("version_id") or remote.get("build_id") or 0)
    local_id = current_build_id()
    if remote_id > local_id:
        return 1
    if remote_id < local_id:
        return -1
    return 0


def current_build_id() -> int:
    return max(int(APP_VERSION_ID), int(APP_BUILD_ID))


def _int_value(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _target_channels(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("target_channels") or payload.get("channels") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def update_manifest_applies_to_this_client(manifest: dict[str, Any]) -> bool:
    if not manifest.get("enabled", True):
        return False
    channels = _target_channels(manifest)
    if channels and APP_UPDATE_CHANNEL not in channels:
        return False
    local_id = current_build_id()
    exact_ids = manifest.get("target_version_ids") or manifest.get("target_build_ids") or manifest.get("app_version_ids")
    if exact_ids is not None:
        if not isinstance(exact_ids, list):
            exact_ids = [exact_ids]
        allowed = set()
        for item in exact_ids:
            try:
                allowed.add(int(item))
            except (TypeError, ValueError):
                continue
        if allowed and local_id not in allowed:
            return False
    min_id = _int_value(manifest, "target_min_version_id", "min_version_id", "min_build_id", "min_app_version_id")
    max_id = _int_value(manifest, "target_max_version_id", "max_version_id", "max_build_id", "max_app_version_id")
    if min_id is not None and local_id < min_id:
        return False
    if max_id is not None and local_id > max_id:
        return False
    return True


def select_applicable_update_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("updates") or payload.get("manifests")
    if isinstance(candidates, list):
        for candidate in candidates:
            if (
                isinstance(candidate, dict)
                and update_manifest_applies_to_this_client(candidate)
                and compare_builds(candidate) > 0
            ):
                return candidate
        local_id = current_build_id()
        return {"version_id": local_id, "build_id": local_id, "_no_applicable_update": True}
    if not update_manifest_applies_to_this_client(payload):
        local_id = current_build_id()
        return {"version_id": local_id, "build_id": local_id, "_no_applicable_update": True}
    return payload


def _read_url(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"", "file"}:
        path = urllib.request.url2pathname(parsed.path if parsed.scheme == "file" else url)
        with open(path, "rb") as handle:
            return handle.read()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read()


def friendly_cloud_error(error: str) -> str:
    lowered = str(error).lower()
    if "timed out" in lowered or "timeout" in lowered or "_ssl.c" in lowered:
        return tr("update.timeout")
    if "signature" in lowered or "签名" in lowered:
        return tr("update.invalid_signature")
    if "json" in lowered:
        return tr("update.invalid_format")
    return tr("update.service_unavailable")


def fetch_json(url: str, *, params: dict[str, str | int] | None = None) -> CloudResult:
    try:
        final_url = url
        if params and urllib.parse.urlparse(url).scheme in {"http", "https"}:
            separator = "&" if "?" in url else "?"
            final_url = url + separator + urllib.parse.urlencode(params)
        raw = _read_url(final_url)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            error = "cloud response is not a JSON object"
            return CloudResult(False, error=error, user_message=friendly_cloud_error(error))
        signature = verify_signed_envelope(payload)
        if not signature.ok:
            return CloudResult(False, error=signature.reason, user_message=friendly_cloud_error(signature.reason))
        return CloudResult(True, payload=payload.get("signed", payload))
    except Exception as exc:
        error = str(exc)
        return CloudResult(False, error=error, user_message=friendly_cloud_error(error))


def fetch_update_manifest(url: str) -> CloudResult:
    result = fetch_json(
        FIXED_UPDATE_MANIFEST_URL,
        params={
            "version": APP_VERSION,
            "version_id": APP_VERSION_ID,
            "build_id": APP_BUILD_ID,
            "channel": APP_UPDATE_CHANNEL,
        },
    )
    if result.ok and result.payload is not None:
        result.payload = select_applicable_update_manifest(result.payload)
    return result


def fetch_cloud_messages(url: str) -> CloudResult:
    return fetch_json(
        FIXED_CLOUD_MESSAGES_URL,
        params={
            "version": APP_VERSION,
            "version_id": APP_VERSION_ID,
            "build_id": APP_BUILD_ID,
            "channel": APP_UPDATE_CHANNEL,
        },
    )
