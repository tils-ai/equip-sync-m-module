"""에이전트 페어링 상태 (api_key, base_url, tenantName) 영속화 — agent.json."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

APP_NAME = "equip-sync-m-module"


def _base_dir() -> Path:
    """exe 파일 폴더 (spec §11.5)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # dev: agent/state.py → 프로젝트 루트
    return Path(__file__).resolve().parent.parent


def _state_path() -> Path:
    return _base_dir() / "agent.json"


@dataclass
class AgentState:
    base_url: str = "https://store.dpl.shop"
    tenant_name: str = ""
    api_key: str = ""
    paired: bool = False


def load_state() -> AgentState:
    path = _state_path()
    if not path.exists():
        return AgentState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AgentState(**{k: v for k, v in data.items() if k in AgentState.__dataclass_fields__})
    except (json.JSONDecodeError, OSError):
        return AgentState()


def save_state(state: AgentState) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, ensure_ascii=False), encoding="utf-8")


def clear_state() -> None:
    path = _state_path()
    if path.exists():
        path.unlink()
