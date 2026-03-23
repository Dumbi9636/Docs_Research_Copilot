"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import styles from "../page.module.css";
import { summarizeText, summarizeFile, UnauthorizedError } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import Header from "../components/Header";
import FileUploadInput from "../components/FileUploadInput";
import SummaryResult from "../components/SummaryResult";
import DownloadSection from "../components/DownloadSection";

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

  const { isLoggedIn, isLoading, accessToken, tryRefreshToken } = useAuth();
  const router = useRouter();

  const abortControllerRef = useRef<AbortController | null>(null);

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

  function handleFileChange(selected: File | null) {
    setFile(selected);
    setSummary("");
    setSteps([]);
    setHistoryId(undefined);
    setError("");
    setCancelledMessage("");
  }

  async function handleSummarize() {
    if (!accessToken) return;

    setError("");
    setCancelledMessage("");
    setSummary("");
    setSteps([]);
    setHistoryId(undefined);
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
            직접 입력
          </label>
          <textarea
            id="docInput"
            className={`${styles.textarea} ${file ? styles.textareaDisabled : ""}`}
            disabled={file !== null}
            placeholder="요약할 문서 내용을 여기에 붙여넣으세요..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />

          <div className={styles.divider}>또는</div>

          <FileUploadInput file={file} onFileChange={handleFileChange} />

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
          <SummaryResult summary={summary} steps={steps} />
          {summary && accessToken && (
            <DownloadSection
              summary={summary}
              sourceFilename={file?.name ?? ""}
              accessToken={accessToken}
              historyId={historyId}
            />
          )}
        </div>

        <div className={styles.backLinkRow}>
          <Link href="/" className={styles.backLinkSmall}>← 홈으로 돌아가기</Link>
        </div>
      </div>
    </div>
  );
}
