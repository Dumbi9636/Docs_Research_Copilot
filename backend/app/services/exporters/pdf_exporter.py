import os
from datetime import datetime

from fpdf import FPDF

# Windows 기본 탑재 폰트 (맑은 고딕)
# 설치 경로가 다른 경우 아래 경로를 수정하거나, 프로젝트 내 폰트 파일 경로를 지정하세요.
_FONT_REGULAR = r"C:/Windows/Fonts/malgun.ttf"
_FONT_BOLD = r"C:/Windows/Fonts/malgunbd.ttf"


def _load_fonts(pdf: FPDF) -> None:
    if not os.path.exists(_FONT_REGULAR):
        raise RuntimeError(
            "PDF 생성에 필요한 한글 폰트(맑은 고딕)를 찾을 수 없습니다. "
            f"경로를 확인해 주세요: {_FONT_REGULAR}"
        )
    pdf.add_font("Malgun", "", _FONT_REGULAR)
    if os.path.exists(_FONT_BOLD):
        pdf.add_font("Malgun", "B", _FONT_BOLD)
    else:
        # 볼드 폰트가 없으면 일반 폰트로 대체합니다.
        pdf.add_font("Malgun", "B", _FONT_REGULAR)


def export(summary: str, source_filename: str) -> bytes:
    pdf = FPDF()
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()
    _load_fonts(pdf)

    # ── 제목 ──────────────────────────────────────────────────────────────────
    pdf.set_font("Malgun", "B", 16)
    pdf.cell(0, 12, "요약 결과", new_x="LMARGIN", new_y="NEXT")

    # ── 메타데이터 ─────────────────────────────────────────────────────────────
    meta_parts: list[str] = []
    if source_filename:
        meta_parts.append(f"원본 파일: {source_filename}")
    meta_parts.append(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    pdf.set_font("Malgun", "", 9)
    pdf.set_text_color(136, 136, 136)
    pdf.cell(0, 6, "  |  ".join(meta_parts), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    # ── 구분선 ─────────────────────────────────────────────────────────────────
    pdf.ln(3)
    pdf.set_draw_color(221, 221, 221)
    page_width = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_width, pdf.get_y())
    pdf.ln(5)

    # ── 본문 ──────────────────────────────────────────────────────────────────
    pdf.set_font("Malgun", "", 11)
    for line in summary.split("\n"):
        if line.strip():
            pdf.multi_cell(0, 7, line)
        else:
            pdf.ln(4)

    return bytes(pdf.output())
