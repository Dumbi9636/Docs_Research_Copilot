"use client";

// 인증 전역 상태 관리
//
// 저장 전략:
//   access_token  → 메모리(state) — XSS 노출 최소화, 새로고침 시 refresh로 복구
//   refresh_token → localStorage  — 새로고침 후에도 로그인 유지
//   user 정보     → 메모리(state) — localStorage 저장 안 함, 항상 /users/me로 복구

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import {
  loginUser,
  logoutUser,
  registerUser,
  getMe,
  refreshAccessToken,
  UserInfo,
} from "./auth-api";
import { clearUserChats } from "./chatStorage";
import { clearSession as clearSummarizeSession } from "./summarizeStorage";

const REFRESH_TOKEN_KEY = "refresh_token";

// ── Context 타입 ──────────────────────────────────────────────────────────────

interface AuthContextValue {
  user: UserInfo | null;
  accessToken: string | null;
  isLoggedIn: boolean;
  // 앱 최초 로드 시 refresh 시도 완료 전까지 true
  // 이 값이 true인 동안 페이지는 인증 상태를 판단하지 않아야 합니다.
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  // 401 발생 시 호출. 성공하면 새 access_token 반환, 실패하면 null 반환.
  tryRefreshToken: () => Promise<string | null>;
}

// ── Context 생성 ──────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 앱 최초 로드: localStorage의 refresh_token으로 세션 복구
  useEffect(() => {
    async function restoreSession() {
      const stored = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!stored) {
        setIsLoading(false);
        return;
      }
      try {
        const newAccessToken = await refreshAccessToken(stored);
        const userInfo = await getMe(newAccessToken);
        setAccessToken(newAccessToken);
        setUser(userInfo);
      } catch {
        // refresh 실패 → 저장된 토큰 폐기, 비로그인 상태 유지
        localStorage.removeItem(REFRESH_TOKEN_KEY);
      } finally {
        setIsLoading(false);
      }
    }
    restoreSession();
  }, []);

  // 로그인
  const signIn = useCallback(async (email: string, password: string) => {
    const { access_token, refresh_token } = await loginUser(email, password);
    const userInfo = await getMe(access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
    setAccessToken(access_token);
    setUser(userInfo);
  }, []);

  // 로그아웃
  const signOut = useCallback(async () => {
    if (accessToken) await logoutUser(accessToken);
    // user가 메모리에 있는 이 시점에 localStorage를 정리합니다.
    // setUser(null) 이후에는 userId를 알 수 없으므로 반드시 먼저 호출합니다.
    if (user) {
      clearUserChats(user.user_id);         // 문서 대화 기록
      clearSummarizeSession(user.user_id);  // 요약 세션
    }
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setAccessToken(null);
    setUser(null);
  }, [accessToken, user]);

  // 회원가입
  const register = useCallback(
    async (email: string, password: string, name: string) => {
      await registerUser(email, password, name);
      // 회원가입 성공 후 자동 로그인
      await signIn(email, password);
    },
    [signIn]
  );

  const tryRefreshToken = useCallback(async (): Promise<string | null> => {
    const stored = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!stored) return null;
    try {
      const newToken = await refreshAccessToken(stored);
      // /users/me는 재호출하지 않음 — 이미 user 정보는 메모리에 있음
      setAccessToken(newToken);
      return newToken;
    } catch {
      // refresh 실패 → 전체 로그아웃 처리
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      setAccessToken(null);
      setUser(null);
      return null;
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isLoggedIn: !!accessToken,
        isLoading,
        signIn,
        signOut,
        register,
        tryRefreshToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth는 AuthProvider 내부에서만 사용할 수 있습니다.");
  return ctx;
}
