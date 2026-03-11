"use client";

// DOM 직접 접근(input.value 초기화)이 있어 "use client"가 필요합니다.

import styles from "../page.module.css";

interface Props {
  file: File | null;
  // 파일 선택 / 제거 모두 이 하나의 콜백으로 처리합니다.
  // 제거 시에는 null을 전달합니다.
  onFileChange: (file: File | null) => void;
}

export default function FileUploadInput({ file, onFileChange }: Props) {
  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    onFileChange(e.target.files?.[0] ?? null);
  }

  function handleClear() {
    // input[type=file]은 React state로 값을 제어할 수 없으므로
    // DOM을 직접 찾아 초기화합니다. 이 로직은 input을 소유한 이 컴포넌트 안에 있어야 합니다.
    const input = document.getElementById("fileInput") as HTMLInputElement | null;
    if (input) input.value = "";
    onFileChange(null);
  }

  return (
    <>
      <label htmlFor="fileInput" className={styles.label}>
        파일 업로드 <span className={styles.labelSub}>(txt / pdf / docx)</span>
        <span className={styles.policyHint}>파일이 선택되면 파일을 우선합니다</span>
      </label>
      <input
        id="fileInput"
        type="file"
        accept=".txt,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className={styles.fileInput}
        onChange={handleInputChange}
      />
      {file && (
        <div className={styles.fileInfo}>
          <span>선택된 파일: {file.name}</span>
          <button type="button" className={styles.clearFile} onClick={handleClear}>
            ✕ 파일 제거
          </button>
        </div>
      )}
    </>
  );
}
