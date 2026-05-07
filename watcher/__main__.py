"""equip-sync-m-module 진입점.

사용법:
    python -m watcher
또는:
    equip-sync-m
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from .config import Config, ensure_dirs, load_config
from .logger import setup_logging
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
        # 충돌 시 suffix 부여
        dst = dst_dir / f"{src.stem}-{uuid.uuid4().hex[:4]}{src.suffix}"
    shutil.move(str(src), str(dst))
    return dst


def _make_pair_handler(cfg: Config):
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

        # 원본 처리
        for src in (top, bot):
            if not src.exists():
                continue
            if cfg.keep_originals:
                _move(src, cfg.originals)
            else:
                src.unlink(missing_ok=True)

        logger.info("done: %s", out_path.name)

    return on_pair


def main() -> int:
    cfg = load_config()
    setup_logging(cfg.log_file, cfg.log_level)
    ensure_dirs(cfg)

    logger.info("equip-sync-m-module starting")
    logger.info("config: %s", cfg.config_path)
    logger.info("incoming: %s", cfg.incoming)
    logger.info("done: %s", cfg.done)

    queue = PairingQueue(_make_pair_handler(cfg))
    queue.restore_from_disk(cfg.incoming)

    observer = start_observer(cfg.incoming, queue)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        observer.stop()
        observer.join(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
