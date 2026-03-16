"use client";

import { useState, useEffect, useRef } from "react";
import styles from "./page.module.css";
import { summarizeText, summarizeFile } from "./lib/api";
import FileUploadInput from "./components/FileUploadInput";
import SummaryResult from "./components/SummaryResult";
import DownloadSection from "./components/DownloadSection";

// 입력 우선순위 정책: 파일이 선택되어 있으면 파일을 우선합니다.
// 파일이 없을 때만 textarea 텍스트를 사용합니다.
// 이 정책은 handleSummarize 분기, 버튼 비활성화 조건, UI 힌트에서 일관되게 적용됩니다.

export default function Home() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [cancelledMessage, setCancelledMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [dots, setDots] = useState("");

  // 진행 중인 요약 요청을 취소하기 위한 ref입니다.
  // 렌더링에 영향을 주지 않으므로 useState가 아닌 useRef를 사용합니다.
  const abortControllerRef = useRef<AbortController | null>(null);

  // loading 상태에 따라 점 애니메이션을 시작하거나 정리합니다.
  // loading이 false가 되면 cleanup 함수가 interval을 제거하고 dots를 초기화합니다.
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
    // 파일이 바뀌면 이전 결과를 초기화합니다.
    setSummary("");
    setSteps([]);
    setError("");
    setCancelledMessage("");
  }

  async function handleSummarize() {
    setError("");
    setCancelledMessage("");
    setSummary("");
    setSteps([]);
    setLoading(true);

    // 새 요청마다 AbortController를 생성합니다.
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // 파일 우선 정책: file이 있으면 파일 요약, 없으면 텍스트 요약
      const result = file
        ? await summarizeFile(file, { signal: controller.signal })
        : await summarizeText(text, { signal: controller.signal });
      setSummary(result.summary);
      setSteps(result.steps);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        // 사용자가 직접 취소한 경우 — 에러가 아니므로 error state를 건드리지 않습니다.
        setCancelledMessage("요약이 취소되었습니다.");
      } else {
        // api.ts에서 네트워크 에러와 API 에러 모두 Error로 변환해 throw합니다.
        setError(e instanceof Error ? e.message : "알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
  }

  const canSubmit = file !== null || text.trim() !== "";

  return (
    <main className={styles.container}>
      <h1 className={styles.title}>Docs Research Copilot</h1>
      <p className={styles.subtitle}>문서를 붙여넣거나 txt / pdf / docx 파일을 업로드하면 AI가 요약합니다.</p>

      {/* ── 직접 입력 영역 ──────────────────────────────────────────────────── */}
      <label htmlFor="docInput" className={styles.label}>
        직접 입력
      </label>
      <textarea
        id="docInput"
        // disabled + CSS 모두 적용해 파일 우선 정책을 동작과 시각 양쪽에서 일치시킵니다.
        className={`${styles.textarea} ${file ? styles.textareaDisabled : ""}`}
        disabled={file !== null}
        placeholder="요약할 문서 내용을 여기에 붙여넣으세요..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      {/* ── 파일 업로드 영역 ─────────────────────────────────────────────────── */}
      <FileUploadInput file={file} onFileChange={handleFileChange} />

      <div className={styles.divider}></div>

      {/* ── 요약 / 취소 버튼 ─────────────────────────────────────────────────── */}
      <br />
      <div className={styles.buttonRow}>
        {loading && (
          <button className={styles.cancelButton} onClick={handleCancel}>
            취소
          </button>
        )}
        <button
          className={styles.button}
          onClick={handleSummarize}
          disabled={loading || !canSubmit}
        >
          {loading ? `요약중${dots}` : "요약하기"}
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {cancelledMessage && (
        <div className={styles.cancelledMessage}>{cancelledMessage}</div>
      )}

      {/* ── 결과 영역 ────────────────────────────────────────────────────────── */}
      <SummaryResult summary={summary} steps={steps} />
      {summary && (
        <DownloadSection summary={summary} sourceFilename={file?.name ?? ""} />
      )}
    </main>
  );
}
