from __future__ import annotations


DEFAULT_LANGUAGE = "zh_CN"

LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    (DEFAULT_LANGUAGE, "简体中文"),
    ("en_US", "English"),
    ("ja_JP", "日本語"),
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


TEXT: dict[str, dict[str, str]] = {
    DEFAULT_LANGUAGE: {
        "menu.view": "查看",
        "menu.settings": "设置",
        "menu.help": "帮助",
        "menu.help_website": "帮助与官网",
        "dialog.help_title": "帮助与官网",
        "dialog.help_body": "需要帮助请联系，请查看官网。",
        "action.open_website": "打开官网",
        "action.close": "关闭",
        "view.cleanup": "打开不适合保留的图片",
        "view.similar": "打开相似图片组",
        "view.scan_summary": "最近扫描摘要",
        "view.repair_summary": "最近修复摘要",
        "settings.app": "应用设置",
        "right.title": "图片信息",
        "right.diagnosis": "诊断",
        "right.preview": "预览图",
        "right.properties": "属性 / EXIF",
        "right.console": "Console",
        "preview.empty": "选择图片后，这里会显示更大的预览图。",
    },
    "en_US": {
        "menu.view": "View",
        "menu.settings": "Settings",
        "menu.help": "Help",
        "menu.help_website": "Help & Website",
        "dialog.help_title": "Help & Website",
        "dialog.help_body": "Need help? Please contact us or visit the official website.",
        "action.open_website": "Open Website",
        "action.close": "Close",
        "view.cleanup": "Unsuitable Images",
        "view.similar": "Similar Images",
        "view.scan_summary": "Recent Scan Summary",
        "view.repair_summary": "Recent Repair Summary",
        "settings.app": "App Settings",
        "right.title": "Image Info",
        "right.diagnosis": "Diagnosis",
        "right.preview": "Preview",
        "right.properties": "Properties / EXIF",
        "right.console": "Console",
        "preview.empty": "Select an image to see a larger preview here.",
    },
    "ja_JP": {
        "menu.view": "表示",
        "menu.settings": "設定",
        "menu.help": "ヘルプ",
        "menu.help_website": "ヘルプと公式サイト",
        "dialog.help_title": "ヘルプと公式サイト",
        "dialog.help_body": "サポートが必要な場合は、公式サイトをご確認ください。",
        "action.open_website": "公式サイトを開く",
        "action.close": "閉じる",
        "view.cleanup": "保留に向かない画像",
        "view.similar": "類似画像グループ",
        "view.scan_summary": "最近のスキャン概要",
        "view.repair_summary": "最近の修復概要",
        "settings.app": "アプリ設定",
        "right.title": "画像情報",
        "right.diagnosis": "診断",
        "right.preview": "プレビュー",
        "right.properties": "属性 / EXIF",
        "right.console": "Console",
        "preview.empty": "画像を選択すると、ここに大きなプレビューが表示されます。",
    },
}


def tr(key: str) -> str:
    lang = normalize_language(get_current_language())
    return TEXT.get(lang, TEXT[DEFAULT_LANGUAGE]).get(key, TEXT[DEFAULT_LANGUAGE].get(key, key))
