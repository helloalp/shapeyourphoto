from __future__ import annotations

from pathlib import Path

from models import AnalysisResult


def sort_paths(
    paths: list[Path],
    results: dict[Path, AnalysisResult],
    errors: dict[Path, str],
    column: str,
    reverse: bool,
) -> list[Path]:
    def sort_key(path: Path):
        result = results.get(path)
        error = errors.get(path)
        if column == "name":
            return path.name.lower()
        if column == "status":
            if error:
                return (2, path.name.lower())
            if result:
                return (1, path.name.lower())
            return (0, path.name.lower())
        if column == "risk":
            return result.overall_score if result else -1.0
        if column == "tags":
            if result and result.issues:
                return (len(result.issues), "、".join(issue.label for issue in result.issues))
            return (0, "")
        return path.name.lower()

    return sorted(paths, key=sort_key, reverse=reverse)
