"""FIFO 페어링 큐. 2개 슬롯이 모이면 콜백 호출. 1개만 있으면 대기.

v0.7부터 가상 복제 비활성화: Agent가 _qty{N}_{idx}.pdf로 N개의 독립 파일을 만들어
incoming/에 떨어뜨린다. PairingQueue는 각 파일을 단일 슬롯으로만 다룬다.

파일명 규칙 (메타 토큰 추출용, 큐 동작에는 영향 없음):
  - {base}_qty{N}_{idx}.pdf  → 같은 디자인 N장 중 idx번째
  - {base}.pdf               → qty=1 단독
"""

from __future__ import annotations

import logging
import re
import threading
from collections import deque
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# 파일명에서 (slot_index, total_slots) 추출 — pipeline 메타 토큰에 사용.
_SLOT_RE = re.compile(r"_qty(\d+)_(\d+)(?=\.pdf$)", re.IGNORECASE)


def parse_slot(path: Path) -> tuple[int, int]:
    """파일명 `_qty{N}_{idx}.pdf`에서 (slot_index, total_slots) 추출. 없으면 (1, 1)."""
    m = _SLOT_RE.search(path.name)
    if m:
        try:
            total = max(1, int(m.group(1)))
            idx = max(1, int(m.group(2)))
            return idx, total
        except ValueError:
            pass
    return 1, 1


# 호환성: 구버전 호출자가 parse_qty를 import할 수 있음
def parse_qty(path: Path) -> int:
    """[deprecated v0.6 호환] v0.7부터 Agent가 N개로 분할 저장하므로 항상 1."""
    return 1


class PairingQueue:
    """thread-safe FIFO. 2슬롯 모이면 콜백을 별도 스레드로 호출.

    v0.7: 각 path는 큐에 정확히 1회만 추가됨 (가상 복제 없음).
    """

    def __init__(self, on_pair: Callable[[Path, Path], None]) -> None:
        self._lock = threading.Lock()
        self._items: deque[Path] = deque()
        self._on_pair = on_pair

    def add(self, path: Path) -> None:
        pair: tuple[Path, Path] | None = None
        with self._lock:
            if path in self._items:
                logger.debug("ignore duplicate enqueue: %s", path.name)
                return
            self._items.append(path)
            depth = len(self._items)
            if len(self._items) >= 2:
                a = self._items.popleft()
                b = self._items.popleft()
                pair = (a, b)
        logger.info("queued: %s (depth=%d, dispatched=%d)", path.name, depth, 1 if pair else 0)
        if pair:
            self._dispatch(*pair)

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
