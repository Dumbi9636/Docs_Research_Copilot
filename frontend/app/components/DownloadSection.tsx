"use client";

// 형식 목록을 한 곳에서 관리합니다.
// 새 출력 형식 추가 시 이 배열에만 항목을 추가하면 UI가 자동으로 반영됩니다.
// 백엔드 export_service._EXPORTERS에도 동일한 key로 추가해야 합니다.
const FORMAT_OPTIONS = [
  { value: "txt", label: "텍스트 (.txt)" },
  { value: "docx", label: "Word (.docx)" },
  { value: "pdf", label: "PDF (.pdf)" },
] as const;

type ExportFormat = (typeof FORMAT_OPTIONS)[number]["value"];

import { useState } from "react";
import { exportSummary } from "../lib/api";
import styles from "../page.module.css";

interface Props {
  summary: string;
  sourceFilename?: string;
  accessToken: string;
  historyId?: number;
}

export default function DownloadSection({ summary, sourceFilename = "", accessToken, historyId }: Props) {
  const [format, setFormat] = useState<ExportFormat>("txt");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleDownload() {
    setError("");
    setLoading(true);
    try {
      await exportSummary(summary, format, sourceFilename, accessToken, historyId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "다운로드 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.downloadSection}>
      <select
        value={format}
        onChange={(e) => setFormat(e.target.value as ExportFormat)}
        disabled={loading}
        className={styles.downloadSelect}
      >
        {FORMAT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <button
        onClick={handleDownload}
        disabled={loading}
        className={styles.downloadButton}
      >
        {loading ? "다운로드 중..." : "다운로드"}
      </button>
      {error && <div className={styles.error}>{error}</div>}
    </div>
  );
}
