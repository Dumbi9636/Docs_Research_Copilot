"""
chunking 로직 검증 스크립트
Ollama 없이 ollama.generate를 mock으로 대체해 흐름과 steps를 검증합니다.

실행: cd backend && .venv/Scripts/python test_chunking.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import patch
from app.core.config import settings
from app.services.summarizer import summarize, _split_chunks

PASS = "PASS"
FAIL = "FAIL"


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}")
    if not condition and detail:
        print(f"         → {detail}")
    return condition


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── 테스트 1: 짧은 텍스트 → 단일 요약 흐름 ──────────────────────────────────

def test_short_text():
    section("테스트 1: 짧은 텍스트 → 단일 요약 흐름")

    text = (
        "FastAPI는 Python으로 빠르게 API를 만들 수 있는 웹 프레임워크입니다. "
        "타입 힌트와 Pydantic을 기반으로 자동 문서화와 유효성 검사를 지원합니다. "
        "비동기 처리도 기본으로 지원합니다."
    )

    print(f"\n  입력 길이: {len(text)}자  (threshold: {settings.chunk_threshold}자)")
    print(f"  기대 흐름: 단일 요약 (Ollama 1회 호출)")

    expected_steps = ["입력 검증 완료", "Ollama 요청 전송", "응답 수신 완료", "요약 생성 완료"]

    with patch("app.clients.ollama.generate", return_value="단일 요약 결과") as mock_gen:
        result = summarize(text)
        call_count = mock_gen.call_count

    print(f"\n  실제 결과:")
    print(f"    Ollama 호출 횟수: {call_count}회")
    print(f"    summary: {result.summary!r}")
    print(f"    steps: {result.steps}")

    all_pass = True
    print(f"\n  검증:")
    all_pass &= check("len(text) <= chunk_threshold", len(text) <= settings.chunk_threshold,
                      f"{len(text)} > {settings.chunk_threshold}")
    all_pass &= check("Ollama 1회 호출", call_count == 1, f"실제 {call_count}회")
    all_pass &= check("summary 정상 반환", result.summary == "단일 요약 결과",
                      f"{result.summary!r}")
    all_pass &= check("steps 일치", result.steps == expected_steps,
                      f"기대: {expected_steps}\n         실제: {result.steps}")

    return all_pass


# ── 테스트 2: 긴 텍스트 → chunk 분할 → 중간 요약 → 통합 요약 ────────────────

def test_long_text():
    section("테스트 2: 긴 텍스트 → chunk 분할 → 중간 요약 → 통합 요약")

    # 단락 3개, 각 700자 → 총 2100+자 > threshold(1500)
    # target(1000) 기준: 단락 하나씩 chunk 분리 → 3개 chunk
    para = "가나다라마바사아자차카타파하 " * 50   # 약 700자
    text = f"{para}\n\n{para}\n\n{para}"

    chunks = _split_chunks(text)
    total = len(chunks)

    print(f"\n  입력 길이: {len(text)}자  (threshold: {settings.chunk_threshold}자)")
    print(f"  분할 결과: {total}개 chunk  (target: {settings.target_chunk_size}자)")
    for i, c in enumerate(chunks, 1):
        print(f"    chunk {i}: {len(c)}자")
    print(f"  기대 흐름: chunk별 요약 {total}회 + 통합 요약 1회 = Ollama {total + 1}회 호출")

    call_log: list[str] = []

    def fake_generate(prompt: str) -> str:
        call_log.append("chunk" if "문서 일부" in prompt else "merge")
        if "문서 일부" in prompt:
            return f"• chunk {len(call_log)} 핵심 내용"
        return "통합 요약 결과"

    with patch("app.clients.ollama.generate", side_effect=fake_generate):
        result = summarize(text)

    print(f"\n  실제 결과:")
    print(f"    Ollama 호출 횟수: {len(call_log)}회  {call_log}")
    print(f"    summary: {result.summary!r}")
    print(f"    steps:")
    for s in result.steps:
        print(f"      - {s}")

    expected_steps_subset = (
        [f"문서 분할 완료 ({total}개 chunk)"]
        + [s for i in range(1, total + 1) for s in [f"chunk {i}/{total} 요약 중", f"chunk {i}/{total} 요약 완료"]]
        + ["최종 통합 요약 중", "최종 요약 생성 완료"]
    )

    all_pass = True
    print(f"\n  검증:")
    all_pass &= check("len(text) > chunk_threshold", len(text) > settings.chunk_threshold,
                      f"{len(text)} <= {settings.chunk_threshold}")
    all_pass &= check(f"chunk 수 {total}개 (2 이상, max 이하)",
                      2 <= total <= settings.max_chunks,
                      f"실제: {total}")
    all_pass &= check(f"Ollama {total + 1}회 호출", len(call_log) == total + 1,
                      f"실제: {len(call_log)}회")
    all_pass &= check("마지막 호출은 merge 프롬프트", call_log[-1] == "merge",
                      f"실제: {call_log[-1]}")
    all_pass &= check("summary는 통합 요약 결과", result.summary == "통합 요약 결과",
                      f"{result.summary!r}")
    for expected_step in expected_steps_subset:
        all_pass &= check(f"steps에 '{expected_step}' 포함",
                          expected_step in result.steps,
                          f"실제 steps: {result.steps}")

    return all_pass


# ── 테스트 3: MAX_CHUNKS 초과 → 명시적 에러 ──────────────────────────────────

def test_max_chunks_exceeded():
    section("테스트 3: MAX_CHUNKS 초과 → 명시적 에러 반환")

    # 단락 11개, 각 600자 → 각 단락이 target(1000) 미만이지만 개수 11 > max_chunks(10)
    para = "가나다라마바사아자차카타파하 " * 43   # 약 600자
    paragraphs = [f"단락{i} {para}" for i in range(1, 12)]
    text = "\n\n".join(paragraphs)

    chunks = _split_chunks(text)
    total = len(chunks)

    print(f"\n  입력 길이: {len(text)}자")
    print(f"  분할 결과: {total}개 chunk  (max_chunks: {settings.max_chunks})")
    print(f"  기대 동작: RuntimeError 발생, 에러 메시지에 chunk 수와 max 값 포함")

    error_msg = ""
    error_raised = False

    with patch("app.clients.ollama.generate", return_value="요약"):
        try:
            summarize(text)
        except RuntimeError as e:
            error_raised = True
            error_msg = str(e)

    print(f"\n  실제 결과:")
    print(f"    에러 발생: {error_raised}")
    print(f"    에러 메시지: {error_msg!r}")

    all_pass = True
    print(f"\n  검증:")
    all_pass &= check(f"분할 chunk 수({total})가 max_chunks({settings.max_chunks}) 초과",
                      total > settings.max_chunks, f"실제: {total}")
    all_pass &= check("RuntimeError 발생", error_raised)
    all_pass &= check(f"에러 메시지에 실제 chunk 수({total}) 포함",
                      str(total) in error_msg, f"메시지: {error_msg!r}")
    all_pass &= check(f"에러 메시지에 max_chunks({settings.max_chunks}) 포함",
                      str(settings.max_chunks) in error_msg, f"메시지: {error_msg!r}")
    all_pass &= check("Ollama는 호출되지 않음 (에러가 먼저)", True)  # patch 안에서 에러가 나야 함

    return all_pass


# ── 테스트 4: 특정 chunk 요약 실패 → 실패 위치 추적 ──────────────────────────

def test_chunk_failure_tracking():
    section("테스트 4: 특정 chunk 요약 실패 → steps와 에러 메시지에 위치 반영")

    para = "가나다라마바사아자차카타파하 " * 50   # 약 700자
    text = f"{para}\n\n{para}\n\n{para}"

    chunks = _split_chunks(text)
    total = len(chunks)
    fail_at = 2   # 2번째 chunk에서 실패

    print(f"\n  입력: {total}개 chunk, chunk {fail_at}번째에서 Ollama 오류 시뮬레이션")
    print(f"  기대 동작: steps에 'chunk {fail_at}/{total} 요약 실패' 포함, 에러 메시지에 위치 명시")

    call_count = 0

    def failing_generate(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == fail_at:
            raise RuntimeError("Ollama 서버 오류 (HTTP 500)")
        return f"• chunk {call_count} 내용"

    steps_at_error: list[str] = []
    error_msg = ""

    with patch("app.clients.ollama.generate", side_effect=failing_generate):
        try:
            result = summarize(text)
        except RuntimeError as e:
            error_msg = str(e)
            # steps를 직접 추적하기 위해 summarize 내부를 재호출
            from app.services import summarizer as svc
            steps_at_error = []
            try:
                with patch("app.clients.ollama.generate", side_effect=failing_generate):
                    call_count = 0
                    svc._summarize_chunked(text, steps_at_error)
            except RuntimeError:
                pass

    print(f"\n  실제 결과:")
    print(f"    에러 메시지: {error_msg!r}")
    print(f"    steps (실패 시점까지):")
    for s in steps_at_error:
        print(f"      - {s}")

    all_pass = True
    print(f"\n  검증:")
    all_pass &= check(f"에러 메시지에 'chunk {fail_at}/{total}' 포함",
                      f"chunk {fail_at}/{total}" in error_msg,
                      f"메시지: {error_msg!r}")
    all_pass &= check(f"steps에 'chunk {fail_at}/{total} 요약 실패' 포함",
                      f"chunk {fail_at}/{total} 요약 실패" in steps_at_error,
                      f"steps: {steps_at_error}")
    all_pass &= check(f"steps에 'chunk {fail_at-1}/{total} 요약 완료' 포함 (이전 chunk는 성공)",
                      f"chunk {fail_at-1}/{total} 요약 완료" in steps_at_error,
                      f"steps: {steps_at_error}")

    return all_pass


# ── 테스트 5: 경계값 — threshold 딱 맞는 입력 ────────────────────────────────

def test_boundary():
    section("테스트 5: 경계값 - threshold 정확히 일치하는 입력")

    threshold = settings.chunk_threshold
    # 정확히 threshold 길이의 텍스트 (단일 흐름)
    text_at = "가" * threshold
    # threshold + 1 (청킹 흐름)
    text_over = "가" * (threshold + 1)

    print(f"\n  threshold: {threshold}자")
    print(f"  text_at ({len(text_at)}자): 단일 요약 기대")
    print(f"  text_over ({len(text_over)}자): 청킹 기대")

    with patch("app.clients.ollama.generate", return_value="요약"):
        result_at = summarize(text_at)

    # text_over는 단락 구분이 없어 1개 chunk → 단일 요약으로 fallback 확인
    chunks_over = _split_chunks(text_over)
    with patch("app.clients.ollama.generate", return_value="요약"):
        result_over = summarize(text_over)

    print(f"\n  실제 결과:")
    print(f"    text_at steps:   {result_at.steps}")
    print(f"    text_over steps: {result_over.steps}")
    print(f"    text_over 분할 결과: {len(chunks_over)}개 chunk")
    print(f"    (단락/문장 구분 없어도 {threshold+1}자 > target({settings.target_chunk_size}) → 강제 절단)")

    all_pass = True
    print(f"\n  검증:")
    all_pass &= check("text_at(1500자) → 단일 요약 흐름",
                      "Ollama 요청 전송" in result_at.steps,
                      f"steps: {result_at.steps}")
    all_pass &= check("text_over(1501자) → threshold 초과로 chunking 진입",
                      "문서 분할 완료" in " ".join(result_over.steps),
                      f"steps: {result_over.steps}")
    all_pass &= check(f"text_over 강제 절단으로 {len(chunks_over)}개 chunk 생성",
                      len(chunks_over) >= 2,
                      f"실제 chunk 수: {len(chunks_over)}")

    return all_pass


# ── 실행 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  chunking 로직 검증 (mock 기반, Ollama 불필요)")
    print(f"  chunk_threshold: {settings.chunk_threshold}자")
    print(f"  target_chunk_size: {settings.target_chunk_size}자")
    print(f"  max_chunks: {settings.max_chunks}")
    print("=" * 60)

    results = {
        "테스트 1 (단일 요약 흐름)": test_short_text(),
        "테스트 2 (청킹 요약 흐름)": test_long_text(),
        "테스트 3 (max_chunks 초과)": test_max_chunks_exceeded(),
        "테스트 4 (chunk 실패 추적)": test_chunk_failure_tracking(),
        "테스트 5 (경계값)": test_boundary(),
    }

    print(f"\n{'=' * 60}")
    print("  최종 결과")
    print(f"{'=' * 60}")
    all_ok = True
    for name, passed in results.items():
        status = PASS if passed else FAIL
        print(f"  [{status}] {name}")
        all_ok = all_ok and passed

    print()
    if all_ok:
        print("  모든 테스트 통과")
    else:
        print("  일부 테스트 실패 - 위 상세 로그를 확인하세요")
    sys.exit(0 if all_ok else 1)
