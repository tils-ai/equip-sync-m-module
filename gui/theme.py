"""CustomTkinter 테마 매니저 — system / light / dark 즉시 전환."""

from __future__ import annotations

import customtkinter as ctk

VALID = ("system", "light", "dark")


def _normalize(value: str) -> str:
    v = (value or "system").strip().lower()
    return v if v in VALID else "system"


def apply(appearance: str) -> str:
    """ctk에 즉시 반영. 정규화된 값을 반환."""
    norm = _normalize(appearance)
    ctk.set_appearance_mode(norm.capitalize())  # "System" / "Light" / "Dark"
    return norm
