-- Migration 002: SUMMARY_HISTORY에 원문 텍스트 컬럼 추가
--
-- 목적:
--   문서 기반 Q&A(/chat)에서 요약문만이 아닌 원문을 컨텍스트로 활용하기 위해
--   추출된 원문 텍스트를 저장합니다.
--
-- 적용 방법:
--   sqlplus 또는 DBeaver 등에서 아래 구문을 실행합니다.
--
-- 호환성:
--   기존 레코드의 INPUT_TEXT는 NULL로 유지됩니다.
--   /chat API는 NULL인 경우 요약문만 사용하는 방식으로 fallback합니다.

ALTER TABLE SUMMARY_HISTORY ADD (input_text CLOB DEFAULT NULL);
