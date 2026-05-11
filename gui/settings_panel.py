"""SettingsSlidePanel — 우측 슬라이드 패널, 섹션 단위 스크롤 (spec §8).

m-module 섹션:
- 페어링 (스토어 ID / Base URL / API Key)
- 폴더 (incoming/done/error/processing/originals)
- 파이프라인 (mirror / fit / oversize_action)
- 정보 (config.ini 경로 + 외부 편집기)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import customtkinter as ctk

from agent.state import AgentState, clear_state, load_state, save_state
from watcher.config import Config, save_pipeline_settings
from watcher.fonts import family as _font_family

from . import theme

MIRROR_LABELS = {"horizontal": "좌우 반전", "none": "반전 안 함"}
MIRROR_REVERSE = {v: k for k, v in MIRROR_LABELS.items()}

FIT_LABELS = {"original": "원본 사이즈 유지", "contain": "슬롯에 맞춤", "cover": "슬롯 가득 채움"}
FIT_REVERSE = {v: k for k, v in FIT_LABELS.items()}

OVERSIZE_LABELS = {"error": "에러 폴더로", "single": "1-up 단독 출력"}
OVERSIZE_REVERSE = {v: k for k, v in OVERSIZE_LABELS.items()}


def _open_in_editor(path: Path) -> None:
    if not path.exists():
        return
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-t", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class SettingsPanel(ctk.CTkFrame):
    WIDTH = 380
    ANIM_MS = 220
    ANIM_STEPS = 12

    def __init__(self, root: ctk.CTk, cfg: Config) -> None:
        super().__init__(root, width=self.WIDTH, corner_radius=0, fg_color=theme.SURFACE)
        self.cfg = cfg
        # NOTE: `_root`는 tkinter 내부 메서드와 충돌하므로 별도 속성으로 보관하지 않음.
        # 필요 시 self.master 또는 self.winfo_toplevel() 사용.
        self._open = False
        self._agent_state: AgentState = load_state()

        # 시작 위치: 화면 밖 우측
        self.place(relx=1.0, rely=0, anchor="ne", relheight=1.0, x=self.WIDTH)

        self._build()

    # ── 외부 API ───────────────────────────────────────
    def open(self) -> None:
        if self._open:
            return
        self._open = True
        self.lift()
        self._slide(target_x=0)

    def close(self) -> None:
        if not self._open:
            return
        self._open = False
        self._slide(target_x=self.WIDTH)

    def toggle(self) -> None:
        if self._open:
            self.close()
        else:
            self.open()

    # ── 슬라이드 애니메이션 ───────────────────────────
    def _slide(self, *, target_x: int) -> None:
        info = self.place_info()
        current_x = int(float(info.get("x", 0)))
        delta = (target_x - current_x) / self.ANIM_STEPS
        step_delay = max(1, self.ANIM_MS // self.ANIM_STEPS)

        def step(i: int) -> None:
            new_x = int(current_x + delta * i)
            self.place_configure(x=new_x)
            if i < self.ANIM_STEPS:
                self.after(step_delay, lambda: step(i + 1))
            else:
                self.place_configure(x=target_x)

        step(1)

    # ── UI ────────────────────────────────────────────
    def _build(self) -> None:
        # 헤더 + 닫기
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(
            header,
            text="설정",
            font=ctk.CTkFont(family=_font_family(), size=14, weight="bold"),
            text_color=theme.TEXT,
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="⨯",
            width=32,
            font=ctk.CTkFont(family=_font_family(), size=14),
            command=self.close,
        ).pack(side="right")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._section(body, "페어링", self._build_pairing)
        self._section(body, "폴더", self._build_folders)
        self._section(body, "파이프라인", self._build_pipeline)
        self._section(body, "정보", self._build_info)

    def _section(self, parent, title: str, builder) -> None:
        wrap = ctk.CTkFrame(parent, corner_radius=theme.CORNER, fg_color=theme.SURFACE_2)
        wrap.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            wrap,
            text=title,
            font=ctk.CTkFont(family=_font_family(), size=12, weight="bold"),
            text_color=theme.TEXT,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        inner = ctk.CTkFrame(wrap, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=(0, 10))
        builder(inner)

    # ── 페어링 ────────────────────────────────────────
    def _build_pairing(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="v0.3에서 dps-store API 연동 활성화 — 현재는 정보만 저장",
            font=ctk.CTkFont(family=_font_family(), size=10),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            wraplength=320,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(parent, text="Base URL", font=ctk.CTkFont(family=_font_family(), size=11)).grid(
            row=1, column=0, sticky="w", pady=2
        )
        self._entry_base = ctk.CTkEntry(parent, width=200)
        self._entry_base.grid(row=1, column=1, sticky="ew", pady=2)
        self._entry_base.insert(0, self._agent_state.base_url)

        ctk.CTkLabel(parent, text="스토어 ID", font=ctk.CTkFont(family=_font_family(), size=11)).grid(
            row=2, column=0, sticky="w", pady=2
        )
        self._entry_tenant = ctk.CTkEntry(parent, width=200)
        self._entry_tenant.grid(row=2, column=1, sticky="ew", pady=2)
        self._entry_tenant.insert(0, self._agent_state.tenant_name)

        ctk.CTkLabel(parent, text="API Key", font=ctk.CTkFont(family=_font_family(), size=11)).grid(
            row=3, column=0, sticky="w", pady=2
        )
        self._entry_key = ctk.CTkEntry(parent, width=200, show="•")
        self._entry_key.grid(row=3, column=1, sticky="ew", pady=2)
        self._entry_key.insert(0, self._agent_state.api_key)

        parent.grid_columnconfigure(1, weight=1)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ctk.CTkButton(
            actions, text="저장", width=70, font=ctk.CTkFont(family=_font_family(), size=11), command=self._save_pairing
        ).pack(side="right")
        ctk.CTkButton(
            actions,
            text="삭제",
            width=70,
            fg_color=theme.DANGER,
            hover_color="#C0392B",
            font=ctk.CTkFont(family=_font_family(), size=11),
            command=self._clear_pairing,
        ).pack(side="right", padx=(0, 6))

        self._pairing_msg = ctk.CTkLabel(
            parent, text="", anchor="w", font=ctk.CTkFont(family=_font_family(), size=10), text_color=theme.SUCCESS
        )
        self._pairing_msg.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def _save_pairing(self) -> None:
        self._agent_state.base_url = self._entry_base.get().strip() or "https://store.dpl.shop"
        self._agent_state.tenant_name = self._entry_tenant.get().strip()
        self._agent_state.api_key = self._entry_key.get().strip()
        self._agent_state.paired = bool(self._agent_state.api_key and self._agent_state.tenant_name)
        save_state(self._agent_state)
        self._pairing_msg.configure(text="저장됨", text_color=theme.SUCCESS)

    def _clear_pairing(self) -> None:
        clear_state()
        self._agent_state = AgentState()
        self._entry_base.delete(0, "end")
        self._entry_base.insert(0, self._agent_state.base_url)
        self._entry_tenant.delete(0, "end")
        self._entry_key.delete(0, "end")
        self._pairing_msg.configure(text="삭제됨", text_color=theme.DANGER)

    # ── 폴더 ──────────────────────────────────────────
    def _build_folders(self, parent) -> None:
        rows = [
            ("incoming", self.cfg.incoming),
            ("processing", self.cfg.processing),
            ("done", self.cfg.done),
            ("error", self.cfg.error),
            ("originals", self.cfg.originals),
        ]
        for i, (label, path) in enumerate(rows):
            ctk.CTkLabel(
                parent,
                text=label,
                font=ctk.CTkFont(family=_font_family(), size=11),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=i, column=0, sticky="w", pady=1)
            ctk.CTkLabel(
                parent,
                text=str(path),
                font=ctk.CTkFont(family=_font_family(), size=10),
                anchor="w",
                wraplength=240,
                justify="left",
            ).grid(row=i, column=1, sticky="ew", pady=1)
        parent.grid_columnconfigure(1, weight=1)

    # ── 파이프라인 ────────────────────────────────────
    def _build_pipeline(self, parent) -> None:
        ctk.CTkLabel(parent, text="좌우 반전", font=ctk.CTkFont(family=_font_family(), size=11)).grid(
            row=0, column=0, sticky="w", pady=2
        )
        self._mirror_menu = ctk.CTkOptionMenu(parent, values=list(MIRROR_LABELS.values()), width=160)
        self._mirror_menu.set(MIRROR_LABELS.get(self.cfg.mirror, "좌우 반전"))
        self._mirror_menu.grid(row=0, column=1, sticky="w", pady=2)

        ctk.CTkLabel(parent, text="배치 방식", font=ctk.CTkFont(family=_font_family(), size=11)).grid(
            row=1, column=0, sticky="w", pady=2
        )
        self._fit_menu = ctk.CTkOptionMenu(parent, values=list(FIT_LABELS.values()), width=160)
        self._fit_menu.set(FIT_LABELS.get(self.cfg.fit, "원본 사이즈 유지"))
        self._fit_menu.grid(row=1, column=1, sticky="w", pady=2)

        ctk.CTkLabel(parent, text="사이즈 초과 시", font=ctk.CTkFont(family=_font_family(), size=11)).grid(
            row=2, column=0, sticky="w", pady=2
        )
        self._oversize_menu = ctk.CTkOptionMenu(parent, values=list(OVERSIZE_LABELS.values()), width=160)
        self._oversize_menu.set(OVERSIZE_LABELS.get(self.cfg.oversize_action, "에러 폴더로"))
        self._oversize_menu.grid(row=2, column=1, sticky="w", pady=2)

        parent.grid_columnconfigure(1, weight=1)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ctk.CTkButton(
            actions,
            text="저장",
            width=70,
            font=ctk.CTkFont(family=_font_family(), size=11),
            command=self._save_pipeline,
        ).pack(side="right")

        self._pipeline_msg = ctk.CTkLabel(
            parent, text="", anchor="w", font=ctk.CTkFont(family=_font_family(), size=10), text_color=theme.SUCCESS
        )
        self._pipeline_msg.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def _save_pipeline(self) -> None:
        mirror = MIRROR_REVERSE.get(self._mirror_menu.get(), "horizontal")
        fit = FIT_REVERSE.get(self._fit_menu.get(), "original")
        oversize = OVERSIZE_REVERSE.get(self._oversize_menu.get(), "error")
        save_pipeline_settings(self.cfg, mirror=mirror, fit=fit, oversize_action=oversize)
        self._pipeline_msg.configure(text="저장됨 — 다음 처리부터 적용", text_color=theme.SUCCESS)

    # ── 정보 ──────────────────────────────────────────
    def _build_info(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text=str(self.cfg.config_path),
            font=ctk.CTkFont(family=_font_family(), size=10),
            anchor="w",
            wraplength=320,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            parent,
            text="config.ini 편집",
            width=120,
            font=ctk.CTkFont(family=_font_family(), size=11),
            command=lambda: _open_in_editor(self.cfg.config_path),
        ).grid(row=1, column=0, sticky="w", pady=2)
