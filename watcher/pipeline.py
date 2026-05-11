"""PDF 좌우 반전 + A4 가로 2-up 합성 (pypdf) + reportlab overlay.

v0.7: 합본 PDF 우상단에 메타 텍스트 + 그리드 가운데 선 + 슬롯별 절단선 합성.
색은 모두 마젠타(#FF00FF) — 절단 시 머그 비전사 보장.

명세: docs/print/20260511-mug-transfer-overlay.md
Fail-soft: overlay 단계 예외는 격리, base PDF는 항상 출력된다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation

from .fonts import register_reportlab

# A4 (포인트, 1mm = 2.834645 pt)
A4_PORTRAIT_W = 595.276
A4_PORTRAIT_H = 841.890
A4_LANDSCAPE_W = A4_PORTRAIT_H  # 841.89
A4_LANDSCAPE_H = A4_PORTRAIT_W  # 595.276

MM_PT = 2.834645  # 1mm → pt

logger = logging.getLogger(__name__)


@dataclass
class Slot:
    x: float
    y: float
    w: float
    h: float


@dataclass
class OverlayConfig:
    """오버레이 합성 옵션 (config.ini [overlay] 섹션 미러)."""

    enabled: bool = True
    cut_margin_mm: float = 3.0
    meta_corner_mm: float = 5.0
    meta_font_size: float = 6.5
    meta_color: str = "#FF00FF"
    grid_color: str = "#FF00FF"
    cut_color: str = "#FF00FF"


@dataclass
class SlotMeta:
    """슬롯별 메타 토큰 입력 (compose_2up/1up 호출자가 채움)."""

    identifier: str = ""
    order_number: str = ""
    slot_index: int = 1
    total_slots: int = 1
    paper_label: str = "A4 297×210mm"


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


# ── overlay 헬퍼 ──────────────────────────────────────────────────────


def _build_meta_text(meta: SlotMeta) -> str:
    tokens: list[str] = []
    if meta.paper_label.strip():
        tokens.append(meta.paper_label.strip())
    tokens.append(f"{meta.slot_index}/{meta.total_slots}")
    if meta.identifier.strip():
        tokens.append(meta.identifier.strip())
    if meta.order_number.strip():
        tokens.append(meta.order_number.strip())
    return "  ".join(tokens)


@dataclass
class _SlotPlacement:
    slot: Slot
    meta: SlotMeta
    src_w: float
    src_h: float
    scale: float


def _build_overlay(
    placements: list[_SlotPlacement],
    *,
    overlay_cfg: OverlayConfig,
    draw_grid: bool,
    canvas_w: float,
    canvas_h: float,
) -> bytes | None:
    """reportlab으로 overlay PDF 1페이지 생성. 실패 시 None."""
    try:
        from reportlab.lib.colors import HexColor
        from reportlab.pdfgen import canvas as rl_canvas
    except Exception:
        logger.exception("reportlab 미설치 — overlay 생략")
        return None

    try:
        font_name = register_reportlab()
        buf = BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(canvas_w, canvas_h))

        # 그리드 가운데 선
        if draw_grid:
            try:
                c.setStrokeColor(HexColor(overlay_cfg.grid_color))
                c.setLineWidth(0.4)
                c.line(0, canvas_h / 2, canvas_w, canvas_h / 2)
            except Exception:
                logger.exception("grid 그리기 실패")

        for p in placements:
            # 절단선 (디자인 mediabox + cut_margin 외곽)
            try:
                pw = p.src_w * p.scale
                ph = p.src_h * p.scale
                cx = p.slot.x + (p.slot.w - pw) / 2
                cy = p.slot.y + (p.slot.h - ph) / 2
                margin = overlay_cfg.cut_margin_mm * MM_PT
                rect_x = cx - margin
                rect_y = cy - margin
                rect_w = pw + 2 * margin
                rect_h = ph + 2 * margin
                if (
                    rect_x >= 0
                    and rect_y >= 0
                    and rect_x + rect_w <= canvas_w
                    and rect_y + rect_h <= canvas_h
                ):
                    c.setStrokeColor(HexColor(overlay_cfg.cut_color))
                    c.setLineWidth(0.4)
                    c.rect(rect_x, rect_y, rect_w, rect_h, stroke=1, fill=0)
                else:
                    logger.info("절단선이 캔버스 초과 — 생략 (slot=%s)", p.slot)
            except Exception:
                logger.exception("절단선 그리기 실패")

            # 메타 텍스트 (우상단 절대 좌표)
            try:
                text = _build_meta_text(p.meta)
                if not text.strip():
                    continue
                corner = overlay_cfg.meta_corner_mm * MM_PT
                x = p.slot.x + p.slot.w - corner
                y = p.slot.y + p.slot.h - corner - overlay_cfg.meta_font_size
                c.setFillColor(HexColor(overlay_cfg.meta_color))
                c.setFont(font_name, overlay_cfg.meta_font_size)
                c.drawRightString(x, y, text)
            except Exception:
                logger.exception("메타 텍스트 그리기 실패")

        c.showPage()
        c.save()
        return buf.getvalue()
    except Exception:
        logger.exception("overlay 생성 실패")
        return None


def _merge_overlay(writer: PdfWriter, overlay_bytes: bytes) -> None:
    """base writer의 첫 페이지 위에 overlay PDF를 머지. 실패 시 base 유지."""
    try:
        reader = PdfReader(BytesIO(overlay_bytes))
        if not reader.pages or not writer.pages:
            return
        writer.pages[0].merge_page(reader.pages[0])
    except Exception:
        logger.exception("overlay 머지 실패 — base만 유지")


# ── compose ───────────────────────────────────────────────────────────


def compose_2up(
    pdf_top: Path,
    pdf_bot: Path,
    output_path: Path,
    *,
    mirror: str = "horizontal",
    fit: str = "original",
    meta_top: SlotMeta | None = None,
    meta_bot: SlotMeta | None = None,
    overlay_cfg: OverlayConfig | None = None,
) -> None:
    """두 PDF의 첫 페이지를 좌우 반전 후 A4 가로 한 장에 위·아래로 배치.

    v0.7: meta_*가 주어지고 overlay_cfg.enabled가 True면 메타·그리드·절단선 합성.
    overlay 합성 실패는 base PDF에 영향 없음 (Fail-soft).
    """
    sources = [pdf_top, pdf_bot]
    slots = _slots_a4_landscape_2up()

    writer = PdfWriter()
    canvas_page = writer.add_blank_page(width=A4_LANDSCAPE_W, height=A4_LANDSCAPE_H)
    placements: list[_SlotPlacement] = []
    metas: list[SlotMeta | None] = [meta_top, meta_bot]

    for src_path, slot, meta in zip(sources, slots, metas):
        reader = PdfReader(str(src_path))
        if not reader.pages:
            raise ValueError(f"empty PDF: {src_path.name}")
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

        canvas_page.merge_transformed_page(page, op)

        if meta is not None:
            placements.append(_SlotPlacement(slot=slot, meta=meta, src_w=sw, src_h=sh, scale=scale))

    if overlay_cfg is None or not overlay_cfg.enabled or not placements:
        _write(writer, output_path)
        logger.info("composed: %s + %s -> %s (overlay=off)", pdf_top.name, pdf_bot.name, output_path.name)
        return

    overlay = _build_overlay(
        placements,
        overlay_cfg=overlay_cfg,
        draw_grid=True,
        canvas_w=A4_LANDSCAPE_W,
        canvas_h=A4_LANDSCAPE_H,
    )
    if overlay:
        _merge_overlay(writer, overlay)
    _write(writer, output_path)
    logger.info(
        "composed: %s + %s -> %s (overlay=%s)",
        pdf_top.name,
        pdf_bot.name,
        output_path.name,
        "on" if overlay else "off-failed",
    )


def compose_1up(
    pdf_src: Path,
    output_path: Path,
    *,
    mirror: str = "horizontal",
    fit: str = "contain",
    meta: SlotMeta | None = None,
    overlay_cfg: OverlayConfig | None = None,
) -> None:
    """단독 1-up 출력 — A4 가로 캔버스 가운데에 한 디자인만 배치 (oversize fallback)."""
    slot = _slot_a4_landscape_full()

    writer = PdfWriter()
    canvas_page = writer.add_blank_page(width=A4_LANDSCAPE_W, height=A4_LANDSCAPE_H)

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

    canvas_page.merge_transformed_page(page, op)

    if overlay_cfg is not None and overlay_cfg.enabled and meta is not None:
        overlay = _build_overlay(
            [_SlotPlacement(slot=slot, meta=meta, src_w=sw, src_h=sh, scale=scale)],
            overlay_cfg=overlay_cfg,
            draw_grid=False,  # 1-up은 가운데 분할선 없음
            canvas_w=A4_LANDSCAPE_W,
            canvas_h=A4_LANDSCAPE_H,
        )
        if overlay:
            _merge_overlay(writer, overlay)

    _write(writer, output_path)
    logger.info("composed 1up (oversize fallback): %s -> %s", pdf_src.name, output_path.name)


def _write(writer: PdfWriter, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
