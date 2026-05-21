from __future__ import annotations

APP_NAME = "Shape Your Photo"
APP_VERSION = "1.2.7"
APP_VERSION_ID = 11
APP_BUILD_ID = 11
APP_UPDATE_CHANNEL = "stable"
APP_ID = "helloalp.shapeyourphoto.desktop"


CHANGELOG_I18N: dict[str, list[dict[str, object]]] = {
    "zh_CN": [
        {
            "version": "1.2.7",
            "date": "2026-05-20",
            "items": [
                "启动入口升级为根目录 ShapeYourPhoto.exe，源码兼容入口移动到 tools/launcher/start.bat。",
                "根目录只保留 README.md、ShapeYourPhoto.exe 和 .gitignore，运行依赖、GUI 薄入口和版本记录移入子目录。",
                "批量处理目标严格以当前列表和当前选择为准，移出列表的图片不会被重新加入任务。",
                "EXIF 编辑页区分可编辑项、只读项和软件保留项，标题、作者、版权和关键词可正常保存。",
                "不适合保留的图片复核窗口改为多图大预览，文件名、严重程度和主要原因更清晰。",
                "Console 优化了时间与事件显示，批量处理时界面响应更稳定。",
            ],
        }
    ],
    "en_US": [
        {
            "version": "1.2.7",
            "date": "2026-05-20",
            "items": [
                "The root ShapeYourPhoto.exe is now the primary startup entry, with tools/launcher/start.bat kept for source-tree compatibility.",
                "The root folder now keeps only README.md, ShapeYourPhoto.exe, and .gitignore; runtime requirements, GUI entry shims, and release notes live under subfolders.",
                "Batch targets now come strictly from the current list and current selection, so removed images are not restored by stale task state.",
                "The EXIF editor separates editable fields, read-only camera data, and software-reserved fields.",
                "Unsuitable-image review now uses larger multi-image previews with clearer file names, severity, and reasons.",
                "Console timestamps and event formatting are clearer while batch processing remains more responsive.",
            ],
        }
    ],
    "ja_JP": [
        {
            "version": "1.2.7",
            "date": "2026-05-20",
            "items": [
                "ルートの ShapeYourPhoto.exe を主な起動入口にし、tools/launcher/start.bat はソースツリー互換用に残しました。",
                "ルートフォルダーには README.md、ShapeYourPhoto.exe、.gitignore のみを残し、実行依存関係、GUI 起動シム、更新履歴はサブフォルダーへ移動しました。",
                "一括処理の対象は現在の一覧と現在の選択だけになり、削除済み画像が古い状態から戻らなくなりました。",
                "EXIF 編集画面は編集可能項目、読み取り専用のカメラ情報、ソフトウェア予約項目を分けて表示します。",
                "保存に向かない画像の確認画面は複数画像の大きなプレビューになり、ファイル名、重要度、理由が見やすくなりました。",
                "Console の時刻とイベント表示を整理し、一括処理中の応答性を改善しました。",
            ],
        }
    ],
}

CHANGELOG: list[dict[str, object]] = CHANGELOG_I18N["zh_CN"]
