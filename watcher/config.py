"""config.ini 로드/생성. Windows %LOCALAPPDATA%\\equip-sync-m-module 기본 사용."""

from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "equip-sync-m-module"


def _appdata_root() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local:
            return Path(local) / APP_NAME
    return Path.home() / f".{APP_NAME}"


def _config_path() -> Path:
    return _appdata_root() / "config.ini"


_DEFAULT_TEMPLATE = """\
; equip-sync-m-module 설정

[paths]
incoming = {base}/incoming
processing = {base}/processing
done = {base}/done
error = {base}/error
originals = {base}/done/originals

[layout]
mode = a4-landscape-2up

[pipeline]
mirror = horizontal       ; horizontal | none
fit = contain             ; contain | cover
keep_originals = true     ; true → done/originals/로 보관, false → 삭제

[printer]
name =                    ; v2 자동 인쇄 시 사용

[gui]
appearance = system       ; system | light | dark

[log]
level = INFO              ; DEBUG | INFO | WARNING | ERROR
file = {base}/logs/watcher.log
"""


@dataclass
class Config:
    incoming: Path
    processing: Path
    done: Path
    error: Path
    originals: Path
    layout_mode: str
    mirror: str
    fit: str
    keep_originals: bool
    printer_name: str
    appearance: str
    log_level: str
    log_file: Path
    config_path: Path


def load_config() -> Config:
    base = _appdata_root()
    config_file = _config_path()

    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(_DEFAULT_TEMPLATE.format(base=base.as_posix()), encoding="utf-8")

    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    parser.read(config_file, encoding="utf-8")

    def _path(section: str, option: str) -> Path:
        return Path(os.path.expandvars(parser.get(section, option))).expanduser()

    def _bool(section: str, option: str, default: bool = True) -> bool:
        raw = parser.get(section, option, fallback=str(default)).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    return Config(
        incoming=_path("paths", "incoming"),
        processing=_path("paths", "processing"),
        done=_path("paths", "done"),
        error=_path("paths", "error"),
        originals=_path("paths", "originals"),
        layout_mode=parser.get("layout", "mode", fallback="a4-landscape-2up"),
        mirror=parser.get("pipeline", "mirror", fallback="horizontal"),
        fit=parser.get("pipeline", "fit", fallback="contain"),
        keep_originals=_bool("pipeline", "keep_originals", default=True),
        printer_name=parser.get("printer", "name", fallback=""),
        appearance=parser.get("gui", "appearance", fallback="system").strip().lower(),
        log_level=parser.get("log", "level", fallback="INFO"),
        log_file=_path("log", "file"),
        config_path=config_file,
    )


def ensure_dirs(cfg: Config) -> None:
    for p in (cfg.incoming, cfg.processing, cfg.done, cfg.error, cfg.originals, cfg.log_file.parent):
        p.mkdir(parents=True, exist_ok=True)


def save_appearance(cfg: Config, appearance: str) -> None:
    """GUI 테마 선택을 config.ini에 영속화."""
    appearance = appearance.strip().lower()
    if appearance not in {"system", "light", "dark"}:
        appearance = "system"

    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    parser.read(cfg.config_path, encoding="utf-8")
    if not parser.has_section("gui"):
        parser.add_section("gui")
    parser.set("gui", "appearance", appearance)
    with cfg.config_path.open("w", encoding="utf-8") as f:
        parser.write(f)
    cfg.appearance = appearance
