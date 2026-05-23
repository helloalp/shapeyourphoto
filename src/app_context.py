from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from app_console import AppConsole
from app_settings import AppSettings, load_app_settings
from preview_cache import ThumbnailCache
from stats_store import load_stats
from task_state import TaskManager
from ui import language as language_service
from ui.themes import get_theme


T = TypeVar("T")


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> Any:
        self._services[name] = service
        return service

    def get(self, name: str, default: T | None = None) -> Any | T | None:
        return self._services.get(name, default)

    def require(self, name: str) -> Any:
        if name not in self._services:
            raise KeyError(f"service not registered: {name}")
        return self._services[name]

    def as_dict(self) -> dict[str, Any]:
        return dict(self._services)


@dataclass
class PlatformServices:
    configure_window_icon: Callable[..., Any] | None = None
    open_url: Callable[[str], Any] | None = None


@dataclass
class UpdateClientService:
    check_for_updates: Callable[..., Any] | None = None
    run_updater: Callable[..., Any] | None = None


@dataclass
class AppContext:
    settings: AppSettings
    logger: AppConsole
    i18n: Any
    theme: Any
    preview_cache: ThumbnailCache
    task_manager: TaskManager
    stats_store: Any
    update_client: UpdateClientService
    platform_services: PlatformServices
    registry: ServiceRegistry = field(default_factory=ServiceRegistry)

    def __post_init__(self) -> None:
        self.registry.register("settings", self.settings)
        self.registry.register("logger", self.logger)
        self.registry.register("i18n", self.i18n)
        self.registry.register("theme", self.theme)
        self.registry.register("preview_cache", self.preview_cache)
        self.registry.register("task_manager", self.task_manager)
        self.registry.register("stats_store", self.stats_store)
        self.registry.register("update_client", self.update_client)
        self.registry.register("platform_services", self.platform_services)


def create_app_context(
    *,
    settings: AppSettings | None = None,
    settings_warnings: list[str] | None = None,
    logger: AppConsole | None = None,
    preview_cache: ThumbnailCache | None = None,
    task_manager: TaskManager | None = None,
    stats: Any | None = None,
    update_client: UpdateClientService | None = None,
    platform_services: PlatformServices | None = None,
) -> AppContext:
    if settings is None:
        settings = load_app_settings(
            report_warning=settings_warnings.append if settings_warnings is not None else None,
            create_if_missing=True,
        )
    theme = get_theme(getattr(settings, "theme_id", "classic_green"))
    return AppContext(
        settings=settings,
        logger=logger or AppConsole(),
        i18n=language_service,
        theme=theme,
        preview_cache=preview_cache or ThumbnailCache(),
        task_manager=task_manager or TaskManager(),
        stats_store=stats if stats is not None else load_stats(),
        update_client=update_client or UpdateClientService(),
        platform_services=platform_services or PlatformServices(),
    )
