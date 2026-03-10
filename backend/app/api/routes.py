# API 라우터 모듈
#
# 이 파일의 역할:
# 1. 입력 검증: 서비스 계층에 도달하기 전에 분명히 잘못된 요청을 걸러냅니다.
# 2. 에러 변환: 서비스에서 올라온 RuntimeError를 HTTP 상태 코드로 변환합니다.
#
# 비즈니스 로직은 summarizer.py에 작성되어 있습니다.

from fastapi import APIRouter, HTTPException, UploadFile, File
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services import summarizer

router = APIRouter()

# Swagger UI나 테스트 도구의 기본값("string", "example" 등)처럼
# 의미 없는 입력을 차단합니다.
# LLM 호출 비용을 낭비하지 않고 사용자에게 명확한 안내를 줍니다.
PLACEHOLDER_VALUES = {"string", "text", "example", "sample"}


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
    txt 파일을 업로드받아 기존 요약 파이프라인으로 처리합니다.

    async def를 쓰는 이유: UploadFile.read()가 비동기 I/O이기 때문입니다.
    summarize_route(텍스트 입력)는 I/O 없이 단순 JSON을 받으므로 동기 함수입니다.

    steps 병합 전략:
    - 파일 처리 단계(pre_steps)를 먼저 수집합니다.
    - summarizer.summarize()가 반환한 steps 앞에 prepend합니다.
    - summarizer.py 내부는 전혀 수정하지 않아도 됩니다.
    """
    # ── 파일 형식 검증 ───────────────────────────────────────────────────────
    # .txt 이외의 파일(pdf, docx 등)은 이번 단계에서 지원하지 않습니다.
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=400,
            detail="txt 파일만 업로드할 수 있습니다. pdf, docx 등은 아직 지원하지 않습니다.",
        )

    pre_steps: list[str] = ["파일 수신 완료"]

    # ── 파일 내용 읽기 및 디코딩 ─────────────────────────────────────────────
    raw = await file.read()

    try:
        # utf-8-sig는 BOM(Byte Order Mark) 포함 UTF-8 파일도 처리합니다.
        # 메모장 등 Windows 기본 편집기로 저장한 txt 파일에 BOM이 붙는 경우가 많습니다.
        text = raw.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        # UTF-8이 아닌 인코딩(EUC-KR 등)으로 저장된 파일은 여기서 걸립니다.
        raise HTTPException(
            status_code=400,
            detail="파일을 UTF-8로 읽을 수 없습니다. 파일을 UTF-8로 저장한 뒤 다시 시도해 주세요.",
        )

    pre_steps.append("텍스트 추출 완료")

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
