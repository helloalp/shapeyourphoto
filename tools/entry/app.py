from __future__ import annotations

import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
APP_PACKAGE_DIR = APP_ROOT / "src"
if str(APP_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(APP_PACKAGE_DIR))

from app_metadata import APP_VERSION
from app_context import create_app_context
from desktop_integration import configure_window_icon
from dnd_support import create_root
from ui.hidpi import configure_fonts, configure_tk_scaling, enable_dpi_awareness
from ui.splash import SplashScreen
from ui_app import PhotoAnalyzerApp


def main() -> None:
    enable_dpi_awareness()
    root = create_root()
    configure_tk_scaling(root)
    configure_fonts(root)
    root.withdraw()
    splash = SplashScreen(root)
    root.title(f"Shape Your Photo | v{APP_VERSION} | by Helloalp")
    configure_window_icon(root)
    app_context = create_app_context()
    try:
        PhotoAnalyzerApp(root, app_context=app_context)
    except Exception:
        splash.close_now()
        raise

    def _show_main() -> None:
        splash.close_now()
        root.deiconify()
        root.lift()

    root.after(max(650, splash.min_ms), _show_main)
    root.mainloop()


if __name__ == "__main__":
    main()
