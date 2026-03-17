// 인증 전용 API 모듈
//
// 역할: 백엔드 인증 엔드포인트(/auth/*, /users/me)와의 통신만 전담합니다.
// 에러는 항상 Error 객체로 throw해 호출부에서 catch 하나로 처리합니다.

const BACKEND_URL = "http://localhost:8000";

// ── 에러 메시지 정제 ──────────────────────────────────────────────────────────
// 백엔드 detail을 그대로 보여주되, 기술적인 문구는 사람이 읽을 수 있는 fallback으로 대체합니다.
function parseDetail(detail: unknown, fallback: string): string {
  if (typeof detail !== "string" || !detail.trim()) return fallback;
  // DB/서버 내부 오류 패턴은 사용자에게 노출하지 않습니다.
  if (/ORA-\d+|sqlalchemy|traceback|exception|Internal Server/i.test(detail)) {
    return fallback;
  }
  return detail;
}

// ── 타입 ──────────────────────────────────────────────────────────────────────

export interface UserInfo {
  user_id: number;
  email: string;
  name: string;
  role: "USER" | "ADMIN";
  status: string;
  email_verified: string;
  last_login_at: string | null;
  created_at: string;
}

// ── API 함수 ──────────────────────────────────────────────────────────────────

export async function registerUser(
  email: string,
  password: string,
  name: string
): Promise<UserInfo> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });
  } catch {
    throw new Error("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }
  const data = await res.json();
  if (!res.ok) throw new Error(parseDetail(data.detail, "회원가입에 실패했습니다."));
  return data;
}

export async function loginUser(
  email: string,
  password: string
): Promise<{ access_token: string; refresh_token: string }> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new Error("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error(parseDetail(data.detail, "이메일 또는 비밀번호를 확인해 주세요."));
  }
  return data;
}

export async function logoutUser(accessToken: string): Promise<void> {
  // 로그아웃은 네트워크 실패해도 로컬 상태는 비웁니다. 에러를 throw하지 않습니다.
  try {
    await fetch(`${BACKEND_URL}/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    // 무시
  }
}

export async function getMe(accessToken: string): Promise<UserInfo> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/users/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    throw new Error("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }
  const data = await res.json();
  if (!res.ok) throw new Error(parseDetail(data.detail, "사용자 정보를 불러올 수 없습니다."));
  return data;
}

export async function refreshAccessToken(storedRefreshToken: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: storedRefreshToken }),
    });
  } catch {
    throw new Error("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error(parseDetail(data.detail, "세션이 만료되었습니다. 다시 로그인해 주세요."));
  }
  return data.access_token;
}
