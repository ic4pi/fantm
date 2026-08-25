import io
import logging
import requests
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

logger = logging.getLogger(__name__)


def _fetch_image_flowable(url: str, max_width_mm: float, max_height_mm: float):
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image(io.BytesIO(resp.content))
        avail_w, avail_h = max_width_mm * mm, max_height_mm * mm
        ratio = min(avail_w / img.drawWidth, avail_h / img.drawHeight)
        img.drawWidth *= ratio
        img.drawHeight *= ratio
        return img
    except Exception as e:
        logger.warning("Could not fetch illustration %s: %s", url, e)
        return None


def build_book_pdf(book: dict, chapters: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A5, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("BookTitle", parent=styles["Title"], fontSize=22, alignment=TA_CENTER, spaceAfter=12)
    premise_style = ParagraphStyle("Premise", parent=styles["Italic"], fontSize=10, alignment=TA_CENTER, textColor="#333333")
    chapter_title_style = ParagraphStyle("ChapterTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=10, alignment=TA_CENTER)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=15, alignment=TA_JUSTIFY, spaceAfter=8)

    elements = []
    cover_img = _fetch_image_flowable(book.get("cover_image_url"), 90, 110)
    if cover_img:
        elements.append(Spacer(1, 8 * mm))
        elements.append(cover_img)
        elements.append(Spacer(1, 8 * mm))
    else:
        elements.append(Spacer(1, 40 * mm))
    elements.append(Paragraph(book.get("title", "Untitled"), title_style))
    if book.get("premise"):
        elements.append(Paragraph(book["premise"], premise_style))
    elements.append(PageBreak())

    for ch in chapters:
        elements.append(Paragraph(f"Chapter {ch['index'] + 1}: {ch['title']}", chapter_title_style))
        elements.append(Spacer(1, 4 * mm))
        ch_img = _fetch_image_flowable(ch.get("image_url"), 100, 70)
        if ch_img:
            elements.append(ch_img)
            elements.append(Spacer(1, 6 * mm))
        for para in (ch.get("content") or "").split("\n\n"):
            para = para.strip()
            if para:
                elements.append(Paragraph(para.replace("\n", "<br/>"), body_style))
        elements.append(PageBreak())

    doc.build(elements)
    return buf.getvalue()
