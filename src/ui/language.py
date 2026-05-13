from __future__ import annotations


DEFAULT_LANGUAGE = "zh_CN"

LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    (DEFAULT_LANGUAGE, "中文"),
    ("en_US", "English"),
]

LANGUAGE_LABELS = {value: label for value, label in LANGUAGE_OPTIONS}

_CURRENT_LANGUAGE = DEFAULT_LANGUAGE


def normalize_language(value: object) -> str:
    raw = str(value or DEFAULT_LANGUAGE).strip()
    return raw if raw in LANGUAGE_LABELS else DEFAULT_LANGUAGE


def set_current_language(lang: object) -> None:
    global _CURRENT_LANGUAGE
    _CURRENT_LANGUAGE = normalize_language(lang)


def get_current_language() -> str:
    return _CURRENT_LANGUAGE


def language_label(value: object) -> str:
    return LANGUAGE_LABELS[normalize_language(value)]
