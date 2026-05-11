"""config.ini 로드/생성. exe 파일이 있는 폴더 기준 (spec §11.5)."""

from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "equip-sync-m-module"


def _base_dir() -> Path:
    """frozen exe면 exe 폴더, 스크립트면 main.py가 있는 프로젝트 루트."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # dev: main.py가 watcher/의 상위(프로젝트 루트)에 있음
    return Path(__file__).resolve().parent.parent


def _config_path() -> Path:
    return _base_dir() / "config.ini"


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
fit = original            ; original | contain | cover (original = 원본 사이즈 유지)
keep_originals = true     ; true → done/originals/로 보관, false → 삭제
oversize_action = error   ; error | single (사이즈 초과 시: error → error/로, single → 1-up 단독 출력)

[printer]
name =                    ; Windows 프린터명 (설정 > 프린터에서 정확한 이름 확인)
enabled = false           ; true → 합본 PDF 자동 출력, false → 합본만 저장
render_dpi = 300          ; PDF → 이미지 변환 해상도

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
    oversize_action: str
    printer_name: str
    printer_enabled: bool
    render_dpi: int
    appearance: str
    log_level: str
    log_file: Path
    config_path: Path


def load_config() -> Config:
    base = _base_dir()
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
        oversize_action=parser.get("pipeline", "oversize_action", fallback="error").strip().lower(),
        printer_name=parser.get("printer", "name", fallback="").strip(),
        printer_enabled=_bool("printer", "enabled", default=False),
        render_dpi=parser.getint("printer", "render_dpi", fallback=300),
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
    _write_setting(cfg.config_path, "gui", "appearance", appearance)
    cfg.appearance = appearance


def save_pipeline_settings(cfg: Config, *, mirror: str, fit: str, oversize_action: str) -> None:
    """파이프라인 옵션(mirror/fit/oversize_action)을 config.ini에 영속화."""
    mirror = mirror.strip().lower()
    if mirror not in {"horizontal", "none"}:
        mirror = "horizontal"

    fit = fit.strip().lower()
    if fit not in {"original", "contain", "cover"}:
        fit = "original"

    oversize_action = oversize_action.strip().lower()
    if oversize_action not in {"error", "single"}:
        oversize_action = "error"

    _write_setting(cfg.config_path, "pipeline", "mirror", mirror)
    _write_setting(cfg.config_path, "pipeline", "fit", fit)
    _write_setting(cfg.config_path, "pipeline", "oversize_action", oversize_action)
    cfg.mirror = mirror
    cfg.fit = fit
    cfg.oversize_action = oversize_action


def save_printer_settings(cfg: Config, *, name: str, enabled: bool) -> None:
    """프린터 이름/활성화 토글을 config.ini에 영속화."""
    name = (name or "").strip()
    _write_setting(cfg.config_path, "printer", "name", name)
    _write_setting(cfg.config_path, "printer", "enabled", "true" if enabled else "false")
    cfg.printer_name = name
    cfg.printer_enabled = bool(enabled)


def _write_setting(config_path: Path, section: str, key: str, value: str) -> None:
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    with config_path.open("w", encoding="utf-8") as f:
        parser.write(f)
