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


def _contain_scale(src_w: float, src_h: float, slot: Slot) -> float:
    return min(slot.w / src_w, slot.h / src_h)


def _cover_scale(src_w: float, src_h: float, slot: Slot) -> float:
    return max(slot.w / src_w, slot.h / src_h)


def compose_2up(
    pdf_top: Path,
    pdf_bot: Path,
    output_path: Path,
    *,
    mirror: str = "horizontal",
    fit: str = "contain",
) -> None:
    """두 PDF의 첫 페이지를 좌우 반전 후 A4 가로 한 장에 위·아래로 배치해 저장.

    Args:
        pdf_top: 상단에 들어갈 원본 PDF (FIFO 첫 번째)
        pdf_bot: 하단에 들어갈 원본 PDF (FIFO 두 번째)
        output_path: 결과 PDF 경로
        mirror: "horizontal" → 좌우 반전, "none" → 반전 없음
        fit: "contain" → 슬롯 안에 비율 유지하며 맞춤, "cover" → 슬롯 가득 채움(잘림 가능)
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

        scale = _cover_scale(sw, sh, slot) if fit == "cover" else _contain_scale(sw, sh, slot)
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
