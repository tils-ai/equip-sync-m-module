"""watchdog Observer 래퍼 — incoming/ 폴더에 PDF 신규 파일이 들어오면 콜백 호출."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

PdfCallback = Callable[[Path], None]


def _wait_until_stable(path: Path, max_wait: float = 8.0, poll: float = 0.15) -> bool:
    """파일 크기가 일정해질 때까지 폴링해 쓰기 완료를 대기."""
    last_size = -1
    waited = 0.0
    while waited < max_wait:
        if not path.exists():
            return False
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size > 0 and size == last_size:
            return True
        last_size = size
        time.sleep(poll)
        waited += poll
    return path.exists()


class _IncomingHandler(FileSystemEventHandler):
    def __init__(self, on_pdf: PdfCallback) -> None:
        self._on_pdf = on_pdf

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix.lower() != ".pdf":
            return
        if not _wait_until_stable(path):
            logger.warning("file disappeared or unstable: %s", path.name)
            return
        self._on_pdf(path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # 이름 변경/이동도 신규 입력으로 취급
        if event.is_directory:
            return
        dest_attr = getattr(event, "dest_path", "") or ""
        path = Path(str(dest_attr))
        if path.suffix.lower() != ".pdf":
            return
        if not _wait_until_stable(path):
            return
        self._on_pdf(path)


def start_observer(incoming_dir: Path, on_pdf: PdfCallback) -> Observer:
    handler = _IncomingHandler(on_pdf)
    observer = Observer()
    observer.schedule(handler, str(incoming_dir), recursive=False)
    observer.start()
    logger.info("observing: %s", incoming_dir)
    return observer
