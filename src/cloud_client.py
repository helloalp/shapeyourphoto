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
    local_id = max(int(APP_VERSION_ID), int(APP_BUILD_ID))
    if remote_id > local_id:
        return 1
    if remote_id < local_id:
        return -1
    return 0


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
        return "暂时无法连接更新服务，请稍后再试。"
    if "signature" in lowered or "签名" in lowered:
        return "更新信息校验未通过，请稍后再试。"
    if "json" in lowered:
        return "更新信息格式异常，请稍后再试。"
    return "暂时无法获取更新信息，请稍后再试。"


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
    return fetch_json(
        FIXED_UPDATE_MANIFEST_URL,
        params={
            "version": APP_VERSION,
            "version_id": APP_VERSION_ID,
            "build_id": APP_BUILD_ID,
            "channel": APP_UPDATE_CHANNEL,
        },
    )


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
