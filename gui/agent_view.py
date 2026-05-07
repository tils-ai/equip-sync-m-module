"""에이전트 탭 — v0.2.0은 스켈레톤. dps-store API 연동은 v0.3에서 활성화."""

from __future__ import annotations

import customtkinter as ctk

from agent.state import AgentState, clear_state, load_state, save_state


class AgentTab(ctk.CTkFrame):
    def __init__(self, parent) -> None:
        super().__init__(parent, fg_color="transparent")

        self.state: AgentState = load_state()

        self.grid_columnconfigure(1, weight=1)

        # 헤더
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="에이전트 (dps-store API 연동)",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            header,
            text="비활성",
            text_color=("#9ca3af", "#6b7280"),
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            self,
            text=(
                "v0.2.0은 페어링 정보만 저장합니다.\n"
                "실제 풀링/다운로드/완료 보고는 v0.3에서 dps-store 측 엔드포인트와 함께 활성화됩니다."
            ),
            justify="left",
            anchor="w",
            text_color=("#6b7280", "#9ca3af"),
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))

        # 입력 필드 ──────────────────────────────────────────
        ctk.CTkLabel(self, text="Base URL").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        self.entry_base = ctk.CTkEntry(self)
        self.entry_base.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=4)
        self.entry_base.insert(0, self.state.base_url)

        ctk.CTkLabel(self, text="스토어 ID").grid(row=3, column=0, sticky="w", padx=12, pady=4)
        self.entry_tenant = ctk.CTkEntry(self)
        self.entry_tenant.grid(row=3, column=1, sticky="ew", padx=(0, 12), pady=4)
        self.entry_tenant.insert(0, self.state.tenant_name)

        ctk.CTkLabel(self, text="API Key").grid(row=4, column=0, sticky="w", padx=12, pady=4)
        self.entry_key = ctk.CTkEntry(self, show="•")
        self.entry_key.grid(row=4, column=1, sticky="ew", padx=(0, 12), pady=4)
        self.entry_key.insert(0, self.state.api_key)

        # 액션 버튼 ─────────────────────────────────────────
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(actions, text="저장", width=88, command=self._save).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="페어링 정보 삭제",
            fg_color=("#ef4444", "#7f1d1d"),
            hover_color=("#dc2626", "#991b1b"),
            width=140,
            command=self._clear,
        ).grid(row=0, column=2)

        self.msg = ctk.CTkLabel(self, text="", text_color=("#16a34a", "#22c55e"), anchor="w")
        self.msg.grid(row=6, column=0, columnspan=2, sticky="ew", padx=12)

    def _save(self) -> None:
        self.state.base_url = self.entry_base.get().strip() or "https://store.dpl.shop"
        self.state.tenant_name = self.entry_tenant.get().strip()
        self.state.api_key = self.entry_key.get().strip()
        self.state.paired = bool(self.state.api_key and self.state.tenant_name)
        save_state(self.state)
        self.msg.configure(text="저장되었습니다.", text_color=("#16a34a", "#22c55e"))

    def _clear(self) -> None:
        clear_state()
        self.state = type(self.state)()
        self.entry_base.delete(0, "end")
        self.entry_base.insert(0, self.state.base_url)
        self.entry_tenant.delete(0, "end")
        self.entry_key.delete(0, "end")
        self.msg.configure(text="페어링 정보가 삭제되었습니다.", text_color=("#ef4444", "#f87171"))
