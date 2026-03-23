# Docs Research Copilot
<img width="1590" height="1570" alt="image" src="https://github.com/user-attachments/assets/d8d1c8e0-e753-4279-b187-200f3db59616" />

문서를 업로드하거나 텍스트를 입력하면 로컬 LLM(Ollama)이 핵심 내용을 **한국어로 요약**해 주는 서비스입니다.
요약 후에는 해당 문서를 기반으로 **후속 질문(문서 기반 대화)** 을 이어갈 수 있으며, 결과는 txt / docx / pdf로 다운로드할 수 있습니다.
회원가입/로그인 후 모든 요약 이력과 다운로드 이력이 Oracle DB에 저장되고, 마이페이지에서 확인할 수 있습니다.

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

## 현재 구현 완료 기능

| 영역 | 상태 | 내용 |
|------|------|------|
| 파일 텍스트 추출 | ✅ 완료 | txt / pdf / docx / png / jpg |
| 요약 파이프라인 | ✅ 완료 | 단일 요약 / 청킹 요약 자동 분기 |
| 요약 결과 다운로드 | ✅ 완료 | txt / docx / pdf 내보내기 |
| 요약 취소 | ✅ 완료 | AbortController 기반 |
| 회원가입 / 로그인 | ✅ 완료 | 이메일 + 비밀번호, JWT 인증 |
| 마이페이지 | ✅ 완료 | 사용자 이름 클릭 진입, 요약·다운로드 이력 조회 |
| 문서 기반 대화 | ✅ 완료 | 요약한 문서 원문 기반 Q&A, ChatPanel |
| 세션 복원 | ✅ 완료 | 새로고침 시 요약 결과·대화 내역 localStorage 복원 |
| 한국어 출력 보정 | ✅ 완료 | 요약 단계 보정 구현 (채팅 단계는 보완 필요) |
| 관리자 전용 debug | ✅ 완료 | ADMIN 역할만 처리 단계(steps) 노출 |
| 파일 변환 서비스 | 예정 | 대시보드에 비활성 카드로 표시 중 |

---

## 주요 기능

### 대시보드 구조

메인 홈(`/`)은 서비스 목록을 보여주는 대시보드입니다.
현재는 **요약 서비스**와 **파일 변환(예정)** 두 카드로 구성되며, 서비스가 추가될수록 카드가 늘어나는 구조입니다.

```
/           → 대시보드 홈 (서비스 카드 목록)
/summarize  → 요약 서비스 (파일 업로드 + 요약 + 문서 대화)
/mypage     → 마이페이지 (요약 이력 + 다운로드 이력)
/login      → 로그인
/register   → 회원가입
```

마이페이지는 별도 탭이 아니라 **헤더의 사용자 이름 클릭**으로 진입합니다.
활동 이력은 마이페이지 내부에 통합되어 있습니다.

---

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

---

### 요약 파이프라인

문서 길이에 따라 처리 방식이 자동으로 분기됩니다.

- **단일 요약**: 짧은 문서를 LLM 1회 호출로 직접 요약
- **청킹 요약**: 긴 문서를 chunk로 분할 → 각 chunk 중간 요약 → 최종 통합 요약

---

### 문서 기반 대화 (ChatPanel)

요약이 완료되면 요약 결과 하단에 ChatPanel이 활성화됩니다.
일반 자유 채팅이 아니라, **방금 요약한 문서의 원문을 컨텍스트로 사용하는 Q&A** 구조입니다.

**컨텍스트 선택 전략 (`chat_service.py`)**

| 조건 | 사용 컨텍스트 |
|------|--------------|
| `input_text` 없음 (구버전 기록) | 요약문 전용 fallback |
| 원문 50자 미만 (OCR 노이즈) | 요약문 전용 fallback |
| 원문 6000자 이하 | 원문 전체 + 요약문 |
| 원문 6000자 초과 | 요약문 + 키워드 기반 관련 문단 선택 |

- `history_id`를 기준으로 문서 컨텍스트를 연결합니다.
- 대화 내역은 `localStorage`에 user+document 단위로 저장됩니다.
- 토큰 만료 시 UI 안내 배너를 표시하되, 대화 기록은 삭제하지 않습니다.

> Phase 2 확장 포인트: `_select_relevant_paragraphs()` 함수를 임베딩 기반 코사인 유사도 검색으로 교체하면 외부 호출부 변경 없이 벡터 검색으로 전환됩니다.

---

### localStorage 세션 복원

`/summarize` 페이지를 새로고침해도 이전 작업 상태가 복원됩니다.

| 복원 항목 | 저장 위치 | 비고 |
|-----------|-----------|------|
| 요약 결과 | `docsresearch:user:{id}:summarize:current` | history_id, summary, steps, filename 포함 |
| 텍스트 입력 draft | `docsresearch:user:{id}:summarize:draft` | 600ms debounce 저장 |
| 문서 대화 기록 | `docchat:user:{id}:history:{historyId}` | 문서별 독립 저장 |

- 실제 `File` 객체는 복원하지 않습니다 (파일명만 표시).
- **로그아웃 시** 요약 세션과 채팅 기록 모두 초기화합니다.

---

### 요약 결과 다운로드

- 지원 출력 형식: **txt / docx / pdf**
- 파일명 규칙:
  - 원본 파일 업로드 시: `원본파일명_요약결과_YYYYMMDD.확장자`
  - 텍스트 직접 입력 시: `요약결과_YYYYMMDD.확장자`
- PDF 출력은 한글 폰트(맑은 고딕) 기반으로 생성

---

### 요약 이력 및 활동 이력 (마이페이지)

- 로그인 사용자의 모든 요약 요청(성공/실패 모두) Oracle DB에 기록
- 다운로드 이력도 DOWNLOAD_LOGS 테이블에 별도 기록
- 마이페이지에서 필터 / 검색 / 상세 보기 가능
- 다운로드 이력과 요약 이력은 `history_id`로 연결 (삭제 시 FK NULL 처리)

---

### 회원가입 / 로그인 / JWT 인증

- 이메일 + 비밀번호 기반 회원가입 (8자 이상)
- JWT access token (30분) + refresh token (7일) 발급
- access token 만료 시 자동 갱신 후 요청 1회 재시도
- 로그아웃 시 refresh token DB에서 무효화
- 페이지 새로고침 시 localStorage의 refresh token으로 세션 자동 복원
- 미로그인 상태에서는 요약 버튼 비활성화 + 안내 메시지 표시

---

### 처리 단계(steps) — ADMIN 전용

요약 결과와 함께 파일 수신부터 최종 요약까지 각 처리 단계를 표시합니다.
`user.role === "ADMIN"` 사용자에게만 노출됩니다.

```
파일 수신 완료
PDF 페이지별 혼합 추출 시작 (3페이지)
페이지 2: 이미지 → OCR 완료
문서 분할 완료 (4개 chunk)
chunk 1/4 요약 완료
...
최종 요약 생성 완료
```

---

## 처리 흐름

```
txt   ──→ UTF-8 텍스트 추출
docx  ──→ 문단 · 표 셀 텍스트 추출
이미지 ──→ OCR (전처리 → Tesseract)               ┐
pdf   ──→ 페이지별: 텍스트 레이어 or OCR fallback   ┘
                   ↓
           공통 텍스트 검증
                   ↓
           summarizer (single or chunking)
                   ↓
           한국어 출력 보정
                   ↓
           요약 이력 DB 저장 (input_text도 함께 저장)
                   ↓
           { summary, steps, history_id }
                   ↓
           ┌── 다운로드 (txt / docx / pdf)
           └── ChatPanel 활성화 → 문서 기반 Q&A
                   ↓
           /chat: input_text 기반 컨텍스트 구성 → Ollama 답변
```

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 백엔드 | Python 3.12+, FastAPI |
| 프론트엔드 | Next.js 15, React 19, TypeScript 5 |
| DB | Oracle XE 11g, SQLAlchemy 2.x |
| 인증 | JWT (python-jose), bcrypt (passlib) |
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
│   │   │   ├── routes.py            # /summarize, /summarize/file, /export, /chat
│   │   │   ├── auth.py              # /auth/register, login, refresh, logout
│   │   │   └── users.py             # /users/me, /users/me/summaries, /users/me/activities
│   │   ├── clients/
│   │   │   └── ollama.py            # Ollama HTTP 호출
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py          # JWT 생성/검증, 비밀번호 해시
│   │   │   └── dependencies.py      # get_current_user, require_admin
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py           # Oracle 연결 (thick mode)
│   │   │   └── models/              # User, SummaryHistory, RefreshToken, DownloadLog
│   │   ├── migrations/
│   │   │   └── 002_add_input_text.sql  # SUMMARY_HISTORY.input_text CLOB 추가
│   │   ├── repositories/            # DB CRUD 계층
│   │   ├── schemas/                 # Pydantic 스키마 (chat.py 포함)
│   │   └── services/
│   │       ├── summarizer.py        # 요약 파이프라인
│   │       ├── chat_service.py      # 문서 기반 Q&A 컨텍스트 구성 + Ollama 호출
│   │       └── ...
│   ├── requirements.txt
│   └── .env
│
└── frontend/
    └── app/
        ├── components/
        │   ├── Header.tsx            # 인증 상태 반영 헤더 (사용자명 → 마이페이지 링크)
        │   ├── FileUploadInput.tsx
        │   ├── SummaryResult.tsx     # 요약 결과 + steps (ADMIN만 steps 표시)
        │   ├── DownloadSection.tsx
        │   └── ChatPanel.tsx         # 문서 기반 대화 UI
        ├── lib/
        │   ├── api.ts               # 요약 / export / chat API 호출
        │   ├── auth-api.ts
        │   ├── auth-context.tsx     # AuthProvider (로그아웃 시 storage 초기화)
        │   ├── chatStorage.ts       # localStorage 채팅 기록 관리
        │   └── summarizeStorage.ts  # localStorage 요약 세션 / draft 관리
        ├── summarize/               # 요약 서비스 페이지
        ├── mypage/                  # 마이페이지 (요약 이력 + 다운로드 이력)
        ├── login/
        ├── register/
        └── page.tsx                 # 대시보드 홈
```

---

## 실행 방법

### 사전 준비

- Python 3.12+
- Node.js 18+
- Oracle XE 11g 설치 및 실행 중
- [Ollama](https://ollama.com) 설치 및 모델 pull
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) 설치 (kor+eng 언어팩 포함)

```bash
ollama pull qwen2.5:7b
```

### Oracle DB 초기 설정

Oracle에서 `COPILOT` 계정과 테이블/시퀀스를 생성합니다. (`.claude/README.md` 참고)

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

ORACLE_USER=COPILOT
ORACLE_PASSWORD=your_password
ORACLE_DSN=localhost:1521/XE
ORACLE_CLIENT_LIB_DIR=C:\oraclexe\app\oracle\product\11.2.0\server\bin

JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

---

## DB 설계

Oracle XE 11g의 `COPILOT` 스키마에 4개 테이블로 구성됩니다.
전체 DDL 및 Oracle 11g 호환 주의사항은 `.claude/README.md`를 참고하세요.

### 테이블 구성

#### USERS

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | NUMBER PK | 시퀀스 자동 증가 |
| email | VARCHAR2(320) UNIQUE | 로그인 식별자 |
| password_hash | VARCHAR2(256) | bcrypt 해시 |
| name | VARCHAR2(100) | 화면 표시용 이름, 헤더 표시 및 마이페이지 진입 링크에 사용 |
| role | VARCHAR2(20) | `USER` / `ADMIN` — JWT payload 포함, DB 조회 없이 권한 확인 |
| status | VARCHAR2(20) | `ACTIVE` / `SUSPENDED` |
| created_at / updated_at | TIMESTAMP | |

#### SUMMARY_HISTORY

| 컬럼 | 타입 | 설명 |
|------|------|------|
| history_id | NUMBER PK | |
| user_id | NUMBER FK | USERS 참조, NOT NULL |
| original_filename | VARCHAR2(500) | 파일 업로드 시만 저장 |
| file_type | VARCHAR2(20) | txt / pdf / docx / png / jpg / text |
| model_name | VARCHAR2(100) | |
| summary_mode | VARCHAR2(20) | `single` / `chunked` |
| input_chars | NUMBER | |
| output_summary | CLOB | 요약 결과 |
| **input_text** | **CLOB** | **원문 텍스트 — 문서 기반 Q&A 컨텍스트로 사용. 구버전 기록은 NULL** |
| status | VARCHAR2(20) | `SUCCESS` / `FAILED` |
| processing_time_ms | NUMBER | |
| created_at | TIMESTAMP | |

`input_text`는 마이그레이션(`002_add_input_text.sql`)으로 추가된 컬럼입니다. NULL인 기존 기록은 `/chat`에서 요약문 전용 fallback으로 처리합니다.

#### REFRESH_TOKENS

| 컬럼 | 타입 | 설명 |
|------|------|------|
| token_id | NUMBER PK | |
| user_id | NUMBER FK | |
| token_value | VARCHAR2(1000) UNIQUE | JWT 문자열 |
| expires_at | TIMESTAMP | 7일 |
| is_revoked | VARCHAR2(1) | Y / N |

#### DOWNLOAD_LOGS

| 컬럼 | 타입 | 설명 |
|------|------|------|
| log_id | NUMBER PK | |
| user_id | NUMBER FK | USERS 참조 |
| history_id | NUMBER FK | SUMMARY_HISTORY 참조 (요약 기록 삭제 시 NULL 처리) |
| file_format | VARCHAR2(20) | txt / docx / pdf |
| downloaded_at | TIMESTAMP | |

---

### PK 생성 전략 (Oracle 11g 제약)

Oracle 11g는 `GENERATED ALWAYS AS IDENTITY`를 지원하지 않습니다 (12c+ 전용).
SQLAlchemy `Sequence`로 연결하며, **DB 트리거는 사용하지 않습니다** (ORA-04098 방지).

---

## API 목록

### 인증

| Method | Path | 설명 |
|--------|------|------|
| POST | `/auth/register` | 회원가입 |
| POST | `/auth/login` | 로그인, access/refresh token 반환 |
| POST | `/auth/refresh` | access token 재발급 |
| POST | `/auth/logout` | 로그아웃, refresh token 무효화 |

### 사용자 / 마이페이지

| Method | Path | 설명 |
|--------|------|------|
| GET | `/users/me` | 내 정보 조회 |
| GET | `/users/me/summaries` | 요약 이력 조회 (skip/limit 페이지네이션) |
| GET | `/users/me/activities` | 다운로드 이력 조회 |

### 요약 / 내보내기 / 대화

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| POST | `/summarize` | 텍스트 요약 (인증 필요) |
| POST | `/summarize/file` | 파일 업로드 후 요약 (인증 필요) |
| POST | `/export` | 요약 결과 파일 다운로드 |
| POST | `/chat` | 문서 기반 Q&A (인증 필요, history_id로 문서 연결) |

---

## 최근 업데이트 (2026-03-23)

- **대시보드 구조 개편**: 메인 홈을 서비스 목록 대시보드로 개편, 요약 서비스는 `/summarize`로 분리
- **문서 기반 Q&A**: 요약 원문(`input_text`)을 활용하는 ChatPanel 구현 완료
- **localStorage 세션 복원**: 요약 결과·대화 내역·텍스트 draft 새로고침 후 복원
- **마이페이지 통합**: 활동 이력을 별도 페이지 대신 마이페이지 내부로 통합
- **ADMIN 전용 debug**: 처리 단계(steps)를 ADMIN 역할만 볼 수 있도록 제어
- **SUMMARY_HISTORY.input_text**: 원문 텍스트 CLOB 컬럼 추가 (마이그레이션 포함)

---

## 현재 한계

| 항목 | 상태 |
|---|---|
| 채팅 한국어 보정 | 일부 중국어(한자) 혼용 출력 발생 — 요약 단계 보정은 있으나 채팅 단계 후처리 미구현 |
| OCR 정확도 | 이미지 품질·해상도에 따라 결과가 크게 달라질 수 있음 |
| docx 내부 이미지 | OCR 미지원 |
| 텍스트 상자·도형 | docx / PDF 모두 미지원 |
| 요약 취소 | 브라우저 요청은 취소되지만 서버의 Ollama 추론은 계속 진행됨 |
| 채팅 DB 저장 | 현재 localStorage에만 저장 — 브라우저 삭제 시 소실 |
| 문단 검색 | 키워드 기반 (임베딩/벡터 검색 미구현) |
| PDF 폰트 | 맑은 고딕 경로 고정 — Windows 외 환경 추가 설정 필요 |

---

## 다음 작업 우선순위

1. **채팅 한국어 후처리** — `/chat` 응답에서 중국어 혼용 출력 정제 로직 추가
2. **파일 변환 서비스** — 대시보드에 이미 카드로 예고됨, 다음 서비스로 구현 예정
3. **채팅 이력 DB 저장** — `CHAT_SESSIONS` / `CHAT_MESSAGES` 테이블로 서버 영속화
4. **임베딩 기반 문단 검색** — `_select_relevant_paragraphs()` 를 벡터 유사도 검색으로 교체
5. **docx 내부 이미지 OCR** — 내부 이미지 추출 후 기존 OCR 파이프라인 연결
