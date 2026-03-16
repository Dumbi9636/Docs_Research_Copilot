# Docs Research Copilot

문서 또는 이미지 파일을 업로드하면 텍스트를 추출하고, Ollama 기반 로컬 LLM이 핵심 내용을 **한국어로 요약**해 주는 서비스입니다.
요약 결과는 txt / docx / pdf 형식으로 다운로드할 수 있습니다.

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
- 페이지 단위 hybrid 처리: 텍스트 레이어가 충분한 페이지는 텍스트로, 부족한 페이지는 자동으로 OCR 적용
- 텍스트 PDF, 스캔 PDF, 텍스트+이미지 혼합 PDF 모두 처리 가능

**docx**
- 일반 문단, 제목, 표(table) 셀 텍스트 추출
- 원문 순서(단락·표 순서) 유지
- 미지원: 텍스트 상자, 머리글/바닥글, 주석/각주, 이미지 내부 텍스트

**이미지 (png / jpg / jpeg)**
- Tesseract OCR (kor+eng 언어팩)
- 전처리 파이프라인: 그레이스케일 → 소형 이미지 확대 → 오토 컨트라스트 → 이진화
- Tesseract 옵션: `--psm 6 --oem 3`

### 요약 파이프라인

문서 길이에 따라 처리 방식이 자동으로 분기됩니다.

- **단일 요약**: 짧은 문서를 LLM 1회 호출로 직접 요약
- **청킹 요약**: 긴 문서를 chunk로 분할 → 각 chunk 중간 요약 → 최종 통합 요약

### 요약 결과 다운로드

요약이 완료되면 결과를 파일로 저장할 수 있습니다.

- 지원 출력 형식: **txt / docx / pdf**
- 다운로드 UI: 형식 선택(드롭다운) + 다운로드 버튼
- 파일명 규칙:
  - 원본 파일 업로드 시: `원본파일명_요약결과_YYYYMMDD.확장자`
  - 텍스트 직접 입력 시: `요약결과_YYYYMMDD.확장자`
- PDF 출력은 한글 폰트(맑은 고딕) 기반으로 생성

### 요약 중 취소

요약이 오래 걸리는 경우 진행 중인 요청을 취소할 수 있습니다.

- 로딩 중에만 취소 버튼 표시
- 취소 시 요약 결과를 초기화하고 안내 메시지 표시
- AbortController 기반 프론트 요청 취소 (1차 구현)

### 처리 단계(steps) 제공

요약 결과와 함께 파일 수신부터 최종 요약까지 각 처리 단계를 표시합니다.

```
파일 수신 완료
PDF 페이지별 혼합 추출 시작 (3페이지)
페이지 2: 이미지 → OCR 완료
PDF 추출 완료 (텍스트 2페이지, OCR 1페이지)
입력 검증 완료
문서 분할 완료 (4개 chunk)
chunk 1/4 요약 완료
...
최종 요약 생성 완료
```

### 한국어 출력 안정성

`qwen2.5:7b` 사용 시 중국어·한자 혼입 문제에 대응하는 보정 구조가 포함되어 있습니다.

- 프롬프트에 한국어 전용 출력 규칙 강화
- 최종 출력에서 한자·히라가나·카타카나 감지 시 한국어로 재작성
- 허용 영어 표현(기술 약어, 플랫폼 고유명사)은 whitelist로 관리

---

## 처리 흐름

```
txt   ──→ UTF-8 텍스트 추출
docx  ──→ 문단 · 표 셀 텍스트 추출
이미지 ──→ OCR (전처리 → Tesseract)              ┐
pdf   ──→ 페이지별: 텍스트 레이어 or OCR fallback  ┘
                   ↓
           공통 텍스트 검증
                   ↓
           summarizer (single or chunking)
                   ↓
           한국어 출력 보정
                   ↓
           { summary, steps }
                   ↓
           export (txt / docx / pdf 선택 다운로드)
```

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 백엔드 | Python 3.11+, FastAPI |
| 프론트엔드 | Next.js 16, React 19, TypeScript 5 |
| LLM | Ollama (`qwen2.5:7b`) |
| OCR | Tesseract OCR, pytesseract, Pillow |
| PDF 처리 | pypdf, pymupdf |
| Word 처리 | python-docx |
| PDF 생성 | fpdf2 |

---

## 프로젝트 구조

```
docs_research_copilot/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py            # 업로드·export 엔드포인트, 파일 형식 분기
│   │   ├── clients/
│   │   │   └── ollama.py            # Ollama HTTP 호출
│   │   ├── core/
│   │   │   └── config.py            # 환경설정
│   │   ├── schemas/
│   │   │   ├── summarize.py         # 요약 요청·응답 스키마
│   │   │   └── export.py            # export 요청 스키마
│   │   └── services/
│   │       ├── summarizer.py        # 요약 파이프라인 + 한국어 출력 보정
│   │       ├── pdf_extractor.py     # PDF 텍스트 추출 + 페이지 단위 OCR hybrid
│   │       ├── ocr_extractor.py     # 이미지 OCR (전처리 포함)
│   │       ├── export_service.py    # export 형식 분기
│   │       └── exporters/
│   │           ├── txt_exporter.py
│   │           ├── docx_exporter.py
│   │           └── pdf_exporter.py
│   ├── requirements.txt
│   └── .env                         # 환경변수 (git 미포함)
│
└── frontend/
    └── app/
        ├── components/
        │   ├── FileUploadInput.tsx   # 파일 업로드 존 UI
        │   ├── SummaryResult.tsx     # 요약 결과 및 steps 표시
        │   └── DownloadSection.tsx   # 다운로드 형식 선택 + 버튼
        ├── lib/
        │   └── api.ts               # 백엔드 API 호출
        └── page.tsx                 # 메인 페이지 (Header / Hero / MainCard / 기능 카드)
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

> 로컬 환경에서는 `SUMMARIZE_MAX_WORKERS=1`이 가장 안정적입니다.

> PDF 다운로드는 Windows 기본 폰트 맑은 고딕(`C:/Windows/Fonts/malgun.ttf`)을 사용합니다. 해당 경로에 폰트가 없으면 PDF 생성 시 오류가 발생합니다.

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
| OCR 오인식 | 띄어쓰기 과분리, 고유명사 오인식 가능 |
| 혼합형 PDF | 서로 다른 맥락의 페이지를 합칠 때 문맥 연결이 어색할 수 있음 |
| docx 내부 이미지 | OCR 미지원 — 이미지로만 구성된 내용은 추출되지 않음 |
| 텍스트 상자·도형 | docx / PDF 모두 미지원 |
| 영어 허용 정책 | whitelist 기반 — 미등록 고유명사가 금지 표현으로 오판될 수 있음 |
| 모델 의존성 | `qwen2.5:7b` 기준 튜닝 — 다른 모델에서는 출력 안정성이 다를 수 있음 |
| 요약 취소 | 브라우저 요청은 취소되지만 서버의 Ollama 추론은 완료될 때까지 계속 진행됨 |
| PDF 폰트 | 맑은 고딕 경로 고정 — Windows 외 환경에서 추가 설정 필요 |

---

## 향후 개선 방향

1. **혼합 문서 merge 프롬프트 개선** — 서로 다른 맥락 페이지 간 통합 요약 품질 향상
2. **docx 내부 이미지 OCR** — 내부 이미지 추출 후 기존 OCR 파이프라인 연결
3. **OCR 품질 개선** — 적응형 이진화, 노이즈 제거 등 전처리 강화
4. **영어 허용 정책 고도화** — 단순 whitelist를 넘어 문맥 기반 판단 검토
5. **LLM 교체 검토** — 로컬 모델 한계 확인 시 OpenAI / Gemini 등 API 모델 비교
6. **로그인 / 작업 기록** — DB 도입 후 사용자별 요약 이력 저장 및 재사용
