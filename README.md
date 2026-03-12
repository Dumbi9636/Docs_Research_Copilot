# Docs Research Copilot

문서 파일을 업로드하면 텍스트를 추출하고 Ollama 기반 LLM이 핵심 내용을 한국어로 요약해 주는 서비스입니다.

---

## 지원 입력 형식

| 형식 | 처리 방식 |
|---|---|
| `.txt` | UTF-8 텍스트 직접 읽기 |
| `.pdf` | 텍스트 레이어 추출 + 이미지 페이지 OCR (페이지 단위 hybrid) |
| `.docx` | 문단·제목·표 셀 텍스트 추출 |
| `.png` `.jpg` `.jpeg` | Tesseract OCR로 이미지 텍스트 추출 |

직접 텍스트 입력도 지원합니다.

---

## 주요 기능

### 파일 형식별 텍스트 추출

**txt**
- UTF-8 / UTF-8 BOM 자동 처리

**pdf**
- pypdf로 텍스트 레이어 추출 시도
- 페이지별로 텍스트가 충분하면 텍스트 사용, 부족하면 pymupdf로 이미지 변환 후 OCR 적용
- 텍스트 PDF, 스캔 PDF, 혼합형 PDF 모두 처리 가능

**docx**
- 일반 문단, 제목, 표(table) 셀 텍스트 추출
- 원문 순서(단락·표 순서)를 유지하며 추출
- 미지원: 텍스트 상자, 머리글/바닥글, 주석/각주, 이미지 내부 텍스트

**이미지 (png / jpg / jpeg)**
- Tesseract OCR (kor+eng 언어팩)
- 전처리: 그레이스케일 → 소형 이미지 확대 → 오토 컨트라스트 → 이진화
- Tesseract 옵션: `--psm 6 --oem 3`
- OCR 원문 미리보기를 steps와 서버 로그에 기록 (디버깅용)

### 요약 파이프라인

문서 길이에 따라 처리 방식이 자동으로 분기됩니다.

- **단일 요약**: 짧은 문서를 LLM 1회 호출로 직접 요약
- **청킹 요약**: 긴 문서를 chunk로 분할 → 각 chunk 중간 요약(병렬) → 최종 통합 요약

### 처리 단계(steps) 제공

요약 결과와 함께 파일 수신부터 최종 요약까지 각 단계를 사용자에게 표시합니다.

```
파일 수신 완료
PDF 페이지별 혼합 추출 시작 (3페이지)
페이지 2: 이미지 → OCR 완료
PDF 추출 완료 (텍스트 2페이지, OCR 1페이지)
입력 검증 완료
문서 분할 완료 (4개 chunk)
chunk 병렬 요약 시작 (4개, 동시 1개)
chunk 1/4 요약 완료
...
최종 요약 생성 완료
```

---

## 처리 흐름

```
txt   ──→ UTF-8 텍스트 추출
docx  ──→ 문단 · 표 셀 텍스트 추출
이미지 ──→ OCR (전처리 → Tesseract)              ┐
pdf   ──→ 페이지별: 텍스트 레이어 or OCR fallback  ┘
                   ↓
           공통 텍스트 검증 (빈 내용 · 너무 짧은 입력 차단)
                   ↓
           summarizer (single or chunking)
                   ↓
           한국어 출력 보정 (CJK · 금지 영어 구절 감지 → 재작성)
                   ↓
           { summary, steps }
```

---

## 프로젝트 구조

```
docs_research_copilot/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py            # 업로드 엔드포인트, 파일 형식 분기, 에러 변환
│   │   ├── clients/
│   │   │   └── ollama.py            # Ollama HTTP 호출 전담
│   │   ├── core/
│   │   │   └── config.py            # 환경설정 (pydantic-settings, .env)
│   │   ├── schemas/
│   │   │   └── summarize.py         # 요청·응답 스키마
│   │   └── services/
│   │       ├── summarizer.py        # single / chunk / merge 요약, 한국어 출력 보정
│   │       ├── pdf_extractor.py     # PDF 텍스트 추출 + 페이지 단위 OCR hybrid
│   │       └── ocr_extractor.py     # 이미지 OCR 추출 (전처리 포함)
│   ├── requirements.txt
│   └── .env                         # 환경변수 (git 미포함)
│
└── frontend/
    └── app/
        ├── components/
        │   ├── FileUploadInput.tsx   # 파일 선택 UI (accept 설정 포함)
        │   └── SummaryResult.tsx     # 요약 결과 및 steps 표시
        ├── lib/
        │   └── api.ts               # 백엔드 API 호출 함수
        └── page.tsx                 # 메인 페이지
```

---

## 한국어 출력 안정성

`qwen2.5:7b` 사용 시 요약 출력에 중국어·한자가 혼입되는 문제가 있었습니다.

**관찰된 문제 유형**

| 유형 | 예시 |
|---|---|
| 중국어 지시 메타 문구 | `继续用中文`, `若要概括...`, `请用韩语...` |
| 본문 항목 중국어 출력 | `- 编程`, `- 散步`, `- 喝咖啡` |

**적용한 대응**

- single / chunk / merge 프롬프트에 한국어 전용 출력 규칙 강화
  - 한자·히라가나·카타카나 1자도 허용하지 않음
  - 목록 항목 포함 전체 출력 대상
- `_clean_summary_prefix`: 앞머리 메타 문구 제거
- `_strip_language_noise`: 중국어 오염 라인 비율 검사 후 제거

**최종 출력 감지 및 재작성 구조**

```
_has_forbidden_output(text)
    ├── _has_cjk()              한자 · 히라가나 · 카타카나 1자 이상 → True
    └── _has_forbidden_english() 2개 이상 연속 영어 단어 중 whitelist 外 존재 → True

감지 시 → _korean_rewrite()     의미 보존 + 한국어 재작성 1회
재작성 후 재검증 → 잔존 시 step 기록
재작성 실패 시 → 원본 결과 유지 (전체 요약 중단 없음)
```

**허용 영어 표현 (whitelist)**

기술 약어·플랫폼 고유명사는 한국어 문장 안에서도 허용합니다.

```
AI, ML, DL, NLP, LLM, GPT, API, OCR, PDF
CPU, GPU, RAM, URL, HTTP, JSON, SQL ...
FastAPI, Python, Tesseract, Docker, GitHub
Qwen, ChatGPT, Claude, Ollama, OpenAI, Gemini
Google, Naver, Kakao, Microsoft, Apple, Amazon ...
```

---

## 실행 방법

### 사전 준비

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) 설치 및 모델 pull
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) 설치 (kor+eng 언어팩 포함)

```bash
# Ollama 모델 설치
ollama pull qwen2.5:7b
```

### 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# .env 파일 생성
cp .env.example .env          # 없으면 직접 작성

uvicorn app.main:app --reload --port 8000
```

**.env 주요 설정**

```env
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=180
TARGET_CHUNK_SIZE=2000
SUMMARIZE_MAX_WORKERS=1
```

> `SUMMARIZE_MAX_WORKERS=1`이 로컬 환경에서 가장 안정적입니다.
> GPU 병렬 추론 환경에서는 `OLLAMA_NUM_PARALLEL`과 함께 2 이상으로 조정할 수 있습니다.

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

---

## 현재 한계

| 항목 | 상태 |
|---|---|
| OCR 정확도 | 이미지 품질·해상도에 따라 결과가 크게 달라질 수 있음 |
| 이미지/스캔 페이지 | 띄어쓰기 과분리·오인식 가능 |
| 혼합형 PDF | 페이지별 추출은 되지만, 서로 다른 맥락의 페이지를 합칠 때 문맥 연결이 어색할 수 있음 |
| docx 내부 이미지 | OCR 미지원 — 이미지로만 구성된 내용은 추출되지 않음 |
| 텍스트 상자·도형 | docx / PDF 모두 미지원 |
| 영어 허용 정책 | whitelist 기반 1차 구현 — 미등록 고유명사는 금지 표현으로 오판될 수 있음 |
| 모델 의존성 | qwen2.5:7b 기준 튜닝 — 다른 모델에서 출력 안정성이 다를 수 있음 |

---

## 향후 개선 방향

1. **docx 내부 이미지 OCR** — zipfile 기반 이미지 추출 후 기존 OCR 파이프라인 연결
2. **혼합 문서 merge 프롬프트 개선** — 서로 다른 맥락 페이지 간 통합 요약 품질 향상
3. **OCR 추가 개선** — 적응형 이진화, 노이즈 제거 등 전처리 강화
4. **영어 허용 정책 고도화** — 단순 whitelist를 넘어 문맥 기반 판단
5. **LLM 교체 검토** — 로컬 모델 한계 확인 시 OpenAI / Gemini 등 API 모델 비교
