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

export async function summarizeText(text: string): Promise<SummarizeResult> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    // fetch 자체가 실패하면 서버가 꺼져 있거나 CORS 문제입니다.
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}

export async function summarizeFile(file: File): Promise<SummarizeResult> {
  // Content-Type 헤더는 FormData 사용 시 브라우저가 자동으로 설정합니다.
  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/summarize/file`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "알 수 없는 오류가 발생했습니다.");
  return data;
}
