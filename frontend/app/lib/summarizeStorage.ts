// 요약 세션 localStorage 유틸
//
// 저장 키 구조: docsresearch:user:{userId}:summarize:current
//
// 설계 원칙:
// - 사용자당 하나의 "현재 요약 세션"을 저장합니다.
// - 새 요약이 완료되면 덮어씁니다 (항상 최신 1개 유지).
// - File 객체, textarea 입력 등 직렬화 불가능한 상태는 저장하지 않습니다.
//
// Phase 2 확장 방법:
// - getSession / saveSession / clearSession 함수를 API 호출로 교체하면
//   page.tsx 코드 변경 없이 서버 기반 세션 저장으로 전환할 수 있습니다.

const PREFIX = "docsresearch";

/**
 * 요약 세션 타입.
 * DB(summary_history) 레코드와 1:1 대응되도록 설계했습니다.
 * Phase 2에서 DB 세션 저장으로 옮길 때 이 구조를 그대로 사용할 수 있습니다.
 */
export interface SummarizeSession {
  history_id: number;
  summary: string;
  steps: string[];
  source_filename: string; // 파일명만 저장 (File 객체 제외)
  saved_at: string;        // ISO 문자열 — 세션이 언제 저장됐는지 추적용
}

// ── 키 생성 헬퍼 ──────────────────────────────────────────────────────────────

function sessionKey(userId: number): string {
  return `${PREFIX}:user:${userId}:summarize:current`;
}

function userPrefix(userId: number): string {
  return `${PREFIX}:user:${userId}:`;
}

// ── 키 생성 헬퍼 (draft) ─────────────────────────────────────────────────────

/** 요약 전 텍스트 입력 draft를 저장하는 키. prefix가 같으므로 clearSession으로 함께 삭제됩니다. */
function draftKey(userId: number): string {
  return `${PREFIX}:user:${userId}:summarize:draft`;
}

// ── 공개 인터페이스 ───────────────────────────────────────────────────────────

/**
 * 저장된 요약 세션을 반환합니다.
 * 없거나 파싱 실패 시 null을 반환합니다.
 */
export function getSession(userId: number): SummarizeSession | null {
  try {
    const raw = localStorage.getItem(sessionKey(userId));
    if (!raw) return null;
    return JSON.parse(raw) as SummarizeSession;
  } catch {
    return null;
  }
}

/**
 * 요약 세션을 저장합니다. 기존 세션은 덮어씁니다.
 */
export function saveSession(userId: number, session: Omit<SummarizeSession, "saved_at">): void {
  try {
    const withTimestamp: SummarizeSession = {
      ...session,
      saved_at: new Date().toISOString(),
    };
    localStorage.setItem(sessionKey(userId), JSON.stringify(withTimestamp));
  } catch {
    // quota exceeded 등 무시
  }
}

/**
 * 요약 전 textarea 텍스트 draft를 반환합니다.
 * 없으면 빈 문자열을 반환합니다.
 */
export function getDraft(userId: number): string {
  try {
    return localStorage.getItem(draftKey(userId)) ?? "";
  } catch {
    return "";
  }
}

/**
 * textarea 텍스트 draft를 저장합니다.
 * 빈 문자열이면 키를 삭제합니다 (불필요한 항목 방지).
 */
export function saveDraft(userId: number, text: string): void {
  try {
    if (text) {
      localStorage.setItem(draftKey(userId), text);
    } else {
      localStorage.removeItem(draftKey(userId));
    }
  } catch {
    // 무시
  }
}

/**
 * 해당 사용자의 모든 요약 세션 데이터를 삭제합니다.
 * 로그아웃 시 호출합니다.
 * draft 키도 docsresearch:user:{userId}: prefix를 공유하므로 함께 삭제됩니다.
 */
export function clearSession(userId: number): void {
  try {
    const prefix = userPrefix(userId);
    const keysToRemove = Object.keys(localStorage).filter((k) =>
      k.startsWith(prefix)
    );
    keysToRemove.forEach((k) => localStorage.removeItem(k));
  } catch {
    // 무시
  }
}
