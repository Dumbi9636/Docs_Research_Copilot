// 요약 결과 표시 컴포넌트
// summary와 steps를 받아 렌더링만 합니다.
// 훅, 이벤트, 부작용이 없는 순수 표시용 컴포넌트입니다.

import styles from "../page.module.css";

interface Props {
  summary: string;
  steps: string[];
}

export default function SummaryResult({ summary, steps }: Props) {
  return (
    <>
      {summary && (
        <div className={styles.resultBox}>
          <div className={styles.resultLabel}>요약 결과</div>
          {summary}
        </div>
      )}
      {steps.length > 0 && (
        <ul className={styles.stepsList}>
          {steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ul>
      )}
    </>
  );
}
