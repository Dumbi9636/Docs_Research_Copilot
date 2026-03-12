# API 라우터 모듈
#
# 이 파일의 역할:
# 1. 입력 검증: 서비스 계층에 도달하기 전에 분명히 잘못된 요청을 걸러냅니다.
# 2. 에러 변환: 서비스에서 올라온 RuntimeError를 HTTP 상태 코드로 변환합니다.
#
# 비즈니스 로직은 summarizer.py에 작성되어 있습니다.

import io

from docx import Document
from docx.oxml.ns import qn
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services import summarizer
from app.services.ocr_extractor import extract_text_from_image
from app.services.pdf_extractor import extract_text_from_pdf

router = APIRouter()

# Swagger UI나 테스트 도구의 기본값("string", "example" 등)처럼
# 의미 없는 입력을 차단합니다.
PLACEHOLDER_VALUES = {"string", "text", "example", "sample"}

# 파일 업로드에서 허용하는 확장자 목록입니다.
# 새 형식을 지원할 때 여기에 추가하고, _extract_text()에 분기를 추가합니다.
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}


# ── 파일별 텍스트 추출 헬퍼 ──────────────────────────────────────────────────
#
# 각 함수는 파일 형식에 맞게 텍스트를 추출하고, 실패 시 HTTPException을 raise합니다.
# 라우트 함수는 확장자에 따라 적절한 헬퍼를 호출

def _read_txt(raw: bytes) -> str:
    """
    txt 파일 바이트를 UTF-8 문자열로 디코딩합니다.
    utf-8-sig를 사용해 Windows 메모장 등이 추가하는 BOM도 자동 제거합니다.
    """
    try:
        return raw.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        # UTF-8이 아닌 인코딩(EUC-KR 등)으로 저장된 파일은 여기서 걸립니다.
        raise HTTPException(
            status_code=400,
            detail="파일을 UTF-8로 읽을 수 없습니다. 파일을 UTF-8로 저장한 뒤 다시 시도해 주세요.",
        )



def _read_docx(raw: bytes) -> str:
    """
    Word(.docx) 파일 바이트에서 텍스트를 추출합니다.

    지원 범위:
    - 일반 문단 및 제목 (Heading 스타일 포함 — 내부적으로 모두 w:p 요소)
    - 표(table) 셀 텍스트 — 행 단위로 추출, 셀은 " | "로 구분

    제외 범위 (1차 버전):
    - 머리글/바닥글 (페이지 번호·문서 제목 등 요약 불필요 정보)
    - 텍스트 상자·도형 안 텍스트 (추출 복잡도 대비 빈도 낮음)
    - 주석(comment), 각주(footnote), 이미지 내 텍스트

    문서 구조 보존:
    - doc.element.body를 직접 순회해 단락과 표를 원문 순서대로 처리합니다.
    - doc.paragraphs + doc.tables를 따로 수집하면 문서 내 순서가 뒤섞입니다.

    병합 셀 처리:
    - 가로 병합 셀은 python-docx 내부에서 동일 텍스트가 반복됩니다.
    - dict.fromkeys()로 삽입 순서를 유지하면서 중복을 제거합니다.
    """
    try:
        doc = Document(io.BytesIO(raw))
    except Exception:
        # python-docx는 zipfile.BadZipFile, ValueError 등 다양한 예외를 낼 수 있습니다.
        # .doc(구형 바이너리 포맷)을 올리면 여기서 걸립니다.
        raise HTTPException(
            status_code=400,
            detail=(
                "Word 파일을 읽을 수 없습니다. "
                "파일이 손상되었거나 올바른 .docx 형식이 아닙니다. "
                "구형 .doc 파일은 지원하지 않으며, .docx로 변환 후 업로드해 주세요."
            ),
        )

    parts: list[str] = []

    for block in doc.element.body:
        # namespace URI를 제거해 로컬 태그 이름만 비교합니다.
        # 예: "{http://...wordml...}p" → "p"
        tag = block.tag.split("}")[-1]

        if tag == "p":
            # 단락 및 제목: w:t 요소의 텍스트를 이어붙입니다.
            # run 분리나 스타일 구분 없이 순수 텍스트만 추출합니다.
            text = "".join(
                node.text or ""
                for node in block.iter()
                if node.tag.endswith("}t")
            ).strip()
            if text:
                parts.append(text)

        elif tag == "tbl":
            # 표: 행(w:tr) → 셀(w:tc) 순서로 순회합니다.
            for row in block.findall(".//" + qn("w:tr")):
                seen: dict[str, None] = {}  # 삽입 순서 유지 + 중복 제거
                for cell in row.findall(".//" + qn("w:tc")):
                    cell_text = "".join(
                        node.text or ""
                        for node in cell.iter()
                        if node.tag.endswith("}t")
                    ).strip()
                    if cell_text:
                        seen[cell_text] = None  # dict는 삽입 순서를 보장합니다 (Python 3.7+)
                if seen:
                    parts.append(" | ".join(seen.keys()))

    text = "\n\n".join(parts).strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail=(
                "Word 파일에서 텍스트를 추출할 수 없습니다. "
                "문서 내용이 비어 있거나, 텍스트 상자·이미지로만 구성된 파일일 수 있습니다."
            ),
        )

    return text


# ── 라우트 ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/summarize", response_model=SummarizeResponse)
def summarize_route(request: SummarizeRequest):
    text = request.text.strip()

    # ── 입력 검증 ────────────────────────────────────────────────────────────
    # 여기서 검증하는 이유: 잘못된 입력이 서비스 계층까지 흘러들어가면
    # 불필요한 LLM 호출이 발생하거나 모호한 에러가 날 수 있습니다.
    # 경계(boundary)에서 일찍 차단하면 서비스 계층은 "유효한 입력만 온다"고 가정할 수 있습니다.

    if not text:
        raise HTTPException(status_code=400, detail="텍스트가 비어 있습니다.")

    # Swagger UI 기본값 등 무의미한 placeholder 차단
    if text.lower() in PLACEHOLDER_VALUES:
        raise HTTPException(status_code=400, detail="실제 문서 내용을 입력해 주세요. 예시 텍스트는 허용되지 않습니다.")

    # 10자 미만은 요약 의미가 없고 LLM이 품질 낮은 응답을 낼 수 있습니다.
    if len(text) < 10:
        raise HTTPException(status_code=400, detail="텍스트가 너무 짧습니다. 요약할 내용을 충분히 입력해 주세요.")

    # ── 서비스 호출 및 에러 변환 ─────────────────────────────────────────────
    try:
        return summarizer.summarize(text)
    except RuntimeError as e:
        # RuntimeError를 502 Bad Gateway로 변환합니다.
        # 502를 쓰는 이유: 우리 서버가 의존하는 외부 서버(Ollama)에서 문제가 발생했기 때문입니다.
        # 클라이언트 잘못(4xx)이 아니라, 백엔드가 의존하는 서비스 문제(5xx)입니다.
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/summarize/file", response_model=SummarizeResponse)
async def summarize_file_route(file: UploadFile = File(...)):
    """
    txt, pdf, docx 파일을 업로드받아 기존 요약 파이프라인으로 처리합니다.

    async def를 쓰는 이유: UploadFile.read()가 비동기 I/O이기 때문입니다.

    흐름:
      1. 파일 수신 및 확장자 검증
      2. 확장자에 따라 _read_txt() / _read_pdf() / _read_docx()로 텍스트 추출
      3. 텍스트 내용 검증 (비어있음 / 너무 짧음)
      4. summarizer.summarize(text) 호출 — 기존 요약 파이프라인 그대로 사용
      5. 파일 처리 단계(pre_steps)를 summarizer steps 앞에 붙여 반환

    새 파일 형식 추가 방법:
      1. ALLOWED_EXTENSIONS에 확장자 추가
      2. 해당 형식의 _read_XXX() 함수 작성
      3. 아래 추출 분기에 elif 추가
    """
    # ── 파일 형식 검증 ───────────────────────────────────────────────────────
    filename = file.filename or ""
    # rsplit으로 마지막 점 이후를 확장자로 취급합니다.
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="txt, pdf, docx, png, jpg, jpeg 파일만 업로드할 수 있습니다.",
        )

    pre_steps: list[str] = ["파일 수신 완료"]

    # ── 파일 읽기 및 텍스트 추출 ─────────────────────────────────────────────
    raw = await file.read()

    if ext == ".txt":
        text = _read_txt(raw)
        pre_steps.append("텍스트 추출 완료")
    elif ext == ".pdf":
        try:
            text, pdf_steps = extract_text_from_pdf(raw)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        pre_steps.extend(pdf_steps)
    elif ext == ".docx":
        text = _read_docx(raw)
        pre_steps.append("Word 텍스트 추출 완료")
    else:  # .png / .jpg / .jpeg
        try:
            text = extract_text_from_image(raw)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        pre_steps.append("이미지 OCR 추출 완료")
        # ── OCR 원문 디버그 ───────────────────────────────────────────────────
        # OCR 품질 확인용 임시 로그입니다. 서버 콘솔과 steps 양쪽에 남깁니다.
        # 인식 결과가 기대와 다를 때 이 출력으로 전처리/psm 튜닝 방향을 잡습니다.
        # 품질 확인 후 제거하거나 로그 레벨로 격하해도 됩니다.
        _ocr_preview = text[:300].replace("\n", " ↵ ")
        print(f"[OCR RAW] {_ocr_preview}")
        pre_steps.append(f"[OCR 원문 미리보기] {_ocr_preview}")

    # ── 텍스트 내용 검증 ─────────────────────────────────────────────────────
    # 파일은 선택됐지만 내용이 없거나 너무 짧은 경우를 걸러냅니다.
    if not text:
        raise HTTPException(status_code=400, detail="파일 내용이 비어 있습니다.")

    if len(text) < 10:
        raise HTTPException(
            status_code=400,
            detail="텍스트가 너무 짧습니다. 요약할 내용이 충분한 파일을 업로드해 주세요.",
        )

    # ── 요약 실행 및 steps 병합 ──────────────────────────────────────────────
    try:
        result = summarizer.summarize(text)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 파일 처리 단계를 요약 단계 앞에 붙여 하나의 흐름으로 반환합니다.
    return SummarizeResponse(summary=result.summary, steps=pre_steps + result.steps)
