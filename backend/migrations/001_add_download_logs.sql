-- ============================================================
-- Migration 001: 다운로드 히스토리 기능 추가
-- ============================================================

-- [1] SUMMARY_HISTORY 테이블에 document_type 컬럼 추가
ALTER TABLE SUMMARY_HISTORY ADD (
    document_type VARCHAR2(50) NULL
);

COMMENT ON COLUMN SUMMARY_HISTORY.document_type IS '문서 유형 (general / legal / medical / technical 등)';

-- [2] DOWNLOAD_LOGS 시퀀스 생성
CREATE SEQUENCE DOWNLOAD_LOGS_SEQ
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- [3] DOWNLOAD_LOGS 테이블 생성
CREATE TABLE DOWNLOAD_LOGS (
    download_id     NUMBER          NOT NULL,
    user_id         NUMBER          NOT NULL,
    history_id      NUMBER          NULL,
    file_name       VARCHAR2(500)   NULL,
    download_format VARCHAR2(10)    NOT NULL,
    status          VARCHAR2(20)    DEFAULT 'SUCCESS' NOT NULL,
    error_message   VARCHAR2(2000)  NULL,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT PK_DOWNLOAD_LOGS PRIMARY KEY (download_id),
    CONSTRAINT FK_DOWNLOAD_LOGS_USER
        FOREIGN KEY (user_id) REFERENCES USERS(user_id),
    CONSTRAINT FK_DOWNLOAD_LOGS_HISTORY
        FOREIGN KEY (history_id) REFERENCES SUMMARY_HISTORY(history_id),
    CONSTRAINT CHK_DOWNLOAD_FORMAT
        CHECK (download_format IN ('txt', 'docx', 'pdf'))
);

COMMENT ON TABLE DOWNLOAD_LOGS IS '사용자 다운로드(내보내기) 이력';
COMMENT ON COLUMN DOWNLOAD_LOGS.download_id IS 'PK (DOWNLOAD_LOGS_SEQ)';
COMMENT ON COLUMN DOWNLOAD_LOGS.user_id IS '다운로드한 사용자 (FK → USERS)';
COMMENT ON COLUMN DOWNLOAD_LOGS.history_id IS '원본 요약 이력 (FK → SUMMARY_HISTORY, 선택)';
COMMENT ON COLUMN DOWNLOAD_LOGS.file_name IS '다운로드 시점의 원본 파일명';
COMMENT ON COLUMN DOWNLOAD_LOGS.download_format IS '내보낸 형식: txt / docx / pdf';
COMMENT ON COLUMN DOWNLOAD_LOGS.status IS '처리 결과: SUCCESS / FAILED';
COMMENT ON COLUMN DOWNLOAD_LOGS.error_message IS '실패 시 오류 메시지';
COMMENT ON COLUMN DOWNLOAD_LOGS.created_at IS '다운로드 일시';

COMMIT;
