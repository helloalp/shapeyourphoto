from __future__ import annotations

from app_metadata import APP_NAME, APP_VERSION
from desktop_integration import configure_window_icon
from dnd_support import create_root
from ui.hidpi import configure_fonts, configure_tk_scaling, enable_dpi_awareness
from ui.splash import SplashScreen
from ui_app import PhotoAnalyzerApp
from window_layout import center_window


def main() -> None:
    enable_dpi_awareness()
    root = create_root()
    configure_tk_scaling(root)
    configure_fonts(root)
    root.withdraw()
    splash = SplashScreen(root)
    root.title(f"{APP_NAME} v{APP_VERSION}")
    configure_window_icon(root)
    try:
        PhotoAnalyzerApp(root)
        center_window(root, 1700, 1020)
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
