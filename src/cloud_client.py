from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app_metadata import APP_BUILD_ID, APP_UPDATE_CHANNEL, APP_VERSION, APP_VERSION_ID
from app_settings import FIXED_CLOUD_MESSAGES_URL, FIXED_UPDATE_MANIFEST_URL
from cloud_security import verify_signed_envelope


DEFAULT_TIMEOUT = 8


@dataclass
class CloudResult:
    ok: bool
    payload: dict[str, Any] | None = None
    error: str = ""


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
    request = urllib.request.Request(url, headers={"User-Agent": f"ShapeYourPhoto/{APP_VERSION}"})
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read()


def fetch_json(url: str, *, params: dict[str, str | int] | None = None) -> CloudResult:
    try:
        final_url = url
        if params and urllib.parse.urlparse(url).scheme in {"http", "https"}:
            separator = "&" if "?" in url else "?"
            final_url = url + separator + urllib.parse.urlencode(params)
        raw = _read_url(final_url)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return CloudResult(False, error="cloud response is not a JSON object")
        signature = verify_signed_envelope(payload)
        if not signature.ok:
            return CloudResult(False, error=signature.reason)
        return CloudResult(True, payload=payload.get("signed", payload))
    except Exception as exc:
        return CloudResult(False, error=str(exc))


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
