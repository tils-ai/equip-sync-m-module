"""dps-store 머그 전사지 프린터 API 클라이언트.

엔드포인트: `/api/printer/mug/*` — dps-store 백엔드 구현 시 활성화.
명세: dps-store/docs/print/20260507-mug-transfer-printer.md (v0.3 TODO 섹션)
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

VERSION = "0.5.0"


class MugApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["X-Client-Version"] = VERSION

    def get_pending_jobs(self, limit: int = 10) -> dict:
        """미출력 머그 디자인 큐 조회."""
        resp = self.session.get(
            f"{self.base_url}/api/printer/mug",
            params={"status": "pending", "limit": limit},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def mark_done(self, job_id: str) -> None:
        """완료 보고."""
        resp = self.session.post(
            f"{self.base_url}/api/printer/mug/{job_id}/done",
            timeout=10,
        )
        resp.raise_for_status()

    def mark_failed(self, job_id: str, reason: str = "") -> None:
        """실패 보고."""
        resp = self.session.post(
            f"{self.base_url}/api/printer/mug/{job_id}/failed",
            json={"reason": reason} if reason else None,
            timeout=10,
        )
        resp.raise_for_status()
