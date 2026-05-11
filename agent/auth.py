"""Device Auth: 브라우저 인증으로 머그 프린터 API 키 발급.

dps-store `/api/printer/auth/request` 의 typeMap에 `mug: PrinterType.MUG_TRANSFER`가
추가되어야 동작 (v0.3 TODO).
"""

from __future__ import annotations

import logging
import time
import webbrowser

import requests

logger = logging.getLogger(__name__)


def authenticate(base_url: str, tenant: str) -> str:
    """인증 플로우 실행 — Device Auth (브라우저 승인 후 API 키 반환)."""
    resp = requests.post(
        f"{base_url}/api/printer/auth/request",
        json={"tenant": tenant, "type": "mug"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    verify_url = data["verifyUrl"]
    user_code = data["userCode"]
    expires_in = data["expiresIn"]

    logger.info("인증이 필요합니다 — 브라우저: %s", verify_url)
    logger.info("인증 코드: %s (%d분 내 완료)", user_code, expires_in // 60)
    webbrowser.open(verify_url)

    device_code = data["deviceCode"]
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(2)
        try:
            resp = requests.post(
                f"{base_url}/api/printer/auth/poll",
                json={"deviceCode": device_code},
                timeout=10,
            )
            result = resp.json()
            if result["status"] == "approved":
                logger.info("인증 완료")
                return result["apiKey"]
            if result["status"] == "expired":
                raise RuntimeError("인증 시간이 만료되었습니다.")
        except requests.RequestException as e:
            logger.warning("인증 폴링 오류: %s", e)

    raise RuntimeError("인증 시간이 만료되었습니다.")
