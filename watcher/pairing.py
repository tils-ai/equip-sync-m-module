"""FIFO 페어링 큐. 2개 슬롯이 모이면 콜백 호출. 1개만 있으면 대기.

파일명 규칙으로 수량 표현:
  - {base}.pdf            → qty=1 (기본)
  - {base}_qty2.pdf       → qty=2 (한 디자인 두 번 배치)
  - {base}_qty3.pdf       → qty=3
"""

from __future__ import annotations

import logging
import re
import threading
from collections import deque
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_QTY_RE = re.compile(r"_qty(\d+)(?=\.pdf$)", re.IGNORECASE)


def parse_qty(path: Path) -> int:
    """파일명 끝의 `_qtyN.pdf` 패턴에서 수량을 파싱. 없으면 1."""
    m = _QTY_RE.search(path.name)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            pass
    return 1


class PairingQueue:
    """thread-safe FIFO. 2슬롯 모이면 콜백을 별도 스레드로 호출.

    동일 path가 qty만큼 큐에 적재 — 같은 디자인이 여러 슬롯에 배치되는 시나리오 지원.
    watchdog 중복 이벤트는 큐 내 동일 path 카운트가 이미 qty와 같으면 무시한다.
    """

    def __init__(self, on_pair: Callable[[Path, Path], None]) -> None:
        self._lock = threading.Lock()
        self._items: deque[Path] = deque()
        self._on_pair = on_pair

    def add(self, path: Path) -> None:
        qty = parse_qty(path)
        pairs: list[tuple[Path, Path]] = []
        with self._lock:
            existing = sum(1 for p in self._items if p == path)
            if existing >= qty:
                logger.debug("ignore duplicate enqueue: %s (existing=%d, qty=%d)", path.name, existing, qty)
                return
            for _ in range(qty - existing):
                self._items.append(path)
            depth = len(self._items)
            # qty가 2 이상이면 한 번의 add로 여러 쌍이 가능 — 가능한 모든 쌍을 dispatch.
            while len(self._items) >= 2:
                a = self._items.popleft()
                b = self._items.popleft()
                pairs.append((a, b))
        logger.info("queued: %s qty=%d (depth=%d, dispatched=%d)", path.name, qty, depth, len(pairs))
        for a, b in pairs:
            self._dispatch(a, b)

    def remove(self, path: Path) -> bool:
        """대기 중인 항목을 제거 (모든 인스턴스). 페어링 처리 중이면 영향 없음."""
        removed = False
        with self._lock:
            while True:
                try:
                    self._items.remove(path)
                    removed = True
                except ValueError:
                    break
        return removed

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
