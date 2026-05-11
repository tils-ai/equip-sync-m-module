"""Watcher 백그라운드 서비스 — GUI/CLI 양쪽에서 start/stop 제어.

신규 PDF 수신 → 사이즈 검사 → 정상이면 페어링 큐, 초과면 oversize 정책에 따라 처리.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers.api import BaseObserver

from .config import Config
from .observer import start_observer
from .pairing import PairingQueue, parse_slot
from .pipeline import OverlayConfig, SlotMeta, compose_1up, compose_2up, fits_in_2up_slot
from .printer import print_pdf, resolve_poppler_path

logger = logging.getLogger(__name__)


def _batch_filename() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:6]}.pdf"


def _paper_label(paper: str) -> str:
    """config.paper → 메타 토큰용 문자열."""
    p = (paper or "A4").strip().upper()
    if p == "A3":
        return "A3 420×297mm"
    return "A4 297×210mm"


def _move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        dst = dst_dir / f"{src.stem}-{uuid.uuid4().hex[:4]}{src.suffix}"
    shutil.move(str(src), str(dst))
    return dst


class WatcherService:
    """수명주기 가능한 Watcher — start()/stop()/running.

    GUI 통합용 콜백:
      - on_done(name): 합본 완료 시 결과 파일명
      - on_error(name): 처리 실패 시 원본 파일명
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._observer: Optional[BaseObserver] = None
        self._queue: Optional[PairingQueue] = None
        self._lock = threading.Lock()
        self._running = False
        self.on_done: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    @property
    def running(self) -> bool:
        return self._running

    def queue_depth(self) -> int:
        return len(self._queue.snapshot()) if self._queue else 0

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._queue = PairingQueue(self._make_pair_handler())
            self._observer = start_observer(self.config.incoming, self._handle_design)
            self._restore_existing()
            self._running = True
            logger.info("watcher service started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            if self._observer is not None:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None
            self._queue = None
            self._running = False
            logger.info("watcher service stopped")

    def _restore_existing(self) -> None:
        if not self._queue:
            return
        existing = sorted(
            (p for p in self.config.incoming.glob("*.pdf") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        for p in existing:
            self._handle_design(p)

    def _handle_design(self, path: Path) -> None:
        """신규 PDF 진입 시 라우팅 — 사이즈 검사 → 큐 또는 oversize 처리."""
        if self._queue is None:
            return
        try:
            fits = fits_in_2up_slot(path)
        except Exception:
            logger.exception("size check failed: %s → error/", path.name)
            if path.exists():
                _move(path, self.config.error)
            return
        if not fits:
            self._handle_oversize(path)
            return
        self._queue.add(path)

    def _handle_oversize(self, path: Path) -> None:
        action = self.config.oversize_action
        if action == "single":
            out_path = self.config.done / _batch_filename()
            try:
                compose_1up(
                    path,
                    out_path,
                    mirror=self.config.mirror,
                    fit=self.config.fit,
                    meta=self._build_slot_meta(path),
                    overlay_cfg=self._overlay_cfg(),
                )
            except Exception:
                logger.exception("oversize single compose failed: %s", path.name)
                if path.exists():
                    _move(path, self.config.error)
                self._notify_error(path.name)
                return
            self._dispose_original(path)
            if not self._maybe_print(out_path):
                return
            logger.info("oversize → single done: %s", out_path.name)
            self._notify_done(out_path.name)
        else:  # "error"
            logger.warning("oversize → error/: %s", path.name)
            if path.exists():
                _move(path, self.config.error)
            self._notify_error(path.name)

    def _maybe_print(self, pdf_path: Path) -> bool:
        """프린터 토글이 켜져있으면 합본 PDF를 출력. 실패 시 error/로 이동하고 False."""
        if not self.config.printer_enabled:
            return True
        if not self.config.printer_name:
            logger.warning("프린터 이름 미설정 — 출력 건너뜀: %s", pdf_path.name)
            return True
        try:
            print_pdf(
                pdf_path,
                printer_name=self.config.printer_name,
                dpi=self.config.render_dpi,
                poppler_path=resolve_poppler_path(),
            )
            return True
        except Exception:
            logger.exception("프린터 출력 실패: %s → error/", pdf_path.name)
            if pdf_path.exists():
                _move(pdf_path, self.config.error)
            self._notify_error(pdf_path.name)
            return False

    def _notify_done(self, name: str) -> None:
        if self.on_done:
            try:
                self.on_done(name)
            except Exception:
                logger.exception("on_done callback failed")

    def _notify_error(self, name: str) -> None:
        if self.on_error:
            try:
                self.on_error(name)
            except Exception:
                logger.exception("on_error callback failed")

    def _dispose_original(self, path: Path) -> None:
        sidecar = path.with_suffix(".json")
        if path.exists():
            if self.config.keep_originals:
                _move(path, self.config.originals)
            else:
                path.unlink(missing_ok=True)
        # 사이드카 JSON도 같이 정리 (originals로 보내거나 삭제)
        if sidecar.exists():
            try:
                if self.config.keep_originals:
                    _move(sidecar, self.config.originals)
                else:
                    sidecar.unlink(missing_ok=True)
            except Exception:
                logger.exception("사이드카 처리 실패: %s", sidecar.name)

    def _build_slot_meta(self, pdf_path: Path) -> SlotMeta:
        """파일명에서 (slot, total) 추출 + 사이드카 JSON에서 identifier·orderNumber 로드."""
        slot_index, total_slots = parse_slot(pdf_path)
        identifier = ""
        order_number = ""
        sidecar = pdf_path.with_suffix(".json")
        if sidecar.exists():
            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                identifier = str(data.get("identifier") or "")
                order_number = str(data.get("orderNumber") or "")
            except Exception:
                logger.exception("사이드카 JSON 파싱 실패: %s", sidecar.name)
        return SlotMeta(
            identifier=identifier,
            order_number=order_number,
            slot_index=slot_index,
            total_slots=total_slots,
            paper_label=_paper_label(self.config.paper),
        )

    def _overlay_cfg(self) -> OverlayConfig:
        return OverlayConfig(
            enabled=self.config.overlay_enabled,
            cut_margin_mm=self.config.cut_margin_mm,
            meta_corner_mm=self.config.meta_corner_mm,
            meta_font_size=self.config.meta_font_size,
            meta_color=self.config.meta_color,
            grid_color=self.config.grid_color,
            cut_color=self.config.cut_color,
        )

    def _make_pair_handler(self):
        config = self.config
        service = self

        def on_pair(top: Path, bot: Path) -> None:
            out_path = config.done / _batch_filename()
            try:
                compose_2up(
                    top,
                    bot,
                    out_path,
                    mirror=config.mirror,
                    fit=config.fit,
                    meta_top=service._build_slot_meta(top),
                    meta_bot=service._build_slot_meta(bot),
                    overlay_cfg=service._overlay_cfg(),
                )
            except Exception:
                logger.exception("compose failed: %s + %s", top.name, bot.name)
                for src in {top, bot}:
                    if src.exists():
                        _move(src, config.error)
                service._notify_error(f"{top.name} + {bot.name}")
                return

            consumed: set[Path] = set()
            still_pending: set[Path] = set(service._queue.snapshot()) if service._queue else set()
            for src in (top, bot):
                if src in consumed:
                    continue
                consumed.add(src)
                if src in still_pending:
                    continue
                service._dispose_original(src)

            if not service._maybe_print(out_path):
                return

            logger.info("done: %s", out_path.name)
            service._notify_done(out_path.name)

        return on_pair
