"""GUI 메인 앱 — 단일 화면 (Header / StatusCards / OpControlBox / RecentList / LogBox).

dps-store/docs/print/20260511-equipment-gui-spec.md §9 결합 패턴.
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from watcher.config import Config, save_appearance
from watcher.service import WatcherService

from . import theme
from .cards import StatusCards
from .header import Header
from .log_box import LogBox, attach_logging
from .op_control import OpControlBox
from .recent import ActivityItem, RecentList
from .settings_panel import SettingsPanel
from .stats import SessionStats

logger = logging.getLogger(__name__)

WINDOW_TITLE = "DPS Mug Transfer"
WINDOW_SIZE = (860, 640)
DEVICE_LABEL = "🍶 머그 전사지"


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _count_pdfs(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


class App(ctk.CTk):
    REFRESH_MS = 1500

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.service = WatcherService(cfg)
        self.stats = SessionStats()
        self._log_queue: queue.Queue = queue.Queue()
        self._after_id: Optional[str] = None

        theme.apply(cfg.appearance)

        self.title(WINDOW_TITLE)
        self.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}")
        self.minsize(720, 540)
        self.configure(fg_color=theme.BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.grid_columnconfigure(0, weight=1)
        # row 비중: header(0) / cards(0) / control(0) / recent(1) / log(2)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=2)

        self.header = Header(
            self,
            device_label=DEVICE_LABEL,
            on_settings=self._open_settings,
            on_theme_change=self._on_theme_change,
            appearance=cfg.appearance,
        )
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.set_pairing("unpaired")

        self.cards = StatusCards(self, on_error_click=lambda: _open_folder(cfg.error))
        self.cards.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 4))

        self.control = OpControlBox(
            self,
            on_toggle_agent=self._noop,
            on_toggle_watcher=self._toggle_watcher,
            on_open_folder=lambda: _open_folder(cfg.incoming),
        )
        self.control.grid(row=2, column=0, sticky="ew", padx=12, pady=4)

        self.recent = RecentList(self)
        self.recent.grid(row=3, column=0, sticky="nsew", padx=12, pady=4)

        self.log = LogBox(self)
        self.log.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 12))

        # 로그 큐 핸들러 부착
        attach_logging(self._log_queue)

        # 슬라이드 패널 (마지막에 배치해야 lift 가능)
        self.settings_panel = SettingsPanel(self, cfg)

        # 서비스 콜백
        self.service.on_done = self._on_service_done
        self.service.on_error = self._on_service_error

        # 부팅 시 자동 시작
        self.after(200, self._start_services)
        self._tick()
        self._drain_log()

    # ── 외부 인터랙션 ─────────────────────────────────
    def _open_settings(self) -> None:
        self.settings_panel.open()

    def _on_theme_change(self, label: str) -> None:
        appearance = theme.APPEARANCE_REVERSE.get(label, "system")
        applied = theme.apply(appearance)
        save_appearance(self.cfg, applied)

    def _toggle_watcher(self) -> None:
        if self.service.running:
            self.service.stop()
        else:
            self.service.start()

    def _noop(self) -> None:
        pass

    # ── 서비스 콜백 (백그라운드 스레드) ────────────────
    def _on_service_done(self, name: str) -> None:
        self.stats.on_done()
        self.after(0, lambda: self.recent.push(ActivityItem(ts=time.time(), label=name, status="ok")))
        self.after(0, lambda: self.control.push_activity(f"{name} 합본 완료"))

    def _on_service_error(self, name: str) -> None:
        self.stats.on_error()
        self.after(0, lambda: self.recent.push(ActivityItem(ts=time.time(), label=name, status="error", detail="실패")))
        self.after(0, lambda: self.control.push_activity(f"{name} 처리 실패"))

    # ── 라이프사이클 ──────────────────────────────────
    def _start_services(self) -> None:
        self.service.start()
        # 초기 상태 표시
        self.control.set_watcher(running=self.service.running, detail=f"감시 중 · {self.cfg.incoming}")
        self.control.set_agent(running=False, detail="비활성 (v0.3 예정)", enabled=False)

    def _tick(self) -> None:
        # 카드 갱신
        self.cards.set_counts(
            pending=_count_pdfs(self.cfg.incoming),
            processing=_count_pdfs(self.cfg.processing),
            done=self.stats.done,
            error=self.stats.error,
        )
        # Watcher 상태
        if self.service.running:
            self.control.set_watcher(running=True, detail=f"감시 중 · {self.cfg.incoming.name}/")
        else:
            self.control.set_watcher(running=False, detail="정지됨")
        # 마지막 활동 상대시각 갱신
        self.control.tick()

        self._after_id = self.after(self.REFRESH_MS, self._tick)

    def _drain_log(self) -> None:
        had_new = False
        for _ in range(100):
            try:
                line = self._log_queue.get_nowait()
                self.log.append(line)
                had_new = True
            except queue.Empty:
                break
        self.after(150, self._drain_log)

    def _on_close(self) -> None:
        try:
            if self._after_id:
                self.after_cancel(self._after_id)
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
