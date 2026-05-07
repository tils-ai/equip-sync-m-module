"""설정 탭 — 파이프라인 옵션(편집 가능) + config.ini 경로/내용 미리보기."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import customtkinter as ctk

from watcher.config import Config, save_pipeline_settings

MIRROR_LABELS = {"horizontal": "좌우 반전", "none": "반전 안 함"}
MIRROR_REVERSE = {v: k for k, v in MIRROR_LABELS.items()}

FIT_LABELS = {"original": "원본 사이즈 유지", "contain": "슬롯에 맞춤(축소/확대)", "cover": "슬롯 가득 채움"}
FIT_REVERSE = {v: k for k, v in FIT_LABELS.items()}

OVERSIZE_LABELS = {"error": "에러 폴더로 이동", "single": "1-up 단독 출력"}
OVERSIZE_REVERSE = {v: k for k, v in OVERSIZE_LABELS.items()}


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
        self.grid_rowconfigure(3, weight=1)

        # ── 파이프라인 옵션 (편집 가능) ─────────────────────
        form = ctk.CTkFrame(self, corner_radius=8)
        form.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="파이프라인 설정", anchor="w", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 6)
        )

        ctk.CTkLabel(form, text="좌우 반전", anchor="w").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        self.mirror_menu = ctk.CTkOptionMenu(form, values=list(MIRROR_LABELS.values()), width=200)
        self.mirror_menu.set(MIRROR_LABELS.get(cfg.mirror, "좌우 반전"))
        self.mirror_menu.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=4)

        ctk.CTkLabel(form, text="배치 방식", anchor="w").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        self.fit_menu = ctk.CTkOptionMenu(form, values=list(FIT_LABELS.values()), width=200)
        self.fit_menu.set(FIT_LABELS.get(cfg.fit, "원본 사이즈 유지"))
        self.fit_menu.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=4)

        ctk.CTkLabel(form, text="사이즈 초과 시", anchor="w").grid(row=3, column=0, sticky="w", padx=12, pady=4)
        self.oversize_menu = ctk.CTkOptionMenu(form, values=list(OVERSIZE_LABELS.values()), width=200)
        self.oversize_menu.set(OVERSIZE_LABELS.get(cfg.oversize_action, "에러 폴더로 이동"))
        self.oversize_menu.grid(row=3, column=1, sticky="w", padx=(0, 12), pady=4)

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", padx=12, pady=(8, 12))
        actions.grid_columnconfigure(0, weight=1)

        self.save_msg = ctk.CTkLabel(actions, text="", anchor="w", text_color=("#16a34a", "#22c55e"))
        self.save_msg.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(actions, text="저장", width=90, command=self._save).grid(row=0, column=1)

        # ── config.ini 경로 + 외부 편집기 ───────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text=str(cfg.config_path), anchor="w", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="ew"
        )
        ctk.CTkButton(header, text="에디터로 열기", width=110, command=lambda: _open_in_editor(cfg.config_path)).grid(
            row=0, column=1, padx=(8, 4)
        )
        ctk.CTkButton(header, text="폴더 보기", width=80, command=lambda: _reveal(cfg.config_path)).grid(
            row=0, column=2
        )

        ctk.CTkLabel(
            self,
            text="config.ini를 직접 수정한 경우 앱 재시작이 필요합니다.",
            anchor="w",
            text_color=("#6b7280", "#9ca3af"),
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))

        # ── config.ini 내용 (읽기 전용) ────────────────────
        self.text = ctk.CTkTextbox(self, wrap="none")
        self.text.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._load()

    def _save(self) -> None:
        mirror = MIRROR_REVERSE.get(self.mirror_menu.get(), "horizontal")
        fit = FIT_REVERSE.get(self.fit_menu.get(), "original")
        oversize = OVERSIZE_REVERSE.get(self.oversize_menu.get(), "error")
        save_pipeline_settings(self.cfg, mirror=mirror, fit=fit, oversize_action=oversize)
        self.save_msg.configure(text="저장되었습니다 — 다음 처리부터 적용", text_color=("#16a34a", "#22c55e"))
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
