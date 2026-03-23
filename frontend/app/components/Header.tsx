"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth-context";
import styles from "./Header.module.css";

export default function Header() {
  const { user, isLoggedIn, isLoading, signOut } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await signOut();
    router.push("/");
  }

  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link href="/" className={styles.logo}>
          Docs<span>Research</span> Copilot
        </Link>

        <div className={styles.actions}>
          {/* isLoading 중에는 버튼을 렌더링하지 않아 깜빡임을 방지합니다. */}
          {!isLoading && (
            <>
              {isLoggedIn && user ? (
                <>
                  <Link href="/mypage" className={styles.userNameLink}>
                    {user.name}님
                    {user.role === "ADMIN" && (
                      <span className={styles.adminBadge}>관리자</span>
                    )}
                  </Link>
                  <button
                    className={`${styles.btn} ${styles.btnGhost}`}
                    onClick={handleLogout}
                  >
                    로그아웃
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login">
                    <button className={`${styles.btn} ${styles.btnGhost}`}>
                      로그인
                    </button>
                  </Link>
                  <Link href="/register">
                    <button className={`${styles.btn} ${styles.btnPrimary}`}>
                      회원가입
                    </button>
                  </Link>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </header>
  );
}
