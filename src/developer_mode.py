from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from paths import user_data_dir


HASH_ENV = "SHAPEYOURPHOTO_DEV_PASSWORD_HASH"
SECRET_FILE_ENV = "SHAPEYOURPHOTO_DEV_SECRET_FILE"
DEFAULT_SECRET_FILE = user_data_dir() / "developer_secret.json"
HASH_ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 260_000


def make_password_hash(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        [
            HASH_ALGORITHM,
            str(iterations),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def _read_hash_from_file(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("password_hash", "")
    return str(value).strip()


def load_password_hash() -> tuple[str | None, str]:
    env_hash = os.environ.get(HASH_ENV, "").strip()
    if env_hash:
        return env_hash, f"environment:{HASH_ENV}"
    configured_file = os.environ.get(SECRET_FILE_ENV, "").strip()
    secret_path = Path(configured_file) if configured_file else DEFAULT_SECRET_FILE
    if secret_path.exists():
        try:
            value = _read_hash_from_file(secret_path)
        except Exception as exc:
            return None, f"{secret_path} read failed: {exc}"
        if value:
            return value, str(secret_path)
    return None, "not configured"


def verify_password(password: str, encoded_hash: str) -> bool:
    parts = encoded_hash.split("$")
    if len(parts) != 4 or parts[0] != HASH_ALGORITHM:
        return False
    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2], validate=True)
        expected = base64.b64decode(parts[3], validate=True)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


@dataclass
class DeveloperSession:
    unlocked: bool = False
    source: str = ""

    def unlock(self, password: str) -> tuple[bool, str]:
        encoded_hash, source = load_password_hash()
        if not encoded_hash:
            self.unlocked = False
            self.source = ""
            return False, "Developer password is not configured on this machine."
        if verify_password(password, encoded_hash):
            self.unlocked = True
            self.source = source
            return True, "Developer mode is unlocked for this app session."
        self.unlocked = False
        self.source = ""
        return False, "Developer password verification failed."

    def lock(self) -> None:
        self.unlocked = False
        self.source = ""


developer_session = DeveloperSession()
