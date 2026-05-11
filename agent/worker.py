"""머그 프린터 Agent worker — dps-store API 풀링 → PDF 다운로드 → incoming/에 저장.

저장 시 파일명: `{designId}_qty{quantity}.pdf`로 수량 정보를 인코딩.
워처가 동일 파일을 큐에서 qty만큼 가상 복제해 페어링 처리.

dps-store 백엔드(/api/printer/mug/*) 구현 시 활성화 — v0.3 TODO 참조.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import requests

from .api_client import MugApiClient
from .auth import authenticate
from .state import AgentState, load_state, save_state

logger = logging.getLogger(__name__)


def _backoff(empty_count: int, base: float) -> float:
    if empty_count < 3:
        return base
    if empty_count < 6:
        return 10.0
    if empty_count < 10:
        return 20.0
    return 30.0


def _safe_filename(job: dict) -> str:
    """파일명: {orderId or designId}_qty{quantity}.pdf — 워처가 qty를 파싱."""
    design_id = job.get("designId") or job.get("orderNumber") or job.get("id") or "design"
    qty = int(job.get("quantity") or 1)
    base = str(design_id).replace("/", "_").replace("\\", "_")
    return f"{base}_qty{qty}.pdf"


def _download(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error("다운로드 실패: %s", e)
        return False


class AgentWorker:
    """풀링 → 다운로드 → incoming/ 저장 → 완료 보고. 워처가 후속 처리."""

    def __init__(self, *, incoming_dir: Path):
        self.incoming_dir = incoming_dir
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[MugApiClient] = None
        self.on_started: Optional[Callable[[], None]] = None
        self.on_stopped: Optional[Callable[[], None]] = None
        self.on_downloaded: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Agent 시작 — API 키 없으면 인증 플로우 자동 트리거 (가먼트 패턴)."""
        if self._running:
            return
        state = load_state()
        if not state.api_key:
            if not state.tenant_name:
                logger.error("스토어 ID 미설정 — 설정 패널에서 입력 후 다시 시도하세요.")
                if self.on_error:
                    self.on_error("스토어 ID 미설정")
                return
            logger.info("인증 시작 — tenant: %s", state.tenant_name)
            threading.Thread(target=self._auth_and_start, args=(state,), daemon=True).start()
            return
        self._start_polling(state)

    def _auth_and_start(self, state) -> None:
        """브라우저 Device Auth → API 키 발급 → 풀링 시작."""
        try:
            api_key = authenticate(state.base_url, state.tenant_name)
            state.api_key = api_key
            state.paired = True
            save_state(state)
            logger.info("인증 완료 — 풀링 시작")
            self._start_polling(state)
        except SystemExit:
            return
        except Exception:
            logger.exception("인증 오류")
            if self.on_error:
                self.on_error("인증 실패")

    def _start_polling(self, state) -> None:
        self._client = MugApiClient(state.base_url, state.api_key)
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        if self.on_started:
            self.on_started()
        logger.info("Agent 풀링 시작 — %s", state.base_url)

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._running = False
        if self.on_stopped:
            self.on_stopped()
        logger.info("Agent 정지됨")

    def _loop(self) -> None:
        assert self._client is not None
        empty = 0
        base_interval = 5.0
        while not self._stop_event.is_set():
            try:
                data = self._client.get_pending_jobs()
                jobs = data.get("jobs", [])
                server_interval = data.get("pollInterval")
                if server_interval and server_interval > 0:
                    base_interval = float(server_interval)
                if not jobs:
                    empty += 1
                else:
                    empty = 0
                    for job in jobs:
                        if self._stop_event.is_set():
                            break
                        self._process_job(job)
            except requests.HTTPError as e:
                logger.error("API 오류: %s", e)
                empty += 1
            except requests.RequestException as e:
                logger.warning("네트워크 오류: %s — 30초 후 재시도", e)
                self._stop_event.wait(30)
                continue
            except Exception:
                logger.exception("풀링 예외 — 10초 후 재시도")
                self._stop_event.wait(10)
                continue
            interval = _backoff(empty, base_interval)
            self._stop_event.wait(interval)
        self._running = False

    def _process_job(self, job: dict) -> None:
        job_id = job.get("id")
        url = job.get("downloadUrl") or job.get("designUrl")
        if not job_id or not url:
            logger.warning("잘못된 job: %s", job)
            return
        filename = _safe_filename(job)
        dest = self.incoming_dir / filename
        logger.info("디자인 다운로드: %s → %s", job_id, dest.name)
        if _download(url, dest):
            try:
                if self._client:
                    self._client.mark_done(job_id)
                if self.on_downloaded:
                    self.on_downloaded(filename)
            except Exception:
                logger.exception("완료 보고 실패: %s", job_id)
        else:
            try:
                if self._client:
                    self._client.mark_failed(job_id, "download failed")
            except Exception:
                logger.exception("실패 보고 실패: %s", job_id)
            if self.on_error:
                self.on_error(filename)
