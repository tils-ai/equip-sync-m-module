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
paper = A4                ; A4 | A3 (메타 표기에 사용, 캔버스 사이즈는 mode 고정)

[overlay]
enabled = true            ; 메타·그리드·절단선 합성 (false → base만)
cut_margin_mm = 3         ; 절단선 외곽 마진 (mm)
meta_corner_mm = 5        ; 메타 텍스트 모서리 여백 (mm)
meta_font_size = 6.5      ; pt
meta_color = #FF00FF
grid_color = #FF00FF
cut_color = #FF00FF

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
    paper: str  # A4 | A3 — 메타 토큰에만 사용
    mirror: str
    fit: str
    keep_originals: bool
    oversize_action: str
    printer_name: str
    printer_enabled: bool
    render_dpi: int
    overlay_enabled: bool
    cut_margin_mm: float
    meta_corner_mm: float
    meta_font_size: float
    meta_color: str
    grid_color: str
    cut_color: str
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

    def _float(section: str, option: str, default: float) -> float:
        try:
            return parser.getfloat(section, option, fallback=default)
        except ValueError:
            return default

    return Config(
        incoming=_path("paths", "incoming"),
        processing=_path("paths", "processing"),
        done=_path("paths", "done"),
        error=_path("paths", "error"),
        originals=_path("paths", "originals"),
        layout_mode=parser.get("layout", "mode", fallback="a4-landscape-2up"),
        paper=parser.get("layout", "paper", fallback="A4").strip().upper(),
        mirror=parser.get("pipeline", "mirror", fallback="horizontal"),
        fit=parser.get("pipeline", "fit", fallback="contain"),
        keep_originals=_bool("pipeline", "keep_originals", default=True),
        oversize_action=parser.get("pipeline", "oversize_action", fallback="error").strip().lower(),
        printer_name=parser.get("printer", "name", fallback="").strip(),
        printer_enabled=_bool("printer", "enabled", default=False),
        render_dpi=parser.getint("printer", "render_dpi", fallback=300),
        overlay_enabled=_bool("overlay", "enabled", default=True),
        cut_margin_mm=_float("overlay", "cut_margin_mm", 3.0),
        meta_corner_mm=_float("overlay", "meta_corner_mm", 5.0),
        meta_font_size=_float("overlay", "meta_font_size", 6.5),
        meta_color=parser.get("overlay", "meta_color", fallback="#FF00FF").strip(),
        grid_color=parser.get("overlay", "grid_color", fallback="#FF00FF").strip(),
        cut_color=parser.get("overlay", "cut_color", fallback="#FF00FF").strip(),
        appearance=parser.get("gui", "appearance", fallback="system").strip().lower(),
        log_level=parser.get("log", "level", fallback="INFO"),
        log_file=_path("log", "file"),
        config_path=config_file,
    )


def ensure_dirs(config: Config) -> None:
    for p in (config.incoming, config.processing, config.done, config.error, config.originals, config.log_file.parent):
        p.mkdir(parents=True, exist_ok=True)


def save_appearance(config: Config, appearance: str) -> None:
    """GUI 테마 선택을 config.ini에 영속화."""
    appearance = appearance.strip().lower()
    if appearance not in {"system", "light", "dark"}:
        appearance = "system"
    _write_setting(config.config_path, "gui", "appearance", appearance)
    config.appearance = appearance


def save_pipeline_settings(config: Config, *, mirror: str, fit: str, oversize_action: str) -> None:
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

    _write_setting(config.config_path, "pipeline", "mirror", mirror)
    _write_setting(config.config_path, "pipeline", "fit", fit)
    _write_setting(config.config_path, "pipeline", "oversize_action", oversize_action)
    config.mirror = mirror
    config.fit = fit
    config.oversize_action = oversize_action


def save_printer_settings(config: Config, *, name: str, enabled: bool) -> None:
    """프린터 이름/활성화 토글을 config.ini에 영속화."""
    name = (name or "").strip()
    _write_setting(config.config_path, "printer", "name", name)
    _write_setting(config.config_path, "printer", "enabled", "true" if enabled else "false")
    config.printer_name = name
    config.printer_enabled = bool(enabled)


def save_overlay_settings(
    config: Config, *, paper: str, overlay_enabled: bool, cut_margin_mm: float
) -> None:
    """오버레이 옵션(용지·ON/OFF·절단 마진)을 config.ini에 영속화."""
    paper = (paper or "A4").strip().upper()
    if paper not in {"A4", "A3"}:
        paper = "A4"
    cut_margin_mm = max(1.0, min(10.0, float(cut_margin_mm or 3.0)))
    _write_setting(config.config_path, "layout", "paper", paper)
    _write_setting(config.config_path, "overlay", "enabled", "true" if overlay_enabled else "false")
    _write_setting(config.config_path, "overlay", "cut_margin_mm", str(cut_margin_mm))
    config.paper = paper
    config.overlay_enabled = bool(overlay_enabled)
    config.cut_margin_mm = cut_margin_mm


def _write_setting(config_path: Path, section: str, key: str, value: str) -> None:
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";", "#"))
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    with config_path.open("w", encoding="utf-8") as f:
        parser.write(f)
