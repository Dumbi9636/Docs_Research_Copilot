"use client";

import { useState, useEffect, useRef } from "react";
import { useAuth } from "../lib/auth-context";
import { sendChat, UnauthorizedError, ChatMode } from "../lib/api";
import { getMessages, saveMessages, ChatMessage } from "../lib/chatStorage";
import styles from "./ChatPanel.module.css";

// 예시 질문 — 사용자가 처음 진입 시 클릭해 바로 사용할 수 있습니다.
const EXAMPLE_QUESTIONS = [
  "핵심 결론이 뭐야?",
  "3줄로 다시 설명해줘",
  "중요한 일정만 뽑아줘",
  "발표용 말투로 바꿔줘",
];

interface ChatPanelProps {
  historyId: number;
}

export default function ChatPanel({ historyId }: ChatPanelProps) {
  const { user, accessToken, tryRefreshToken } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  // 토큰 만료로 재로그인이 필요한 상태. localStorage 대화는 유지됩니다.
  const [authExpired, setAuthExpired] = useState(false);
  const [error, setError] = useState("");
  // 응답 모드: strict(문서 근거만) / chat(해석·일반 설명 허용)
  const [mode, setMode] = useState<ChatMode>("chat");

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── 초기 로드: localStorage 복원 ────────────────────────────────────────────
  useEffect(() => {
    if (!user) return;
    const stored = getMessages(user.user_id, historyId);
    setMessages(stored);
  }, [user, historyId]);

  // ── 메시지 변경 시 localStorage 동기화 ──────────────────────────────────────
  // messages.length === 0 일 때는 저장하지 않습니다.
  // 이유: 컴포넌트 마운트 직후 restore effect가 setMessages를 호출하기 전에
  //       이 effect가 빈 배열로 먼저 실행되어 저장된 대화를 덮어쓸 수 있습니다.
  //       React StrictMode(개발)에서는 이중 실행으로 인해 데이터 소실이 확정됩니다.
  //       빈 배열을 저장해야 하는 "채팅 초기화" 기능이 추가될 경우,
  //       해당 핸들러에서 saveMessages를 직접 호출하는 방식으로 처리합니다.
  useEffect(() => {
    if (!user || messages.length === 0) return;
    saveMessages(user.user_id, historyId, messages);
  }, [messages, user, historyId]);

  // ── 새 메시지 도착 시 하단 스크롤 ──────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // ── 전송 핸들러 ─────────────────────────────────────────────────────────────
  async function handleSend() {
    if (!accessToken || !input.trim() || loading || authExpired) return;

    const question = input.trim();
    setInput("");
    setError("");

    // 현재 대화 스냅샷 — 에러 시 롤백 기준점
    const prevMessages = messages;

    // 사용자 메시지를 즉시 화면에 표시
    const withUserMsg: ChatMessage[] = [
      ...prevMessages,
      { role: "user", content: question },
    ];
    setMessages(withUserMsg);
    setLoading(true);

    // 실제 API 호출 함수 (token을 인자로 받아 재시도 가능)
    async function callChat(token: string): Promise<string> {
      // 이전 대화(prevMessages)만 서버에 전달합니다.
      // 현재 질문은 question 파라미터로 별도 전달합니다.
      const result = await sendChat(historyId, prevMessages, question, token, mode);
      return result.answer;
    }

    try {
      const answer = await callChat(accessToken);
      setMessages([...withUserMsg, { role: "assistant", content: answer }]);
    } catch (e) {
      if (e instanceof UnauthorizedError) {
        // access_token 만료 → refresh 1회 시도
        const newToken = await tryRefreshToken();
        if (newToken) {
          try {
            const answer = await callChat(newToken);
            setMessages([...withUserMsg, { role: "assistant", content: answer }]);
          } catch (retryErr) {
            // 재시도도 실패 — 사용자 메시지 롤백
            setMessages(prevMessages);
            setError(retryErr instanceof Error ? retryErr.message : "오류가 발생했습니다.");
          }
        } else {
          // refresh 실패 — 인증 만료 상태로 전환, localStorage는 유지
          setMessages(prevMessages);
          setAuthExpired(true);
        }
      } else {
        setMessages(prevMessages);
        setError(e instanceof Error ? e.message : "오류가 발생했습니다.");
      }
    } finally {
      setLoading(false);
      // 에러가 없을 때만 입력창 포커스 복귀
      if (!authExpired) inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleExampleClick(question: string) {
    setInput(question);
    inputRef.current?.focus();
  }

  return (
    <div className={styles.panel}>

      {/* ── 패널 헤더 ────────────────────────────────────────────────── */}
      <div className={styles.panelHeader}>
        <div className={styles.panelHeaderLeft}>
          <span className={styles.panelTitle}>문서 기반 질문하기</span>
          <span className={styles.panelHint}>
            {mode === "chat"
              ? "문서 근거 우선 · 해석·일반 설명 허용"
              : "문서에 있는 내용만 답변"}
          </span>
        </div>
        <div className={styles.modeToggle}>
          <button
            className={`${styles.modeBtn} ${mode === "chat" ? styles.modeBtnActive : ""}`}
            onClick={() => setMode("chat")}
            title="문서 근거 우선, 해석과 일반 설명도 허용합니다"
          >
            대화형
          </button>
          <button
            className={`${styles.modeBtn} ${mode === "strict" ? styles.modeBtnActive : ""}`}
            onClick={() => setMode("strict")}
            title="문서에 있는 내용만 답변합니다"
          >
            엄격
          </button>
        </div>
      </div>

      {/* ── 인증 만료 배너 ───────────────────────────────────────────── */}
      {authExpired && (
        <div className={styles.authBanner}>
          로그인이 만료되었습니다.{" "}
          <a href="/login" className={styles.authBannerLink}>
            다시 로그인하기 →
          </a>
          <span className={styles.authBannerSub}>
            (이전 대화 내용은 로그인 후에도 유지됩니다)
          </span>
        </div>
      )}

      {/* ── 메시지 목록 ──────────────────────────────────────────────── */}
      <div className={styles.messageList}>

        {/* 대화가 없을 때 예시 질문 chips */}
        {messages.length === 0 && (
          <div className={styles.emptyState}>
            <p className={styles.emptyHint}>
              이 문서에 대해 궁금한 점을 질문해보세요.
            </p>
            <div className={styles.exampleChips}>
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className={styles.exampleChip}
                  onClick={() => handleExampleClick(q)}
                  disabled={authExpired}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 대화 말풍선 */}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`${styles.bubble} ${
              msg.role === "user" ? styles.bubbleUser : styles.bubbleAssistant
            }`}
          >
            <span className={styles.bubbleRole}>
              {msg.role === "user" ? "나" : "AI"}
            </span>
            <p className={styles.bubbleContent}>{msg.content}</p>
          </div>
        ))}

        {/* 로딩 말풍선 */}
        {loading && (
          <div className={`${styles.bubble} ${styles.bubbleAssistant}`}>
            <span className={styles.bubbleRole}>AI</span>
            <p className={styles.bubbleContent}>
              <span className={styles.typingDots}>
                <span />
                <span />
                <span />
              </span>
            </p>
          </div>
        )}

        {/* 에러 메시지 */}
        {error && <div className={styles.errorMsg}>{error}</div>}

        {/* 스크롤 앵커 */}
        <div ref={bottomRef} />
      </div>

      {/* ── 입력 영역 ────────────────────────────────────────────────── */}
      <div className={styles.inputRow}>
        <textarea
          ref={inputRef}
          className={styles.input}
          placeholder={
            authExpired
              ? "로그인 후 다시 질문할 수 있습니다."
              : "질문을 입력하세요... (Enter로 전송, Shift+Enter로 줄바꿈)"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || authExpired}
          rows={2}
        />
        <button
          className={styles.sendButton}
          onClick={handleSend}
          disabled={!input.trim() || loading || authExpired}
        >
          전송
        </button>
      </div>
    </div>
  );
}
