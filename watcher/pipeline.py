"""PDF 좌우 반전 + A4 가로 2-up 합성 (pypdf 사용)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation

# A4 (포인트, 1mm = 2.834645 pt)
A4_PORTRAIT_W = 595.276
A4_PORTRAIT_H = 841.890
A4_LANDSCAPE_W = A4_PORTRAIT_H  # 841.89
A4_LANDSCAPE_H = A4_PORTRAIT_W  # 595.276

logger = logging.getLogger(__name__)


@dataclass
class Slot:
    x: float
    y: float
    w: float
    h: float


def _slots_a4_landscape_2up() -> tuple[Slot, Slot]:
    """A4 가로 캔버스를 위·아래 절반으로 나눈 두 슬롯. ①(상) 먼저, ②(하) 나중."""
    half_h = A4_LANDSCAPE_H / 2
    return (
        Slot(x=0, y=half_h, w=A4_LANDSCAPE_W, h=half_h),  # 상단
        Slot(x=0, y=0, w=A4_LANDSCAPE_W, h=half_h),  # 하단
    )


def _slot_a4_landscape_full() -> Slot:
    """A4 가로 캔버스 전체 슬롯 (1-up 단독 출력용)."""
    return Slot(x=0, y=0, w=A4_LANDSCAPE_W, h=A4_LANDSCAPE_H)


def fits_in_2up_slot(pdf_path: Path) -> bool:
    """원본 사이즈로 2-up 슬롯(절반 A4 가로)에 들어가는지 확인."""
    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        return False
    page = reader.pages[0]
    slot = _slots_a4_landscape_2up()[0]
    return float(page.mediabox.width) <= slot.w and float(page.mediabox.height) <= slot.h


def _contain_scale(src_w: float, src_h: float, slot: Slot) -> float:
    return min(slot.w / src_w, slot.h / src_h)


def _cover_scale(src_w: float, src_h: float, slot: Slot) -> float:
    return max(slot.w / src_w, slot.h / src_h)


def _scale_for(fit: str, src_w: float, src_h: float, slot: Slot) -> float:
    if fit == "cover":
        return _cover_scale(src_w, src_h, slot)
    if fit == "contain":
        return _contain_scale(src_w, src_h, slot)
    # "original" — 원본 사이즈 유지. 슬롯보다 크면 contain으로 폴백.
    if src_w > slot.w or src_h > slot.h:
        return _contain_scale(src_w, src_h, slot)
    return 1.0


def compose_2up(
    pdf_top: Path,
    pdf_bot: Path,
    output_path: Path,
    *,
    mirror: str = "horizontal",
    fit: str = "original",
) -> None:
    """두 PDF의 첫 페이지를 좌우 반전 후 A4 가로 한 장에 위·아래로 배치해 저장.

    같은 경로가 두 번 들어와도 동작 (한 디자인 × 수량 2 시나리오 — 같은 파일 두 슬롯에 배치).

    Args:
        pdf_top: 상단에 들어갈 원본 PDF (FIFO 첫 번째)
        pdf_bot: 하단에 들어갈 원본 PDF (FIFO 두 번째, pdf_top과 같아도 됨)
        output_path: 결과 PDF 경로
        mirror: "horizontal" → 좌우 반전, "none" → 반전 없음
        fit: "original" → 원본 크기 유지(슬롯보다 크면 contain), "contain" → 슬롯 비율 맞춤,
             "cover" → 슬롯 가득 채움(잘림 가능)
    """
    sources = [pdf_top, pdf_bot]
    slots = _slots_a4_landscape_2up()

    writer = PdfWriter()
    canvas = writer.add_blank_page(width=A4_LANDSCAPE_W, height=A4_LANDSCAPE_H)

    for src_path, slot in zip(sources, slots):
        reader = PdfReader(str(src_path))
        if not reader.pages:
            raise ValueError(f"empty PDF: {src_path.name}")
        page = reader.pages[0]

        sw = float(page.mediabox.width)
        sh = float(page.mediabox.height)

        scale = _scale_for(fit, sw, sh, slot)
        pw = sw * scale
        ph = sh * scale

        # 슬롯 내 가운데 정렬
        cx = slot.x + (slot.w - pw) / 2
        cy = slot.y + (slot.h - ph) / 2

        if mirror == "horizontal":
            # x축 반전: scale(-s, s) 후 +pw 만큼 평행이동해 캔버스에 정상 위치
            op = Transformation().scale(-scale, scale).translate(cx + pw, cy)
        else:
            op = Transformation().scale(scale, scale).translate(cx, cy)

        canvas.merge_transformed_page(page, op)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)

    logger.info(
        "composed: %s + %s -> %s (mirror=%s, fit=%s)",
        pdf_top.name,
        pdf_bot.name,
        output_path.name,
        mirror,
        fit,
    )


def compose_1up(
    pdf_src: Path,
    output_path: Path,
    *,
    mirror: str = "horizontal",
    fit: str = "contain",
) -> None:
    """단독 1-up 출력 — A4 가로 캔버스 가운데에 한 디자인만 배치.
    사이즈 초과 디자인의 폴백 출력에 사용."""
    slot = _slot_a4_landscape_full()

    writer = PdfWriter()
    canvas = writer.add_blank_page(width=A4_LANDSCAPE_W, height=A4_LANDSCAPE_H)

    reader = PdfReader(str(pdf_src))
    if not reader.pages:
        raise ValueError(f"empty PDF: {pdf_src.name}")
    page = reader.pages[0]

    sw = float(page.mediabox.width)
    sh = float(page.mediabox.height)

    scale = _scale_for(fit, sw, sh, slot)
    pw = sw * scale
    ph = sh * scale

    cx = slot.x + (slot.w - pw) / 2
    cy = slot.y + (slot.h - ph) / 2

    if mirror == "horizontal":
        op = Transformation().scale(-scale, scale).translate(cx + pw, cy)
    else:
        op = Transformation().scale(scale, scale).translate(cx, cy)

    canvas.merge_transformed_page(page, op)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)

    logger.info("composed 1up (oversize fallback): %s -> %s", pdf_src.name, output_path.name)
