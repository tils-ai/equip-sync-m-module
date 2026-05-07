"""GUI 메인 앱 — 헤더(테마 토글) + 3 탭(Dashboard / Settings / Agent)."""

from __future__ import annotations

import customtkinter as ctk

from watcher.config import Config, save_appearance
from watcher.service import WatcherService

from . import theme
from .agent_view import AgentTab
from .dashboard import DashboardTab
from .settings_view import SettingsTab

WINDOW_TITLE = "DPS Mug Transfer Watcher"
WINDOW_SIZE = (720, 540)
APPEARANCE_LABELS = {"system": "시스템", "light": "라이트", "dark": "다크"}
APPEARANCE_REVERSE = {v: k for k, v in APPEARANCE_LABELS.items()}


class App(ctk.CTk):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.service = WatcherService(cfg)
        # 부팅 시 자동 시작 (운영 편의 — Stop 버튼으로 즉시 중단 가능)
        self.service.start()

        theme.apply(cfg.appearance)

        self.title(WINDOW_TITLE)
        self.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}")
        self.minsize(620, 460)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_tabs()

    # ── Header ─────────────────────────────────────────
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="DPS Mug Transfer Watcher",
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(header, text="테마", font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=(8, 4))

        self.theme_menu = ctk.CTkOptionMenu(
            header,
            values=list(APPEARANCE_LABELS.values()),
            width=110,
            command=self._on_theme_change,
        )
        self.theme_menu.set(APPEARANCE_LABELS.get(self.cfg.appearance, "시스템"))
        self.theme_menu.grid(row=0, column=2)

    def _on_theme_change(self, label: str) -> None:
        appearance = APPEARANCE_REVERSE.get(label, "system")
        applied = theme.apply(appearance)
        save_appearance(self.cfg, applied)

    # ── Tabs ────────────────────────────────────────────
    def _build_tabs(self) -> None:
        tabs = ctk.CTkTabview(self)
        tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

        tabs.add("Dashboard")
        tabs.add("Settings")
        tabs.add("Agent")

        self.dashboard = DashboardTab(tabs.tab("Dashboard"), self.cfg, self.service)
        self.dashboard.pack(fill="both", expand=True)

        self.settings = SettingsTab(tabs.tab("Settings"), self.cfg)
        self.settings.pack(fill="both", expand=True)

        self.agent = AgentTab(tabs.tab("Agent"))
        self.agent.pack(fill="both", expand=True)

    # ── Lifecycle ───────────────────────────────────────
    def _on_close(self) -> None:
        try:
            self.dashboard.stop()
        except Exception:
            pass
        try:
            self.service.stop()
        except Exception:
            pass
        self.destroy()


def launch_app(cfg: Config) -> int:
    app = App(cfg)
    app.mainloop()
    return 0
