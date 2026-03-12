# OCR 텍스트 추출 모듈
#
# 이 모듈의 책임: 이미지 바이트를 받아 Tesseract OCR로 텍스트를 반환합니다.
#
# 전처리 적용 범위 (1차):
#   - 그레이스케일 변환
#   - 소형 이미지 확대 (Tesseract 권장 해상도 확보)
#   - 오토 컨트라스트 (배경·글자 명암 강화)
#   - 이진화 (흑백 고정으로 노이즈 억제)
#
# 제외 범위: 손글씨 최적화, 표 구조 복원, 고급 노이즈 필터
#
# 의존성:
#   pip  : pytesseract, Pillow
#   시스템: Tesseract OCR (kor+eng 언어팩 포함 버전)
#          Windows → winget install UB-Mannheim.TesseractOCR
#          설치 후 PATH에 tesseract.exe가 잡혀 있어야 합니다.

import io

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from PIL import Image, ImageOps, UnidentifiedImageError

# Tesseract 설정
# --psm 6 : 단일 균일 텍스트 블록으로 가정합니다.
#   psm 3(기본 자동)은 다단 컬럼/복잡한 레이아웃에 적합하지만,
#   문서·목록처럼 단순한 구조에서는 오히려 레이아웃을 잘못 파악해 인식률이 떨어집니다.
#   psm 6은 전체 이미지를 하나의 텍스트 덩어리로 읽으므로 단문서·리스트 인식에 유리합니다.
# --oem 3 : LSTM 엔진 사용 (Tesseract 4+ 기본값이지만 명시해 혼용을 방지합니다)
_TESS_CONFIG = "--psm 6 --oem 3"

# 소형 이미지의 확대 기준 너비(px)입니다.
# Tesseract는 ~300 DPI 수준에서 인식률이 가장 높습니다.
# 일반 문서 이미지는 최소 1200px 이상이어야 그에 근접합니다.
_MIN_WIDTH_PX = 1200

# 이진화 임계값 (0~255). 이 값보다 밝으면 흰색(255), 어두우면 검정(0)으로 고정합니다.
# 128은 중간값으로, 대부분의 스캔 문서·스크린샷에 무난합니다.
_BINARIZE_THRESHOLD = 128


def _preprocess(image: Image.Image) -> Image.Image:
    """
    OCR 인식률을 높이기 위한 최소 전처리를 수행합니다.

    적용 순서:
      1. 그레이스케일 — 컬러 채널을 제거해 Tesseract 처리 부하를 낮춥니다.
      2. 소형 이미지 확대 — 너비가 _MIN_WIDTH_PX 미만이면 비율을 유지하며 확대합니다.
      3. 오토 컨트라스트 — 히스토그램 늘리기로 명암 범위를 최대화합니다.
      4. 이진화 — 임계값 기준으로 흑/백만 남겨 노이즈를 억제합니다.
    """
    # 1. 그레이스케일
    image = image.convert("L")

    # 2. 소형 이미지 확대
    w, h = image.size
    if w < _MIN_WIDTH_PX:
        scale = _MIN_WIDTH_PX / w
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # 3. 오토 컨트라스트
    image = ImageOps.autocontrast(image)

    # 4. 이진화
    image = image.point(lambda px: 255 if px > _BINARIZE_THRESHOLD else 0)

    return image


def extract_text_from_image(raw: bytes) -> str:
    """
    이미지 바이트에서 OCR로 텍스트를 추출합니다.

    지원 형식: PNG, JPG, JPEG (Pillow가 열 수 있는 모든 래스터 이미지)
    언어: kor+eng — 한국어 우선, 영어 병행 인식

    Args:
        raw: 이미지 파일의 바이트 데이터

    Returns:
        OCR로 추출한 텍스트 문자열 (앞뒤 공백 제거)

    Raises:
        RuntimeError: 이미지 열기 실패 / Tesseract 미설치 / 텍스트 인식 불가
    """
    # ── 1단계: 이미지 열기 ────────────────────────────────────────────────────
    try:
        image = Image.open(io.BytesIO(raw))
    except UnidentifiedImageError:
        raise RuntimeError(
            "이미지 파일을 열 수 없습니다. "
            "손상되지 않은 PNG, JPG, JPEG 파일을 업로드해 주세요."
        )
    except Exception as e:
        raise RuntimeError(f"이미지 파일 처리 중 오류가 발생했습니다: {e}")

    # ── 2단계: 전처리 ─────────────────────────────────────────────────────────
    image = _preprocess(image)

    # ── 3단계: OCR 실행 ───────────────────────────────────────────────────────
    try:
        text = pytesseract.image_to_string(image, lang="kor+eng", config=_TESS_CONFIG)
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract OCR이 설치되어 있지 않습니다. "
            "Tesseract를 설치하고 한국어 언어 데이터(kor.traineddata)를 포함해 주세요. "
            "Windows: winget install UB-Mannheim.TesseractOCR"
        )
    except pytesseract.TesseractError as e:
        raise RuntimeError(
            f"OCR 실행 중 오류가 발생했습니다. "
            f"kor+eng 언어팩이 설치되어 있는지 확인해 주세요. (원인: {e})"
        )
    except Exception as e:
        raise RuntimeError(f"OCR 처리 중 예상치 못한 오류가 발생했습니다: {e}")

    # ── 4단계: 결과 검증 ──────────────────────────────────────────────────────
    text = text.strip()
    if not text:
        raise RuntimeError(
            "이미지에서 텍스트를 인식할 수 없습니다. "
            "텍스트가 포함된 선명한 이미지를 업로드해 주세요."
        )

    return text
