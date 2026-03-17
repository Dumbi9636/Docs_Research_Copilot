# Docs Research Copilot

문서 또는 이미지 파일을 업로드하면 텍스트를 추출하고, Ollama 기반 로컬 LLM이 핵심 내용을 **한국어로 요약**해 주는 서비스입니다.
요약 결과는 txt / docx / pdf 형식으로 다운로드할 수 있으며, 회원가입 후 로그인하면 모든 요약 이력이 DB에 저장됩니다.

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

### 회원가입 / 로그인 / JWT 인증

- 이메일 + 비밀번호 기반 회원가입 (8자 이상)
- JWT access token (30분) + refresh token (7일) 발급
- access token 만료 시 자동 갱신 후 요청 1회 재시도
- 로그아웃 시 refresh token DB에서 무효화
- 페이지 새로고침 시 localStorage의 refresh token으로 세션 자동 복원
- 미로그인 상태에서는 요약 버튼 비활성화 + 안내 메시지 표시

### 요약 이력 저장

- 로그인 사용자의 모든 요약 요청(성공/실패 모두)이 Oracle DB에 기록됨
- 저장 항목: 모델명, 요약 방식, 입력 글자수, 요약 결과, 상태, 파일 정보, 처리 시간
- `GET /users/me/summaries` API로 이력 조회 가능

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
           요약 이력 DB 저장
                   ↓
           { summary, steps }
                   ↓
           export (txt / docx / pdf 선택 다운로드)
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
│   │   │   ├── routes.py            # /summarize, /summarize/file, /export
│   │   │   ├── auth.py              # /auth/register, login, refresh, logout
│   │   │   └── users.py             # /users/me, /users/me/summaries
│   │   ├── clients/
│   │   │   └── ollama.py            # Ollama HTTP 호출
│   │   ├── core/
│   │   │   ├── config.py            # 환경설정 (pydantic-settings)
│   │   │   ├── security.py          # JWT 생성/검증, 비밀번호 해시
│   │   │   └── dependencies.py      # get_current_user, require_admin
│   │   ├── db/
│   │   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   │   ├── session.py           # Oracle 연결 (thick mode)
│   │   │   └── models/              # User, SummaryHistory, RefreshToken
│   │   ├── repositories/            # DB CRUD 계층
│   │   ├── schemas/                 # Pydantic 스키마
│   │   └── services/                # 요약, OCR, 내보내기, 인증 비즈니스 로직
│   ├── requirements.txt
│   └── .env                         # 환경변수 (git 미포함)
│
└── frontend/
    └── app/
        ├── components/
        │   ├── Header.tsx            # 인증 상태 반영 헤더
        │   ├── FileUploadInput.tsx   # 파일 업로드 존 UI
        │   ├── SummaryResult.tsx     # 요약 결과 및 steps 표시
        │   └── DownloadSection.tsx   # 다운로드 형식 선택 + 버튼
        ├── lib/
        │   ├── api.ts               # 요약 / export API 호출
        │   ├── auth-api.ts          # 인증 API 호출
        │   └── auth-context.tsx     # AuthProvider, useAuth
        ├── login/                   # 로그인 페이지
        ├── register/                # 회원가입 페이지
        └── page.tsx                 # 메인 페이지
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
# Ollama 모델 설치
ollama pull qwen2.5:7b
```

### Oracle DB 초기 설정

Oracle에서 `COPILOT` 계정과 3개 테이블을 생성합니다. (`.claude/README.md` 참고)

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
# Ollama
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=180
TARGET_CHUNK_SIZE=2000
SUMMARIZE_MAX_WORKERS=1

# Oracle DB
ORACLE_USER=COPILOT
ORACLE_PASSWORD=your_password
ORACLE_DSN=localhost:1521/XE
ORACLE_CLIENT_LIB_DIR=C:\oraclexe\app\oracle\product\11.2.0\server\bin

# JWT
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

> 로컬 환경에서는 `SUMMARIZE_MAX_WORKERS=1`이 가장 안정적입니다.

> PDF 다운로드는 Windows 기본 폰트 맑은 고딕(`C:/Windows/Fonts/malgun.ttf`)을 사용합니다.

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

---

## DB 설계

Oracle XE 11g의 `COPILOT` 스키마에 3개 테이블로 구성됩니다.
전체 DDL 및 Oracle 11g 호환 주의사항은 `.claude/README.md`를 참고하세요.

### 테이블 구성 및 설계 이유

#### USERS — 사용자 계정

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | NUMBER PK | 시퀀스 자동 증가 |
| email | VARCHAR2(320) UNIQUE | 로그인 식별자 |
| password_hash | VARCHAR2(256) | bcrypt 해시 |
| name | VARCHAR2(100) | 화면 표시용 이름 |
| role | VARCHAR2(20) | `USER` / `ADMIN` — JWT payload에 포함해 DB 조회 없이 권한 확인 |
| status | VARCHAR2(20) | `ACTIVE` / `SUSPENDED` — 계정 비활성화 대비 |
| email_verified | VARCHAR2(1) | `Y` / `N` — 컬럼 준비, 현재 미적용 |
| failed_login_count | NUMBER | 브루트포스 대응 준비 |
| last_login_at | TIMESTAMP | 마지막 로그인 시점 |
| created_at / updated_at | TIMESTAMP | SQLAlchemy `onupdate`로 갱신 (트리거 없음) |

**설계 이유**: 현재 서비스에서 요약 기능은 로그인 사용자만 사용 가능합니다. role 컬럼은 향후 관리자 전용 기능(모델 교체, 이력 전체 조회 등) 확장을 위해 처음부터 포함했습니다.

---

#### SUMMARY_HISTORY — 요약 이력

| 컬럼 | 타입 | 설명 |
|------|------|------|
| history_id | NUMBER PK | 시퀀스 자동 증가 |
| user_id | NUMBER FK | USERS 참조, NOT NULL (비로그인 요약 불허 정책) |
| original_filename | VARCHAR2(500) | 파일 업로드 시만 저장 |
| file_type | VARCHAR2(20) | txt / pdf / docx / png / jpg / text |
| file_size | NUMBER | bytes |
| model_name | VARCHAR2(100) | 사용된 Ollama 모델명 |
| summary_mode | VARCHAR2(20) | `single` / `chunked` |
| input_chars | NUMBER | 입력 텍스트 길이 |
| output_summary | CLOB | 요약 결과 (Oracle CLOB, 대용량 텍스트 지원) |
| status | VARCHAR2(20) | `SUCCESS` / `FAILED` |
| error_message | VARCHAR2(2000) | 실패 시 에러 내용 |
| processing_time_ms | NUMBER | 요약 소요 시간 |
| created_at | TIMESTAMP | 요청 시각 |

**설계 이유**: 성공뿐 아니라 실패한 요청도 모두 기록합니다. 어떤 모델·모드에서 실패가 많은지 분석하고, 향후 작업 기록 UI에서 재요약 기능을 제공하기 위한 기반 데이터입니다. `output_summary`를 CLOB으로 설정한 것은 긴 문서의 요약 결과가 VARCHAR2 한계를 초과할 수 있기 때문입니다.

---

#### REFRESH_TOKENS — 갱신 토큰 관리

| 컬럼 | 타입 | 설명 |
|------|------|------|
| token_id | NUMBER PK | 시퀀스 자동 증가 |
| user_id | NUMBER FK | USERS 참조 |
| token_value | VARCHAR2(1000) UNIQUE | JWT 문자열 원문 저장 |
| expires_at | TIMESTAMP | 만료 시각 (7일) |
| is_revoked | VARCHAR2(1) | `Y` / `N` |
| revoked_at | TIMESTAMP | 로그아웃 시점 |
| created_at | TIMESTAMP | 발급 시각 |

**설계 이유**: access token(30분)이 만료되면 이 테이블의 refresh token으로 새 access token을 재발급합니다. 로그아웃 시 `is_revoked = 'Y'`로 표시해 탈취된 토큰의 재사용을 차단합니다. token_value에 UNIQUE 제약을 두어 동일 토큰이 중복 저장되지 않도록 합니다.

---

### PK 생성 전략 (Oracle 11g 제약)

Oracle 11g는 `GENERATED ALWAYS AS IDENTITY`를 지원하지 않습니다 (12c+ 전용).
대신 시퀀스를 생성하고 SQLAlchemy `Sequence`로 연결합니다.
**DB 트리거는 사용하지 않습니다** — SQLAlchemy가 INSERT VALUES절에 `SEQ.nextval`을 직접 삽입하므로 트리거가 존재하면 충돌(ORA-04098)이 발생합니다.

---

## API 목록

### 인증

| Method | Path | 설명 |
|--------|------|------|
| POST | `/auth/register` | 회원가입 (201) |
| POST | `/auth/login` | 로그인, access/refresh token 반환 |
| POST | `/auth/refresh` | access token 재발급 |
| POST | `/auth/logout` | 로그아웃, refresh token 무효화 (204) |

### 사용자

| Method | Path | 설명 |
|--------|------|------|
| GET | `/users/me` | 내 정보 조회 (인증 필요) |
| GET | `/users/me/summaries` | 내 요약 이력 조회 (인증 필요) |

### 요약 / 내보내기

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| POST | `/summarize` | 텍스트 요약 (인증 필요) |
| POST | `/summarize/file` | 파일 업로드 후 요약 (인증 필요) |
| POST | `/export` | 요약 결과 파일 다운로드 (인증 불필요) |

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
| 작업 기록 UI | 이력 저장은 구현됨, 조회 UI(프론트엔드 페이지)는 미구현 |

---

## 향후 개선 방향

1. **작업 기록 UI** — `/users/me/summaries` API를 연결한 이력 조회 페이지
2. **혼합 문서 merge 프롬프트 개선** — 서로 다른 맥락 페이지 간 통합 요약 품질 향상
3. **docx 내부 이미지 OCR** — 내부 이미지 추출 후 기존 OCR 파이프라인 연결
4. **OCR 품질 개선** — 적응형 이진화, 노이즈 제거 등 전처리 강화
5. **영어 허용 정책 고도화** — 단순 whitelist를 넘어 문맥 기반 판단 검토
6. **LLM 교체 검토** — 로컬 모델 한계 확인 시 OpenAI / Gemini 등 API 모델 비교
