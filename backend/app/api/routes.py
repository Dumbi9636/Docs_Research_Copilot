from fastapi import APIRouter, HTTPException
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services import summarizer

router = APIRouter()

# Swagger UI 기본값("string")처럼 의미 없는 입력을 거부합니다.
PLACEHOLDER_VALUES = {"string", "text", "example", "sample"}


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/summarize", response_model=SummarizeResponse)
def summarize_route(request: SummarizeRequest):
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="텍스트가 비어 있습니다.")

    if text.lower() in PLACEHOLDER_VALUES:
        raise HTTPException(status_code=400, detail="실제 문서 내용을 입력해 주세요. 예시 텍스트는 허용되지 않습니다.")

    if len(text) < 10:
        raise HTTPException(status_code=400, detail="텍스트가 너무 짧습니다. 요약할 내용을 충분히 입력해 주세요.")

    try:
        return summarizer.summarize(text)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
