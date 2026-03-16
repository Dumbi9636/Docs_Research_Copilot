"use client";

// DOM 직접 접근(input.value 초기화)이 있어 "use client"가 필요합니다.

import styles from "../page.module.css";

interface Props {
  file: File | null;
  onFileChange: (file: File | null) => void;
}

export default function FileUploadInput({ file, onFileChange }: Props) {
  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    onFileChange(e.target.files?.[0] ?? null);
  }

  function handleClear(e: React.MouseEvent) {
    e.preventDefault();
    // input[type=file]은 React state로 값을 제어할 수 없으므로
    // DOM을 직접 찾아 초기화합니다.
    const input = document.getElementById("fileInput") as HTMLInputElement | null;
    if (input) input.value = "";
    onFileChange(null);
  }

  return (
    <label htmlFor="fileInput" className={styles.uploadZone}>
      <input
        id="fileInput"
        type="file"
        accept=".txt,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.png,.jpg,.jpeg,image/png,image/jpeg"
        className={styles.fileInput}
        onChange={handleInputChange}
      />

      {file ? (
        /* 파일 선택 후 상태 */
        <div className={styles.fileInfo}>
          <span>📎 {file.name}</span>
          <button type="button" className={styles.clearFile} onClick={handleClear}>
            ✕
          </button>
        </div>
      ) : (
        /* 파일 미선택 상태 */
        <>
          <div className={styles.uploadIcon}>📂</div>
          <p className={styles.uploadMainText}>파일을 클릭해서 업로드</p>
          <p className={styles.uploadSubText}>txt · pdf · docx · png · jpg 지원</p>
        </>
      )}
    </label>
  );
}
