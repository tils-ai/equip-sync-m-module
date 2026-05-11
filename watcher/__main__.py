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
from .fonts import register as register_fonts
from .logger import setup_logging
from .service import WatcherService

logger = logging.getLogger(__name__)


def _bootstrap() -> Config:
    config = load_config()
    setup_logging(config.log_file, config.log_level)
    ensure_dirs(config)
    family = register_fonts()
    logger.info("equip-sync-m-module starting (config: %s, font: %s)", config.config_path, family)
    return config


def run_headless(config: Config) -> int:
    service = WatcherService(config)
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


def run_gui(config: Config) -> int:
    # 지연 임포트 — 헤드리스 환경에서 customtkinter 없이도 동작 가능
    from watcher.gui.app import launch_app

    return launch_app(config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="equip-sync-m")
    parser.add_argument("--headless", action="store_true", help="GUI 없이 콘솔에서 실행")
    args = parser.parse_args(argv)

    config = _bootstrap()
    if args.headless:
        return run_headless(config)
    return run_gui(config)


if __name__ == "__main__":
    sys.exit(main())
