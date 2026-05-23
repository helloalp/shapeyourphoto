from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "src" / "app_metadata.py"
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"
UPDATES_DIR = ROOT / "docs" / "updates"
SOURCE = ROOT / "config" / "changelog" / "versions.json"


def read_metadata() -> tuple[str, int, str]:
    tree = ast.parse(METADATA.read_text(encoding="utf-8-sig"))
    version = ""
    version_id = -1
    first_changelog_version = ""
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value_node = node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "APP_VERSION":
                version = ast.literal_eval(value_node)
            if isinstance(target, ast.Name) and target.id == "APP_VERSION_ID":
                version_id = ast.literal_eval(value_node)
            if isinstance(target, ast.Name) and target.id == "CHANGELOG":
                value = ast.literal_eval(value_node)
                if value:
                    first_changelog_version = str(value[0].get("version", ""))
    return version, int(version_id), first_changelog_version


def main() -> int:
    version, version_id, first_changelog_version = read_metadata()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    latest = (source.get("versions") or [{}])[0]
    if latest.get("version") != version:
        failures = [f"structured changelog latest is {latest.get('version')}, expected {version}"]
    else:
        failures = []
    if int(latest.get("version_id") or -1) != version_id:
        failures.append(f"structured changelog version_id is {latest.get('version_id')}, expected {version_id}")
    if first_changelog_version != version:
        failures.append(f"app_metadata.CHANGELOG first version is {first_changelog_version}, expected {version}")

    changelog_text = CHANGELOG.read_text(encoding="utf-8")
    first_heading = re.search(r"^##\s+(.+)$", changelog_text, re.MULTILINE)
    if not first_heading or version not in first_heading.group(1):
        failures.append(f"docs/CHANGELOG.md first version block must be {version}")
    if f"版本 ID {version_id}" not in changelog_text and f"version_id={version_id}" not in changelog_text:
        failures.append(f"docs/CHANGELOG.md does not mention version id {version_id}")

    update_doc = UPDATES_DIR / f"{version}.md"
    if not update_doc.exists():
        failures.append(f"missing docs/updates/{version}.md")
    else:
        update_text = update_doc.read_text(encoding="utf-8")
        if version not in update_text.splitlines()[0]:
            failures.append(f"docs/updates/{version}.md first heading does not match {version}")

    if failures:
        print("Changelog sync check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Changelog sync ok: {version} / version id {version_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
