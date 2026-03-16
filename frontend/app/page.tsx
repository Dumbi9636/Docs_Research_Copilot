"use client";

import { useState, useEffect, useRef } from "react";
import styles from "./page.module.css";
import { summarizeText, summarizeFile } from "./lib/api";
import FileUploadInput from "./components/FileUploadInput";
import SummaryResult from "./components/SummaryResult";
import DownloadSection from "./components/DownloadSection";

// 입력 우선순위 정책: 파일이 선택되어 있으면 파일을 우선합니다.
// 파일이 없을 때만 textarea 텍스트를 사용합니다.

const CATEGORY_CARDS = [
  {
    icon: "📄",
    name: "문서 요약",
    desc: "txt · pdf · docx · image 형식의 파일을 업로드하면 핵심 내용을 한국어로 요약합니다.",
    active: true,
  },
  {
    icon: "🗂️",
    name: "작업 기록",
    desc: "로그인 후 이전 요약 결과를 조회하고 재사용할 수 있습니다. 최근 작업을 이어보거나 자주 쓰는 문서를 빠르게 다시 요약할 수 있습니다.",
    active: false,
  },
];

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
    setError("");
    setCancelledMessage("");
  }

  async function handleSummarize() {
    setError("");
    setCancelledMessage("");
    setSummary("");
    setSteps([]);
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const result = file
        ? await summarizeFile(file, { signal: controller.signal })
        : await summarizeText(text, { signal: controller.signal });
      setSummary(result.summary);
      setSteps(result.steps);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setCancelledMessage("요약이 취소되었습니다.");
      } else {
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
    <div className={styles.pageWrapper}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <span className={styles.headerLogo}>
            Docs<span>Research</span> Copilot
          </span>
          <div className={styles.headerActions}>
            <button className={`${styles.headerBtn} ${styles.headerBtnGhost}`}>
              로그인
            </button>
            <button className={`${styles.headerBtn} ${styles.headerBtnPrimary}`}>
              시작하기
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
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

        {/* ── 메인 카드 (입력 / 요약 / 결과) ──────────────────────────────── */}
        <div className={styles.mainCard}>

          {/* 직접 입력 */}
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

          {/* 구분선 */}
          <div className={styles.divider}>또는</div>

          {/* 파일 업로드 */}
          <FileUploadInput file={file} onFileChange={handleFileChange} />

          {/* 버튼 행 */}
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

          {/* 메시지 */}
          {error && <div className={styles.error}>{error}</div>}
          {cancelledMessage && (
            <div className={styles.cancelledMessage}>{cancelledMessage}</div>
          )}

          {/* 결과 영역 */}
          {(summary || steps.length > 0) && (
            <div className={styles.resultDivider} />
          )}
          <SummaryResult summary={summary} steps={steps} />
          {summary && (
            <DownloadSection summary={summary} sourceFilename={file?.name ?? ""} />
          )}
        </div>

        {/* ── 카테고리 카드 ─────────────────────────────────────────────────── */}
        <section className={styles.categorySection}>
          <h2 className={styles.categorySectionTitle}>주요 기능</h2>
          <div className={styles.categoryGrid}>
            {CATEGORY_CARDS.map((card) => (
              <div
                key={card.name}
                className={`${styles.categoryCard} ${
                  card.active ? styles.categoryCardActive : styles.categoryCardDisabled
                }`}
              >
                <div className={styles.categoryIcon}>{card.icon}</div>
                <p className={styles.categoryCardName}>{card.name}</p>
                <p className={styles.categoryCardDesc}>{card.desc}</p>
                <span
                  className={`${styles.categoryCardBadge} ${
                    card.active ? styles.badgeActive : styles.badgeSoon
                  }`}
                >
                  {card.active ? "지원" : "준비 중"}
                </span>
              </div>
            ))}
          </div>
        </section>

      </div>
    </div>
  );
}
