"use client";

import { useState } from "react";
import styles from "./page.module.css";

const BACKEND_URL = "http://localhost:8000";

export default function Home() {
  const [text, setText] = useState("");
  const [summary, setSummary] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSummarize() {
    setError("");
    setSummary("");
    setSteps([]);
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

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

  return (
    <main className={styles.container}>
      <h1 className={styles.title}>Docs Research Copilot</h1>
      <p className={styles.subtitle}>문서를 붙여넣고 AI로 요약합니다.</p>

      <label htmlFor="docInput" className={styles.label}>
        문서 내용
      </label>
      <textarea
        id="docInput"
        className={styles.textarea}
        placeholder="요약할 문서 내용을 여기에 붙여넣으세요..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      <button
        className={styles.button}
        onClick={handleSummarize}
        disabled={loading || text.trim() === ""}
      >
        {loading ? "요약 중..." : "요약하기"}
      </button>

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
