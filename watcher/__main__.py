"""equip-sync-m-module 진입점.

사용법:
    python -m watcher              # GUI 실행 (기본)
    python -m watcher --headless   # 콘솔 모드 (GUI 없이 무한 루프)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from .config import Config, ensure_dirs, load_config
from .logger import setup_logging
from .service import WatcherService

logger = logging.getLogger(__name__)


def _bootstrap() -> Config:
    cfg = load_config()
    setup_logging(cfg.log_file, cfg.log_level)
    ensure_dirs(cfg)
    logger.info("equip-sync-m-module starting (config: %s)", cfg.config_path)
    return cfg


def run_headless(cfg: Config) -> int:
    service = WatcherService(cfg)
    service.start()
    logger.info("headless mode — Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        service.stop()
    return 0


def run_gui(cfg: Config) -> int:
    # 지연 임포트 — 헤드리스 환경에서 customtkinter 없이도 동작 가능
    from gui.app import launch_app

    return launch_app(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="equip-sync-m")
    parser.add_argument("--headless", action="store_true", help="GUI 없이 콘솔에서 실행")
    args = parser.parse_args(argv)

    cfg = _bootstrap()
    if args.headless:
        return run_headless(cfg)
    return run_gui(cfg)


if __name__ == "__main__":
    sys.exit(main())
