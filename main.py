"""PyInstaller 진입점 — 패키지 컨텍스트가 보존되도록 watcher.__main__를 absolute import로 호출.

`watcher/__main__.py`를 직접 빌드 진입점으로 쓰면 PyInstaller가 frozen 환경에서
패키지 부모를 인식하지 못해 내부 relative import(from .config 등)가 깨질 수 있다.
"""

from __future__ import annotations

import sys

from watcher.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
