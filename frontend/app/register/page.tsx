"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth-context";
import Header from "../components/Header";
import styles from "./page.module.css";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { register } = useAuth();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // register() 내부에서 회원가입 후 자동 로그인까지 처리합니다.
      await register(email, password, name);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = name.trim() !== "" && email !== "" && password !== "";

  return (
    <div className={styles.page}>
      <Header />
      <main className={styles.main}>
        <div className={styles.card}>
          <h1 className={styles.title}>회원가입</h1>
          <p className={styles.subtitle}>계정을 만들어 요약 기능을 이용하세요.</p>

          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="name">
                이름
              </label>
              <input
                id="name"
                type="text"
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="홍길동"
                required
                autoComplete="name"
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="email">
                이메일
              </label>
              <input
                id="email"
                type="email"
                className={styles.input}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                required
                autoComplete="email"
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="password">
                비밀번호
              </label>
              <input
                id="password"
                type="password"
                className={styles.input}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="8자 이상 입력하세요"
                required
                minLength={8}
                autoComplete="new-password"
              />
              <p className={styles.hint}>8자 이상이어야 합니다.</p>
            </div>

            {error && <div className={styles.error}>{error}</div>}

            <button
              type="submit"
              className={styles.submitButton}
              disabled={loading || !canSubmit}
            >
              {loading ? "처리 중..." : "회원가입"}
            </button>
          </form>

          <p className={styles.footer}>
            이미 계정이 있으신가요?
            <Link href="/login" className={styles.footerLink}>
              로그인
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
