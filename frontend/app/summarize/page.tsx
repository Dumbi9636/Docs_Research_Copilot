"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import styles from "../page.module.css";
import { summarizeText, summarizeFile, UnauthorizedError } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import { getSession, saveSession, getDraft, saveDraft } from "../lib/summarizeStorage";
import Header from "../components/Header";
import FileUploadInput from "../components/FileUploadInput";
import SummaryResult from "../components/SummaryResult";
import DownloadSection from "../components/DownloadSection";
import ChatPanel from "../components/ChatPanel";

// 입력 우선순위 정책: 파일이 선택되어 있으면 파일을 우선합니다.
// 파일이 없을 때만 textarea 텍스트를 사용합니다.

export default function SummarizePage() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [historyId, setHistoryId] = useState<number | undefined>(undefined);
  const [error, setError] = useState("");
  const [cancelledMessage, setCancelledMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [dots, setDots] = useState("");

  // ── 세션 복원 관련 상태 ──────────────────────────────────────────────────────
  // File 객체는 직렬화 불가 → 파일명만 복원해서 표시용으로 사용합니다.
  const [restoredFilename, setRestoredFilename] = useState("");
  // true: localStorage에서 복원된 세션을 현재 보여주고 있는 상태
  const [isRestored, setIsRestored] = useState(false);
  // 복원 시도가 완료됐는지 (복원 여부와 무관, 중복 복원 방지용)
  const restoredRef = useRef(false);

  const { user, isLoggedIn, isLoading, accessToken, tryRefreshToken } = useAuth();
  const router = useRouter();

  const abortControllerRef = useRef<AbortController | null>(null);

  // ── 로딩 dots 애니메이션 ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!loading) {
      setDots("");
      return;
    }
    const id = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 500);
    return () => clearInterval(id);
  }, [loading]);

  // ── 텍스트 draft 자동 저장 (debounce) ───────────────────────────────────────
  // 사용자가 입력을 멈춘 뒤 600ms 후에 localStorage에 저장합니다.
  // 로그아웃 상태(user=null)이면 저장하지 않습니다.
  // 파일이 선택된 경우에도 저장하지 않습니다(파일 요약이 우선).
  useEffect(() => {
    if (!user || isLoading || file) return;
    const timeout = setTimeout(() => {
      saveDraft(user.user_id, text);
    }, 600);
    return () => clearTimeout(timeout);
  }, [text, user, isLoading, file]);

  // ── 세션 복원 ────────────────────────────────────────────────────────────────
  // 인증이 완료된 직후 1회만 실행합니다.
  // isLoading이 false가 되고 user가 확정된 시점에 localStorage를 읽습니다.
  useEffect(() => {
    if (isLoading || !user) return;
    if (restoredRef.current) return; // 이미 복원 시도함
    restoredRef.current = true;

    // 텍스트 draft 복원 — 요약 결과 유무와 무관하게 항상 시도합니다.
    const draft = getDraft(user.user_id);
    if (draft) setText(draft);

    // 요약 세션 복원
    const session = getSession(user.user_id);
    if (!session) return;

    setSummary(session.summary);
    setSteps(session.steps);
    setHistoryId(session.history_id);
    setRestoredFilename(session.source_filename);
    setIsRestored(true);
  }, [isLoading, user]);

  // ── 세션 저장 ────────────────────────────────────────────────────────────────
  // summary와 historyId가 유효할 때마다 최신 상태를 덮어씁니다.
  useEffect(() => {
    if (!user || !summary || historyId === undefined) return;
    saveSession(user.user_id, {
      history_id: historyId,
      summary,
      steps,
      source_filename: file?.name ?? restoredFilename,
    });
  }, [summary, historyId, steps, file, restoredFilename, user]);

  // ── 파일 선택 핸들러 ─────────────────────────────────────────────────────────
  function handleFileChange(selected: File | null) {
    setFile(selected);
    setSummary("");
    setSteps([]);
    setHistoryId(undefined);
    setError("");
    setCancelledMessage("");
    // 새 파일이 선택되면 복원 상태 및 텍스트 draft 초기화
    setIsRestored(false);
    setRestoredFilename("");
    // 파일 업로드 모드에서는 텍스트 draft가 의미 없으므로 삭제합니다.
    if (user) saveDraft(user.user_id, "");
  }

  // ── 요약 실행 핸들러 ─────────────────────────────────────────────────────────
  async function handleSummarize() {
    if (!accessToken) return;

    setError("");
    setCancelledMessage("");
    setSummary("");
    setSteps([]);
    setHistoryId(undefined);
    setIsRestored(false);    // 새 요약 시작 시 복원 배너 제거
    setRestoredFilename(""); // 새 요약 결과로 대체됨
    // 파일 요약이 아닌 경우, 현재 텍스트를 draft로 저장합니다.
    // (요약 실패 시에도 입력한 텍스트가 유지됩니다)
    if (user && !file) saveDraft(user.user_id, text);
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const result = await _callSummarize(accessToken, controller.signal);
      setSummary(result.summary);
      setSteps(result.steps);
      setHistoryId(result.history_id);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setCancelledMessage("요약이 취소되었습니다.");
      } else if (e instanceof UnauthorizedError) {
        // access_token 만료 → refresh 시도 후 1회 재시도
        const newToken = await tryRefreshToken();
        if (newToken) {
          try {
            const result = await _callSummarize(newToken, controller.signal);
            setSummary(result.summary);
            setSteps(result.steps);
            setHistoryId(result.history_id);
          } catch (retryErr) {
            setError(retryErr instanceof Error ? retryErr.message : "알 수 없는 오류가 발생했습니다.");
          }
        } else {
          router.push("/login");
        }
      } else {
        setError(e instanceof Error ? e.message : "알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  }

  async function _callSummarize(token: string, signal: AbortSignal) {
    return file
      ? summarizeFile(file, token, { signal })
      : summarizeText(text, token, { signal });
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
  }

  const hasInput = file !== null || text.trim() !== "";
  const canSubmit = isLoggedIn && hasInput && !loading;

  // 다운로드 섹션에 넘길 파일명: 실제 파일 선택 > 복원된 파일명 > 빈 문자열 순으로 사용
  const effectiveFilename = file?.name ?? restoredFilename;

  return (
    <div className={styles.pageWrapper}>
      <Header />

      <section className={styles.hero}>
        <h1 className={styles.heroTitle}>
          문서와 이미지를 업로드하고<br />
          <span>핵심만 빠르게 요약</span>하세요
        </h1>
        <p className={styles.heroDesc}>
          텍스트를 직접 붙여넣거나 파일을 업로드하면 AI가 한국어로 요약합니다
        </p>
        <div className={styles.heroBadges}>
          <span className={styles.badge}>txt</span>
          <span className={styles.badge}>pdf</span>
          <span className={styles.badge}>docx</span>
          <span className={styles.badge}>png / jpg</span>
          <span className={styles.badge}>이미지 OCR</span>
          <span className={styles.badge}>스캔 PDF</span>
        </div>
      </section>

      <div className={styles.contentArea}>
        <div className={styles.mainCard}>

          <label htmlFor="docInput" className={styles.label}>
            텍스트 요약
          </label>
          <textarea
            id="docInput"
            className={`${styles.textarea} ${file ? styles.textareaDisabled : ""}`}
            disabled={file !== null}
            placeholder="요약할 내용을 여기에 붙여넣으세요."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />

          <div className={styles.divider}>또는</div>

          <FileUploadInput file={file} onFileChange={handleFileChange} />

          {/* 복원된 파일명 표시 — file input은 비워져 있지만 이전 파일명을 안내합니다 */}
          {!file && restoredFilename && (
            <div className={styles.restoredFileHint}>
              이전 파일: <strong>{restoredFilename}</strong>
              <span className={styles.restoredFileNote}>(새로고침으로 파일 선택이 초기화되었습니다)</span>
            </div>
          )}

          {!isLoading && !isLoggedIn && (
            <div className={styles.authNotice}>
              요약 기능을 사용하려면{" "}
              <a href="/login" className={styles.authNoticeLink}>
                로그인
              </a>
              이 필요합니다.
            </div>
          )}

          <div className={styles.buttonRow}>
            {loading && (
              <button className={styles.cancelButton} onClick={handleCancel}>
                취소
              </button>
            )}
            <button
              className={styles.button}
              onClick={handleSummarize}
              disabled={!canSubmit}
            >
              {loading ? `요약중${dots}` : "요약하기"}
            </button>
          </div>

          {error && <div className={styles.error}>{error}</div>}
          {cancelledMessage && (
            <div className={styles.cancelledMessage}>{cancelledMessage}</div>
          )}

          {(summary || steps.length > 0) && (
            <div className={styles.resultDivider} />
          )}

          {/* 복원 안내 배너 — 요약 결과가 있을 때만 표시 */}
          {isRestored && summary && (
            <div className={styles.restoredBanner}>
              이전 작업이 복원되었습니다.
              <button
                className={styles.restoredDismiss}
                onClick={() => setIsRestored(false)}
              >
                닫기
              </button>
            </div>
          )}

          <SummaryResult summary={summary} steps={steps} />
          {summary && accessToken && (
            <DownloadSection
              summary={summary}
              sourceFilename={effectiveFilename}
              accessToken={accessToken}
              historyId={historyId}
            />
          )}
        </div>

        {/* ── 문서 기반 대화 패널 ──────────────────────────────────────────── */}
        {/* historyId가 있을 때만 렌더링 — 복원 후에도 자동으로 표시됩니다.      */}
        {/* key={historyId}를 사용해 historyId가 바뀔 때 완전히 remount합니다.    */}
        {/* 이렇게 하면 이전 문서의 messages 상태가 새 문서로 누출되지 않습니다.  */}
        {historyId !== undefined && (
          <ChatPanel key={historyId} historyId={historyId} />
        )}

        <div className={styles.backLinkRow}>
          <Link href="/" className={styles.backLinkSmall}>← 홈으로 돌아가기</Link>
        </div>
      </div>
    </div>
  );
}
