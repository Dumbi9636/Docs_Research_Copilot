// 문서 기반 대화 localStorage 유틸
//
// 저장 키 구조: docchat:user:{userId}:history:{historyId}
//
// 설계 원칙:
// - 사용자별 + 문서별로 격리된 키를 사용합니다.
// - 이 파일이 localStorage 접근의 단일 진입점입니다.
//
// Phase 2 확장 방법:
// - getMessages / saveMessages / clearUserChats 함수를 API 호출로 교체하면
//   ChatPanel 코드 변경 없이 DB 저장 방식으로 전환할 수 있습니다.
// - ChatMessage 타입에 id / session_id / created_at 필드를 추가하면
//   DB 스키마(chat_messages 테이블)와 바로 매핑됩니다.

const DOCCHAT_PREFIX = "docchat";

/**
 * 문서 대화 메시지 타입.
 *
 * role / content는 DB 저장 시에도 그대로 사용할 수 있습니다.
 * Phase 2에서 아래 주석 필드를 추가하면 됩니다.
 */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  // Phase 2 DB 확장 시 추가:
  // id?: number;
  // session_id?: number;
  // created_at?: string;
}

// ── 키 생성 헬퍼 ──────────────────────────────────────────────────────────────

function storageKey(userId: number, historyId: number): string {
  return `${DOCCHAT_PREFIX}:user:${userId}:history:${historyId}`;
}

function userPrefix(userId: number): string {
  return `${DOCCHAT_PREFIX}:user:${userId}:`;
}

// ── 공개 인터페이스 ───────────────────────────────────────────────────────────

/**
 * userId + historyId 조합에 저장된 대화 메시지를 반환합니다.
 * 저장된 데이터가 없거나 파싱 실패 시 빈 배열을 반환합니다.
 */
export function getMessages(userId: number, historyId: number): ChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(userId, historyId));
    if (!raw) return [];
    return JSON.parse(raw) as ChatMessage[];
  } catch {
    return [];
  }
}

/**
 * userId + historyId 조합에 대화 메시지를 저장합니다.
 * localStorage 용량 초과 등 예외는 무시합니다 (대화가 사라지는 것보다 낫습니다).
 */
export function saveMessages(
  userId: number,
  historyId: number,
  messages: ChatMessage[]
): void {
  try {
    localStorage.setItem(storageKey(userId, historyId), JSON.stringify(messages));
  } catch {
    // 무시 (quota exceeded 등)
  }
}

/**
 * 특정 사용자의 모든 문서 대화를 localStorage에서 삭제합니다.
 * 로그아웃 시 호출합니다.
 */
export function clearUserChats(userId: number): void {
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
