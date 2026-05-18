from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    theme_id: str
    label: str
    primary: str
    accent: str
    background: str
    panel: str
    panel_alt: str
    text: str
    muted_text: str
    button: str
    selection: str
    border: str = "#b9c7bc"
    input_bg: str = "#ffffff"
    disabled_bg: str = "#e5e8e5"
    disabled_text: str = "#777777"
    danger: str = "#9a2d2d"
    success: str = "#2f8f63"
    font_delta: int = 0
    spacing: int = 0


THEMES: dict[str, ThemeTokens] = {
    "classic_green": ThemeTokens(
        "classic_green",
        "经典清绿",
        "#17361f",
        "#2f8f63",
        "#eef3ef",
        "#fbfcfa",
        "#f5faf6",
        "#1f3527",
        "#45604d",
        "#e4efe7",
        "#cdebd9",
    ),
    "graphite": ThemeTokens(
        "graphite",
        "石墨灰",
        "#20252b",
        "#3d7f9f",
        "#f2f4f5",
        "#ffffff",
        "#f6f8f9",
        "#1f262d",
        "#53606b",
        "#e7edf0",
        "#d8ebf0",
    ),
    "studio_blue": ThemeTokens(
        "studio_blue",
        "影像蓝",
        "#18344a",
        "#3978b8",
        "#eef4f8",
        "#fbfdff",
        "#f4f9fc",
        "#1d3546",
        "#4f6878",
        "#e2edf5",
        "#d4e8fa",
    ),
    "warm_paper": ThemeTokens(
        "warm_paper",
        "暖白纸",
        "#3c3328",
        "#9a6a2f",
        "#f5f2ec",
        "#fffdf8",
        "#faf6ee",
        "#2f2a24",
        "#665d52",
        "#eee5d7",
        "#f2dfba",
    ),
    "high_contrast": ThemeTokens(
        "high_contrast",
        "高对比",
        "#050505",
        "#005fcc",
        "#ffffff",
        "#ffffff",
        "#f4f4f4",
        "#000000",
        "#1f1f1f",
        "#e8e8e8",
        "#ffe15a",
        border="#000000",
        input_bg="#ffffff",
        disabled_bg="#d0d0d0",
        disabled_text="#4a4a4a",
        danger="#b00020",
        success="#007a3d",
        font_delta=1,
        spacing=1,
    ),
    "forest_mist": ThemeTokens(
        "forest_mist",
        "森林薄雾",
        "#163a34",
        "#3f8f7b",
        "#edf4f1",
        "#fcfefd",
        "#f2f8f5",
        "#1d332f",
        "#4a6760",
        "#dfeee8",
        "#c9e8dd",
    ),
    "clear_sky": ThemeTokens(
        "clear_sky",
        "晴空",
        "#18324f",
        "#3f86c5",
        "#edf5fa",
        "#ffffff",
        "#f3f9fd",
        "#1b3448",
        "#4c6575",
        "#dfedf6",
        "#cfe8f8",
    ),
    "rose_gray": ThemeTokens(
        "rose_gray",
        "玫瑰灰",
        "#3d2f36",
        "#9b617c",
        "#f4f0f2",
        "#fffdfd",
        "#faf5f7",
        "#312a2f",
        "#665862",
        "#efe2e8",
        "#f0d0dc",
    ),
}

DEFAULT_THEME_ID = "classic_green"
THEME_OPTIONS = [(theme_id, tokens.label) for theme_id, tokens in THEMES.items()]


def normalize_theme_id(theme_id: object) -> str:
    value = str(theme_id or DEFAULT_THEME_ID).strip()
    return value if value in THEMES else DEFAULT_THEME_ID


def get_theme(theme_id: object) -> ThemeTokens:
    return THEMES[normalize_theme_id(theme_id)]
