from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cloud_security import sha256_file, verify_signed_envelope
from paths import resource_path


REQUIRED_RUNTIME_FILES = [
    "cloud_client.py",
    "cloud_security.py",
    "cloud_state.py",
    "integrity_guard.py",
    "updater.py",
    "ui/cloud_actions.py",
    "ui/cloud_dialogs.py",
]
INTEGRITY_MANIFEST = resource_path("assets/core_integrity.json")


@dataclass
class IntegrityReport:
    ok: bool
    messages: list[str]


def check_cloud_update_modules(app_dir: Path | None = None) -> IntegrityReport:
    base = (app_dir or Path(__file__).resolve().parent).resolve()
    messages: list[str] = []
    for relative in REQUIRED_RUNTIME_FILES:
        path = base / relative
        if not path.exists():
            messages.append(f"required update/message module is missing: {relative}")
    if messages:
        return IntegrityReport(False, messages)

    if not INTEGRITY_MANIFEST.exists():
        return IntegrityReport(True, ["core integrity hash manifest is not packaged; existence checks passed"])
    try:
        envelope = json.loads(INTEGRITY_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        return IntegrityReport(False, [f"core integrity manifest read failed: {exc}"])
    signature = verify_signed_envelope(envelope)
    if not signature.ok:
        return IntegrityReport(False, [signature.reason])
    signed = envelope.get("signed", {})
    files = signed.get("files", {})
    if not isinstance(files, dict):
        return IntegrityReport(False, ["core integrity manifest has no files map"])
    for relative, expected_hash in files.items():
        if str(relative) not in REQUIRED_RUNTIME_FILES:
            continue
        path = base / str(relative)
        actual = sha256_file(path)
        if actual.lower() != str(expected_hash).lower():
            messages.append(f"core module hash mismatch: {relative}")
    return IntegrityReport(not messages, messages or ["core module integrity passed"])
