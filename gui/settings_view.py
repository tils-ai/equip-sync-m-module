"""설정 탭 — config.ini 경로/내용을 읽기 전용으로 보여주고 외부 편집기로 열기."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import customtkinter as ctk

from watcher.config import Config


def _reveal(path: Path) -> None:
    if not path.exists():
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


def _open_in_editor(path: Path) -> None:
    if not path.exists():
        return
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-t", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, cfg: Config) -> None:
        super().__init__(parent, fg_color="transparent")
        self.cfg = cfg

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=str(cfg.config_path),
            anchor="w",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(header, text="에디터로 열기", width=110, command=lambda: _open_in_editor(cfg.config_path)).grid(
            row=0, column=1, padx=(8, 4)
        )
        ctk.CTkButton(header, text="폴더 보기", width=80, command=lambda: _reveal(cfg.config_path)).grid(
            row=0, column=2
        )

        ctk.CTkLabel(
            self,
            text="설정 변경 후 앱 재시작이 필요할 수 있습니다.",
            anchor="w",
            text_color=("#6b7280", "#9ca3af"),
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.text = ctk.CTkTextbox(self, wrap="none")
        self.text.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._load()

    def _load(self) -> None:
        try:
            content = self.cfg.config_path.read_text(encoding="utf-8")
        except OSError as e:
            content = f"(읽을 수 없음: {e})"
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")
