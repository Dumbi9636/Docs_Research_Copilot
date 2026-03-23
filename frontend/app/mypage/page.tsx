"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../lib/auth-context";
import Header from "../components/Header";
import ActivityList from "../components/ActivityList";
import styles from "./page.module.css";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function MyPage() {
  const { user, isLoggedIn, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isLoggedIn) {
      router.replace("/login");
    }
  }, [isLoading, isLoggedIn, router]);

  if (isLoading || !user) return null;

  return (
    <div className={styles.pageWrapper}>
      <Header />

      <main className={styles.main}>

        {/* ── 사용자 정보 카드 ───────────────────────────────────────────── */}
        <section className={styles.profileCard}>
          <div className={styles.profileAvatar}>
            {user.name.charAt(0).toUpperCase()}
          </div>
          <div className={styles.profileInfo}>
            <div className={styles.profileNameRow}>
              <h1 className={styles.profileName}>{user.name}</h1>
              {user.role === "ADMIN" && (
                <span className={styles.adminBadge}>관리자</span>
              )}
            </div>
            <p className={styles.profileEmail}>{user.email}</p>
            <div className={styles.profileMeta}>
              {user.created_at && (
                <span>가입일 {formatDate(user.created_at)}</span>
              )}
              {user.last_login_at && (
                <span>최근 로그인 {formatDate(user.last_login_at)}</span>
              )}
            </div>
          </div>
          <Link href="/" className={styles.backLink}>← 메인으로</Link>
        </section>

        {/* ── 활동 이력 섹션 ────────────────────────────────────────────── */}
        <section className={styles.activitySection}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>작업 이력</h2>
            <p className={styles.sectionDesc}>요약 및 다운로드 활동 내역을 확인할 수 있습니다.</p>
          </div>
          <ActivityList />
        </section>

      </main>
    </div>
  );
}
