from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "changelog" / "versions.json"
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"
UPDATES_DIR = ROOT / "docs" / "updates"


def load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def render_version(version: dict) -> str:
    lines = [
        f"## {version['version']} ({version['date']})",
        f"- 版本 ID {version['version_id']}",
        "",
    ]
    lines.extend(f"- {item}" for item in version["items"])
    return "\n".join(lines).rstrip() + "\n"


def generate() -> None:
    data = load_source()
    versions = data.get("versions") or []
    if not versions:
        raise SystemExit("missing changelog versions")
    latest = versions[0]
    latest_block = render_version(latest)

    existing = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# ShapeYourPhoto 更新历史\n\n"
    lines = existing.splitlines()
    heading_indexes = [index for index, line in enumerate(lines) if line.startswith("## ")]
    if heading_indexes:
        first = heading_indexes[0]
        second = heading_indexes[1] if len(heading_indexes) > 1 else len(lines)
        prefix = "\n".join(lines[:first]).rstrip() + "\n\n"
        suffix = "\n".join(lines[second:]).lstrip()
        CHANGELOG.write_text((prefix + latest_block + "\n" + suffix).rstrip() + "\n", encoding="utf-8")
    else:
        CHANGELOG.write_text(existing.rstrip() + "\n\n" + latest_block, encoding="utf-8")

    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    (UPDATES_DIR / f"{latest['version']}.md").write_text(f"# ShapeYourPhoto {latest['version']}\n\n{latest_block}", encoding="utf-8")


if __name__ == "__main__":
    generate()
