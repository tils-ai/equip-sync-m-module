"""대시보드 탭 — Watcher 상태, 큐 카운트, 최근 결과, 폴더 열기."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from watcher.config import Config
from watcher.service import WatcherService


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


def _recent_files(folder: Path, n: int = 5) -> list[Path]:
    if not folder.exists():
        return []
    pdfs = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    pdfs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[:n]


class DashboardTab(ctk.CTkFrame):
    REFRESH_MS = 1500

    def __init__(self, parent, cfg: Config, service: WatcherService) -> None:
        super().__init__(parent, fg_color="transparent")
        self.cfg = cfg
        self.service = service
        self._after_id: Optional[str] = None

        self.grid_columnconfigure(0, weight=1)

        # ── Watcher 상태 + 토글 ────────────────────────────
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        status_row.grid_columnconfigure(1, weight=1)

        self.status_dot = ctk.CTkLabel(status_row, text="●", font=ctk.CTkFont(size=18))
        self.status_dot.grid(row=0, column=0, padx=(0, 8))

        self.status_label = ctk.CTkLabel(status_row, text="Watcher: -", anchor="w")
        self.status_label.grid(row=0, column=1, sticky="ew")

        self.toggle_btn = ctk.CTkButton(status_row, text="Start", width=88, command=self._toggle_service)
        self.toggle_btn.grid(row=0, column=2, padx=(8, 0))

        # ── 카운트 카드 ─────────────────────────────────────
        counts_row = ctk.CTkFrame(self, fg_color="transparent")
        counts_row.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        for i in range(4):
            counts_row.grid_columnconfigure(i, weight=1)

        self.cards: dict[str, ctk.CTkLabel] = {}
        for i, (key, label) in enumerate(
            [("pending", "대기"), ("processing", "처리중"), ("done", "완료"), ("error", "오류")]
        ):
            card = ctk.CTkFrame(counts_row, corner_radius=8)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11)).pack(pady=(8, 0))
            value = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=22, weight="bold"))
            value.pack(pady=(0, 8))
            self.cards[key] = value

        # ── 폴더 열기 ───────────────────────────────────────
        folder_row = ctk.CTkFrame(self, fg_color="transparent")
        folder_row.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        for i in range(4):
            folder_row.grid_columnconfigure(i, weight=1)

        for i, (label, path) in enumerate(
            [("incoming", cfg.incoming), ("done", cfg.done), ("error", cfg.error), ("originals", cfg.originals)]
        ):
            ctk.CTkButton(
                folder_row,
                text=f"📂 {label}",
                command=self._open_callback(path),
                height=32,
            ).grid(row=0, column=i, padx=4, sticky="ew")

        # ── 최근 결과 ────────────────────────────────────────
        recent_label = ctk.CTkLabel(self, text="최근 완료 (5건)", anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
        recent_label.grid(row=3, column=0, sticky="w", padx=12, pady=(12, 4))

        self.recent_box = ctk.CTkTextbox(self, height=140, activate_scrollbars=True, wrap="none")
        self.recent_box.configure(state="disabled")
        self.recent_box.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.grid_rowconfigure(4, weight=1)

        self._refresh()

    def stop(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _toggle_service(self) -> None:
        if self.service.running:
            self.service.stop()
        else:
            self.service.start()
        self._refresh_status()

    def _open_callback(self, path: Path) -> Callable[[], None]:
        return lambda: _open_folder(path)

    def _refresh_status(self) -> None:
        running = self.service.running
        self.status_dot.configure(text_color=("#16a34a" if running else "#9ca3af"))
        self.status_label.configure(text=f"Watcher: {'Running' if running else 'Stopped'}")
        self.toggle_btn.configure(text="Stop" if running else "Start")

    def _refresh_counts(self) -> None:
        cfg = self.cfg
        self.cards["pending"].configure(text=str(_count_pdfs(cfg.incoming)))
        self.cards["processing"].configure(text=str(_count_pdfs(cfg.processing)))
        self.cards["done"].configure(text=str(_count_pdfs(cfg.done)))
        self.cards["error"].configure(text=str(_count_pdfs(cfg.error)))

    def _refresh_recent(self) -> None:
        files = _recent_files(self.cfg.done, n=5)
        text = "\n".join(p.name for p in files) if files else "(없음)"
        self.recent_box.configure(state="normal")
        self.recent_box.delete("1.0", "end")
        self.recent_box.insert("1.0", text)
        self.recent_box.configure(state="disabled")

    def _refresh(self) -> None:
        self._refresh_status()
        self._refresh_counts()
        self._refresh_recent()
        self._after_id = self.after(self.REFRESH_MS, self._refresh)
