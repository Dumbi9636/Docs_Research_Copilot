# PDF 텍스트 추출 모듈
#
# 이 모듈의 책임: PDF 바이트를 받아 텍스트를 반환하고, 처리 단계를 함께 반환합니다.
#
# 추출 전략 — 페이지 단위 hybrid:
#   각 페이지를 독립적으로 판단합니다.
#   ① 페이지 텍스트 ≥ _TEXT_THRESHOLD_PER_PAGE 자  → 텍스트 레이어 그대로 사용
#   ② 페이지 텍스트 <  _TEXT_THRESHOLD_PER_PAGE 자  → 해당 페이지만 이미지 변환 후 OCR
#   페이지별 결과를 원문 순서대로 합쳐 최종 텍스트를 반환합니다.
#
#   기존 문서 단위 fallback과의 차이:
#   - 이전: 전체 평균이 기준 이상이면 OCR을 아예 타지 않음 → 혼합형 PDF에서 이미지 페이지 누락
#   - 현재: 페이지별로 판단하므로 텍스트/이미지가 섞인 PDF도 모두 반영
#
# 의존성:
#   pip: pypdf (기존), pymupdf (OCR fallback용 — 선택 의존성)
#        pymupdf 미설치 시 이미지 페이지는 건너뛰고 step에 기록합니다.

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.ocr_extractor import extract_text_from_image

# 페이지 텍스트가 이 값 미만이면 해당 페이지를 이미지로 판단합니다.
# 30자 기준: 텍스트 레이어 PDF는 대부분 이를 초과하고,
# 이미지 페이지·빈 페이지는 0~수 자 수준입니다.
_TEXT_THRESHOLD_PER_PAGE = 30

# pymupdf(fitz)는 선택 의존성입니다.
# 모듈 로드 시점에 import 실패를 조용히 처리하고,
# 실제 OCR이 필요한 페이지를 만났을 때 미설치 여부를 step에 기록합니다.
try:
    import fitz  # pymupdf
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False

# PDF 페이지를 이미지로 렌더링할 해상도(DPI)입니다.
# 200 DPI: 속도와 OCR 인식률의 균형점.
_RENDER_DPI = 200


def _render_page_as_png(fitz_doc, page_index: int) -> bytes:
    """
    pymupdf로 PDF 페이지를 PNG 바이트로 렌더링합니다.

    Args:
        fitz_doc: fitz.Document 인스턴스
        page_index: 0-based 페이지 인덱스

    Returns:
        PNG 이미지 바이트

    Raises:
        RuntimeError: 렌더링 실패 시
    """
    try:
        zoom = _RENDER_DPI / 72  # 1pt = 1/72인치 → DPI 환산
        matrix = fitz.Matrix(zoom, zoom)
        pix = fitz_doc[page_index].get_pixmap(matrix=matrix)
        return pix.tobytes("png")
    except Exception as e:
        raise RuntimeError(f"페이지 이미지 변환 실패: {e}")


def extract_text_from_pdf(raw: bytes) -> tuple[str, list[str]]:
    """
    PDF 바이트에서 텍스트를 추출합니다 (페이지 단위 hybrid 방식).

    각 페이지를 독립적으로 판단해 텍스트 레이어 또는 OCR 중 적합한 방법을 선택합니다.
    텍스트/이미지가 혼합된 PDF에서도 모든 페이지 내용을 반영합니다.

    Returns:
        (text, steps): 추출된 텍스트와 처리 단계 목록.
            steps는 routes.py의 pre_steps에 extend됩니다.

    Raises:
        RuntimeError: PDF 파싱 실패 / 전체 페이지 텍스트가 비어 있는 경우
    """
    steps: list[str] = []

    # ── PDF 열기 ──────────────────────────────────────────────────────────────
    try:
        reader = PdfReader(io.BytesIO(raw))
    except PdfReadError:
        raise RuntimeError(
            "PDF 파일을 읽을 수 없습니다. "
            "파일이 손상되었거나 올바른 PDF 형식이 아닙니다."
        )
    except Exception:
        raise RuntimeError(
            "PDF 파일을 처리할 수 없습니다. "
            "암호화되지 않은 일반 PDF 파일을 업로드해 주세요."
        )

    page_count = len(reader.pages)
    steps.append(f"PDF 페이지별 혼합 추출 시작 ({page_count}페이지)")

    # ── 페이지 단위 처리 ──────────────────────────────────────────────────────
    parts: list[str] = []  # 페이지 순서를 보장하며 결과를 쌓습니다.
    text_count = 0
    ocr_count = 0
    skip_count = 0

    # pymupdf Document는 OCR이 필요한 첫 페이지에서만 열고,
    # 이후 페이지에서 재사용합니다. (lazy open)
    fitz_doc = None
    fitz_open_failed = False  # 한 번 실패하면 이후 페이지에서 재시도하지 않습니다.

    for i, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()

        if len(page_text) >= _TEXT_THRESHOLD_PER_PAGE:
            # ① 텍스트 레이어가 충분한 페이지 → 그대로 사용
            parts.append(page_text)
            text_count += 1
            continue

        # ② 텍스트가 부족한 페이지 → OCR 시도
        if not _PYMUPDF_AVAILABLE:
            # pymupdf 미설치 경고는 처음 한 번만 step에 남깁니다.
            if skip_count == 0:
                steps.append(
                    "이미지 페이지 감지됐으나 pymupdf 미설치 — "
                    "pip install pymupdf 후 재시도하면 OCR 처리됩니다."
                )
            skip_count += 1
            continue

        # fitz Document를 아직 열지 않았으면 이 시점에 엽니다.
        if fitz_doc is None and not fitz_open_failed:
            try:
                fitz_doc = fitz.open(stream=raw, filetype="pdf")
            except Exception as e:
                fitz_open_failed = True
                steps.append(f"PDF 이미지 변환 준비 실패 ({e}) — 이미지 페이지를 건너뜀")
                skip_count += 1
                continue

        if fitz_open_failed:
            skip_count += 1
            continue

        try:
            img_bytes = _render_page_as_png(fitz_doc, i - 1)  # 0-based index
            ocr_text = extract_text_from_image(img_bytes)
            parts.append(ocr_text)
            ocr_count += 1
            steps.append(f"페이지 {i}: 이미지 → OCR 완료")
        except RuntimeError as e:
            skip_count += 1
            steps.append(f"페이지 {i}: OCR 실패 — 건너뜀 ({e})")

    if fitz_doc is not None:
        fitz_doc.close()

    # ── 결과 검증 및 최종 step ────────────────────────────────────────────────
    final_text = "\n\n".join(parts).strip()
    if not final_text:
        raise RuntimeError(
            "PDF에서 텍스트를 추출할 수 없습니다. "
            "텍스트 레이어가 없고 OCR 처리도 실패했습니다. "
            "이미지 품질이 너무 낮거나 텍스트가 포함되지 않은 파일일 수 있습니다."
        )

    # 처리 결과를 한 줄 요약합니다.
    summary_parts: list[str] = []
    if text_count:
        summary_parts.append(f"텍스트 {text_count}페이지")
    if ocr_count:
        summary_parts.append(f"OCR {ocr_count}페이지")
    if skip_count:
        summary_parts.append(f"건너뜀 {skip_count}페이지")
    steps.append(f"PDF 추출 완료 ({', '.join(summary_parts)})")

    return final_text, steps
