"""Watcher 백그라운드 서비스 — GUI/CLI 양쪽에서 start/stop 제어."""

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
from .pairing import PairingQueue
from .pipeline import compose_2up

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
            self._queue.restore_from_disk(self.cfg.incoming)
            self._observer = start_observer(self.cfg.incoming, self._queue)
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

    def _make_pair_handler(self):
        cfg = self.cfg

        def on_pair(top: Path, bot: Path) -> None:
            out_path = cfg.done / _batch_filename()
            try:
                compose_2up(top, bot, out_path, mirror=cfg.mirror, fit=cfg.fit)
            except Exception:
                logger.exception("compose failed: %s + %s", top.name, bot.name)
                for src in (top, bot):
                    if src.exists():
                        _move(src, cfg.error)
                return

            for src in (top, bot):
                if not src.exists():
                    continue
                if cfg.keep_originals:
                    _move(src, cfg.originals)
                else:
                    src.unlink(missing_ok=True)

            logger.info("done: %s", out_path.name)

        return on_pair
