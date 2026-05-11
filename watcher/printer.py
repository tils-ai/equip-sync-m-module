"""PDF → Windows 프린터 출력 (b-module 패턴).

합본 PDF를 PIL Image로 렌더링 후 win32print/win32ui로 직접 출력한다.
pywin32/Pillow/pdf2image + poppler 필요 (Windows 전용 — macOS dev에선 import 자체가 실패할 수 있음).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def print_pdf(pdf_path: Path, *, printer_name: str, dpi: int = 300, poppler_path: str | None = None) -> None:
    """합본 PDF의 모든 페이지를 지정 프린터로 출력.

    Args:
        pdf_path: 출력할 PDF 경로
        printer_name: Windows 프린터명 (설정 > 프린터에서 확인)
        dpi: PDF → 이미지 변환 해상도
        poppler_path: poppler 바이너리 경로 (frozen exe면 번들 디렉토리)
    """
    if not printer_name:
        raise RuntimeError("프린터명이 설정되지 않았습니다.")

    # Windows 전용 모듈 — 지연 import (macOS dev에서 모듈 로딩 자체는 통과)
    from pdf2image import convert_from_path
    from PIL import Image

    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        poppler_path=poppler_path,
        use_pdftocairo=True,
    )
    if not images:
        raise RuntimeError(f"PDF에 페이지가 없습니다: {pdf_path.name}")

    for i, img in enumerate(images, 1):
        logger.info("페이지 %d/%d 출력 중...", i, len(images))
        _print_image(_flatten_to_white(img), printer_name)


def _print_image(image, printer_name: str) -> None:
    """PIL Image를 win32ui DC로 직접 출력 (비율 유지 스케일)."""
    import win32ui
    from PIL import ImageWin

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    try:
        pw = hdc.GetDeviceCaps(110)  # PHYSICALWIDTH
        ph = hdc.GetDeviceCaps(111)  # PHYSICALHEIGHT

        ratio = pw / image.width
        new_w = pw
        new_h = int(image.height * ratio)
        if new_h > ph:
            ratio = ph / image.height
            new_w = int(image.width * ratio)
            new_h = ph

        hdc.StartDoc("Mug Transfer Print")
        hdc.StartPage()
        dib = ImageWin.Dib(image)
        dib.draw(hdc.GetHandleOutput(), (0, 0, new_w, new_h))
        hdc.EndPage()
        hdc.EndDoc()
        logger.info("출력 완료: %dx%d → %dx%d", image.width, image.height, new_w, new_h)
    finally:
        hdc.DeleteDC()


def _flatten_to_white(img):
    """RGBA → RGB(흰 배경 합성) — 잉크 절약 + 안티앨리어싱 가장자리 정리."""
    from PIL import Image

    if img.mode != "RGBA":
        return img.convert("RGB")
    alpha = img.split()[3]
    mask = alpha.point(lambda a: 255 if a >= 128 else 0)
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img.convert("RGB"), mask=mask)
    return flat


def resolve_poppler_path() -> str | None:
    """frozen exe의 번들 poppler 경로 반환 (없으면 None — 시스템 PATH 사용)."""
    import os
    import sys

    if getattr(sys, "frozen", False):
        bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "poppler")
        if os.path.isdir(bundled):
            return bundled
    return None
