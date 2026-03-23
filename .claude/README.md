# 내부 작업 노트 — Docs Research Copilot

> 이 문서는 Claude가 다음 세션에서 빠르게 맥락을 복원할 수 있도록 작성된 작업 메모입니다.
> 세션 시작 시 이 문서를 먼저 읽으세요.

---

## 현재 구현 상태 (2026-03-23 기준)

### 완료된 기능

| 영역 | 내용 |
|------|------|
| 문서 요약 | txt / pdf / docx / png / jpg 업로드, 텍스트 직접 입력, chunking 요약 |
| 결과 다운로드 | txt / docx / pdf 내보내기, DOWNLOAD_LOGS 기록 |
| 요약 취소 | AbortController 기반 |
| 회원가입 / 로그인 | POST /auth/register, /auth/login, JWT access(30분) + refresh(7일) |
| 로그아웃 | refresh token DB revoke |
| JWT 토큰 갱신 | 자동 재시도, 실패 시 로그인 페이지 이동 |
| 요약 이력 저장 | 성공/실패 모두 SUMMARY_HISTORY에 저장, input_text도 함께 저장 |
| 이력 조회 | GET /users/me/summaries, /users/me/activities |
| 마이페이지 | 사용자 이름 클릭 진입, 요약 이력 + 다운로드 이력 조회 |
| 세션 복원 | JWT refresh_token → /auth/refresh → /users/me |
| 대시보드 홈 | / 에서 서비스 카드 목록 (요약 + 파일변환 예고) |
| 문서 기반 대화 | POST /chat, history_id 기준 input_text 컨텍스트, ChatPanel UI |
| localStorage 복원 | 요약 세션 + 텍스트 draft + 채팅 기록 새로고침 후 복원 |
| ADMIN 전용 debug | user.role === "ADMIN"만 steps 표시 (SummaryResult.tsx isAdmin prop) |

### 미구현 / 다음 작업

| 항목 | 우선순위 | 비고 |
|------|----------|------|
| 채팅 한국어 후처리 | 높음 | 중국어 혼용 출력 발생 중 |
| 파일 변환 서비스 | 중간 | 대시보드 카드 이미 표시, 다음 서비스 |
| 채팅 이력 DB 저장 | 중간 | 현재 localStorage만, CHAT_SESSIONS/MESSAGES 테이블 필요 |
| 임베딩 기반 문단 검색 | 낮음 | _select_relevant_paragraphs() 교체 포인트 명시됨 |

---

## 페이지 / 역할 구분

```
/               대시보드 홈 — 서비스 카드 목록
/summarize      요약 서비스 — 파일 업로드 + 요약 + ChatPanel
/mypage         마이페이지 — 요약 이력 + 다운로드 이력 (헤더 이름 클릭 진입)
/login          로그인
/register       회원가입
```

- **활동 이력은 마이페이지에 통합됨** — 별도 /history 페이지 없음
- **마이페이지 진입**: 헤더의 사용자 이름 클릭 (별도 탭/버튼 아님)

---

## 문서 기반 Q&A 구조

### 백엔드 (`backend/app/services/chat_service.py`)

컨텍스트 선택 전략:

```
input_text is None        → [문서 요약] fallback (구버전 기록)
len(input_text) < 50      → [문서 요약] fallback (OCR 노이즈)
len(input_text) ≤ 6000    → [원문] 전체 + [요약]
len(input_text) > 6000    → [요약] + [원문 중 관련 구절] (키워드 점수 기반 문단 선택)
```

Phase 2 교체 포인트:
- `_select_relevant_paragraphs()` → 임베딩 코사인 유사도로 교체하면 외부 호출부 변경 없음

### API

```
POST /chat
Body: { history_id, messages: [{role, content}], question }
→ 소유권 확인 (user_id 일치)
→ question 길이 검증 (1~500자)
→ chat_service.answer() → Ollama 호출
→ { answer: string }
```

### 프론트엔드 (`frontend/app/components/ChatPanel.tsx`)

- `key={historyId}` — historyId 변경 시 ChatPanel 강제 remount (크로스 오염 방지)
- 메시지 저장 guard: `messages.length === 0`이면 localStorage에 저장하지 않음
  - 이유: React StrictMode 이중 실행에서 restore 전에 빈 배열이 저장되는 버그 방지
- 토큰 만료: `setAuthExpired(true)` UI 배너만 표시, localStorage 기록은 보존

---

## localStorage 복원 구조

### 키 설계

```
docsresearch:user:{userId}:summarize:current   → SummarizeSession (summary, history_id, steps, source_filename)
docsresearch:user:{userId}:summarize:draft     → 텍스트 입력 draft (string)
docchat:user:{userId}:history:{historyId}      → ChatMessage[] (role, content)
```

### 로그아웃 시 초기화

`auth-context.tsx` signOut:
1. `clearUserChats(user.user_id)` — `docchat:user:{id}:` 프리픽스 전체 삭제
2. `clearSummarizeSession(user.user_id)` — `docsresearch:user:{id}:` 프리픽스 전체 삭제

### 복원하지 않는 것

- 실제 `File` 객체 — 파일명만 표시 (`restoredFilename` 상태로 관리)
- 토큰 만료 상태에서는 복원 배너만 표시, 저장 데이터는 보존

---

## SUMMARY_HISTORY.input_text

- 컬럼 추가: `002_add_input_text.sql` (`ALTER TABLE SUMMARY_HISTORY ADD (input_text CLOB DEFAULT NULL)`)
- 모든 summary_repository.create() 호출에 `input_text=text` 전달
- NULL인 기존 기록 → /chat에서 자동 fallback (summary-only)

---

## 현재 알려진 이슈

### 중국어 혼용 출력 (채팅)

- 증상: `/chat` 응답에서 한자가 섞여 나오는 경우 발생
- 원인: `qwen2.5:7b`의 언어 편향, 프롬프트만으로는 완전 차단이 어려움
- 요약 단계: 보정 로직 있음 (`summarizer.py`)
- 채팅 단계: 미적용 — 다음 작업 대상

---

## Oracle XE 11g — 필수 주의사항

### 1. Thick Mode 필수 (DPY-3010)

```python
import oracledb
oracledb.init_oracle_client(lib_dir=settings.oracle_client_lib_dir.strip() or None)
# 반드시 create_engine() 호출 전에 실행
engine = create_engine(f"oracle+oracledb://{user}:{password}@{dsn}", ...)
```

### 2. IDENTITY 컬럼 미지원 — Sequence 사용

```python
from sqlalchemy import Sequence
_users_seq = Sequence("USERS_SEQ")
user_id = Column(Integer, _users_seq, primary_key=True)
```

### 3. PK 트리거 제거 (ORA-04098)

SQLAlchemy가 INSERT VALUES에 `SEQ.nextval`을 직접 삽입 → 트리거가 있으면 충돌.
**현재 DB 상태: 트리거 없음, 시퀀스만 존재**

제거된 트리거: `TRG_USERS_PK`, `TRG_SUMMARY_HISTORY_PK`, `TRG_REFRESH_TOKENS_PK`, `TRG_USERS_UPDATED_AT`

### 4. bcrypt 버전 고정

```
passlib[bcrypt]
bcrypt<5
```

---

## Oracle DB 스키마 (COPILOT 계정)

### 시퀀스

```sql
CREATE SEQUENCE USERS_SEQ           START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE SUMMARY_HISTORY_SEQ START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE REFRESH_TOKENS_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE DOWNLOAD_LOGS_SEQ   START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
```

### USERS

```sql
CREATE TABLE USERS (
    user_id            NUMBER          NOT NULL,
    email              VARCHAR2(320)   NOT NULL,
    password_hash      VARCHAR2(256)   NOT NULL,
    name               VARCHAR2(100)   NOT NULL,
    role               VARCHAR2(20)    DEFAULT 'USER'   NOT NULL,
    status             VARCHAR2(20)    DEFAULT 'ACTIVE' NOT NULL,
    email_verified     VARCHAR2(1)     DEFAULT 'N'      NOT NULL,
    failed_login_count NUMBER          DEFAULT 0        NOT NULL,
    last_login_at      TIMESTAMP,
    created_at         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_USERS       PRIMARY KEY (user_id),
    CONSTRAINT UQ_USERS_EMAIL UNIQUE (email)
);
```

### SUMMARY_HISTORY

```sql
CREATE TABLE SUMMARY_HISTORY (
    history_id         NUMBER          NOT NULL,
    user_id            NUMBER          NOT NULL,
    original_filename  VARCHAR2(500),
    file_type          VARCHAR2(20),
    file_size          NUMBER,
    model_name         VARCHAR2(100)   NOT NULL,
    summary_mode       VARCHAR2(20)    NOT NULL,
    input_chars        NUMBER          NOT NULL,
    output_summary     CLOB,
    input_text         CLOB,                        -- 추가: 원문 텍스트 (마이그레이션 002)
    document_type      VARCHAR2(50),
    status             VARCHAR2(20)    DEFAULT 'SUCCESS' NOT NULL,
    error_message      VARCHAR2(2000),
    processing_time_ms NUMBER,
    created_at         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_SUMMARY_HISTORY PRIMARY KEY (history_id),
    CONSTRAINT FK_SH_USER FOREIGN KEY (user_id) REFERENCES USERS(user_id)
);
-- 마이그레이션으로 추가:
-- ALTER TABLE SUMMARY_HISTORY ADD (input_text CLOB DEFAULT NULL);
```

### REFRESH_TOKENS

```sql
CREATE TABLE REFRESH_TOKENS (
    token_id    NUMBER          NOT NULL,
    user_id     NUMBER          NOT NULL,
    token_value VARCHAR2(1000)  NOT NULL,
    expires_at  TIMESTAMP       NOT NULL,
    is_revoked  VARCHAR2(1)     DEFAULT 'N' NOT NULL,
    revoked_at  TIMESTAMP,
    created_at  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_REFRESH_TOKENS      PRIMARY KEY (token_id),
    CONSTRAINT UQ_REFRESH_TOKEN_VALUE UNIQUE (token_value),
    CONSTRAINT FK_RT_USER FOREIGN KEY (user_id) REFERENCES USERS(user_id)
);
```

### DOWNLOAD_LOGS

```sql
CREATE TABLE DOWNLOAD_LOGS (
    log_id       NUMBER     NOT NULL,
    user_id      NUMBER     NOT NULL,
    history_id   NUMBER,                  -- 요약 기록 삭제 시 NULL 처리 (ON DELETE SET NULL 불가 → 수동 NULL)
    file_format  VARCHAR2(20) NOT NULL,   -- txt / docx / pdf
    downloaded_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_DOWNLOAD_LOGS PRIMARY KEY (log_id),
    CONSTRAINT FK_DL_USER FOREIGN KEY (user_id) REFERENCES USERS(user_id),
    CONSTRAINT FK_DL_HISTORY FOREIGN KEY (history_id) REFERENCES SUMMARY_HISTORY(history_id)
);
```

### 인덱스

```sql
CREATE INDEX IDX_SUMMARY_HISTORY_USER ON SUMMARY_HISTORY(user_id);
CREATE INDEX IDX_REFRESH_TOKENS_VALUE ON REFRESH_TOKENS(token_value);
CREATE INDEX IDX_REFRESH_TOKENS_USER  ON REFRESH_TOKENS(user_id);
CREATE INDEX IDX_DOWNLOAD_LOGS_USER   ON DOWNLOAD_LOGS(user_id);
CREATE INDEX IDX_DOWNLOAD_LOGS_HIST   ON DOWNLOAD_LOGS(history_id);
```

### DB 객체 상태

| 객체 | 이름 | 상태 |
|------|------|------|
| 테이블 | USERS | 운영 중 |
| 테이블 | SUMMARY_HISTORY | 운영 중 (input_text 컬럼 마이그레이션 완료) |
| 테이블 | REFRESH_TOKENS | 운영 중 |
| 테이블 | DOWNLOAD_LOGS | 운영 중 |
| 시퀀스 | *_SEQ (4개) | 운영 중 |
| 트리거 | (없음) | 모두 DROP됨 |

---

## 인증 설계

### JWT Payload

```json
{ "sub": "1", "role": "USER", "exp": ..., "type": "access" }
```

role을 payload에 포함 → `require_admin` dependency에서 DB 조회 없이 확인

### 로그인 요청 형식

JSON body 사용 (OAuth2PasswordRequestForm 미사용 — 필드명이 `email`이라 `username`과 불일치)

### 세션 복원 흐름

```
AuthProvider mount
  → localStorage["refresh_token"] 확인
  → POST /auth/refresh
  → 성공: accessToken 메모리 저장 + GET /users/me → user 상태
  → 실패: localStorage 정리, 비로그인 상태
```

---

## 파일 주요 경로 빠른 참조

```
# 백엔드
backend/app/db/session.py               ← Oracle thick mode 초기화
backend/app/db/models/user.py           ← Sequence PK, role 컬럼
backend/app/db/models/summary_history.py← input_text CLOB 컬럼
backend/app/db/models/download_log.py   ← DOWNLOAD_LOGS 모델
backend/app/core/security.py            ← JWT 생성/검증
backend/app/core/dependencies.py        ← get_current_user, require_admin
backend/app/services/chat_service.py    ← 문서 Q&A 컨텍스트 구성 (교체 포인트 명시됨)
backend/app/api/routes.py               ← /summarize, /export, /chat
backend/app/api/users.py                ← /users/me, /users/me/summaries, /activities
backend/app/repositories/summary_repository.py ← input_text 저장 포함
backend/migrations/002_add_input_text.sql

# 프론트엔드
frontend/app/lib/auth-context.tsx       ← 로그아웃 시 storage 초기화
frontend/app/lib/chatStorage.ts         ← docchat:user:{id}:history:{historyId}
frontend/app/lib/summarizeStorage.ts    ← docsresearch:user:{id}:summarize:*
frontend/app/lib/api.ts                 ← sendChat() 포함
frontend/app/summarize/page.tsx         ← 복원 effect, draft debounce, ChatPanel 마운트
frontend/app/components/ChatPanel.tsx   ← messages.length === 0 guard (StrictMode 버그 대응)
frontend/app/components/SummaryResult.tsx ← isAdmin prop으로 steps 조건부 렌더링
```

---

## 다음 세션 시작 전 체크리스트

- [ ] Oracle XE 서비스 실행 중인지 확인
- [ ] Ollama 실행 중인지 확인 (`ollama run qwen2.5:7b`)
- [ ] `backend/.env` 값 확인 (특히 `ORACLE_CLIENT_LIB_DIR`, `JWT_SECRET_KEY`)
- [ ] 백엔드 `uvicorn app.main:app --reload` 실행
- [ ] 프론트엔드 `npm run dev` 실행
- [ ] **현재 남은 이슈**: 채팅 응답 중국어 혼용 출력 후처리 미구현

---

## 다음 작업 우선순위

1. `/chat` 응답 한국어 후처리 — 중국어 감지 및 재작성 로직
2. 파일 변환 서비스 — 대시보드 카드 활성화 + 변환 파이프라인 구현
3. 채팅 이력 DB 저장 — CHAT_SESSIONS / CHAT_MESSAGES 테이블 설계
4. `_select_relevant_paragraphs()` → 임베딩 기반 검색으로 교체 (Phase 2)
