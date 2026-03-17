# 내부 작업 노트 — Docs Research Copilot

> 이 문서는 개발 이력, Oracle XE 11g 주의사항, 확인된 설계 결정을 기록합니다.
> 다음 세션을 시작할 때 이 문서를 먼저 읽으세요.

---

## 현재 구현 상태 (2026-03-17 기준)

### 완료된 기능

| 영역 | 내용 |
|------|------|
| 문서 요약 | txt / pdf / docx / png / jpg 업로드, 텍스트 직접 입력, chunking 요약 |
| 결과 다운로드 | txt / docx / pdf 내보내기 |
| 요약 취소 | AbortController 기반 |
| 회원가입 | POST /auth/register → 201, role은 항상 "USER" |
| 로그인 / 로그아웃 | POST /auth/login, /auth/logout (refresh token revoke) |
| JWT 인증 | access token 30분, refresh token 7일 |
| 토큰 갱신 | POST /auth/refresh, 프론트 자동 재시도 |
| 요약 이력 저장 | 성공/실패 모두 SUMMARY_HISTORY 테이블에 저장 |
| 이력 조회 API | GET /users/me/summaries (skip/limit 페이지네이션) |
| 프론트 인증 | AuthContext, Header 인증 상태 반영, 로그인/회원가입 페이지 |
| 세션 복원 | 새로고침 시 localStorage refresh_token → /auth/refresh → /users/me |

### 미구현 (다음 작업)

- 작업 기록 UI 페이지 (`/history` 또는 `/me/summaries`)
- 이메일 인증 (email_verified 컬럼은 있으나 현재 미적용)
- ADMIN 전용 페이지

---

## Oracle XE 11g — 필수 주의사항

### 1. Thick Mode 필수 (DPY-3010)

Oracle XE 11g는 python-oracledb thin mode를 지원하지 않습니다.
`backend/app/db/session.py`에서 반드시 thick mode를 초기화해야 합니다.

```python
import oracledb
oracledb.init_oracle_client(lib_dir=settings.oracle_client_lib_dir.strip() or None)
# 반드시 create_engine() 호출 전에 실행
engine = create_engine(f"oracle+oracledb://{user}:{password}@{dsn}", ...)
```

`.env`의 `ORACLE_CLIENT_LIB_DIR`이 비어 있으면 Oracle이 PATH에서 자동 탐지합니다.
현재 설정값: `C:\oraclexe\app\oracle\product\11.2.0\server\bin`

### 2. IDENTITY 컬럼 미지원 — Sequence 사용

Oracle 11g는 `GENERATED ALWAYS AS IDENTITY`를 지원하지 않습니다 (12c+ 전용).
SQLAlchemy `Identity(always=True)` 대신 `Sequence`를 사용합니다.

```python
from sqlalchemy import Sequence
_users_seq = Sequence("USERS_SEQ")
user_id = Column(Integer, _users_seq, primary_key=True)
```

DB에 `CREATE SEQUENCE USERS_SEQ START WITH 1 INCREMENT BY 1`이 있어야 합니다.

### 3. PK 트리거 제거 (ORA-04098)

최초 구현 시 Oracle DDL에 PK INSERT 트리거를 만들었으나 제거했습니다.
SQLAlchemy가 이미 INSERT VALUES절에 `"USERS_SEQ".nextval`을 직접 넣기 때문에,
트리거가 INVALID 상태로 남아 있으면 모든 INSERT가 ORA-04098로 실패합니다.

**현재 DB 상태: 트리거 없음, 시퀀스만 존재**

제거된 트리거:
- `TRG_USERS_PK`
- `TRG_SUMMARY_HISTORY_PK`
- `TRG_REFRESH_TOKENS_PK`
- `TRG_USERS_UPDATED_AT` (SQLAlchemy `onupdate=datetime.utcnow`로 대체)

### 4. bcrypt 버전 고정

passlib과의 버전 충돌로 인해 requirements.txt에 `bcrypt<5`가 고정되어 있습니다.

```
passlib[bcrypt]
bcrypt<5
```

---

## Oracle DB 스키마 (COPILOT 계정)

> 아래 DDL은 실제 운영 중인 DB 상태 기준입니다 (모델 코드와 1:1 대응).
> 새 환경에서 초기 구축 시 그대로 실행하면 됩니다.

### 시퀀스

```sql
-- PK 자동 증가용 시퀀스 (Oracle 11g는 IDENTITY 컬럼 미지원 → Sequence 사용)
CREATE SEQUENCE USERS_SEQ           START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE SUMMARY_HISTORY_SEQ START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE SEQUENCE REFRESH_TOKENS_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
```

### USERS 테이블

```sql
CREATE TABLE USERS (
    user_id            NUMBER          NOT NULL,
    email              VARCHAR2(320)   NOT NULL,   -- RFC 5321 최대 길이
    password_hash      VARCHAR2(256)   NOT NULL,   -- bcrypt 해시 결과
    name               VARCHAR2(100)   NOT NULL,
    role               VARCHAR2(20)    DEFAULT 'USER'   NOT NULL,  -- USER / ADMIN
    status             VARCHAR2(20)    DEFAULT 'ACTIVE' NOT NULL,  -- ACTIVE / SUSPENDED
    email_verified     VARCHAR2(1)     DEFAULT 'N' NOT NULL,       -- Y / N (현재 미적용)
    failed_login_count NUMBER          DEFAULT 0   NOT NULL,
    last_login_at      TIMESTAMP,
    created_at         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_USERS      PRIMARY KEY (user_id),
    CONSTRAINT UQ_USERS_EMAIL UNIQUE      (email)
);
```

### SUMMARY_HISTORY 테이블

```sql
CREATE TABLE SUMMARY_HISTORY (
    history_id         NUMBER          NOT NULL,
    user_id            NUMBER          NOT NULL,
    original_filename  VARCHAR2(500),              -- 파일 업로드 시만 저장, 텍스트 입력 시 NULL
    file_type          VARCHAR2(20),               -- txt / pdf / docx / png / jpg / text
    file_size          NUMBER,                     -- bytes, 파일 업로드 시만 저장
    model_name         VARCHAR2(100)   NOT NULL,
    summary_mode       VARCHAR2(20)    NOT NULL,   -- single / chunked
    input_chars        NUMBER          NOT NULL,
    output_summary     CLOB,                       -- SQLAlchemy Text → Oracle CLOB 자동 매핑
    status             VARCHAR2(20)    DEFAULT 'SUCCESS' NOT NULL,  -- SUCCESS / FAILED
    error_message      VARCHAR2(2000),             -- 실패 시 에러 내용
    processing_time_ms NUMBER,                     -- 요약 소요 시간 (ms)
    created_at         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_SUMMARY_HISTORY PRIMARY KEY (history_id),
    CONSTRAINT FK_SH_USER FOREIGN KEY (user_id) REFERENCES USERS(user_id)
);
```

### REFRESH_TOKENS 테이블

```sql
CREATE TABLE REFRESH_TOKENS (
    token_id    NUMBER        NOT NULL,
    user_id     NUMBER        NOT NULL,
    token_value VARCHAR2(1000) NOT NULL,           -- JWT 문자열 원문 저장 (MVP 방식)
    expires_at  TIMESTAMP     NOT NULL,
    is_revoked  VARCHAR2(1)   DEFAULT 'N' NOT NULL, -- Y / N
    revoked_at  TIMESTAMP,                          -- 로그아웃 시점 기록
    created_at  TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_REFRESH_TOKENS      PRIMARY KEY (token_id),
    CONSTRAINT UQ_REFRESH_TOKEN_VALUE UNIQUE       (token_value),
    CONSTRAINT FK_RT_USER FOREIGN KEY (user_id) REFERENCES USERS(user_id)
);
```

### 인덱스

```sql
-- 사용자별 요약 이력 조회 (GET /users/me/summaries)
CREATE INDEX IDX_SUMMARY_HISTORY_USER  ON SUMMARY_HISTORY(user_id);

-- 토큰 값으로 refresh token 조회 (/auth/refresh, /auth/logout)
CREATE INDEX IDX_REFRESH_TOKENS_VALUE  ON REFRESH_TOKENS(token_value);

-- 사용자별 전체 토큰 revoke (로그아웃 시 해당 user의 모든 토큰 무효화)
CREATE INDEX IDX_REFRESH_TOKENS_USER   ON REFRESH_TOKENS(user_id);
```

### 현재 DB 객체 상태 요약

| 객체 종류 | 이름 | 상태 |
|-----------|------|------|
| 테이블 | USERS | 운영 중 |
| 테이블 | SUMMARY_HISTORY | 운영 중 |
| 테이블 | REFRESH_TOKENS | 운영 중 |
| 시퀀스 | USERS_SEQ | 운영 중 |
| 시퀀스 | SUMMARY_HISTORY_SEQ | 운영 중 |
| 시퀀스 | REFRESH_TOKENS_SEQ | 운영 중 |
| 트리거 | (없음) | 모두 DROP됨 — 아래 참고 |

---

## 인증 설계 결정

### JWT Payload 구조

```json
{
  "sub": "1",          // user_id (문자열)
  "role": "USER",      // role을 포함해 DB 조회 없이 권한 확인 가능
  "exp": 1234567890,
  "type": "access"
}
```

- role을 payload에 포함한 이유: `require_admin` dependency에서 DB 조회 없이 확인 가능
- refresh token payload에는 role 없음 — refresh는 새 access_token 발급 전용

### 로그인 요청 형식

JSON body 사용 (OAuth2PasswordRequestForm 미사용)

```json
{ "email": "user@example.com", "password": "password123" }
```

이유: 필드명이 `email`이라 OAuth2 form의 `username`과 맞지 않음, 프론트가 JSON API로 구현됨

### refresh token 저장

- 백엔드 DB: `REFRESH_TOKENS.token_value`에 raw JWT 문자열 저장
- 프론트 브라우저: `localStorage["refresh_token"]`에 저장

### 세션 복원 흐름 (페이지 새로고침)

```
AuthProvider mount
  → localStorage["refresh_token"] 확인
  → POST /auth/refresh
  → 성공: accessToken 메모리에 저장 + GET /users/me → user 상태 설정
  → 실패: 로그아웃 상태로 (localStorage 정리)
  → isLoading: false (헤더 버튼 표시)
```

---

## 프론트엔드 인증 구조

### 상태 저장 위치

| 데이터 | 저장 위치 | 이유 |
|--------|-----------|------|
| access_token | React 상태 (메모리) | 짧은 만료, XSS 노출 최소화 |
| refresh_token | localStorage | 세션 복원 필요 |
| user 정보 | React 상태 (메모리) | localStorage에 저장하지 않음, /users/me로 복원 |

### 401 처리 패턴 (page.tsx)

```
API 호출 → 401 → tryRefreshToken()
  → 성공: 새 토큰으로 1회 재시도
  → 실패: router.push("/login")
```

### 에러 메시지 필터링 (auth-api.ts)

`parseDetail()` 함수가 ORA-*, sqlalchemy.*, traceback 패턴을 감지해
기술적 에러 메시지를 사용자 친화적 문구로 대체합니다.

---

## 파일 주요 경로 빠른 참조

```
backend/app/db/session.py           ← Oracle thick mode 초기화
backend/app/db/models/user.py       ← Sequence PK, role 컬럼
backend/app/core/security.py        ← JWT 생성/검증, 비밀번호 해시
backend/app/core/dependencies.py    ← get_current_user, require_admin
backend/app/services/auth_service.py ← register, login, refresh, logout
backend/app/api/auth.py             ← /auth/* 라우터
backend/app/api/users.py            ← /users/me, /users/me/summaries
backend/app/api/routes.py           ← /summarize (인증 + 이력 저장)

frontend/app/lib/auth-context.tsx   ← AuthProvider (세션 복원 로직)
frontend/app/lib/auth-api.ts        ← 인증 API 호출 + 에러 필터
frontend/app/lib/api.ts             ← 요약/export API (UnauthorizedError)
frontend/app/components/Header.tsx  ← 인증 상태 반영 헤더
```

---

## 다음 세션 시작 전 체크리스트

- [ ] Oracle XE 서비스 실행 중인지 확인
- [ ] Ollama 실행 중인지 확인 (`ollama run qwen2.5:7b`)
- [ ] `backend/.env` 값 확인 (특히 `ORACLE_CLIENT_LIB_DIR`, `JWT_SECRET_KEY`)
- [ ] 백엔드 `uvicorn app.main:app --reload` 실행
- [ ] 프론트엔드 `npm run dev` 실행
