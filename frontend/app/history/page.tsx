"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getActivity, deleteActivity, exportSummary, ActivityItem, UnauthorizedError, ExportFormat } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import Header from "../components/Header";
import styles from "./page.module.css";

// ── 상수 ──────────────────────────────────────────────────────────────────────

type FilterType = "ALL" | "SUMMARY" | "DOWNLOAD";

const FILTER_OPTIONS: { value: FilterType; label: string }[] = [
  { value: "ALL", label: "전체" },
  { value: "SUMMARY", label: "요약" },
  { value: "DOWNLOAD", label: "다운로드" },
];

const ACTIVITY_LABEL: Record<string, string> = { SUMMARY: "요약", DOWNLOAD: "다운로드" };
const STATUS_LABEL: Record<string, string> = { SUCCESS: "O", FAILED: "실패" };

// ── 날짜 포맷 ─────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// ── 상세 모달 ─────────────────────────────────────────────────────────────────

function DetailModal({
  item,
  onClose,
  onRedownload,
}: {
  item: ActivityItem;
  onClose: () => void;
  onRedownload: (item: ActivityItem) => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rows: { label: string; value: React.ReactNode }[] = [
    { label: "활동 유형", value: ACTIVITY_LABEL[item.activity_type] ?? item.activity_type },
    { label: "파일명", value: item.file_name ?? "-" },
    { label: "문서 타입", value: item.document_type ?? "-" },
    { label: "다운로드 형식", value: item.download_format?.toUpperCase() ?? "-" },
    { label: "상태", value: STATUS_LABEL[item.status] ?? item.status },
    { label: "생성일시", value: formatDate(item.created_at) },
  ];

  return (
    <div className={styles.modalBackdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <span className={styles.modalTitle}>상세 정보</span>
          <button className={styles.modalClose} onClick={onClose}>✕</button>
        </div>
        <div className={styles.modalBody}>
          {rows.map(({ label, value }) => (
            <div className={styles.detailRow} key={label}>
              <span className={styles.detailLabel}>{label}</span>
              <span className={styles.detailValue}>{value}</span>
            </div>
          ))}

          {item.activity_type === "DOWNLOAD" && item.summary_text && item.download_format && (
            <div className={styles.detailSection}>
              <button
                className={styles.redownloadButtonModal}
                onClick={() => onRedownload(item)}
              >
                {item.download_format.toUpperCase()}로 재다운로드
              </button>
            </div>
          )}

          {item.summary_text && item.activity_type === "SUMMARY" && (
            <div className={styles.detailSection}>
              <p className={styles.detailSectionTitle}>요약문</p>
              <p className={styles.summaryText}>{item.summary_text}</p>
            </div>
          )}

          {item.error_message && (
            <div className={styles.detailSection}>
              <p className={styles.detailSectionTitle}>오류 메시지</p>
              <p className={styles.errorText}>{item.error_message}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const { accessToken, isLoggedIn, isLoading, tryRefreshToken } = useAuth();
  const router = useRouter();

  // 원본 배열 (API 응답 — 변경하지 않음)
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState("");

  // 컨트롤 상태
  const [filterType, setFilterType] = useState<FilterType>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // 상세 모달
  const [selectedItem, setSelectedItem] = useState<ActivityItem | null>(null);

  // 삭제 중인 항목 키
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  // 재다운로드 중인 항목 키
  const [redownloadingKey, setRedownloadingKey] = useState<string | null>(null);

  // ── 데이터 fetch ────────────────────────────────────────────────────────────

  useEffect(() => {
    if (isLoading) return;
    if (!isLoggedIn || !accessToken) {
      router.replace("/login");
      return;
    }

    async function load(token: string) {
      try {
        const data = await getActivity(token);
        setItems(data);
      } catch (e) {
        if (e instanceof UnauthorizedError) {
          const newToken = await tryRefreshToken();
          if (newToken) {
            try {
              const data = await getActivity(newToken);
              setItems(data);
            } catch {
              setError("이력을 불러오지 못했습니다.");
            }
          } else {
            router.replace("/login");
          }
        } else {
          setError(e instanceof Error ? e.message : "이력을 불러오지 못했습니다.");
        }
      } finally {
        setFetching(false);
      }
    }

    load(accessToken);
  }, [isLoading, isLoggedIn, accessToken, router, tryRefreshToken]);

  // ── 필터 + 검색 (원본 배열 기반 계산) ─────────────────────────────────────

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return items.filter((item) => {
      const matchType = filterType === "ALL" || item.activity_type === filterType;
      const matchSearch = !q || (item.file_name?.toLowerCase().includes(q) ?? false);
      return matchType && matchSearch;
    });
  }, [items, filterType, searchQuery]);

  // ── 삭제 ───────────────────────────────────────────────────────────────────

  async function handleDelete(item: ActivityItem) {
    const label = ACTIVITY_LABEL[item.activity_type] ?? "항목";
    if (!window.confirm(`이 ${label} 이력을 삭제하시겠습니까?`)) return;
    if (!accessToken) return;

    const key = `${item.activity_type}-${item.id}`;
    setDeletingKey(key);
    try {
      await deleteActivity(item.activity_type, item.id, accessToken);
      setItems((prev) =>
        prev.filter((i) => !(i.activity_type === item.activity_type && i.id === item.id))
      );
      if (selectedItem?.activity_type === item.activity_type && selectedItem?.id === item.id) {
        setSelectedItem(null);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "삭제 중 오류가 발생했습니다.");
    } finally {
      setDeletingKey(null);
    }
  }

  // ── 재다운로드 ─────────────────────────────────────────────────────────────

  async function handleRedownload(item: ActivityItem) {
    if (!accessToken || !item.summary_text || !item.download_format) return;

    const key = `${item.activity_type}-${item.id}`;
    setRedownloadingKey(key);
    try {
      await exportSummary(
        item.summary_text,
        item.download_format as ExportFormat,
        item.file_name ?? "",
        accessToken,
        item.linked_history_id ?? undefined,
        true,  // skip_log: 재다운로드는 이력에 추가하지 않음
      );
    } catch (e) {
      alert(e instanceof Error ? e.message : "재다운로드 중 오류가 발생했습니다.");
    } finally {
      setRedownloadingKey(null);
    }
  }

  // ── 렌더 ───────────────────────────────────────────────────────────────────

  return (
    <div className={styles.pageWrapper}>
      <Header />

      <main className={styles.main}>

        {/* 제목 행 */}
        <div className={styles.titleRow}>
          <h1 className={styles.title}>활동 이력</h1>
          <Link href="/" className={styles.backLink}>← 메인으로</Link>
        </div>

        {/* 컨트롤 바 (필터 + 검색) */}
        {!fetching && !error && (
          <div className={styles.controlRow}>
            <div className={styles.filterBar}>
              {FILTER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  className={`${styles.filterBtn} ${filterType === opt.value ? styles.filterBtnActive : ""}`}
                  onClick={() => setFilterType(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="파일명 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        )}

        {/* 로딩 */}
        {fetching && (
          <div className={styles.stateBox}>
            <span className={styles.stateIcon}></span>
            <p>불러오는 중...</p>
          </div>
        )}

        {/* 에러 */}
        {!fetching && error && (
          <div className={`${styles.stateBox} ${styles.stateBoxError}`}>
            <span className={styles.stateIcon}>⚠️</span>
            <p>{error}</p>
          </div>
        )}

        {/* 빈 상태 */}
        {!fetching && !error && items.length === 0 && (
          <div className={styles.stateBox}>
            <span className={styles.stateIcon}>📭</span>
            <p>아직 활동 이력이 없습니다.</p>
          </div>
        )}

        {/* 검색/필터 결과 없음 */}
        {!fetching && !error && items.length > 0 && filteredItems.length === 0 && (
          <div className={styles.stateBox}>
            <span className={styles.stateIcon}>🔍</span>
            <p>검색 결과가 없습니다.</p>
          </div>
        )}

        {/* 테이블 */}
        {!fetching && filteredItems.length > 0 && (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>유형</th>
                  <th>파일명</th>
                  <th>문서 타입</th>
                  <th>다운로드 형식</th>
                  <th>상태</th>
                  <th>일시</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const key = `${item.activity_type}-${item.id}`;
                  const isDeleting = deletingKey === key;
                  return (
                    <tr
                      key={key}
                      className={styles.clickableRow}
                      onClick={() => setSelectedItem(item)}
                    >
                      <td>
                        <span className={item.activity_type === "SUMMARY" ? styles.badgeSummary : styles.badgeDownload}>
                          {ACTIVITY_LABEL[item.activity_type]}
                        </span>
                      </td>
                      <td className={styles.fileNameCell}>
                        {item.file_name ?? <span className={styles.empty}>-</span>}
                      </td>
                      <td>
                        {item.document_type ?? <span className={styles.empty}>-</span>}
                      </td>
                      <td>
                        {item.download_format
                          ? <span className={styles.formatBadge}>{item.download_format.toUpperCase()}</span>
                          : <span className={styles.empty}>-</span>}
                      </td>
                      <td>
                        <span className={item.status === "SUCCESS" ? styles.statusBadgeSuccess : styles.statusBadgeFailed}>
                          {STATUS_LABEL[item.status] ?? item.status}
                        </span>
                      </td>
                      <td className={styles.dateCell}>{formatDate(item.created_at)}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <div className={styles.actionCell}>
                          {item.activity_type === "DOWNLOAD" && item.summary_text && (
                            <button
                              className={styles.redownloadButton}
                              onClick={() => handleRedownload(item)}
                              disabled={redownloadingKey === key}
                              title="같은 형식으로 다시 다운로드"
                            >
                              {redownloadingKey === key ? "저장 중" : "다운로드"}
                            </button>
                          )}
                          <button
                            className={styles.deleteButton}
                            onClick={() => handleDelete(item)}
                            disabled={isDeleting}
                          >
                            {isDeleting ? "삭제 중" : "삭제"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* 상세 모달 */}
      {selectedItem && (
        <DetailModal
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onRedownload={(item) => {
            setSelectedItem(null);
            handleRedownload(item);
          }}
        />
      )}
    </div>
  );
}
