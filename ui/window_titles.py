from __future__ import annotations

from app_metadata import APP_VERSION


def app_window_title(feature_name: str) -> str:
    feature = str(feature_name or "").strip() or "窗口"
    return f"ShapeYourPhoto v{APP_VERSION} - {feature}"
