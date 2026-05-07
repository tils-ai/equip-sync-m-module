"""Watcher 백그라운드 서비스 — GUI/CLI 양쪽에서 start/stop 제어.

신규 PDF 수신 → 사이즈 검사 → 정상이면 페어링 큐, 초과면 oversize 정책에 따라 처리.
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from watchdog.observers.api import BaseObserver

from .config import Config
from .observer import start_observer
from .pairing import PairingQueue, parse_qty
from .pipeline import compose_1up, compose_2up, fits_in_2up_slot

logger = logging.getLogger(__name__)


def _batch_filename() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:6]}.pdf"


def _move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        dst = dst_dir / f"{src.stem}-{uuid.uuid4().hex[:4]}{src.suffix}"
    shutil.move(str(src), str(dst))
    return dst


class WatcherService:
    """수명주기 가능한 Watcher — start()/stop()/running."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._observer: Optional[BaseObserver] = None
        self._queue: Optional[PairingQueue] = None
        self._lock = threading.Lock()
        self._running = False

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
            self._observer = start_observer(self.cfg.incoming, self._handle_design)
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
            (p for p in self.cfg.incoming.glob("*.pdf") if p.is_file()),
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
                _move(path, self.cfg.error)
            return
        if not fits:
            self._handle_oversize(path)
            return
        self._queue.add(path)

    def _handle_oversize(self, path: Path) -> None:
        action = self.cfg.oversize_action
        if action == "single":
            out_path = self.cfg.done / _batch_filename()
            try:
                compose_1up(path, out_path, mirror=self.cfg.mirror, fit=self.cfg.fit)
            except Exception:
                logger.exception("oversize single compose failed: %s", path.name)
                if path.exists():
                    _move(path, self.cfg.error)
                return
            self._dispose_original(path)
            logger.info("oversize → single done: %s", out_path.name)
        else:  # "error"
            logger.warning("oversize → error/: %s", path.name)
            if path.exists():
                _move(path, self.cfg.error)

    def _dispose_original(self, path: Path) -> None:
        if not path.exists():
            return
        if self.cfg.keep_originals:
            _move(path, self.cfg.originals)
        else:
            path.unlink(missing_ok=True)

    def _make_pair_handler(self):
        cfg = self.cfg
        service = self

        def on_pair(top: Path, bot: Path) -> None:
            out_path = cfg.done / _batch_filename()
            try:
                compose_2up(top, bot, out_path, mirror=cfg.mirror, fit=cfg.fit)
            except Exception:
                logger.exception("compose failed: %s + %s", top.name, bot.name)
                # 같은 파일 두 슬롯 케이스 — 중복 방지하며 error/로
                for src in {top, bot}:
                    if src.exists():
                        _move(src, cfg.error)
                return

            # 정상 합본 — 같은 파일이 두 슬롯에 들어간 경우(qty>=2) 한 번만 이동
            consumed: set[Path] = set()
            # 큐에 같은 path가 더 남아있으면(qty>2) 원본 보존이 필요 — 큐 스냅샷으로 확인
            still_pending: set[Path] = set(service._queue.snapshot()) if service._queue else set()
            for src in (top, bot):
                if src in consumed:
                    continue
                consumed.add(src)
                if src in still_pending:
                    # 같은 디자인이 다음 슬롯에서도 사용됨 — 원본 유지
                    continue
                service._dispose_original(src)

            logger.info("done: %s", out_path.name)

        return on_pair
