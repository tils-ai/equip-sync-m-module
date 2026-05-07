"""FIFO 페어링 큐. 2건 모이면 콜백 호출. 1건만 있으면 대기."""

from __future__ import annotations

import logging
import threading
from collections import deque
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class PairingQueue:
    """thread-safe FIFO. 2건이 쌓이면 콜백을 별도 스레드로 호출."""

    def __init__(self, on_pair: Callable[[Path, Path], None]) -> None:
        self._lock = threading.Lock()
        self._items: deque[Path] = deque()
        self._on_pair = on_pair

    def add(self, path: Path) -> None:
        pair = None
        with self._lock:
            if any(p == path for p in self._items):
                logger.debug("ignore duplicate enqueue: %s", path.name)
                return
            self._items.append(path)
            depth = len(self._items)
            if depth >= 2:
                a = self._items.popleft()
                b = self._items.popleft()
                pair = (a, b)
        logger.info("queued: %s (depth=%d)", path.name, depth)
        if pair is not None:
            self._dispatch(*pair)

    def restore_from_disk(self, incoming_dir: Path) -> None:
        """기동 시 incoming/에 남아있는 PDF를 mtime 순으로 큐에 적재 후 가능하면 페어링."""
        existing = sorted(
            (p for p in incoming_dir.glob("*.pdf") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        pairs: list[tuple[Path, Path]] = []
        with self._lock:
            self._items.clear()
            for p in existing:
                self._items.append(p)
            while len(self._items) >= 2:
                a = self._items.popleft()
                b = self._items.popleft()
                pairs.append((a, b))

        if existing:
            logger.info("restored %d pending file(s)", len(existing))
        for a, b in pairs:
            self._dispatch(a, b)

    def remove(self, path: Path) -> bool:
        """대기 중인 항목을 제거. 페어링 처리 중이면 영향 없음."""
        with self._lock:
            try:
                self._items.remove(path)
                return True
            except ValueError:
                return False

    def snapshot(self) -> list[Path]:
        with self._lock:
            return list(self._items)

    def _dispatch(self, a: Path, b: Path) -> None:
        thread = threading.Thread(
            target=self._on_pair,
            args=(a, b),
            name=f"pair-{a.stem}-{b.stem}",
            daemon=True,
        )
        thread.start()
