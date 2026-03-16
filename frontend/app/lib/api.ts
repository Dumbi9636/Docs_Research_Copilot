// API 호출 모듈
//
// 이 파일의 역할: 백엔드와의 HTTP 통신만 전담합니다.
// - 네트워크 에러와 API 에러 모두 Error 객체로 통일해 상위로 throw합니다.
// - 호출하는 쪽(page.tsx)은 try/catch 하나로 모든 에러를 처리할 수 있습니다.

const BACKEND_URL = "http://localhost:8000";

export interface SummarizeResult {
  summary: string;
  steps: string[];
}

export async function summarizeText(
  text: string,
  options?: { signal?: AbortSignal }
): Promise<SummarizeResult> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: options?.signal,
    });
  } catch (e) {
    // AbortError는 취소 신호이므로 상위(page.tsx)로 그대로 전달합니다.
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    // fetch 자체가 실패하면 서버가 꺼져 있거나 CORS 문제입니다.
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}

export async function summarizeFile(
  file: File,
  options?: { signal?: AbortSignal }
): Promise<SummarizeResult> {
  // Content-Type 헤더는 FormData 사용 시 브라우저가 자동으로 설정합니다.
  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/summarize/file`, {
      method: "POST",
      body: formData,
      signal: options?.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}

export type ExportFormat = "txt" | "docx" | "pdf";

export async function exportSummary(
  summary: string,
  format: ExportFormat,
  sourceFilename: string
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ summary, format, source_filename: sourceFilename }),
    });
  } catch {
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  // 에러 응답은 JSON, 성공 응답은 binary입니다.
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail ?? "다운로드 중 오류가 발생했습니다.");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `요약결과_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}
