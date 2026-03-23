// API 호출 모듈
//
// 이 파일의 역할: 백엔드와의 HTTP 통신만 전담합니다.
// - 401 응답은 UnauthorizedError로 throw해 호출부(page.tsx)에서 token refresh 후 재시도할 수 있게 합니다.
// - 그 외 에러는 Error 객체로 통일해 상위로 throw합니다.

const BACKEND_URL = "http://localhost:8000";

// 401 전용 에러 클래스 — 호출부에서 instanceof로 구분해 refresh 재시도 처리에 사용합니다.
export class UnauthorizedError extends Error {
  constructor() {
    super("인증이 필요합니다. 다시 로그인해 주세요.");
    this.name = "UnauthorizedError";
  }
}

export interface SummarizeResult {
  summary: string;
  steps: string[];
  history_id: number;
}

export async function summarizeText(
  text: string,
  accessToken: string,
  options?: { signal?: AbortSignal; documentType?: string }
): Promise<SummarizeResult> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/summarize`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ text, document_type: options?.documentType ?? null }),
      signal: options?.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  if (res.status === 401) throw new UnauthorizedError();
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}

export async function summarizeFile(
  file: File,
  accessToken: string,
  options?: { signal?: AbortSignal }
): Promise<SummarizeResult> {
  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/summarize/file`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        // Content-Type은 FormData 사용 시 브라우저가 자동 설정합니다.
      },
      body: formData,
      signal: options?.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  if (res.status === 401) throw new UnauthorizedError();
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}

export type ExportFormat = "txt" | "docx" | "pdf";

export async function exportSummary(
  summary: string,
  format: ExportFormat,
  sourceFilename: string,
  accessToken: string,
  historyId?: number,
  skipLog: boolean = false
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/export`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        summary,
        format,
        source_filename: sourceFilename,
        history_id: historyId ?? null,
        skip_log: skipLog,
      }),
    });
  } catch {
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail ?? "다운로드 중 오류가 발생했습니다.");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = _buildExportFilename(sourceFilename, format);
  a.click();
  URL.revokeObjectURL(url);
}

export interface ActivityItem {
  activity_type: "SUMMARY" | "DOWNLOAD";
  id: number;
  file_name: string | null;
  status: string;
  created_at: string;
  document_type?: string | null;
  file_type?: string | null;
  summary_mode?: string | null;
  summary_text?: string | null;
  download_format?: string | null;
  linked_history_id?: number | null;
  error_message?: string | null;
}

export async function getActivity(
  accessToken: string,
  limit: number = 40
): Promise<ActivityItem[]> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/users/me/activity?limit=${limit}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  if (res.status === 401) throw new UnauthorizedError();
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}

export async function deleteActivity(
  activityType: "SUMMARY" | "DOWNLOAD",
  id: number,
  accessToken: string
): Promise<void> {
  const path =
    activityType === "SUMMARY"
      ? `/users/me/summaries/${id}`
      : `/users/me/downloads/${id}`;

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "삭제 중 오류가 발생했습니다.");
  }
}

function _buildExportFilename(sourceFilename: string, format: ExportFormat): string {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  if (sourceFilename) {
    const base = sourceFilename.replace(/\.[^.]+$/, "");
    return `${base}_요약결과_${date}.${format}`;
  }
  return `요약결과_${date}.${format}`;
}
