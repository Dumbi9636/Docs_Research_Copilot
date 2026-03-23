"use client";

import Link from "next/link";
import { useAuth } from "./lib/auth-context";
import Header from "./components/Header";
import styles from "./page.module.css";

const FEATURES = [
  {
    key: "summarize",
    icon: "📄",
    title: "요약 서비스",
    desc: "텍스트·PDF·DOCX·이미지를 AI로 요약합니다",
    href: "/summarize",
    enabled: true,
  },
  {
    key: "convert",
    icon: "🔄",
    title: "파일 변환",
    desc: "다양한 문서 형식 간 변환을 지원합니다",
    href: "#",
    enabled: false,
  },
];

export default function Home() {
  const { isLoggedIn } = useAuth();

  return (
    <div className={styles.pageWrapper}>
      <Header />

      <section className={styles.hero}>
        <h1 className={styles.heroTitle}>
          Docs<span>Research</span> Copilot
        </h1>
        <p className={styles.heroDesc}>
          AI로 문서를 요약하고, 원하는 형식으로 변환하세요
        </p>
      </section>

      <div className={styles.dashboardContent}>
        {!isLoggedIn && (
          <div className={styles.loginBanner}>
            <span>서비스를 이용하려면 로그인이 필요합니다.</span>
            <Link href="/login" className={styles.loginBannerLink}>로그인하기 →</Link>
          </div>
        )}

        <h2 className={styles.featureGridTitle}>서비스 목록</h2>
        <div className={styles.featureGrid}>
          {FEATURES.map((f) =>
            f.enabled ? (
              <Link key={f.key} href={f.href} className={styles.featureCard}>
                <div className={styles.featureIcon}>{f.icon}</div>
                <p className={styles.featureTitle}>{f.title}</p>
                <p className={styles.featureDesc}>{f.desc}</p>
              </Link>
            ) : (
              <div key={f.key} className={`${styles.featureCard} ${styles.featureCardDisabled}`}>
                <div className={styles.featureIcon}>{f.icon}</div>
                <p className={styles.featureTitle}>{f.title}</p>
                <p className={styles.featureDesc}>{f.desc}</p>
                <span className={styles.featureSoonBadge}>준비 중</span>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
