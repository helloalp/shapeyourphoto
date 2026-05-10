from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paths import resource_path


PUBLIC_KEY_ENV = "SHAPEYOURPHOTO_UPDATE_PUBLIC_KEY"
PUBLIC_KEY_FILE_ENV = "SHAPEYOURPHOTO_UPDATE_PUBLIC_KEY_FILE"
DEFAULT_PUBLIC_KEY_FILE = resource_path("assets/update_public_key.pem")


@dataclass(frozen=True)
class SignatureResult:
    ok: bool
    reason: str = ""


def canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_public_key_pem() -> bytes | None:
    env_key = os.environ.get(PUBLIC_KEY_ENV, "").strip()
    if env_key:
        return env_key.encode("utf-8")
    key_file = os.environ.get(PUBLIC_KEY_FILE_ENV, "").strip()
    path = Path(key_file) if key_file else DEFAULT_PUBLIC_KEY_FILE
    if path.exists():
        return path.read_bytes()
    return None


def verify_signature(payload: Any, signature_b64: str | None) -> SignatureResult:
    if not signature_b64:
        return SignatureResult(False, "missing cloud signature")
    key_pem = load_public_key_pem()
    if not key_pem:
        return SignatureResult(False, "update public key is not configured")
    try:
        signature = base64.b64decode(str(signature_b64), validate=True)
    except Exception as exc:
        return SignatureResult(False, f"invalid signature encoding: {exc}")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception as exc:
        return SignatureResult(False, f"cryptography Ed25519 backend unavailable: {exc}")
    try:
        public_key = serialization.load_pem_public_key(key_pem)
        if not isinstance(public_key, Ed25519PublicKey):
            return SignatureResult(False, "configured public key is not Ed25519")
        public_key.verify(signature, canonical_json(payload))
        return SignatureResult(True, "")
    except Exception as exc:
        return SignatureResult(False, f"signature verification failed: {exc}")


def verify_signed_envelope(envelope: dict[str, Any]) -> SignatureResult:
    if not isinstance(envelope, dict):
        return SignatureResult(False, "cloud response is not an object")
    signed = envelope.get("signed")
    if signed is None:
        signed = {key: value for key, value in envelope.items() if key != "signature"}
    return verify_signature(signed, envelope.get("signature"))


def path_within(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
