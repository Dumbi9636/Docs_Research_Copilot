"use client";

import { useState } from "react";
import styles from "./page.module.css";

const BACKEND_URL = "http://localhost:8000";

// 입력 우선순위 정책: 파일이 선택되어 있으면 파일을 우선합니다.
// 파일이 없을 때만 textarea 텍스트를 사용합니다.
// 이 정책은 handleSummarize 분기, 버튼 비활성화 조건, UI 힌트에서 일관되게 적용됩니다.

export default function Home() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    // 파일 선택 시 이전 결과를 초기화합니다.
    setSummary("");
    setSteps([]);
    setError("");
  }

  function handleClearFile() {
    setFile(null);
    // input[type=file]은 React state로 값을 제어할 수 없으므로
    // input 요소를 직접 찾아 값을 초기화합니다.
    const input = document.getElementById("fileInput") as HTMLInputElement | null;
    if (input) input.value = "";
  }

  async function handleSummarize() {
    setError("");
    setSummary("");
    setSteps([]);
    setLoading(true);

    try {
      let res: Response;

      if (file) {
        // ── 파일 업로드 경로 ────────────────────────────────────────────────
        // 파일이 선택된 경우 multipart/form-data로 /summarize/file에 전송합니다.
        // Content-Type 헤더는 FormData 사용 시 브라우저가 자동으로 설정합니다.
        const formData = new FormData();
        formData.append("file", file);
        res = await fetch(`${BACKEND_URL}/summarize/file`, {
          method: "POST",
          body: formData,
        });
      } else {
        // ── 텍스트 직접 입력 경로 ────────────────────────────────────────────
        // 기존 /summarize 엔드포인트를 그대로 사용합니다.
        res = await fetch(`${BACKEND_URL}/summarize`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
      }

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail ?? "알 수 없는 오류가 발생했습니다.");
        return;
      }

      setSummary(data.summary);
      setSteps(data.steps ?? []);
    } catch {
      setError("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
    } finally {
      setLoading(false);
    }
  }

  // 파일이 선택되거나 textarea에 텍스트가 있을 때만 버튼을 활성화합니다.
  const canSubmit = file !== null || text.trim() !== "";

  return (
    <main className={styles.container}>
      <h1 className={styles.title}>Docs Research Copilot</h1>
      <p className={styles.subtitle}>문서를 붙여넣거나 txt 파일을 업로드하면 AI가 요약합니다.</p>

      {/* ── 직접 입력 영역 ──────────────────────────────────────────────────── */}
      <label htmlFor="docInput" className={styles.label}>
        직접 입력
      </label>
      <textarea
        id="docInput"
        // disabled + CSS 모두 적용해 파일 우선 정책을 동작과 시각 양쪽에서 일치시킵니다.
        // disabled만 쓰면 스타일 변화가 없고, CSS만 쓰면 실제로 입력이 가능해 정책이 어긋납니다.
        className={`${styles.textarea} ${file ? styles.textareaDisabled : ""}`}
        disabled={file !== null}
        placeholder="요약할 문서 내용을 여기에 붙여넣으세요..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      {/* ── 파일 업로드 영역 ─────────────────────────────────────────────────── */}
      <label htmlFor="fileInput" className={styles.label}>
        txt 파일 업로드
        <span className={styles.policyHint}>파일이 선택되면 파일을 우선합니다</span>
      </label>
      <input
        id="fileInput"
        type="file"
        accept=".txt"
        className={styles.fileInput}
        onChange={handleFileChange}
      />

      {file && (
        <div className={styles.fileInfo}>
          <span>선택된 파일: {file.name}</span>
          <button type="button" className={styles.clearFile} onClick={handleClearFile}>
            ✕ 파일 제거
          </button>
        </div>
      )}

      {/* ── 구분선 ──────────────────────────────────────────────────────────── */}
      <div className={styles.divider}></div>
      
      {/* ── 요약 버튼 ────────────────────────────────────────────────────────── */}
      <button
        className={styles.button}
        onClick={handleSummarize}
        disabled={loading || !canSubmit}
      >
        {loading ? "요약 중..." : "요약하기"}
      </button>

      {/* ── 결과 영역 ────────────────────────────────────────────────────────── */}
      {error && <div className={styles.error}>{error}</div>}

      {summary && (
        <div className={styles.resultBox}>
          <div className={styles.resultLabel}>요약 결과</div>
          {summary}
        </div>
      )}

      {steps.length > 0 && (
        <ul className={styles.stepsList}>
          {steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ul>
      )}
    </main>
  );
}
