from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import base64
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import io
import sys
import logging
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# AI 브랜딩 시스템 import (선택적 - openai가 없어도 작동)
try:
    from ai_branding import AIBrandingSystem
    AI_BRANDING_AVAILABLE = True
except ImportError:
    AI_BRANDING_AVAILABLE = False
    AIBrandingSystem = None

# pix2pix 추론 엔진 (선택적)
try:
    from pix2pix_inference import SignboardAIEngine
    PIX2PIX_AVAILABLE = True
except ImportError as e:
    PIX2PIX_AVAILABLE = False
    logger.warning(f"Pix2pix 추론 엔진을 사용할 수 없습니다: {e}")

# 전역 pix2pix 엔진 (서버 시작 시 1회만 로드)
pix2pix_engine = None

def get_pix2pix_engine():
    """Pix2pix 엔진 싱글톤 (지연 로딩)"""
    global pix2pix_engine
    if pix2pix_engine is None and PIX2PIX_AVAILABLE:
        try:
            checkpoint_path = os.path.join(
                os.path.dirname(__file__),
                'checkpoints',
                'signboard_pix2pix_v1',
                '140_net_G.pth'
            )
            pix2pix_engine = SignboardAIEngine(checkpoint_path)
            logger.info(f"Pix2pix 모델 로드 완료: {checkpoint_path}")
        except Exception as e:
            logger.error(f"Pix2pix 모델 로드 실패: {e}", exc_info=True)
            pix2pix_engine = None
    return pix2pix_engine

# 전면프레임 전광/후광/전후광 디버그 전용 파일 로거
debug_logger = logging.getLogger("front_back_frame")
if not debug_logger.handlers:
    debug_logger.setLevel(logging.DEBUG)
    try:
        _log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _log_path = os.path.join(_log_dir, "front_back_frame.log")
        _fh = logging.FileHandler(_log_path, encoding="utf-8")
        _fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        debug_logger.addHandler(_fh)
    except Exception as e:
        # 파일 로거 설정에 실패해도 전체 서비스에는 영향 없도록 함
        logger.warning(f"Failed to initialize debug file logger: {e}")

app = FastAPI()

# CORS 설정
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def base64_to_image(base64_string: str) -> np.ndarray:
    """Base64 문자열을 OpenCV 이미지로 변환"""
    image_data = base64.b64decode(base64_string.split(",")[1] if "," in base64_string else base64_string)
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img

def base64_to_image_pil(base64_string: str) -> Image.Image:
    """Base64 문자열을 PIL 이미지로 변환"""
    image_data = base64.b64decode(base64_string.split(",")[1] if "," in base64_string else base64_string)
    img = Image.open(io.BytesIO(image_data))
    return img

def image_to_base64(image: np.ndarray) -> str:
    """OpenCV 이미지를 Base64 문자열로 변환"""
    _, buffer = cv2.imencode('.png', image)
    image_base64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/png;base64,{image_base64}"

def remove_white_background(image_bgr: np.ndarray, threshold: int = 240) -> np.ndarray:
    """흰색 배경을 투명 처리하여 RGBA 이미지로 변환
    Args:
        image_bgr: BGR 형식의 이미지
        threshold: 흰색으로 간주할 RGB 값의 임계값 (0-255, 기본값 240)
    Returns:
        RGBA 형식의 이미지 (흰색 부분은 투명)
    """
    # BGR을 RGB로 변환
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    
    # 흰색 픽셀 감지 (RGB 모두 threshold 이상)
    white_mask = (image_rgb[:, :, 0] >= threshold) & \
                 (image_rgb[:, :, 1] >= threshold) & \
                 (image_rgb[:, :, 2] >= threshold)
    
    # RGBA 이미지 생성
    h, w = image_rgb.shape[:2]
    image_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    image_rgba[:, :, :3] = image_rgb
    image_rgba[:, :, 3] = 255  # 기본 알파값
    
    # 흰색 부분을 투명 처리
    image_rgba[:, :, 3][white_mask] = 0
    
    return image_rgba

def get_korean_font(font_size: int, font_family: str = "malgun", font_weight: str = "400"):
    """한글 폰트 찾기 - 폰트 종류와 굵기를 지정 (Windows/Linux 호환)
    
    Args:
        font_size: 폰트 크기
        font_family: 폰트 종류 ("malgun", "nanumgothic", "nanumbarungothic", "gulim", "batang")
        font_weight: 폰트 굵기 ("regular", "bold") 또는 숫자 ("100", "200", ..., "900")
    """
    import platform
    import os
    is_windows = platform.system() == "Windows"
    
    # font_weight를 숫자로 변환 (100-900)
    weight_num = 400  # 기본값: regular
    if isinstance(font_weight, str):
        if font_weight == "regular":
            weight_num = 400
        elif font_weight == "bold":
            weight_num = 700
        elif font_weight.isdigit():
            weight_num = int(font_weight)
            weight_num = max(100, min(900, weight_num))  # 100-900 범위로 제한
    elif isinstance(font_weight, int):
        weight_num = max(100, min(900, font_weight))
    
    # 굵기 범위를 regular/bold로 매핑
    is_bold = weight_num >= 600
    
    font_paths = []
    
    if is_windows:
        fonts_dir = "C:/Windows/Fonts"
        
        if font_family == "malgun":
            # 맑은 고딕: 여러 볼드 파일명 시도
            if is_bold:
                font_paths = [
                    f"{fonts_dir}/malgunbd.ttf",  # 맑은 고딕 Bold
                    f"{fonts_dir}/malgunb.ttf",   # 대체 이름
                    f"{fonts_dir}/malgun.ttf",    # 폴백: 일반 폰트
                ]
            else:
                font_paths = [f"{fonts_dir}/malgun.ttf"]
                
        elif font_family == "nanumgothic":
            if is_bold:
                font_paths = [
                    f"{fonts_dir}/NanumGothicBold.ttf",
                    f"{fonts_dir}/NanumGothic.ttf",  # 폴백
                ]
            else:
                font_paths = [f"{fonts_dir}/NanumGothic.ttf"]
                
        elif font_family == "nanumbarungothic":
            if is_bold:
                font_paths = [
                    f"{fonts_dir}/NanumBarunGothicBold.ttf",
                    f"{fonts_dir}/NanumBarunGothic.ttf",  # 폴백
                ]
            else:
                font_paths = [f"{fonts_dir}/NanumBarunGothic.ttf"]
                
        elif font_family == "gulim":
            # TTC 파일: 인덱스 0=일반, 1=볼드 (일부 시스템)
            font_paths = [f"{fonts_dir}/gulim.ttc"]
            
        elif font_family == "batang":
            font_paths = [f"{fonts_dir}/batang.ttc"]
        else:
            # 기본값: 맑은 고딕
            if is_bold:
                font_paths = [
                    f"{fonts_dir}/malgunbd.ttf",
                    f"{fonts_dir}/malgun.ttf",
                ]
            else:
                font_paths = [f"{fonts_dir}/malgun.ttf"]
    else:
        # Linux/macOS 경로
        if font_family == "nanumgothic":
            if is_bold:
                font_paths = [
                    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                ]
            else:
                font_paths = [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    "/usr/share/fonts/TTF/NanumGothic.ttf",
                ]
        elif font_family == "nanumbarungothic":
            if is_bold:
                font_paths = [
                    "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
                    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
                ]
            else:
                font_paths = ["/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf"]
        else:
            # 기본값: 나눔고딕
            if is_bold:
                font_paths = [
                    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                ]
            else:
                font_paths = [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    "/usr/share/fonts/TTF/NanumGothic.ttf",
                ]
        
        # 폴백 폰트들
        font_paths.extend([
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/AppleGothic.ttf",  # macOS
        ])
    
    # 폰트 로드 시도
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                # TTC 파일의 경우 인덱스 지정 시도
                if font_path.endswith('.ttc'):
                    try:
                        # TTC 파일에서 볼드 인덱스 시도 (일부 시스템에서 1이 볼드)
                        if is_bold:
                            font = ImageFont.truetype(font_path, font_size, index=1)
                        else:
                            font = ImageFont.truetype(font_path, font_size, index=0)
                    except:
                        # 인덱스 지정 실패 시 기본 인덱스 사용
                        font = ImageFont.truetype(font_path, font_size)
                else:
                    font = ImageFont.truetype(font_path, font_size)
                
                # 폰트 테스트
                test_img = Image.new('RGB', (100, 100))
                test_draw = ImageDraw.Draw(test_img)
                test_draw.text((0, 0), "테스트", font=font)
                return font
        except Exception as e:
            print(f"[DEBUG] 폰트 로드 실패: {font_path}, 오류: {e}")
            continue
    
    # 모든 폰트 로드 실패 시 기본 폰트 반환
    print(f"[WARNING] 폰트를 찾을 수 없음: family={font_family}, weight={font_weight}")
    return ImageFont.load_default()

def hex_to_rgb(hex_color: str) -> tuple:
    """Hex 색상을 RGB 튜플로 변환"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def extract_text_layer(text: str, font, color: tuple, canvas_size: tuple, position: tuple) -> np.ndarray:
    """텍스트만 추출 (RGBA)"""
    if not text or not text.strip():
        return np.zeros((canvas_size[1], canvas_size[0], 4), dtype=np.uint8)
    
    text_img = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_img)
    draw.text(position, text, fill=color + (255,), font=font)

    # 텍스트 상단-좌측 그라디언트 하이라이트 (아주 미묘하게)
    try:
        np_img = np.array(text_img)
        alpha = np_img[:, :, 3]
        ys, xs = np.where(alpha > 0)
        if len(xs) > 0 and len(ys) > 0:
            x_min, x_max = xs.min(), xs.max()
            y_min, y_max = ys.min(), ys.max()
            h = y_max - y_min + 1
            w = x_max - x_min + 1

            # 왼쪽 위 1/4 영역만 10% 밝게
            y_end = int(y_min + h * 0.25)
            x_end = int(x_min + w * 0.25)

            # RGB 채널만 살짝 밝게 (알파는 그대로)
            region = np_img[y_min:y_end, x_min:x_end, :3].astype(np.float32)
            region = np.clip(region * 1.1, 0, 255)
            np_img[y_min:y_end, x_min:x_end, :3] = region.astype(np.uint8)

        return np_img
    except Exception:
        # 하이라이트 계산 중 오류가 나도 기본 텍스트 렌더링은 유지
        return np.array(text_img)

def create_text_mask(text: str, font, canvas_size: tuple, position: tuple) -> np.ndarray:
    """텍스트 마스크 생성"""
    if not text or not text.strip():
        return np.zeros((canvas_size[1], canvas_size[0]), dtype=np.uint8)
    
    mask = Image.new('L', canvas_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.text(position, text, fill=255, font=font)
    return np.array(mask)

def safe_gaussian_blur(image: np.ndarray, ksize: tuple, sigma: float) -> np.ndarray:
    """안전한 GaussianBlur - 이미지 크기와 kernel 크기 확인"""
    if image is None or image.size == 0:
        return image
    
    h, w = image.shape[:2] if len(image.shape) == 2 else image.shape[:2]
    ksize_w, ksize_h = ksize
    
    # kernel size가 홀수인지 확인하고, 이미지보다 작은지 확인
    if ksize_w % 2 == 0:
        ksize_w = max(3, ksize_w - 1) if ksize_w > 0 else 3
    if ksize_h % 2 == 0:
        ksize_h = max(3, ksize_h - 1) if ksize_h > 0 else 3
    
    # 이미지 크기보다 kernel이 크면 조정
    if ksize_w > w:
        ksize_w = w if w % 2 == 1 else max(3, w - 1)
    if ksize_h > h:
        ksize_h = h if h % 2 == 1 else max(3, h - 1)
    
    # 최소 크기 확인
    if ksize_w < 3:
        ksize_w = 3
    if ksize_h < 3:
        ksize_h = 3
    
    try:
        return cv2.GaussianBlur(image, (ksize_w, ksize_h), sigma)
    except:
        # 실패하면 원본 반환
        return image

# ========== 채널 간판 ==========

def add_logo_to_signboard(signboard_pil: Image.Image, logo_img: Image.Image, position: str = "left") -> Image.Image:
    """간판에 로고 추가
    position: 'left', 'right', 'center'
    """
    if logo_img is None:
        return signboard_pil
    
    width, height = signboard_pil.size
    
    # 로고 리사이즈 (간판 높이의 60%)
    logo_height = int(height * 0.6)
    aspect_ratio = logo_img.width / logo_img.height
    logo_width = int(logo_height * aspect_ratio)
    logo_resized = logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
    
    # 로고 위치 계산
    margin = int(height * 0.1)
    y_pos = (height - logo_height) // 2
    
    if position == "left":
        x_pos = margin
    elif position == "right":
        x_pos = width - logo_width - margin
    else:  # center
        x_pos = (width - logo_width) // 2
    
    # 로고 합성 (alpha 채널 고려)
    if logo_resized.mode == 'RGBA':
        signboard_pil.paste(logo_resized, (x_pos, y_pos), logo_resized)
    else:
        signboard_pil.paste(logo_resized, (x_pos, y_pos))
    
    return signboard_pil

def add_3d_depth(image_np: np.ndarray, depth: int = 8) -> np.ndarray:
    """간판에 3D 입체감 추가 (그림자/깊이)"""
    h, w = image_np.shape[:2]
    
    # 오른쪽/아래 그림자 생성
    shadow = np.zeros((h + depth, w + depth, 3), dtype=np.uint8)
    shadow[depth:, depth:] = image_np
    
    # 그림자 blur
    shadow_blur = safe_gaussian_blur(shadow, (15, 15), 5)
    # 그림자 투명도 살짝 강화 (약 55% 수준)
    shadow_blur = (shadow_blur * 0.55).astype(np.uint8)
    
    # 원본 이미지를 그림자 위에 배치
    result = shadow_blur.copy()
    result[:h, :w] = image_np
    
    return result

def analyze_polygon_shape(polygon_points: list) -> str:
    """선택한 폴리곤의 형태를 분석해서 텍스트 방향 결정
    Returns: 'horizontal' or 'vertical'
    """
    if len(polygon_points) < 3:
        return "horizontal"
    
    # 폴리곤의 바운딩 박스 계산
    xs = [p[0] for p in polygon_points]
    ys = [p[1] for p in polygon_points]
    
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    width = max_x - min_x
    height = max_y - min_y
    
    # 가로가 세로보다 1.5배 이상 길면 가로쓰기
    if width > height * 1.5:
        return "horizontal"
    # 세로가 가로보다 1.5배 이상 길면 세로쓰기
    elif height > width * 1.5:
        return "vertical"
    else:
        # 비슷하면 가로쓰기
        return "horizontal"

def render_jeongwang_channel(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> tuple:
    """
    전광채널: 글자 앞면만 발광, 배경(간판영역)은 발광 안 함
    - 배경: 색상 있지만 발광 안 함
    - 글자: 앞에서 발광 (glow 효과)
    Returns: (배경 레이어, 텍스트 레이어) - 야간 모드에서 분리 처리용
    """
    # 배경 생성 (발광 안 함)
    bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (107, 45, 143)
    signboard = Image.new('RGB', (width, height), color=bg_rgb)
    
    # 로고 추가
    if logo_img:
        signboard = add_logo_to_signboard(signboard, logo_img, position="left")
    
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np, None
    
    # 폰트 로드
    font_size = 100 if text_direction == "horizontal" else 80
    font = get_korean_font(font_size)
    
    # 텍스트 위치 계산
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    
    if text_direction == "vertical":
        # 세로쓰기: 각 글자를 줄바꿈
        text_vertical = '\n'.join(list(text))
        bbox = draw_temp.multiline_textbbox((0, 0), text_vertical, font=font)
    else:
        bbox = draw_temp.textbbox((0, 0), text, font=font)
    
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 로고가 있으면 텍스트를 오른쪽으로
    if logo_img:
        x_offset = int(width * 0.55)
    else:
        x_offset = (width - text_width) // 2
    
    position = (x_offset, (height - text_height) // 2)
    
    # 텍스트 레이어 추출
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    
    if text_direction == "vertical":
        text_layer_rgba = extract_text_layer(text_vertical, font, text_rgb, (width, height), position)
    else:
        text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    # 글자에만 glow 효과 (앞면 발광)
    text_glow = safe_gaussian_blur(text_layer_bgr, (25, 25), 10)
    
    # 텍스트 레이어 (글자 + glow)
    text_with_glow = cv2.add(text_layer_bgr, text_glow)
    
    # 주간용: 배경 + 글자 합성
    day_result = signboard_np.copy()
    day_result = cv2.add(day_result, text_layer_bgr)
    day_result = cv2.addWeighted(day_result, 1.0, text_glow, 0.5, 0)
    
    # 3D 입체감 추가
    day_result = add_3d_depth(day_result, depth=6)
    text_with_glow_3d = add_3d_depth(text_with_glow, depth=6)
    
    return day_result, text_with_glow_3d  # 배경, 텍스트 레이어 반환

def render_hugwang_channel(text: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    후광채널: 글자 뒤에 LED가 있어서 글자 주변에만 은은하게 빛남
    - 배경: 어두움 (발광 안 함)
    - 글자: 금속색/회색 (발광 안 함)
    - 후광: 글자 뒤에서만 빛남 (글자 주변에 은은한 glow)
    """
    # 어두운 배경
    signboard = Image.new('RGB', (width, height), (15, 15, 15))
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    # 폰트 로드
    font = get_korean_font(100)
    
    # 텍스트 위치 계산
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    # 후광 레이어 (글자 뒤에서 빛남)
    text_mask = create_text_mask(text, font, (width, height), position)
    if text_mask.sum() == 0:  # 텍스트가 없으면
        return signboard_np
    backlight = safe_gaussian_blur(text_mask.astype(np.float32), (81, 81), 40)
    backlight = safe_gaussian_blur(backlight, (81, 81), 40)  # 더 부드럽게
    backlight = (backlight * 1.5).clip(0, 255).astype(np.uint8)
    backlight_bgr = cv2.cvtColor(backlight, cv2.COLOR_GRAY2BGR)
    
    # 배경에 후광 합성
    result = cv2.add(signboard_np, backlight_bgr)
    
    # 글자는 위에 (발광 안 함, 금속색)
    if not text_color or text_color == "#FFFFFF":
        text_color = "#C0C0C0"  # 기본 회색
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (192, 192, 192)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    result = cv2.add(result, text_layer_bgr)
    
    return result

def render_jeonhugwang_channel(text: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    전후광채널: 글자 앞면 + 뒤에서 둘 다 발광
    """
    # 어두운 배경
    signboard = Image.new('RGB', (width, height), (15, 15, 15))
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    # 폰트 로드
    font = get_korean_font(100)
    
    # 텍스트 위치 계산
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    # 후광 먼저 (제일 뒤)
    text_mask = create_text_mask(text, font, (width, height), position)
    if text_mask.sum() == 0:  # 텍스트가 없으면
        return signboard_np
    backlight = safe_gaussian_blur(text_mask.astype(np.float32), (81, 81), 40)
    backlight = safe_gaussian_blur(backlight, (81, 81), 40)
    backlight = (backlight * 2.0).clip(0, 255).astype(np.uint8)
    backlight_bgr = cv2.cvtColor(backlight, cv2.COLOR_GRAY2BGR)
    
    # 글자 (중간)
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    # 전광 효과 (앞)
    front_glow = safe_gaussian_blur(text_layer_bgr, (25, 25), 10)
    
    # 합성: 배경 → 후광 → 글자 → 전광
    result = cv2.add(signboard_np, backlight_bgr)
    result = cv2.add(result, text_layer_bgr)
    result = cv2.addWeighted(result, 1.0, front_glow, 0.6, 0)
    
    return result

# ========== 설치 방식 ==========

def render_jeonmyeon_frame(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    전면프레임: 벽에 갈바 프레임 설치 후 그 위에 글자 부착
    - 프레임 구조가 보임 (테두리, 두께감)
    - 글자는 프레임 위에 부착된 느낌
    """
    # 배경 (벽 느낌)
    bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (200, 200, 200)
    signboard = Image.new('RGB', (width, height), color=bg_rgb)
    draw = ImageDraw.Draw(signboard)
    
    # 프레임 그리기 (갈바 프레임 느낌)
    frame_thickness = 20
    frame_color = (100, 100, 100)  # 어두운 회색 프레임
    draw.rectangle([frame_thickness, frame_thickness, width-frame_thickness, height-frame_thickness], 
                   outline=frame_color, width=frame_thickness)
    
    # 내부 배경 (프레임 안쪽)
    inner_bg = (240, 240, 240)
    draw.rectangle([frame_thickness*2, frame_thickness*2, width-frame_thickness*2, height-frame_thickness*2], 
                   fill=inner_bg)
    
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    # 텍스트 렌더링
    font = get_korean_font(100)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (0, 0, 0)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    result = cv2.add(signboard_np, text_layer_bgr)
    
    # 약간의 입체감 추가
    result = cv2.addWeighted(result, 0.95, safe_gaussian_blur(result, (5, 5), 0), 0.05, 0)
    
    return result

def render_frame_bar(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    프레임바: 투명 배경 + 얇은 알루미늄 바 + 글자
    - 배경 없음 (투명)
    - 얇은 막대 위에 글자만
    """
    # 투명 배경
    signboard = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(signboard)
    
    # 얇은 프레임바 (높이의 15%)
    bar_height = max(20, int(height * 0.15))
    bar_y = (height - bar_height) // 2
    
    # 알루미늄 막대
    bar_color = (120, 120, 130, 255)
    draw.rectangle([0, bar_y, width, bar_y + bar_height], fill=bar_color)
    
    # 막대 입체감
    draw.rectangle([0, bar_y, width, bar_y + 2], fill=(160, 160, 170, 255))  # 상단 하이라이트
    draw.rectangle([0, bar_y + bar_height - 2, width, bar_y + bar_height], fill=(80, 80, 90, 255))  # 하단 그림자
    
    # RGB로 변환
    bg = Image.new('RGB', (width, height), (0, 0, 0))
    bg.paste(signboard, (0, 0), signboard)
    signboard_np = cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    # 텍스트 렌더링
    font = get_korean_font(int(bar_height * 0.7))  # 막대 높이에 맞춰
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    result = cv2.add(signboard_np, text_layer_bgr)
    
    return result

def render_maenbyeok(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    맨벽: 투명 배경 + 글자만 (벽에 직접 부착)
    - 배경 없음
    - 글자만 벽에 직접
    """
    # 투명 배경
    signboard = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    # RGB로 변환
    bg = Image.new('RGB', (width, height), (0, 0, 0))
    bg.paste(signboard, (0, 0))
    signboard_np = cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    # 텍스트 렌더링
    font = get_korean_font(100)
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    result = cv2.add(signboard_np, text_layer_bgr)
    
    return result

def render_facade(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    파사드: 사용자 지정 배경색 외벽
    - 깔끔한 외벽
    - 간판이 외벽에 통합
    """
    # 사용자 지정 배경색
    bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
    signboard = Image.new('RGB', (width, height), color=bg_rgb)
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    # 텍스트 렌더링
    font = get_korean_font(100)
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    result = cv2.add(signboard_np, text_layer_bgr)
    
    return result

def render_awning_signboard(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    어닝간판: 정면에서 본 간단한 어닝(천막) 표현
    - 위쪽: 천막 앞면 (사다리꼴 + 그라디언트로 약간 입체감)
    - 상단: 설치 봉(막대)
    - 텍스트: 앞면 오른쪽 아래에 작게 배치 (실제 시안처럼)
    """
    # 기본 색상
    base_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (200, 80, 60)
    r, g, b = base_rgb

    # 전체 배경은 투명으로 시작 (벽이 비치도록)
    signboard = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(signboard)

    # 상단 설치 봉(막대)
    rod_height = max(2, int(height * 0.08))
    rod_color = (230, 230, 235, 255)
    shadow_color = (120, 120, 130, 255)
    draw.rectangle([0, 0, width, rod_height], fill=rod_color)
    # 막대 아래 얇은 그림자
    draw.rectangle([0, rod_height, width, rod_height + 2], fill=shadow_color)

    # 어닝 앞면(사다리꼴) 영역
    top_y = rod_height + 2
    bottom_y = height - 1
    front_h = max(1, bottom_y - top_y + 1)

    # 좌측/우측 깊이 (사다리꼴 모양)
    left_depth = int(width * 0.10)   # 좌측이 더 멀리 있는 느낌
    right_depth = int(width * 0.04)  # 우측은 덜 기울어지게

    # 앞면 그라디언트 + 사다리꼴 형태로 라인 그리기
    for yi in range(front_h):
        y = top_y + yi
        t = yi / max(1, front_h - 1)  # 0 위쪽, 1 아래쪽

        # 사다리꼴의 좌/우 x 위치
        x_left = int(left_depth * t)  # 아래쪽으로 갈수록 더 안쪽으로
        x_right = int(width - right_depth * (1.0 - t))

        # 색 그라디언트: 위는 밝게, 아래는 기본색에 가까이
        factor = 1.0 + 0.18 * (1.0 - t)
        rr = int(max(0, min(255, r * factor)))
        gg = int(max(0, min(255, g * factor)))
        bb = int(max(0, min(255, b * factor)))

        draw.line([(x_left, y), (x_right, y)], fill=(rr, gg, bb, 255))

    # 좌측 전면 모서리를 약간 라운딩된 느낌으로 어둡게 처리
    edge_shadow = (int(r * 0.4), int(g * 0.4), int(b * 0.4), 255)
    for yi in range(front_h // 2):
        y = top_y + yi
        draw.point((left_depth * yi / max(1, front_h // 2), y), fill=edge_shadow)

    # 전면 하단 엣지에 얇은 하이라이트/그림자 라인
    fold_y = bottom_y - 1
    if fold_y > top_y:
        highlight = (min(255, r + 35), min(255, g + 35), min(255, b + 35), 255)
        draw.line([(left_depth, fold_y), (width, fold_y)], fill=highlight, width=1)
        if fold_y + 1 < height:
            shadow_line = (int(r * 0.35), int(g * 0.35), int(b * 0.35), 255)
            draw.line([(left_depth, fold_y + 1), (width, fold_y + 1)], fill=shadow_line, width=1)

    # 텍스트가 없으면 어닝 형태만 반환
    signboard_rgb = Image.new('RGB', (width, height), (0, 0, 0))
    signboard_rgb.paste(signboard, (0, 0), signboard)
    signboard_np = cv2.cvtColor(np.array(signboard_rgb), cv2.COLOR_RGB2BGR)
    if not text or not text.strip():
        return signboard_np

    # 텍스트 렌더링 (앞면 오른쪽 아래에 작게)
    # 어닝 앞면 높이에 비례해서 글자 크기를 조정
    approx_font_size = max(18, min(72, int(front_h * 0.30)))
    font = get_korean_font(approx_font_size)
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    # 텍스트는 앞면 오른쪽 아래 모서리 쪽에 작게 배치
    margin_x = int(width * 0.06)
    margin_y_bottom = int(front_h * 0.18)
    text_x = max(left_depth + 5, width - margin_x - text_width)
    text_y = max(top_y + 5, bottom_y - margin_y_bottom - text_height)
    position = (text_x, text_y)

    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)

    result = cv2.add(signboard_np, text_layer_bgr)
    return result

# ========== 기타 간판 ==========

def render_flex_signboard(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    플렉스 간판: 천 재질
    - 텍스처 있음
    - 부드러운 느낌
    - 전체가 발광 (배경 포함)
    """
    bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (107, 45, 143)
    signboard = Image.new('RGB', (width, height), color=bg_rgb)
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        # 플렉스 텍스처 추가
        texture = np.random.randint(-8, 8, signboard_np.shape, dtype=np.int16)
        result = np.clip(signboard_np.astype(np.int16) + texture, 0, 255).astype(np.uint8)
        return result
    
    font = get_korean_font(100)
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    result = cv2.add(signboard_np, text_layer_bgr)
    
    # 플렉스 텍스처 (천 느낌)
    texture = np.random.randint(-8, 8, result.shape, dtype=np.int16)
    result = np.clip(result.astype(np.int16) + texture, 0, 255).astype(np.uint8)
    
    # 전체 발광 효과
    glow = safe_gaussian_blur(result, (15, 15), 0)
    result = cv2.addWeighted(result, 0.7, glow, 0.3, 0)
    
    return result

def render_scashi_signboard(text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, text_direction: str = "horizontal", width: int = 1200, height: int = 300) -> np.ndarray:
    """
    스카시 간판: 아크릴/철제/스테인리스 재질, 입체 글자, 자체 발광 없음 (비조명)
    - 배경/글자 색상: 사용자 입력 반영
    - 입체적인 3D 글자 (그림자+하이라이트)
    - 발광 효과 없음
    """
    # 배경: 사용자 지정 색상 사용
    bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
    signboard = Image.new('RGB', (width, height), color=bg_rgb)
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        return signboard_np
    
    font = get_korean_font(100)
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    bbox = draw_temp.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    # 텍스트 색상: 사용자 입력 반영, 기본은 짙은 회색 금속 느낌
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (90, 90, 90)
    
    # 입체감 있는 텍스트 렌더링 (여러 레이어)
    shadow_offset = 3
    shadow_pos = (position[0] + shadow_offset, position[1] + shadow_offset)
    shadow_layer_rgba = extract_text_layer(text, font, (0, 0, 0), (width, height), shadow_pos)
    shadow_layer_bgr = cv2.cvtColor(shadow_layer_rgba, cv2.COLOR_RGBA2BGR)
    shadow_layer_bgr = safe_gaussian_blur(shadow_layer_bgr, (5, 5), 0)
    
    text_layer_rgba = extract_text_layer(text, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    highlight_pos = (position[0] - 1, position[1] - 1)
    highlight_rgb = tuple(min(255, c + 30) for c in text_rgb)
    highlight_layer_rgba = extract_text_layer(text, font, highlight_rgb, (width, height), highlight_pos)
    highlight_layer_bgr = cv2.cvtColor(highlight_layer_rgba, cv2.COLOR_RGBA2BGR)
    
    # 합성: 배경 → 그림자 → 메인 텍스트 → 하이라이트
    result = signboard_np.copy()
    result = cv2.add(result, shadow_layer_bgr)
    result = cv2.add(result, text_layer_bgr)
    result = cv2.addWeighted(result, 0.95, highlight_layer_bgr, 0.15, 0)
    
    # 금속/아크릴 질감 추가 (미세한 노이즈)
    texture = np.random.randint(-3, 3, result.shape, dtype=np.int16)
    result = np.clip(result.astype(np.int16) + texture, 0, 255).astype(np.uint8)
    
    return result

def render_combined_signboard(installation_type: str, sign_type: str, text: str, bg_color: str, text_color: str, logo_img: Image.Image = None, logo_type: str = "channel", text_direction: str = "horizontal", font_size: int = 100, text_position_x: int = 50, text_position_y: int = 50, width: int = 1200, height: int = 300, use_actual_bg_for_training: bool = False, lights_enabled: bool = False, white_background: bool = False, building_photo: np.ndarray = None, polygon_points: list = None, font_family: str = "malgun", font_weight: str = "400"):
    """설치 방식 + 간판 종류 조합 렌더링
    Returns: (signboard_image, text_layer)
    - 전광채널: (signboard, text_layer) - text_layer는 텍스트만 분리
    - 후광채널: (signboard, text_layer) - text_layer는 텍스트만 분리 (야간 효과용)
    - 기타: (signboard, None)
    
    Args:
        use_actual_bg_for_training: True면 맨벽/프레임바도 실제 배경색 사용 (학습 데이터용)
                                    False면 맨벽/프레임바는 투명 배경 (시안 생성용, 기본값)
        white_background: True면 모든 설치 방식에 대해 흰색 배경 강제 (평면 시안용)
    """
    # 스카시 재질 파싱
    material = None
    if sign_type.startswith("스카시_"):
        material = sign_type.split("_")[1]  # "금속", "아크릴", "고무"
        sign_type = "스카시"
        print(f"[DEBUG] Scasi material: {material}")
    
    # 배경 생성 (설치 방식에 따라) - 프레임바는 텍스트 크기 측정 후에 그려야 함
    is_frame_bar = (installation_type == "프레임바")
    is_window_sheet = (installation_type == "유리창시트시공")
    
    # 프레임 마스크 (유리창시트시공용, 텍스트 렌더링 시 적용)
    window_frame_mask = None
    window_background_before_text = None
    
    # 흰색 배경 강제 옵션
    if white_background:
        signboard = Image.new('RGB', (width, height), color=(255, 255, 255))
    elif installation_type == "프레임바":
        if use_actual_bg_for_training:
            # 학습용: 실제 배경색 사용
            bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
            signboard = Image.new('RGB', (width, height), color=bg_rgb)
        else:
            # 시안용: 투명 배경 (나중에 텍스트 크기 측정 후 막대 그리기)
            signboard = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # 투명 배경
    elif installation_type == "전면프레임":
        # 전면프레임: 사용자 지정 배경색 + 얇은 프레임
        bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (107, 45, 143)
        signboard = Image.new('RGB', (width, height), color=bg_rgb)
        draw = ImageDraw.Draw(signboard)
        
        # 얇은 프레임 (테두리만, 두께 감소)
        frame_thickness = max(3, int(min(width, height) * 0.01))  # 크기의 1%
        frame_color = (60, 60, 60)  # 어두운 프레임
        
        # 외곽 프레임만
        for i in range(frame_thickness):
            draw.rectangle([i, i, width-i-1, height-i-1], outline=frame_color)
        
        signboard = signboard
    elif installation_type == "맨벽":
        if use_actual_bg_for_training:
            # 학습용: 실제 배경색 사용
            bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
            signboard = Image.new('RGB', (width, height), color=bg_rgb)
        else:
            # 시안용: 투명 배경 (글자만 벽에 직접 부착)
            signboard = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            # RGB로 변환 (투명 부분은 검은색으로)
            bg = Image.new('RGB', (width, height), (0, 0, 0))
            bg.paste(signboard, (0, 0))
            signboard = bg
    elif installation_type == "파사드":
        # 파사드: 사용자 지정 배경색 (깔끔한 외벽)
        bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
        signboard = Image.new('RGB', (width, height), color=bg_rgb)
    elif installation_type == "유리창시트시공":
        # 유리창시트시공: 건물 사진에서 선택한 영역을 배경으로 사용
        if building_photo is not None and polygon_points is not None:
            # 건물 사진에서 폴리곤 영역을 추출
            try:
                if len(polygon_points) == 4:
                    # 4점인 경우: 원근 변환
                    src_points = order_points(polygon_points)
                    dst_points = np.array([
                        [0, 0],
                        [width, 0],
                        [width, height],
                        [0, height]
                    ], dtype=np.float32)
                    M = cv2.getPerspectiveTransform(src_points.astype(np.float32), dst_points)
                    warped_region = cv2.warpPerspective(building_photo, M, (width, height), flags=cv2.INTER_LINEAR)
                else:
                    # 4점이 아닌 경우: 바운딩 박스로 크롭 후 리사이즈
                    xs = [p[0] for p in polygon_points]
                    ys = [p[1] for p in polygon_points]
                    min_x, max_x = int(min(xs)), int(max(xs))
                    min_y, max_y = int(min(ys)), int(max(ys))
                    bbox_w = max_x - min_x
                    bbox_h = max_y - min_y
                    if bbox_w > 0 and bbox_h > 0:
                        cropped = building_photo[min_y:max_y, min_x:max_x]
                        warped_region = cv2.resize(cropped, (width, height))
                    else:
                        # 폴백: 배경색 사용
                        bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
                        warped_region = np.full((height, width, 3), bg_rgb, dtype=np.uint8)
                
                # 격자무늬(프레임) 감지: 어두운 부분은 시트지가 붙을 수 없으므로 원본 유지
                # 건물 사진을 그레이스케일로 변환하여 밝기 기반으로 프레임 감지
                warped_gray = cv2.cvtColor(warped_region, cv2.COLOR_BGR2GRAY)
                
                # 어두운 부분(프레임) 감지: 밝기 임계값 사용
                # 유리창은 밝고, 프레임은 어둡다는 가정
                # Otsu 임계값으로 자동 임계값 결정
                _, frame_mask_binary = cv2.threshold(warped_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                
                # 프레임 마스크 생성 (격자무늬가 있는 부분 = 0, 유리창 부분 = 1)
                # 어두운 부분(프레임)을 확장하여 프레임 영역 확보
                kernel_size = max(3, int(min(width, height) * 0.01))
                kernel = np.ones((kernel_size, kernel_size), np.uint8)
                frame_mask_binary = cv2.dilate(frame_mask_binary, kernel, iterations=2)
                frame_mask_binary = cv2.erode(frame_mask_binary, kernel, iterations=1)
                
                # 프레임 마스크를 0~1 범위로 정규화 (프레임 부분 = 0, 유리창 부분 = 1)
                frame_mask = (255 - frame_mask_binary).astype(np.float32) / 255.0
                
                # 텍스트 렌더링 시 사용할 프레임 마스크 저장
                window_frame_mask = frame_mask.copy()
                
                # 시트지 색상(bg_color) 반영: 유리창 부분만 시트지 색상 블렌딩
                bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
                sheet_color = np.full((height, width, 3), bg_rgb, dtype=np.float32)
                
                # 건물 사진 영역과 시트지 색상 블렌딩 (유리창 부분만)
                warped_region_float = warped_region.astype(np.float32)
                # BGR 순서를 RGB로 변환
                warped_region_rgb_float = cv2.cvtColor(warped_region_float, cv2.COLOR_BGR2RGB)
                
                # 프레임 마스크를 3채널로 확장
                frame_mask_3ch = np.stack([frame_mask, frame_mask, frame_mask], axis=2)
                
                # 프레임 부분은 원본 유지, 유리창 부분만 시트지 색상 블렌딩
                # 건물 사진 40% + 시트지 색상 60% (유리창 부분만)
                blended = warped_region_rgb_float * frame_mask_3ch * 0.4 + sheet_color * frame_mask_3ch * 0.6
                # 프레임 부분은 원본 그대로
                blended = blended + warped_region_rgb_float * (1 - frame_mask_3ch)
                blended = np.clip(blended, 0, 255).astype(np.uint8)
                
                # 텍스트 렌더링 시 사용할 원본 배경 이미지 저장 (프레임 부분 복원용)
                window_background_before_text = blended.copy()
                
                # PIL Image로 변환
                signboard = Image.fromarray(blended)
            except Exception as e:
                print(f"[ERROR] 유리창시트시공 영역 추출 실패: {e}, 배경색 사용")
                bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
                signboard = Image.new('RGB', (width, height), color=bg_rgb)
        else:
            # building_photo나 polygon_points가 없는 경우: 배경색 사용
            bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (220, 220, 220)
            signboard = Image.new('RGB', (width, height), color=bg_rgb)
    else:
        # 기본: 전면프레임
        bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (107, 45, 143)
        signboard = Image.new('RGB', (width, height), color=bg_rgb)
    
    # 로고 추가
    if logo_img:
        signboard = add_logo_to_signboard(signboard, logo_img, position="left")
    
    signboard_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
    
    if not text or not text.strip():
        if sign_type == "전광채널":
            return signboard_np, None
        return signboard_np, None
    
    # 폰트 크기 자동 조정: 텍스트가 영역 안에 들어가도록
    min_font_size = 20  # 최소 폰트 크기
    current_font_size = font_size
    text_width = 0
    text_height = 0
    font = None
    
    # 텍스트가 영역 안에 들어갈 때까지 폰트 크기 조정
    draw_temp = ImageDraw.Draw(Image.new('RGB', (width, height)))
    # 유리창시트시공: 패딩 없이 높이에 딱 맞게
    if is_window_sheet:
        min_padding_x = 0
        min_padding_y = 0
    # 프레임바인 경우 더 여유있게 (텍스트가 프레임바 안에 완전히 들어가야 함)
    elif is_frame_bar:
        min_padding_x = int(width * 0.1)   # 좌우 여백 더 여유있게
        min_padding_y = int(height * 0.1)  # 상하 여백 더 여유있게
    else:
        min_padding_x = int(width * 0.05)
        min_padding_y = int(height * 0.05)
    max_text_width = width - (min_padding_x * 2)
    max_text_height = height - (min_padding_y * 2)
    
    while current_font_size >= min_font_size:
        font = get_korean_font(current_font_size, font_family, font_weight)
        
        if text_direction == "vertical":
            text_vertical = '\n'.join(list(text))
            bbox = draw_temp.multiline_textbbox((0, 0), text_vertical, font=font)
        else:
            bbox = draw_temp.textbbox((0, 0), text, font=font)
        
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 텍스트가 영역 안에 들어가는지 확인
        if text_width <= max_text_width and text_height <= max_text_height:
            break
        
        # 폰트 크기 줄이기
        current_font_size -= 2
        if current_font_size < min_font_size:
            current_font_size = min_font_size
            font = get_korean_font(current_font_size, font_family, font_weight)
            if text_direction == "vertical":
                text_vertical = '\n'.join(list(text))
                bbox = draw_temp.multiline_textbbox((0, 0), text_vertical, font=font)
            else:
                bbox = draw_temp.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            break
    
    # 최종 선택된 bbox의 상단/하단 (baseline 기준 오프셋)
    bbox_top = bbox[1]
    bbox_bottom = bbox[3]
    
    # text_position_x, text_position_y 사용 (간판 내에서의 위치, 0-100%)
    # 0% ~ 100% 를 간판 영역 전체에 가깝게 사용하도록 재매핑
    text_pos_x_clamped = max(0, min(100, text_position_x))
    text_pos_y_clamped = max(0, min(100, text_position_y))

    # 최소 패딩: 텍스트가 잘리지 않도록 약간의 여백
    # 유리창시트시공: 패딩 없이 높이에 딱 맞게
    if is_window_sheet:
        min_padding_y = 0
        min_padding_x = 0
    # 프레임바인 경우 더 여유있게 (텍스트가 프레임바 안에 들어가야 함)
    elif is_frame_bar:
        min_padding_y = int(height * 0.1)  # 프레임바는 더 여유있게
        min_padding_x = int(width * 0.1)   # 좌우 여백도 더 여유있게
    else:
        min_padding_y = int(height * 0.05)
        min_padding_x = int(width * 0.05)

    # 세로 방향 위치 계산 (텍스트 실제 bbox 기준)
    # - bbox_top/bottom 은 baseline=0 기준에서의 텍스트 상단/하단 오프셋
    # - baseline y 위치를 조절해서 텍스트 "시각적 중심"이 간판 박스 안에서 움직이도록 함
    #   text_position_y: 0 -> 텍스트 전체가 위로 붙음, 50 -> 중앙, 100 -> 아래로 붙음
    # baseline 이 y_offset 라고 할 때:
    #   실제 텍스트 상단 = y_offset + bbox_top
    #   실제 텍스트 하단 = y_offset + bbox_bottom
    # 전체 텍스트가 박스 안에 들어가기 위한 baseline 범위:
    baseline_min = -bbox_top             # 텍스트 상단이 0에 맞춰질 때
    baseline_max = height - bbox_bottom  # 텍스트 하단이 height에 맞춰질 때
    
    if baseline_max < baseline_min:
        # 텍스트가 너무 큰 경우: 중앙 고정
        y_offset = (height - text_height) // 2
    else:
        # 0~100%를 baseline_min~baseline_max 에 선형 매핑
        t = text_pos_y_clamped / 100.0
        y_offset = baseline_min + t * (baseline_max - baseline_min)
        y_offset = int(round(y_offset))

    # 가로 방향 사용 가능 영역 (텍스트 실제 너비 고려)
    usable_width = width - (min_padding_x * 2) - text_width
    if usable_width < 0:
        x_offset = (width - text_width) // 2
    else:
        # 로고가 있는 경우에도 text_position_x 를 그대로 사용 (로고 위치는 별도로 조정)
        x_offset = min_padding_x + int((text_pos_x_clamped / 100.0) * usable_width)
    
    position = (x_offset, y_offset)
    
    # 프레임바인 경우: 텍스트 위치를 기준으로 프레임바를 중앙에 배치
    # 실제 텍스트 렌더링 위치를 정확히 계산하기 위해 실제 bbox를 다시 측정
    if is_frame_bar:
        # 프레임바 굵기: 글자 높이의 15-20% (최소 3px, 최대 20px)
        bar_height = max(3, min(20, int(text_height * 0.18)))
        
        # 실제 렌더링 위치에서 텍스트 bbox를 다시 측정
        # position은 (x_offset, y_offset)이고, 이게 draw.text()의 baseline 위치
        # textbbox를 position 기준으로 다시 측정하면 실제 텍스트 위치를 알 수 있음
        if text_direction == "vertical":
            text_vertical = '\n'.join(list(text))
            actual_bbox = draw_temp.multiline_textbbox(position, text_vertical, font=font)
        else:
            actual_bbox = draw_temp.textbbox(position, text, font=font)
        
        # 실제 텍스트의 상단과 하단
        text_actual_top = actual_bbox[1]
        text_actual_bottom = actual_bbox[3]
        text_center_y = (text_actual_top + text_actual_bottom) // 2
        
        # 프레임바를 텍스트 중앙에 맞춤
        bar_y = text_center_y - bar_height // 2
        
        # 프레임바가 영역을 벗어나지 않도록 조정
        if bar_y < 0:
            bar_y = 0
        elif bar_y + bar_height > height:
            bar_y = height - bar_height
        
        # 프레임바 길이: 텍스트 너비 + 양옆으로 조금씩 튀어나오기
        # 텍스트의 실제 좌우 위치
        text_actual_left = actual_bbox[0]
        text_actual_right = actual_bbox[2]
        text_actual_width = text_actual_right - text_actual_left
        
        # 양옆으로 튀어나올 길이 (텍스트 너비의 10-15% 또는 최소 20px)
        bar_padding = max(20, int(text_actual_width * 0.12))
        bar_left = max(0, text_actual_left - bar_padding)
        bar_right = min(width, text_actual_right + bar_padding)
        bar_width = bar_right - bar_left
        
        # 텍스트 색상 계산 (프레임바 마스킹을 위해 먼저 필요)
        text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
        
        # 검은색/매우 어두운 텍스트 색상 처리
        try:
            if sum(text_rgb) < 30:
                text_rgb = (35, 35, 35)
                print(f"[DEBUG] 검은색 텍스트 감지 → {text_rgb}로 조정")
        except Exception:
            pass
        
        # 텍스트 렌더링 문자열 준비
        if text_direction == "vertical":
            text_to_render = '\n'.join(list(text))
        else:
            text_to_render = text
        
        # 실제 텍스트 레이어 먼저 추출 (안티앨리어싱 포함된 alpha 채널 사용)
        text_layer_rgba = extract_text_layer(text_to_render, font, text_rgb, (width, height), position)
        text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
        
        # 실제 alpha 채널로 프레임바 마스킹 (안티앨리어싱 정보 포함)
        text_alpha_3ch = np.repeat(
            text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0,
            3,
            axis=2
        )  # (h, w, 3) 형태, 0-1 범위
        
        # 프레임바를 별도 레이어로 생성 (numpy 배열로)
        frame_layer = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 알루미늄 막대 (은색, 약간 어두운 회색) - BGR 형식
        bar_color_bgr = (130, 120, 120)  # RGB(120, 120, 130) -> BGR(130, 120, 120)
        frame_layer[bar_y:bar_y + bar_height, bar_left:bar_right] = bar_color_bgr
        
        # 막대 입체감 (상단 하이라이트) - BGR 형식
        highlight_color_bgr = (170, 160, 160)  # RGB(160, 160, 170) -> BGR(170, 160, 160)
        frame_layer[bar_y:bar_y + 2, bar_left:bar_right] = highlight_color_bgr
        
        # 막대 하단 그림자 - BGR 형식
        shadow_color_bgr = (90, 80, 80)  # RGB(80, 80, 90) -> BGR(90, 80, 80)
        frame_layer[bar_y + bar_height - 2:bar_y + bar_height, bar_left:bar_right] = shadow_color_bgr
        
        # 텍스트 영역을 프레임바에서 부드럽게 제외 (실제 alpha 값 사용)
        # alpha=255(1.0) → 프레임바 0% (완전 제거)
        # alpha=127(0.5) → 프레임바 50% (반만 제거)
        # alpha=0(0.0) → 프레임바 100% (유지)
        frame_layer = (frame_layer.astype(np.float32) * (1 - text_alpha_3ch)).astype(np.uint8)
        
        # 프레임바 레이어를 signboard_np에 합성
        if use_actual_bg_for_training or white_background:
            # 학습용 또는 흰색 배경: 배경이 있으므로 alpha 블렌딩 사용
            # 막대가 있는 영역만 alpha 1.0 (frame_layer는 이미 텍스트 영역 제외됨)
            frame_alpha = (frame_layer.sum(axis=2) > 0).astype(np.float32)
            frame_alpha_3ch = np.stack([frame_alpha, frame_alpha, frame_alpha], axis=2)
            
            signboard_np = (
                signboard_np.astype(np.float32) * (1 - frame_alpha_3ch) +
                frame_layer.astype(np.float32) * frame_alpha_3ch
            ).astype(np.uint8)
        else:
            # 시안용: 투명 배경이므로 cv2.add 사용 (기존 동작)
            signboard_np = cv2.add(signboard_np, frame_layer)
    
    # 간판 종류에 따라 렌더링
    # 전광채널은 모든 설치방식에 대해 동일한 텍스트 렌더링 적용
    # 프레임바가 아닌 경우에만 text_rgb, text_to_render 계산 (프레임바는 위에서 이미 계산됨)
    if not is_frame_bar:
        text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)

        # 검은색/매우 어두운 텍스트 색상 처리:
        # composite_signboard의 transparency_mask(밝기 30 미만 투명 처리)에 걸려서
        # 글자가 사라지는 문제를 막기 위해, 아주 약간 밝은 회색으로 올려줌.
        try:
            if sum(text_rgb) < 30:  # RGB 합이 30 미만이면 거의 검정으로 간주
                text_rgb = (35, 35, 35)  # 투명 threshold(30)보다 살짝 높은 아주 어두운 회색
                print(f"[DEBUG] 검은색 텍스트 감지 → {text_rgb}로 조정")
        except Exception:
            pass
        
        if text_direction == "vertical":
            text_to_render = '\n'.join(list(text))
        else:
            text_to_render = text
    
    if sign_type == "전광채널":
        # 전광채널: 모든 설치방식(맨벽, 프레임바, 프레임판)에 대해 옆면, 앞면을 사용한 입체적 렌더링 (glow 없음)
        # 1) 텍스트 앞면(원본 색상)
        text_layer_rgba = extract_text_layer(text_to_render, font, text_rgb, (width, height), position)
        text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)

        # 2) 텍스트 옆면(원본보다 50% 더 어두운 색상, 오른쪽 아래로 대각선 offset)
        side_color = tuple(int(c * 0.5) for c in text_rgb)
        side_offset_x = 2
        side_offset_y = 1
        side_position = (position[0] + side_offset_x, position[1] + side_offset_y)
        side_layer_rgba = extract_text_layer(text_to_render, font, side_color, (width, height), side_position)
        side_layer_bgr = cv2.cvtColor(side_layer_rgba, cv2.COLOR_RGBA2BGR)

        day_result = signboard_np.copy()

        # 전면프레임인 경우 alpha 블렌딩 사용 (배경색과 섞이지 않도록)
        if installation_type == "전면프레임":
            sys.stdout.write(f"[전면프레임 블렌딩] 시작: text_color={text_color}, bg_color={bg_color}\n")
            sys.stdout.flush()
            print(f"[전면프레임 블렌딩] 시작: text_color={text_color}, bg_color={bg_color}", flush=True)
            # 투명 배경에서 레이어 쌓기 (배경 색과 독립적으로)
            # 전면프레임은 그림자 없음 (프레임에 붙어있어서 그림자가 생기지 않음)
            h, w = day_result.shape[:2]
            result = np.zeros((h, w, 4), dtype=np.float32)  # RGBA
            
            # 1. 옆면 레이어 (앞면 영역 제외) - 입체감을 위한 옆면만
            side_alpha = side_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
            side_rgb = side_layer_rgba[:, :, :3].astype(np.float32)
            text_mask = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
            
            # 앞면 영역 제외
            side_alpha_adjusted = side_alpha * (1 - text_mask)
            
            # 알파 합성
            result[:, :, :3] = result[:, :, :3] * (1 - side_alpha_adjusted) + side_rgb * side_alpha_adjusted
            result[:, :, 3:4] = np.maximum(result[:, :, 3:4], side_alpha_adjusted)
            
            # 2. 앞면 레이어 (100% 불투명)
            text_alpha = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
            text_rgb = text_layer_rgba[:, :, :3].astype(np.float32)
            
            # 알파 합성
            result[:, :, :3] = result[:, :, :3] * (1 - text_alpha) + text_rgb * text_alpha
            result[:, :, 3:4] = np.maximum(result[:, :, 3:4], text_alpha)
            
            # 텍스트 영역의 알파를 1.0으로 강제 설정 (전면프레임은 불투명해야 함)
            text_mask = text_layer_rgba[:, :, 3] > 0
            result[text_mask, 3] = 1.0
            
            # 3. RGB -> BGR 변환 (result[:, :, :3]은 RGB 순서이므로 BGR로 변환 필요)
            result_rgb = result[:, :, :3].astype(np.uint8)
            result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR).astype(np.float32)
            
            # 4. 배경과 합성 (BGR 순서로 통일)
            result_alpha = result[:, :, 3:4]  # 이미 0-1 범위
            bg = day_result.astype(np.float32)
            
            final = bg * (1 - result_alpha) + result_bgr * result_alpha
            day_result = np.clip(final, 0, 255).astype(np.uint8)
            
            # 샘플 확인 (텍스트 영역)
            text_region_mask = text_layer_rgba[:, :, 3] > 0
            if text_region_mask.any():
                sample_y, sample_x = np.where(text_region_mask)
                if len(sample_y) > 0:
                    idx = len(sample_y) // 2
                    y, x = sample_y[idx], sample_x[idx]
                    text_rgb_value = text_layer_rgba[y, x, :3]
                    text_bgr_value = text_layer_bgr[y, x]
                    final_value = day_result[y, x]
                    sys.stdout.write(f"[전면프레임 블렌딩] 완료 - 텍스트 샘플[{y},{x}]: text_rgba={text_rgb_value}, text_bgr={text_bgr_value}, 최종={final_value}\n")
                    sys.stdout.flush()
                    print(f"[전면프레임 블렌딩] 완료 - 텍스트 샘플[{y},{x}]: text_rgba={text_rgb_value}, text_bgr={text_bgr_value}, 최종={final_value}", flush=True)
            
            # 전면프레임은 add_3d_depth를 적용하지 않음 (이미 블렌딩 완료)
        else:
            # 맨벽/프레임바: 기존 방식 (투명 배경이므로 add 사용 가능)
            day_f = day_result.astype(np.float32)

            # 옆면, 앞면 합성 (glow 없이)
            if use_actual_bg_for_training:
                # 학습용: 배경이 있으므로 alpha 블렌딩 사용
                # 옆면 alpha 블렌딩
                side_alpha = side_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
                side_alpha_3ch = np.repeat(side_alpha, 3, axis=2)
                day_result = (
                    day_f * (1 - side_alpha_3ch) +
                    side_layer_bgr.astype(np.float32) * side_alpha_3ch
                ).astype(np.uint8)
                
                # 앞면 alpha 블렌딩
                text_alpha = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
                text_alpha_3ch = np.repeat(text_alpha, 3, axis=2)
                day_result = (
                    day_result.astype(np.float32) * (1 - text_alpha_3ch) +
                    text_layer_bgr.astype(np.float32) * text_alpha_3ch
                ).astype(np.uint8)
            else:
                # 시안용: 투명 배경이므로 cv2.add 사용 (기존 동작)
                day_result = cv2.add(day_f.astype(np.uint8), side_layer_bgr)
                day_result = cv2.add(day_result, text_layer_bgr)
            
            # 맨벽/프레임바는 입체감 추가
            if installation_type == "프레임바":
                day_result = add_3d_depth(day_result, depth=5)
            elif installation_type == "맨벽":
                day_result = add_3d_depth(day_result, depth=5)
        
        # 전광채널: lights_enabled=True일 때만 주간에도 전광 glow 효과 적용
        if lights_enabled:
            # ============ 이미지 크기 기반 동적 전광 조정 ============
            image_area = width * height
            
            # 작은 이미지 (512x512=262,144 이하): pix2pix용 자연스러운 전광
            if image_area <= 300000:  # 약 548x548 이하
                # 작은 blur로 자연스러운 전광
                front_blur_size = (15, 15)
                front_sigma = 8
                front_intensity = 0.8  # 낮은 강도
            else:
                # 큰 이미지: 기존 설정 유지
                front_blur_size = (25, 25)
                front_sigma = 10
                front_intensity = 0.6
            # ========================================================
            
            # 전광 효과: 텍스트 앞에서 빛나는 효과 (동적 파라미터)
            text_glow = safe_gaussian_blur(text_layer_bgr, front_blur_size, front_sigma)
            # day_result 크기에 맞춰서 text_glow 리사이즈 (add_3d_depth로 크기가 변경될 수 있음)
            if day_result.shape[:2] != text_glow.shape[:2]:
                text_glow = cv2.resize(text_glow, (day_result.shape[1], day_result.shape[0]))
            day_result = cv2.addWeighted(day_result, 1.0, text_glow, front_intensity, 0)
        
        # 야간용 text_layer 반환 (후광채널과 동일)
        return day_result, text_layer_bgr
    
    elif sign_type in ["후광채널", "전후광채널"]:
        # 발광 간판: 후광/전후광
        # 주간 이미지 생성 시에는 lights_enabled 무시 (야간 합성에서만 조명 효과 적용)
        # render_combined_signboard는 주간 이미지만 생성하므로 항상 원본 색상 사용
        text_rgb_for_layer = text_rgb
        
        # 1) 텍스트 앞면(원본 색상 또는 밝게 조정된 색상)
        text_layer_rgba = extract_text_layer(text_to_render, font, text_rgb_for_layer, (width, height), position)
        text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
        print(f"[DEBUG] 후광/전후광: text_layer_rgba 생성 후 shape={text_layer_rgba.shape}, RGB.min()={text_layer_rgba[:, :, :3].min()}, max()={text_layer_rgba[:, :, :3].max()}, mean()={text_layer_rgba[:, :, :3].mean()}, alpha.max()={text_layer_rgba[:, :, 3].max()}, mean()={text_layer_rgba[:, :, 3].mean()}")

        # 2) 텍스트 옆면(원본보다 50% 더 어두운 색상, 오른쪽 아래로 대각선 offset)
        side_color = tuple(int(c * 0.5) for c in text_rgb)
        side_offset_x = 2
        side_offset_y = 1
        side_position = (position[0] + side_offset_x, position[1] + side_offset_y)
        side_layer_rgba = extract_text_layer(text_to_render, font, side_color, (width, height), side_position)
        side_layer_bgr = cv2.cvtColor(side_layer_rgba, cv2.COLOR_RGBA2BGR)
        print(f"[DEBUG] 후광/전후광: side_layer_rgba 생성 후 shape={side_layer_rgba.shape}, RGB.min()={side_layer_rgba[:, :, :3].min()}, max()={side_layer_rgba[:, :, :3].max()}, mean()={side_layer_rgba[:, :, :3].mean()}, alpha.max()={side_layer_rgba[:, :, 3].max()}, mean()={side_layer_rgba[:, :, 3].mean()}")

        day_result = signboard_np.copy()
        print(f"[DEBUG] 후광/전후광: signboard_np.shape={signboard_np.shape}, day_result.shape={day_result.shape}, width={width}, height={height}")

        # 전면프레임인 경우 alpha 블렌딩 사용 (배경색과 섞이지 않도록) - 전광채널과 완전히 동일
        if installation_type == "전면프레임":
            debug_logger.info(f"[후광/전후광 전면프레임 블렌딩] 시작: sign_type={sign_type}, text_color={text_color}, bg_color={bg_color}")
            # 투명 배경에서 레이어 쌓기 (배경 색과 독립적으로)
            # 전면프레임은 그림자 없음 (프레임에 붙어있어서 그림자가 생기지 않음)
            h, w = day_result.shape[:2]
            result = np.zeros((h, w, 4), dtype=np.float32)  # RGBA
            
            # 1. 옆면 레이어 (앞면 영역 제외) - 입체감을 위한 옆면만
            side_alpha = side_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
            side_rgb = side_layer_rgba[:, :, :3].astype(np.float32)
            text_mask = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
            
            # 앞면 영역 제외
            side_alpha_adjusted = side_alpha * (1 - text_mask)
            
            # 알파 합성
            result[:, :, :3] = result[:, :, :3] * (1 - side_alpha_adjusted) + side_rgb * side_alpha_adjusted
            result[:, :, 3:4] = np.maximum(result[:, :, 3:4], side_alpha_adjusted)
            
            # 2. 앞면 레이어 (100% 불투명)
            text_alpha = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
            text_rgb = text_layer_rgba[:, :, :3].astype(np.float32)
            
            # 알파 합성
            result[:, :, :3] = result[:, :, :3] * (1 - text_alpha) + text_rgb * text_alpha
            result[:, :, 3:4] = np.maximum(result[:, :, 3:4], text_alpha)
            
            # 텍스트 영역의 알파를 1.0으로 강제 설정 (전면프레임은 불투명해야 함)
            text_mask = text_layer_rgba[:, :, 3] > 0
            result[text_mask, 3] = 1.0
            debug_logger.debug(f"텍스트 알파 강제 설정: text_mask 픽셀 수={text_mask.sum()}, result[text_mask, 3].min()={result[text_mask, 3].min()}, max()={result[text_mask, 3].max()}")
            
            # 3. RGB -> BGR 변환 (result[:, :, :3]은 RGB 순서이므로 BGR로 변환 필요)
            result_rgb = result[:, :, :3].astype(np.uint8)
            result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR).astype(np.float32)
            
            # 4. 배경과 합성 (BGR 순서로 통일)
            result_alpha = result[:, :, 3:4]  # 이미 0-1 범위
            bg = day_result.astype(np.float32)
            debug_logger.debug(f"배경 정보: bg_color={bg_color}, bg_rgb={hex_to_rgb(bg_color) if bg_color.startswith('#') else (107, 45, 143)}, bg.shape={bg.shape}, bg.mean()={bg.mean():.2f}")
            debug_logger.debug(f"텍스트 레이어: result_bgr.shape={result_bgr.shape}, result_bgr.mean()={result_bgr.mean():.2f}, result_alpha.mean()={result_alpha.mean():.4f}, result_alpha.max()={result_alpha.max():.4f}")
            
            final = bg * (1 - result_alpha) + result_bgr * result_alpha
            day_result = np.clip(final, 0, 255).astype(np.uint8)
            debug_logger.debug(f"블렌딩 결과: final.shape={final.shape}, final.mean()={final.mean():.2f}, day_result.mean()={day_result.mean():.2f}")
            
            # 샘플 확인 (텍스트 영역)
            text_region_mask = text_layer_rgba[:, :, 3] > 0
            if text_region_mask.any():
                sample_y, sample_x = np.where(text_region_mask)
                if len(sample_y) > 0:
                    idx = len(sample_y) // 2
                    y, x = sample_y[idx], sample_x[idx]
                    text_rgb_value = text_layer_rgba[y, x, :3]
                    text_bgr_value = text_layer_bgr[y, x]
                    final_value = day_result[y, x]
                    debug_logger.info(f"텍스트 샘플[{y},{x}]: text_rgba={text_rgb_value}, text_bgr={text_bgr_value}, 최종={final_value}, result_alpha[{y},{x}]={result_alpha[y, x, 0]:.4f}")
            
            # 전면프레임은 add_3d_depth를 적용하지 않음 (이미 블렌딩 완료)
            # glow 처리를 위해 result 설정
            result = day_result.copy()
        else:
            # 맨벽/프레임바: 기존 방식 (투명 배경이므로 add 사용 가능)
            day_f = day_result.astype(np.float32)

            # 옆면, 앞면 합성
            if use_actual_bg_for_training:
                # 학습용: 배경이 있으므로 alpha 블렌딩 사용
                # 옆면 alpha 블렌딩
                side_alpha = side_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
                side_alpha_3ch = np.repeat(side_alpha, 3, axis=2)
                day_result = (
                    day_f * (1 - side_alpha_3ch) +
                    side_layer_bgr.astype(np.float32) * side_alpha_3ch
                ).astype(np.uint8)
                
                # 앞면 alpha 블렌딩
                text_alpha = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
                text_alpha_3ch = np.repeat(text_alpha, 3, axis=2)
                day_result = (
                    day_result.astype(np.float32) * (1 - text_alpha_3ch) +
                    text_layer_bgr.astype(np.float32) * text_alpha_3ch
                ).astype(np.uint8)
            else:
                # 시안용: 투명 배경이므로 cv2.add 사용 (기존 동작)
                day_result = cv2.add(day_f.astype(np.uint8), side_layer_bgr)
                day_result = cv2.add(day_result, text_layer_bgr)
            
            # 맨벽/프레임바는 입체감 추가
            if installation_type == "프레임바":
                day_result = add_3d_depth(day_result, depth=5)
            elif installation_type == "맨벽":
                day_result = add_3d_depth(day_result, depth=5)
            
            result = day_result

        # 후광채널/전후광채널 glow 처리 (전광채널과 동일하게 day_result에 직접 적용)
        if sign_type == "후광채널":
            # 후광채널: lights_enabled=True일 때만 주간에도 후광 glow 효과 적용
            if lights_enabled:
                # 후광 효과: 텍스트 뒤에서 빛나는 효과 (더 강하게)
                # text_mask를 (H, W) 형태로 변환 (Gaussian blur를 위해)
                text_mask = text_layer_rgba[:, :, 3].astype(np.float32) / 255.0  # (H, W)
                

                
                # ============ 이미지 크기 기반 동적 후광 조정 ============
                image_area = width * height
                
                # 작은 이미지 (512x512=262,144 이하): pix2pix용 자연스러운 후광
                if image_area <= 300000:  # 약 548x548 이하
                    # 작은 blur로 자연스러운 후광
                    blur_size1, blur_size2, blur_size3 = (31, 31), (31, 31), (21, 21)
                    sigma1, sigma2, sigma3 = 15, 15, 10
                    intensity = 1.8  # 낮은 강도
                else:
                    # 큰 이미지: 기존 설정 유지 (웹 간판시안생성기)
                    blur_size1, blur_size2, blur_size3 = (141, 141), (141, 141), (121, 121)
                    sigma1, sigma2, sigma3 = 70, 70, 60
                    intensity = 4.0
                
                # 동적 blur 적용
                backlight = safe_gaussian_blur(text_mask, blur_size1, sigma1)  # 첫 번째 blur
                backlight = safe_gaussian_blur(backlight, blur_size2, sigma2)  # 두 번째 blur
                backlight = safe_gaussian_blur(backlight, blur_size3, sigma3)  # 세 번째 blur로 더 부드럽게
                # ========================================================
                
                # 후광 색상: 기본 따뜻한 흰색 LED (대부분 후광채널이 이 색상 사용)
                glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)  # BGR: 따뜻한 흰색
                
                # (H, W) -> (H, W, 3)으로 변환, 따뜻한 흰색 LED 적용
                backlight_3d = backlight[:, :, np.newaxis]  # (H, W, 1)
                # 후광 glow: 동적 강도 적용
                backlight_glow = (backlight_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * intensity).clip(0, 255).astype(np.float32)
                
                # day_result와 크기 확인 및 리사이즈
                if day_result.shape[:2] != backlight_glow.shape[:2]:
                    backlight_glow = cv2.resize(backlight_glow, (day_result.shape[1], day_result.shape[0]), interpolation=cv2.INTER_AREA)
                # ============ 수정: text_mask도 크기 조정 ============
                # text_mask를 day_result 크기에 맞춤
                if day_result.shape[:2] != text_mask.shape[:2]:
                    text_mask = cv2.resize(text_mask, (day_result.shape[1], day_result.shape[0]), interpolation=cv2.INTER_AREA)

                # ============ 수정 부분 ============
                # 글자 영역 제외하고 후광만 적용
                text_mask_3ch = np.stack([text_mask, text_mask, text_mask], axis=2)
                backlight_only = backlight_glow * (1 - text_mask_3ch)
                day_result = day_result.astype(np.float32) + backlight_only
                day_result = np.clip(day_result, 0, 255).astype(np.uint8)
                # ==================================
                
        else:
            # 전후광채널: 주간에는 전광채널처럼 약한 glow 효과 추가
            debug_logger.info(f"[전후광채널 glow] 시작: installation_type={installation_type}, day_result.shape={day_result.shape}")
            if installation_type == "전면프레임":
                # 전면프레임: day_result에서 직접 밝은 부분 추출하여 glow 적용 (크기 문제 해결)
                # ============ 이미지 크기 기반 동적 전후광 조정 ============
                image_area = width * height
                
                # 작은 이미지 (512x512=262,144 이하): pix2pix용 자연스러운 전후광
                if image_area <= 300000:  # 약 548x548 이하
                    # 작은 blur로 자연스러운 전후광
                    mixed_blur_size = (15, 15)
                    mixed_sigma = 8
                    mixed_intensity = 0.4  # 낮은 강도
                else:
                    # 큰 이미지: 기존 설정 유지
                    mixed_blur_size = (25, 25)
                    mixed_sigma = 10
                    mixed_intensity = 0.5
                # ========================================================
                
                # day_result에서 텍스트 영역(밝은 부분) 추출
                gray = cv2.cvtColor(day_result, cv2.COLOR_BGR2GRAY)
                bright_mask = (gray > 50).astype(np.float32)  # 밝은 부분 마스크
                bright_mask_3ch = np.stack([bright_mask, bright_mask, bright_mask], axis=2)
                bright_area = day_result.astype(np.float32) * bright_mask_3ch
                text_glow = safe_gaussian_blur(bright_area.astype(np.uint8), mixed_blur_size, mixed_sigma)
                debug_logger.debug(f"전후광채널 전면프레임 glow: bright_mask 픽셀 수={bright_mask.sum()}, text_glow.mean()={text_glow.mean():.2f}")
                day_result = cv2.addWeighted(day_result, 1.0, text_glow, mixed_intensity, 0)
                debug_logger.debug(f"전후광채널 전면프레임 glow 완료: day_result.mean()={day_result.mean():.2f}")
            else:
                # 맨벽/프레임바: 기존 방식 (text_layer_bgr 사용)
                if text_layer_bgr is not None and text_layer_bgr.size > 0:
                    text_glow = safe_gaussian_blur(text_layer_bgr, (25, 25), 10)
                    # day_result 크기에 맞춰 text_glow 리사이즈
                    if day_result.shape[:2] != text_glow.shape[:2]:
                        text_glow = cv2.resize(text_glow, (day_result.shape[1], day_result.shape[0]), interpolation=cv2.INTER_AREA)
                    day_result = cv2.addWeighted(day_result, 1.0, text_glow, 0.5, 0)
        
        # result 설정 (전면프레임이든 아니든 day_result 사용)
        result = day_result
        print(f"[DEBUG] 후광/전후광: result 설정 후 result.shape={result.shape if result is not None else 'None'}, day_result.shape={day_result.shape if day_result is not None else 'None'}")
        
        # 후광채널/전후광채널일 때 text_layer 반환 (야간 효과 구현용)
        if sign_type in ["후광채널", "전후광채널"]:
            # result가 제대로 생성되었는지 확인
            if result is None or result.size == 0:
                print(f"[ERROR] 전후광채널/후광채널 result가 비어있음: result={result}, signboard_np.shape={signboard_np.shape if 'signboard_np' in locals() else 'N/A'}")
                # 기본 이미지 반환
                if 'signboard_np' in locals() and signboard_np is not None and signboard_np.size > 0:
                    result = signboard_np.copy()
                else:
                    # signboard_np도 없으면 빈 이미지 생성
                    result = np.zeros((height, width, 3), dtype=np.uint8)
            print(f"[DEBUG] 전후광채널/후광채널 반환: result.shape={result.shape if result is not None else 'None'}, text_layer_bgr.shape={text_layer_bgr.shape if text_layer_bgr is not None else 'None'}")
            return result, text_layer_bgr
        return result, None
    
    elif sign_type == "스카시":
        # 스카시: 비조명 입체
        # 1) 텍스트 앞면
        text_layer_rgba = extract_text_layer(text_to_render, font, text_rgb, (width, height), position)
        text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)

        # 2) 텍스트 옆면 (원본보다 50% 더 어두운 색상, 오른쪽 아래로 대각선 offset)
        side_color = tuple(int(c * 0.5) for c in text_rgb)  # 0.5x (원래대로)
        side_offset_x = 2
        side_offset_y = 1
        side_position = (position[0] + side_offset_x, position[1] + side_offset_y)
        side_layer_rgba = extract_text_layer(text_to_render, font, side_color, (width, height), side_position)
        side_layer_bgr = cv2.cvtColor(side_layer_rgba, cv2.COLOR_RGBA2BGR)

        result_f = signboard_np.copy().astype(np.float32)

        # 옆면, 앞면 합성 (alpha blending 사용 - 색상 간섭 방지)
        # 옆면 alpha blending
        side_alpha = side_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
        side_alpha_3ch = np.repeat(side_alpha, 3, axis=2)
        result_f = result_f * (1 - side_alpha_3ch) + side_layer_bgr.astype(np.float32) * side_alpha_3ch
        
        # 앞면 alpha blending
        text_alpha = text_layer_rgba[:, :, 3:4].astype(np.float32) / 255.0
        text_alpha_3ch = np.repeat(text_alpha, 3, axis=2)
        result_f = result_f * (1 - text_alpha_3ch) + text_layer_bgr.astype(np.float32) * text_alpha_3ch

        # 살짝 하이라이트 추가 (기존 스카시 느낌 유지)
        highlight_pos = (position[0] - 1, position[1] - 1)
        highlight_rgb = tuple(min(255, c + 30) for c in text_rgb)
        highlight_layer_rgba = extract_text_layer(text_to_render, font, highlight_rgb, (width, height), highlight_pos)
        highlight_layer_bgr = cv2.cvtColor(highlight_layer_rgba, cv2.COLOR_RGBA2BGR)
        result_f = cv2.addWeighted(result_f, 0.95, highlight_layer_bgr.astype(np.float32), 0.15, 0)

        # 금속/아크릴 질감 노이즈 유지
        texture = np.random.randint(-3, 3, result_f.shape, dtype=np.int16).astype(np.float32)
        result_f = np.clip(result_f + texture, 0, 255).astype(np.uint8)

        # 유리창시트시공: 입체감 없음 (유리창에 딱 붙는 시트지)
        if not is_window_sheet:
            result = add_3d_depth(result_f, depth=5)
        else:
            result = result_f
        return result, None
    
    elif sign_type == "플렉스_LED":
        # LED 플렉스: 강한 내부 발광 (LED 백라이트)
        draw = ImageDraw.Draw(signboard)
        draw.text(position, text_to_render, fill=text_rgb, font=font)
        result_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
        # LED 백라이트: 더 큰 범위, 더 강한 효과
        glow = safe_gaussian_blur(result_np, (81, 81), 35)
        result = cv2.addWeighted(result_np, 0.5, glow, 0.5, 0)
        
        # lights_enabled=True일 때 추가 외부 조명 효과
        if lights_enabled:
            extra_glow = safe_gaussian_blur(result, (61, 61), 25)
            result = cv2.addWeighted(result, 0.8, extra_glow, 0.2, 0)
        
        # 유리창시트시공: 입체감 없음 (유리창에 딱 붙는 시트지)
        if not is_window_sheet:
            result = add_3d_depth(result, depth=6)
        return result, None
    
    elif sign_type in ["플렉스_기본", "플렉스"]:
        # 기본 플렉스: 부드러운 천 재질 (LED 없음)
        draw = ImageDraw.Draw(signboard)
        draw.text(position, text_to_render, fill=text_rgb, font=font)
        result_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
        # 기존 방식: 부드러운 glow
        glow = safe_gaussian_blur(result_np, (51, 51), 20)
        result = cv2.addWeighted(result_np, 0.7, glow, 0.3, 0)
        
        # lights_enabled=True일 때 외부 조명으로 약간 밝아짐
        if lights_enabled:
            bright_glow = safe_gaussian_blur(result, (41, 41), 15)
            result = cv2.addWeighted(result, 0.9, bright_glow, 0.1, 0)
        
        # 유리창시트시공: 입체감 없음 (유리창에 딱 붙는 시트지)
        if not is_window_sheet:
            result = add_3d_depth(result, depth=6)
        return result, None
    elif sign_type == "어닝간판":
        # 어닝간판: 전용 렌더러 사용 (비조명 간판)
        result = render_awning_signboard(text, bg_color, text_color, logo_img, text_direction, width, height)
        return result, None
    
    else:
        # 기본: 간단한 텍스트
        draw = ImageDraw.Draw(signboard)
        draw.text(position, text_to_render, fill=text_rgb, font=font)
        result_np = cv2.cvtColor(np.array(signboard), cv2.COLOR_RGB2BGR)
        
        # 유리창시트시공: 프레임 마스크 적용하여 격자무늬 부분의 텍스트 제거
        if is_window_sheet and window_frame_mask is not None and window_background_before_text is not None:
            # 텍스트가 그려진 이미지를 RGB로 변환 (프레임 마스크와 블렌딩하기 위해)
            result_rgb = cv2.cvtColor(result_np, cv2.COLOR_BGR2RGB).astype(np.float32)
            
            # 프레임 마스크를 3채널로 확장 (프레임 부분 = 0, 유리창 부분 = 1)
            frame_mask_3ch = np.stack([window_frame_mask, window_frame_mask, window_frame_mask], axis=2)
            
            # 원본 배경 이미지(RGB)를 float32로 변환
            background_rgb = window_background_before_text.astype(np.float32)
            
            # 프레임 부분(마스크 = 0)에서는 원본 배경 이미지를 사용하고, 유리창 부분(마스크 = 1)에서는 텍스트가 그려진 이미지를 사용
            result_rgb = background_rgb * (1 - frame_mask_3ch) + result_rgb * frame_mask_3ch
            result_rgb = np.clip(result_rgb, 0, 255).astype(np.uint8)
            
            # RGB를 BGR로 변환
            result_np = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
        
        # 유리창시트시공: 입체감 없음 (유리창에 딱 붙는 시트지)
        if not is_window_sheet:
            result = add_3d_depth(result_np, depth=6)
        else:
            result = result_np
        return result, None

def render_signboard(text: str, logo_path: str, logo_type: str, installation_type: str, sign_type: str, bg_color: str, text_color: str, text_direction: str = "horizontal", font_size: int = 100, text_position_x: int = 50, text_position_y: int = 50, width: int = 1200, height: int = 300, use_actual_bg_for_training: bool = False, lights_enabled: bool = False, white_background: bool = False, building_photo: np.ndarray = None, polygon_points: list = None, font_family: str = "malgun", font_weight: str = "400") -> tuple:
    """간판 이미지 생성 - 설치 방식 + 간판 종류
    Returns: (day_image, text_layer) - text_layer는 전광채널만 분리, 나머지는 None
    
    Args:
        white_background: True면 흰색 배경에 간판만 렌더링 (평면 시안용)
    """
    print(f"[DEBUG] render_signboard called with sign_type: {sign_type}")
    # 로고 이미지 로드
    logo_img = None
    if logo_path and logo_path.strip():
        try:
            logo_img = base64_to_image_pil(logo_path)
        except:
            logo_img = None
    
    # 설치 방식 + 간판 종류 조합으로 렌더링
    # 전광채널은 주간은 후광채널과 동일한 렌더링을 사용하고,
    # 야간 합성에서만 전광/후광 차이를 둔다.
    if sign_type == "전광채널":
        # 전광채널: 직접 처리 (주간은 그림자+옆면+앞면, 야간은 별도 처리)
        result, text_layer = render_combined_signboard(installation_type, "전광채널", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, text_layer
    elif sign_type == "후광채널":
        result, text_layer = render_combined_signboard(installation_type, "후광채널", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, text_layer
    elif sign_type == "전후광채널":
        result, text_layer = render_combined_signboard(installation_type, "전후광채널", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, text_layer
    elif sign_type.startswith("스카시"):
        # 스카시_금속, 스카시_아크릴 등 모든 스카시 변형 지원
        print(f"[DEBUG] render_signboard: 스카시 감지, sign_type={sign_type}, render_combined_signboard 호출")
        result, _ = render_combined_signboard(installation_type, sign_type, text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, None
    elif sign_type == "플렉스":
        result, _ = render_combined_signboard(installation_type, "플렉스", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, None
    elif sign_type == "어닝간판":
        result, _ = render_combined_signboard(installation_type, "어닝간판", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, None
    elif sign_type == "시트시공":
        # 시트시공: 유리창에 시트지 부착 (유리창시트시공 설치 방식과 함께 사용)
        result, _ = render_combined_signboard(installation_type, "시트시공", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, None
    else:
        # 기본값: 전광채널
        result, text_layer = render_combined_signboard(installation_type, "전광채널", text, bg_color, text_color, logo_img, logo_type, text_direction, font_size, text_position_x, text_position_y, width, height, use_actual_bg_for_training, lights_enabled, white_background, building_photo, polygon_points, font_family, font_weight)
        return result, text_layer

def order_points(pts):
    """4개의 점을 정렬: [좌상, 우상, 우하, 좌하] 순서로
    Args:
        pts: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    Returns:
        정렬된 4x2 numpy 배열
    """
    pts = np.array(pts, dtype=np.float32)
    
    # 1. 좌상단: x+y 합이 가장 작음 (왼쪽 위)
    sum_pts = pts.sum(axis=1)
    top_left_idx = np.argmin(sum_pts)
    top_left = pts[top_left_idx]
    
    # 2. 우하단: x+y 합이 가장 큼 (오른쪽 아래)
    bottom_right_idx = np.argmax(sum_pts)
    bottom_right = pts[bottom_right_idx]
    
    # 3. 나머지 두 점 찾기
    remaining_indices = [i for i in range(4) if i != top_left_idx and i != bottom_right_idx]
    remaining_pts = pts[remaining_indices]
    
    # 4. 나머지 두 점을 y 좌표로 구분
    # y가 더 작은 점 = 우상단 (위쪽)
    # y가 더 큰 점 = 좌하단 (아래쪽)
    if remaining_pts[0][1] < remaining_pts[1][1]:
        top_right = remaining_pts[0]
        bottom_left = remaining_pts[1]
    else:
        top_right = remaining_pts[1]
        bottom_left = remaining_pts[0]
    
    return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)

def generate_flat_design(
    building_photo: np.ndarray,  # 원본 건물 사진
    polygon_points: list,
    signboard_image: np.ndarray,
    frame_line_color: tuple = (180, 180, 180),  # 회색 프레임 색상
    background_color: tuple = (255, 255, 255),  # 흰색 배경
    padding_ratio: float = 0.1,  # 프레임 주변 여백 비율 (10%)
    show_dimensions: bool = True,  # 치수 표시 여부
    region_width: int = None,  # 실제 영역 너비 (픽셀)
    region_height: int = None,  # 실제 영역 높이 (픽셀)
) -> np.ndarray:
    """
    평면 시안 생성: 원본 건물 사진에서 폴리곤 영역을 정면으로 펴서 가져온 후 간판 시안 합성
    
    Args:
        building_photo: 원본 건물 사진 (BGR)
        polygon_points: 폴리곤 점 리스트 [[x1, y1], [x2, y2], ...]
        signboard_image: 렌더링된 간판 이미지 (BGR)
        frame_line_color: 프레임 선 색상 (BGR)
        background_color: 배경 색상 (RGB)
        padding_ratio: 프레임 주변 여백 비율 (0.1 = 10%)
        show_dimensions: 치수 표시 여부
        region_width: 실제 영역 너비 (픽셀, 치수 표시용)
        region_height: 실제 영역 높이 (픽셀, 치수 표시용)
    
    Returns:
        평면 시안 이미지 (BGR)
    """
    # 1. 폴리곤 영역의 가로세로 비율 계산
    if len(polygon_points) == 4:
        ordered = order_points(polygon_points)
        top_width = np.sqrt((ordered[1][0] - ordered[0][0])**2 + (ordered[1][1] - ordered[0][1])**2)
        left_height = np.sqrt((ordered[3][0] - ordered[0][0])**2 + (ordered[3][1] - ordered[0][1])**2)
        calculated_width = top_width
        calculated_height = left_height
    else:
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        calculated_width = max(xs) - min(xs)
        calculated_height = max(ys) - min(ys)
    
    # region_width/height가 제공되지 않으면 계산된 값 사용
    if region_width is None:
        region_width = int(calculated_width)
    if region_height is None:
        region_height = int(calculated_height)
    
    # 2. 간판 이미지 크기 결정
    signboard_h, signboard_w = signboard_image.shape[:2]
    
    # 3. 원본 건물 사진에서 폴리곤 영역을 정면으로 펴기 (Perspective Transform)
    if len(polygon_points) == 4:
        # 4점인 경우: 정확한 투영 변환
        src_points = order_points(polygon_points)  # 건물 사진의 폴리곤 4점 (정렬됨)
        
        # 목표 사각형 (정면으로 펴진 영역)
        dst_width = int(calculated_width)
        dst_height = int(calculated_height)
        dst_points = np.array([
            [0, 0],
            [dst_width, 0],
            [dst_width, dst_height],
            [0, dst_height]
        ], dtype=np.float32)
        
        # 투영 변환 행렬 계산 (건물 사진의 폴리곤 -> 정면 사각형)
        M = cv2.getPerspectiveTransform(src_points, dst_points)
        
        # 원본 건물 사진에서 폴리곤 영역을 정면으로 펴기
        warped_building = cv2.warpPerspective(
            building_photo,
            M,
            (dst_width, dst_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)  # 여백은 흰색
        )
    else:
        # 4점이 아닌 경우: 바운딩 박스로 크롭
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
        # 바운딩 박스 크기
        bbox_w = max_x - min_x
        bbox_h = max_y - min_y
        
        # 건물 사진에서 해당 영역 크롭
        if min_x >= 0 and min_y >= 0 and max_x <= building_photo.shape[1] and max_y <= building_photo.shape[0]:
            warped_building = building_photo[min_y:max_y, min_x:max_x].copy()
            # 크롭된 이미지를 목표 크기로 리사이즈
            if bbox_w > 0 and bbox_h > 0:
                warped_building = cv2.resize(warped_building, (int(calculated_width), int(calculated_height)))
            else:
                warped_building = np.ones((int(calculated_height), int(calculated_width), 3), dtype=np.uint8) * 255
        else:
            # 범위 초과 시 흰색 배경
            warped_building = np.ones((int(calculated_height), int(calculated_width), 3), dtype=np.uint8) * 255
    
    # 4. 펴진 건물 배경의 크기를 간판 이미지 크기에 맞추기
    warped_building_resized = cv2.resize(warped_building, (signboard_w, signboard_h))
    
    # 5. 캔버스 크기 결정 (펴진 배경 + 여백 + 치수 표시 공간)
    frame_width = signboard_w
    frame_height = signboard_h
    
    padding_x = int(frame_width * padding_ratio)
    padding_y = int(frame_height * padding_ratio)
    
    # 치수 표시를 위한 추가 공간 (우측에 여백 추가)
    dimension_space = 80 if show_dimensions else 0
    canvas_width = frame_width + (padding_x * 2) + dimension_space
    canvas_height = frame_height + (padding_y * 2)
    
    # 6. 흰색 배경 캔버스 생성
    canvas = Image.new('RGB', (canvas_width, canvas_height), color=background_color)
    canvas_np = cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)
    
    # 7. 펴진 건물 배경을 캔버스에 배치
    frame_x = padding_x
    frame_y = padding_y
    canvas_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = warped_building_resized
    
    # 8. 회색 프레임 그리기 (사각형)
    line_thickness = max(2, min(5, int(min(frame_width, frame_height) * 0.005)))
    cv2.rectangle(
        canvas_np,
        (frame_x, frame_y),
        (frame_x + frame_width, frame_y + frame_height),
        frame_line_color,
        line_thickness
    )
    
    # 9. 간판 이미지를 펴진 배경 위에 합성 (알파 블렌딩)
    signboard_resized = cv2.resize(signboard_image, (frame_width, frame_height))
    
    # 간판 이미지가 검은색 배경(투명 처리된 부분)인 경우 마스크 생성
    # 검은색 부분은 건물 배경을 보여주고, 나머지는 간판을 보여줌
    signboard_gray = cv2.cvtColor(signboard_resized, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(signboard_gray, 10, 255, cv2.THRESH_BINARY)  # 검은색(0~10)은 배경, 나머지는 간판
    mask = mask.astype(np.float32) / 255.0
    mask = np.stack([mask, mask, mask], axis=2)
    
    # 알파 블렌딩: 간판이 있는 부분은 간판, 없는 부분은 건물 배경
    canvas_region = canvas_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width]
    blended = (signboard_resized * mask + canvas_region * (1 - mask)).astype(np.uint8)
    canvas_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = blended
    
    # 10. 치수 표시 (우측에)
    if show_dimensions:
        font_scale = 0.6
        font_thickness = 2
        font_color = (100, 100, 100)  # 어두운 회색
        
        # 높이 표시 (h450 형식)
        height_mm = int(region_height * 0.264583)  # 대략적인 변환
        dimension_text = f"h{height_mm}"
        
        # 텍스트 위치 (프레임 우측 상단)
        text_x = frame_x + frame_width + 10
        text_y = frame_y + 30
        
        cv2.putText(
            canvas_np,
            dimension_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            font_color,
            font_thickness,
            cv2.LINE_AA
        )
    
    return canvas_np

def apply_night_glow_to_signboard(
    signboard_img: np.ndarray,  # 간판 이미지 (BGR)
    text_layer: np.ndarray = None,  # 텍스트 레이어 (RGBA)
    sign_type: str = "",  # 간판 종류
    target_width: int = None,  # 목표 너비 (리사이즈용)
    target_height: int = None,  # 목표 높이 (리사이즈용)
) -> np.ndarray:
    """
    간판 이미지에 야간 발광 효과를 적용하는 함수
    Phase 1의 render_combined_signboard에서 사용하는 발광 로직을 재사용
    (Phase 1 코드: 1407-1498줄 참고)
    
    TODO: 나중에 Phase 1의 render_combined_signboard에서도 이 함수를 호출하도록 통합 필요
    """
    if sign_type not in ["전광채널", "후광채널", "전후광채널"]:
        return signboard_img
    
    # 목표 크기가 지정되면 리사이즈
    if target_width and target_height:
        signboard_resized = cv2.resize(signboard_img, (target_width, target_height))
    else:
        signboard_resized = signboard_img.copy()
        target_width = signboard_img.shape[1]
        target_height = signboard_img.shape[0]
    
    image_area = target_width * target_height
    
    if text_layer is not None:
        # text_layer를 간판 크기에 맞게 리사이즈
        text_layer_resized = cv2.resize(text_layer, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
        
        if len(text_layer_resized.shape) == 3 and text_layer_resized.shape[2] == 4:
            # RGBA -> BGR 변환
            text_layer_bgr = cv2.cvtColor(text_layer_resized[:, :, :3], cv2.COLOR_RGB2BGR)
            text_mask = text_layer_resized[:, :, 3].astype(np.float32) / 255.0  # (H, W)
            
            if sign_type == "전광채널":
                # 전광: 텍스트 앞에서 빛남
                text_glow = safe_gaussian_blur(text_layer_bgr, (25, 25), 10)
                signboard_resized = cv2.addWeighted(signboard_resized, 1.0, text_glow, 0.8, 0)
                
            elif sign_type == "후광채널":
                # 후광: Phase 1의 1407-1459줄 로직 그대로 재사용
                # ============ 이미지 크기 기반 동적 후광 조정 ============
                if image_area <= 300000:  # 약 548x548 이하
                    blur_size1, blur_size2, blur_size3 = (31, 31), (31, 31), (21, 21)
                    sigma1, sigma2, sigma3 = 15, 15, 10
                    intensity = 1.8
                else:
                    blur_size1, blur_size2, blur_size3 = (141, 141), (141, 141), (121, 121)
                    sigma1, sigma2, sigma3 = 70, 70, 60
                    intensity = 4.0
                
                # 동적 blur 적용
                backlight = safe_gaussian_blur(text_mask, blur_size1, sigma1)
                backlight = safe_gaussian_blur(backlight, blur_size2, sigma2)
                backlight = safe_gaussian_blur(backlight, blur_size3, sigma3)
                
                # 후광 색상: 기본 따뜻한 흰색 LED (Phase 1과 동일)
                glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)  # BGR
                backlight_3d = backlight[:, :, np.newaxis]  # (H, W, 1)
                backlight_glow = (backlight_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * intensity).clip(0, 255).astype(np.float32)
                
                # 크기 확인 및 리사이즈
                if signboard_resized.shape[:2] != backlight_glow.shape[:2]:
                    backlight_glow = cv2.resize(backlight_glow, (signboard_resized.shape[1], signboard_resized.shape[0]), interpolation=cv2.INTER_AREA)
                if signboard_resized.shape[:2] != text_mask.shape[:2]:
                    text_mask = cv2.resize(text_mask, (signboard_resized.shape[1], signboard_resized.shape[0]), interpolation=cv2.INTER_AREA)
                
                # 글자 영역 제외하고 후광만 적용 (Phase 1과 동일)
                text_mask_3ch = np.stack([text_mask, text_mask, text_mask], axis=2)
                backlight_only = backlight_glow * (1 - text_mask_3ch)
                signboard_resized = signboard_resized.astype(np.float32) + backlight_only
                signboard_resized = np.clip(signboard_resized, 0, 255).astype(np.uint8)
                
            elif sign_type == "전후광채널":
                # 전후광: 후광 + 전광
                # 1) 후광 효과 먼저 적용 (후광채널과 동일)
                if image_area <= 300000:
                    blur_size1, blur_size2, blur_size3 = (31, 31), (31, 31), (21, 21)
                    sigma1, sigma2, sigma3 = 15, 15, 10
                    intensity = 1.8
                else:
                    blur_size1, blur_size2, blur_size3 = (141, 141), (141, 141), (121, 121)
                    sigma1, sigma2, sigma3 = 70, 70, 60
                    intensity = 4.0
                
                backlight = safe_gaussian_blur(text_mask, blur_size1, sigma1)
                backlight = safe_gaussian_blur(backlight, blur_size2, sigma2)
                backlight = safe_gaussian_blur(backlight, blur_size3, sigma3)
                
                glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)
                backlight_3d = backlight[:, :, np.newaxis]
                backlight_glow = (backlight_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * intensity).clip(0, 255).astype(np.float32)
                
                if signboard_resized.shape[:2] != backlight_glow.shape[:2]:
                    backlight_glow = cv2.resize(backlight_glow, (signboard_resized.shape[1], signboard_resized.shape[0]), interpolation=cv2.INTER_AREA)
                if signboard_resized.shape[:2] != text_mask.shape[:2]:
                    text_mask = cv2.resize(text_mask, (signboard_resized.shape[1], signboard_resized.shape[0]), interpolation=cv2.INTER_AREA)
                
                text_mask_3ch = np.stack([text_mask, text_mask, text_mask], axis=2)
                backlight_only = backlight_glow * (1 - text_mask_3ch)
                signboard_resized = signboard_resized.astype(np.float32) + backlight_only
                signboard_resized = np.clip(signboard_resized, 0, 255).astype(np.uint8)
                
                # 2) 전광 효과 추가 적용
                text_glow = safe_gaussian_blur(text_layer_bgr, (25, 25), 10)
                signboard_resized = cv2.addWeighted(signboard_resized, 1.0, text_glow, 0.6, 0)
    else:
        # text_layer가 없으면 간판 이미지에 직접 발광 효과 적용 (기존 로직 유지)
        signboard_gray = cv2.cvtColor(signboard_resized, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(signboard_gray, 30, 255, cv2.THRESH_BINARY)
        
        if sign_type == "전광채널":
            glow = safe_gaussian_blur(signboard_resized, (25, 25), 10)
            signboard_resized = cv2.addWeighted(signboard_resized, 1.0, glow, 0.6, 0)
        elif sign_type == "후광채널":
            backlight = safe_gaussian_blur(mask, (81, 81), 40)
            backlight = safe_gaussian_blur(backlight, (81, 81), 40)
            backlight_bgr = cv2.cvtColor(backlight, cv2.COLOR_GRAY2BGR)
            backlight_bgr = (backlight_bgr.astype(np.float32) * 1.5).clip(0, 255).astype(np.uint8)
            signboard_resized = cv2.add(signboard_resized, backlight_bgr)
        elif sign_type == "전후광채널":
            backlight = safe_gaussian_blur(mask, (81, 81), 40)
            backlight = safe_gaussian_blur(backlight, (81, 81), 40)
            backlight_bgr = cv2.cvtColor(backlight, cv2.COLOR_GRAY2BGR)
            backlight_bgr = (backlight_bgr.astype(np.float32) * 1.5).clip(0, 255).astype(np.uint8)
            signboard_resized = cv2.add(signboard_resized, backlight_bgr)
            
            glow = safe_gaussian_blur(signboard_resized, (25, 25), 10)
            signboard_resized = cv2.addWeighted(signboard_resized, 1.0, glow, 0.6, 0)
    
    return signboard_resized

def generate_dual_flat_design(
    building_photo: np.ndarray,  # 원본 건물 사진 (BGR)
    polygon_points: list,  # 폴리곤 점 리스트 [[x1, y1], [x2, y2], ...]
    signboard_image: np.ndarray,  # 렌더링된 간판 이미지 (BGR)
    text_layer: np.ndarray = None,  # 텍스트 레이어 (RGBA, 선택적)
    frame_line_color: tuple = (180, 180, 180),  # 프레임 선 색상 (BGR)
    background_color: tuple = (255, 255, 255),  # 배경 색상 (RGB)
    padding_ratio: float = 0.1,  # 프레임 주변 여백 비율 (10%)
    show_dimensions: bool = True,  # 치수 표시 여부
    region_width_mm: float = None,  # 실제 영역 너비 (mm, 치수 표시용)
    region_height_mm: float = None,  # 실제 영역 높이 (mm, 치수 표시용)
    region_width_px: int = None,  # 실제 영역 너비 (픽셀)
    region_height_px: int = None,  # 실제 영역 높이 (픽셀)
    night_mode: bool = False,  # 야간 모드 여부
    sign_type: str = "",  # 간판 종류 (발광 효과용)
) -> tuple:
    """
    평면 시안 생성: 두 가지 모드 (design_only, with_context)
    
    Args:
        building_photo: 원본 건물 사진 (BGR)
        polygon_points: 폴리곤 점 리스트
        signboard_image: 렌더링된 간판 이미지 (BGR)
        text_layer: 텍스트 레이어 (RGBA, 선택적, 알파 블렌딩용)
        frame_line_color: 프레임 선 색상 (BGR)
        background_color: 배경 색상 (RGB)
        padding_ratio: 프레임 주변 여백 비율
        show_dimensions: 치수 표시 여부
        region_width_mm: 실제 영역 너비 (mm)
        region_height_mm: 실제 영역 높이 (mm)
        region_width_px: 실제 영역 너비 (픽셀)
        region_height_px: 실제 영역 높이 (픽셀)
        night_mode: 야간 모드 여부 (True면 야간 효과 적용)
        sign_type: 간판 종류 (발광 효과용: "전광채널", "후광채널", "전후광채널")
    
    Returns:
        (design_only_image, with_context_image, dimensions_dict)
        - design_only_image: 흰색 배경 + 간판만 (BGR)
        - with_context_image: 건물 외벽 + 간판 합성 (BGR, 야간 모드면 어두운 배경)
        - dimensions_dict: {"width_mm": int, "height_mm": int, "scale": str}
    """
    # 1. 폴리곤 영역 크기 계산
    if len(polygon_points) == 4:
        # 4점: order_points로 정렬
        ordered = order_points(polygon_points)
        top_width = np.sqrt((ordered[1][0] - ordered[0][0])**2 + (ordered[1][1] - ordered[0][1])**2)
        left_height = np.sqrt((ordered[3][0] - ordered[0][0])**2 + (ordered[3][1] - ordered[0][1])**2)
        calculated_width = top_width
        calculated_height = left_height
    else:
        # n점: 바운딩 박스
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        calculated_width = max(xs) - min(xs)
        calculated_height = max(ys) - min(ys)
    
    # region_width/height_px가 제공되지 않으면 계산된 값 사용
    if region_width_px is None:
        region_width_px = int(calculated_width)
    if region_height_px is None:
        region_height_px = int(calculated_height)
    
    # 최소 크기 보장
    region_width_px = max(300, region_width_px)
    region_height_px = max(100, region_height_px)
    
    # 간판 이미지 크기
    signboard_h, signboard_w = signboard_image.shape[:2]
    
    # 2. Mode B (with_context)용: 영역 확장 (중심 기준 상하좌우 25% 확장)
    # 모든 경우(4점/n점)에 확장 로직 적용
    xs = [p[0] for p in polygon_points]
    ys = [p[1] for p in polygon_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    # 중심점
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    
    # 현재 크기
    bbox_w = max_x - min_x
    bbox_h = max_y - min_y
    
    # 25% 확장 (총 1.5배)
    expanded_w = bbox_w * 1.5
    expanded_h = bbox_h * 1.5
    
    # 확장된 Bounding Box 좌표
    expanded_min_x = center_x - expanded_w / 2
    expanded_max_x = center_x + expanded_w / 2
    expanded_min_y = center_y - expanded_h / 2
    expanded_max_y = center_y + expanded_h / 2
    
    # 이미지 경계 내로 클리핑
    img_h, img_w = building_photo.shape[:2]
    expanded_min_x = max(0, int(expanded_min_x))
    expanded_max_x = min(img_w, int(expanded_max_x))
    expanded_min_y = max(0, int(expanded_min_y))
    expanded_max_y = min(img_h, int(expanded_max_y))
    
    # 확장된 영역 크롭
    expanded_building = building_photo[expanded_min_y:expanded_max_y, expanded_min_x:expanded_max_x].copy()
    expanded_w_px = expanded_max_x - expanded_min_x
    expanded_h_px = expanded_max_y - expanded_min_y
    
    # 확장된 영역을 정면으로 펴기 (Perspective Transform)
    if len(polygon_points) == 4:
        # 원본 폴리곤을 확장된 영역 내 상대 좌표로 변환
        rel_polygon_points = [
            [p[0] - expanded_min_x, p[1] - expanded_min_y]
            for p in polygon_points
        ]
        
        # 상대 좌표로 정렬
        ordered_rel = order_points(rel_polygon_points)
        
        # 목표 사각형 (정면으로 펴진 영역)
        dst_width = int(calculated_width)
        dst_height = int(calculated_height)
        dst_points = np.array([
            [0, 0],
            [dst_width, 0],
            [dst_width, dst_height],
            [0, dst_height]
        ], dtype=np.float32)
        
        # 투영 변환 행렬 계산
        M = cv2.getPerspectiveTransform(ordered_rel.astype(np.float32), dst_points)
        
        # 확장된 건물 배경을 정면으로 펴기
        warped_building = cv2.warpPerspective(
            expanded_building,
            M,
            (dst_width, dst_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)  # 여백은 흰색
        )
    else:
        # 4점이 아닌 경우: 바운딩 박스로 크롭
        if expanded_w_px > 0 and expanded_h_px > 0:
            warped_building = cv2.resize(expanded_building, (region_width_px, region_height_px))
        else:
            warped_building = np.ones((region_height_px, region_width_px, 3), dtype=np.uint8) * 255
    
    # 펴진 건물 배경을 간판 이미지 크기에 맞추기
    warped_building_resized = cv2.resize(warped_building, (signboard_w, signboard_h))
    
    # 야간 모드: 건물 배경 어둡게 처리
    if night_mode:
        warped_building_resized = (warped_building_resized * 0.25).astype(np.uint8)
    
    # 3. 캔버스 크기 결정
    frame_width = signboard_w
    frame_height = signboard_h
    
    padding_x = int(frame_width * padding_ratio)
    padding_y = int(frame_height * padding_ratio)
    
    dimension_space = 150 if show_dimensions else 0
    canvas_width = frame_width + (padding_x * 2) + dimension_space
    canvas_height = frame_height + (padding_y * 2)
    
    # 4. Mode A (design_only): 흰색 배경 + 간판만
    canvas_design = Image.new('RGB', (canvas_width, canvas_height), color=background_color)
    canvas_design_np = cv2.cvtColor(np.array(canvas_design), cv2.COLOR_RGB2BGR)
    
    # 간판 중앙 배치
    frame_x = padding_x
    frame_y = padding_y
    signboard_resized = cv2.resize(signboard_image, (frame_width, frame_height))
    
    # 야간 모드: 간판에 발광 효과 적용 (Phase 1 로직 재사용)
    if night_mode and sign_type in ["전광채널", "후광채널", "전후광채널"]:
        signboard_resized = apply_night_glow_to_signboard(
            signboard_img=signboard_resized,
            text_layer=text_layer,
            sign_type=sign_type,
            target_width=frame_width,
            target_height=frame_height
        )
    
    # 알파 블렌딩 (text_layer가 있으면 사용)
    if text_layer is not None:
        # 야간 모드이고 발광 효과가 적용된 경우: signboard_resized 사용 (발광 효과 유지)
        if night_mode and sign_type in ["전광채널", "후광채널", "전후광채널"]:
            # 발광 효과가 적용된 signboard_resized를 그대로 사용
            signboard_final = signboard_resized
        else:
            # 주간 모드: text_layer 사용
            text_layer_resized = cv2.resize(text_layer, (frame_width, frame_height), interpolation=cv2.INTER_LINEAR)
            alpha = text_layer_resized[:, :, 3:4].astype(np.float32) / 255.0
            alpha_3ch = np.repeat(alpha, 3, axis=2)
            
            text_rgb = text_layer_resized[:, :, :3]
            
            # RGBA -> RGB 변환 (흰색 배경에 합성)
            blended_rgb = (np.ones((frame_height, frame_width, 3), dtype=np.float32) * 255) * (1 - alpha_3ch) + text_rgb * alpha_3ch
            signboard_final = cv2.cvtColor(blended_rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
    else:
        # text_layer가 없으면 간판 이미지 그대로 사용
        signboard_final = signboard_resized
    
    canvas_design_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = signboard_final
    
    # 프레임 그리기
    line_thickness = max(2, min(5, int(min(frame_width, frame_height) * 0.005)))
    cv2.rectangle(
        canvas_design_np,
        (frame_x, frame_y),
        (frame_x + frame_width, frame_y + frame_height),
        frame_line_color,
        line_thickness
    )
    
    # 5. Mode B (with_context): 건물 외벽 + 간판 합성
    canvas_context = Image.new('RGB', (canvas_width, canvas_height), color=background_color)
    canvas_context_np = cv2.cvtColor(np.array(canvas_context), cv2.COLOR_RGB2BGR)
    
    # 펴진 건물 배경 배치
    canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = warped_building_resized
    
    # 프레임 그리기
    cv2.rectangle(
        canvas_context_np,
        (frame_x, frame_y),
        (frame_x + frame_width, frame_y + frame_height),
        frame_line_color,
        line_thickness
    )
    
    # 간판 이미지 합성 (알파 블렌딩)
    if text_layer is not None:
        # 야간 모드이고 발광 효과가 적용된 경우: signboard_resized 사용 (발광 효과 유지)
        if night_mode and sign_type in ["전광채널", "후광채널", "전후광채널"]:
            # 발광 효과가 적용된 signboard_resized를 배경에 합성
            # text_layer의 알파 채널을 마스크로 사용
            text_layer_resized = cv2.resize(text_layer, (frame_width, frame_height), interpolation=cv2.INTER_LINEAR)
            alpha = text_layer_resized[:, :, 3:4].astype(np.float32) / 255.0
            alpha_3ch = np.repeat(alpha, 3, axis=2)
            
            # 배경과 합성 (발광 효과가 적용된 signboard_resized 사용)
            canvas_region = canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width].astype(np.float32)
            blended = canvas_region * (1 - alpha_3ch) + signboard_resized.astype(np.float32) * alpha_3ch
            canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = blended.astype(np.uint8)
        else:
            # 주간 모드: 기존 방식 (text_layer 사용)
            text_layer_resized = cv2.resize(text_layer, (frame_width, frame_height), interpolation=cv2.INTER_LINEAR)
            alpha = text_layer_resized[:, :, 3:4].astype(np.float32) / 255.0
            alpha_3ch = np.repeat(alpha, 3, axis=2)
            
            text_rgb = text_layer_resized[:, :, :3]
            
            # 배경과 합성
            canvas_region = canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width].astype(np.float32)
            canvas_region_rgb = cv2.cvtColor(canvas_region.astype(np.uint8), cv2.COLOR_BGR2RGB)
            
            blended_rgb = canvas_region_rgb * (1 - alpha_3ch) + text_rgb * alpha_3ch
            blended_bgr = cv2.cvtColor(blended_rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
            canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = blended_bgr
    else:
        # text_layer가 없으면 검정 배경 처리 (기존 방식)
        signboard_gray = cv2.cvtColor(signboard_resized, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(signboard_gray, 10, 255, cv2.THRESH_BINARY)
        mask = mask.astype(np.float32) / 255.0
        mask_3ch = np.stack([mask, mask, mask], axis=2)
        
        canvas_region = canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width].astype(np.float32)
        blended = (signboard_resized.astype(np.float32) * mask_3ch + canvas_region * (1 - mask_3ch)).astype(np.uint8)
        canvas_context_np[frame_y:frame_y + frame_height, frame_x:frame_x + frame_width] = blended
    
    # 6. 치수 표시 (두 이미지 모두)
    dimensions_dict = {}
    if show_dimensions:
        # 치수 계산 (mm 단위, region_width_mm/height_mm가 없으면 픽셀 기준 추정)
        if region_width_mm is None:
            # 픽셀을 mm로 변환 (대략 96 DPI 기준: 1px ≈ 0.264583mm)
            region_width_mm = int(region_width_px * 0.264583)
        if region_height_mm is None:
            region_height_mm = int(region_height_px * 0.264583)
        
        # 스케일 계산 (px당 mm) - 올바른 계산
        scale_mm_per_px = region_width_mm / region_width_px if region_width_px > 0 else 0.264583
        if scale_mm_per_px < 0.1:
            scale_text = f"1px = {scale_mm_per_px * 1000:.1f}μm"
        elif scale_mm_per_px < 1:
            scale_text = f"1px = {scale_mm_per_px:.2f}mm"
        else:
            scale_text = f"1px = {scale_mm_per_px:.1f}mm"
        
        dimensions_dict = {
            "width_mm": int(region_width_mm),
            "height_mm": int(region_height_mm),
            "scale": scale_text
        }
        
        # 치수선 색상 및 설정
        dimension_color = (100, 100, 100)  # 어두운 회색 (BGR)
        dimension_thickness = 2
        tip_length = 0.04
        
        # 치수선 오프셋 (프레임 외부)
        dim_offset = 15
        
        # 화살표 좌표 계산
        arrow_y = frame_y - dim_offset  # 상단 가로 치수선
        arrow_x = frame_x + frame_width + dim_offset  # 우측 세로 치수선
        
        # Mode A에 치수선 추가 (양방향 화살표)
        # 상단 가로 치수선
        cv2.arrowedLine(
            canvas_design_np,
            (frame_x, arrow_y),
            (frame_x + frame_width, arrow_y),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        cv2.arrowedLine(
            canvas_design_np,
            (frame_x + frame_width, arrow_y),
            (frame_x, arrow_y),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        
        # 우측 세로 치수선
        cv2.arrowedLine(
            canvas_design_np,
            (arrow_x, frame_y),
            (arrow_x, frame_y + frame_height),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        cv2.arrowedLine(
            canvas_design_np,
            (arrow_x, frame_y + frame_height),
            (arrow_x, frame_y),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        
        # Mode B에 치수선 추가 (양방향 화살표)
        cv2.arrowedLine(
            canvas_context_np,
            (frame_x, arrow_y),
            (frame_x + frame_width, arrow_y),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        cv2.arrowedLine(
            canvas_context_np,
            (frame_x + frame_width, arrow_y),
            (frame_x, arrow_y),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        cv2.arrowedLine(
            canvas_context_np,
            (arrow_x, frame_y),
            (arrow_x, frame_y + frame_height),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        cv2.arrowedLine(
            canvas_context_np,
            (arrow_x, frame_y + frame_height),
            (arrow_x, frame_y),
            dimension_color,
            dimension_thickness,
            tipLength=tip_length
        )
        
        # 한글 폰트 로드 (PIL 사용)
        font_size = 18
        font = get_korean_font(font_size)
        
        # 치수 텍스트
        width_text = f"{int(region_width_mm)}mm"
        height_text = f"{int(region_height_mm)}mm"
        
        # PIL 이미지로 변환
        design_img_pil = Image.fromarray(cv2.cvtColor(canvas_design_np, cv2.COLOR_BGR2RGB))
        context_img_pil = Image.fromarray(cv2.cvtColor(canvas_context_np, cv2.COLOR_BGR2RGB))
        
        draw_design = ImageDraw.Draw(design_img_pil)
        draw_context = ImageDraw.Draw(context_img_pil)
        
        # 텍스트 위치 (화살표 중간/위)
        width_text_x = frame_x + frame_width // 2
        width_text_y = arrow_y - 25
        
        height_text_x = arrow_x + 10
        height_text_y = frame_y + frame_height // 2
        
        # Halo 효과와 함께 텍스트 그리기
        def draw_text_with_halo(draw, x, y, text, font, fill_color=(100, 100, 100), halo_color=(255, 255, 255)):
            """Halo 효과가 있는 텍스트 그리기"""
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, fill=halo_color, font=font)
            draw.text((x, y), text, fill=fill_color, font=font)
        
        # Mode A에 치수 텍스트 표시
        draw_text_with_halo(draw_design, width_text_x, width_text_y, width_text, font, (100, 100, 100), (255, 255, 255))
        draw_text_with_halo(draw_design, height_text_x, height_text_y, height_text, font, (100, 100, 100), (255, 255, 255))
        
        # Mode B에 치수 텍스트 표시 (Halo 효과로 가독성 향상)
        draw_text_with_halo(draw_context, width_text_x, width_text_y, width_text, font, (255, 255, 255), (0, 0, 0))
        draw_text_with_halo(draw_context, height_text_x, height_text_y, height_text, font, (255, 255, 255), (0, 0, 0))
        
        # BGR로 다시 변환
        canvas_design_np = cv2.cvtColor(np.array(design_img_pil), cv2.COLOR_RGB2BGR)
        canvas_context_np = cv2.cvtColor(np.array(context_img_pil), cv2.COLOR_RGB2BGR)
    else:
        dimensions_dict = {
            "width_mm": int(region_width_mm) if region_width_mm else int(region_width_px * 0.264583),
            "height_mm": int(region_height_mm) if region_height_mm else int(region_height_px * 0.264583),
            "scale": "N/A"
        }
    
    return canvas_design_np, canvas_context_np, dimensions_dict

def composite_signboard(
    building_photo: np.ndarray,
    signboard_image: np.ndarray,
    polygon_points: list,
    sign_type: str = "",
    text_layer: np.ndarray = None,
    lights: list = None,
    lights_enabled: bool = True,
    # 멀티 간판용: 이미 어둡게 처리된 야간 이미지를 다시 어둡게 하지 않도록 제어
    building_photo_night: np.ndarray = None,
    pre_darkened: bool = False,
    installation_type: str = "맨벽",  # 추가: 전면프레임에서 transparency_mask 제외하기 위해
) -> tuple:
    """이미지 합성 - 주간/야간 버전 생성 (폴리곤 지원)
    text_layer: 전광채널의 경우 텍스트만 분리된 레이어 (None이면 전체 간판 사용)
    """
    # 전면프레임-전후광채널 디버그: 실제 들어온 값 확인
    debug_logger.info(f"[composite_signboard 진입] installation_type='{installation_type}', sign_type='{sign_type}', installation_type==전면프레임={installation_type == '전면프레임'}, sign_type==전후광채널={sign_type == '전후광채널'}")
    h, w = building_photo.shape[:2]
    sh, sw = signboard_image.shape[:2]
    
    # 폴리곤 점을 numpy 배열로 변환
    src_points = np.array(polygon_points, dtype=np.float32)
    
    # 폴리곤이 정확히 4점이면 원근 변환 사용, 아니면 바운딩 박스 + 마스크
    M = None  # M 변수를 미리 정의
    if len(polygon_points) == 4:
        # 점들을 올바른 순서로 정렬 (좌상, 우상, 우하, 좌하)
        src_points = order_points(polygon_points)
        # 4점: 기존 원근 변환 방식
        dst_points = np.array([
            [0, 0],
            [sw, 0],
            [sw, sh],
            [0, sh]
        ], dtype=np.float32)
        
        M = cv2.getPerspectiveTransform(dst_points, src_points)
        warped_sign = cv2.warpPerspective(signboard_image, M, (w, h))
        print(f"[DEBUG] composite_signboard: 원근 변환 후 warped_sign.shape={warped_sign.shape}, min()={warped_sign.min()}, max()={warped_sign.max()}, sum()={warped_sign.sum()}")
        
        if text_layer is not None:
            warped_text_full = cv2.warpPerspective(text_layer, M, (w, h))
        else:
            warped_text_full = None
    else:
        # n점 (n != 4): 바운딩 박스에 간판을 배치하고 폴리곤 마스크 적용
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        bbox_w = max_x - min_x
        bbox_h = max_y - min_y
        
        # 간판을 바운딩 박스 크기에 맞춰 리사이즈
        if bbox_w > 0 and bbox_h > 0:
            resized_sign = cv2.resize(signboard_image, (bbox_w, bbox_h))
            if text_layer is not None:
                resized_text = cv2.resize(text_layer, (bbox_w, bbox_h))
            else:
                resized_text = None
        else:
            resized_sign = signboard_image
            resized_text = text_layer
        
        # 건물 사진 크기의 빈 이미지에 배치
        warped_sign = np.zeros((h, w, 3), dtype=np.uint8)
        if resized_sign is not None and resized_sign.size > 0:
            if min_y + bbox_h <= h and min_x + bbox_w <= w:
                warped_sign[min_y:min_y+bbox_h, min_x:min_x+bbox_w] = resized_sign
            else:
                print(f"[ERROR] composite_signboard: bbox 범위 초과: min_y={min_y}, bbox_h={bbox_h}, h={h}, min_x={min_x}, bbox_w={bbox_w}, w={w}")
        else:
            print(f"[ERROR] composite_signboard: resized_sign이 비어있음: resized_sign={resized_sign}")
        
        if resized_text is not None:
            warped_text_full = np.zeros((h, w, 3), dtype=np.uint8)
            warped_text_full[min_y:min_y+bbox_h, min_x:min_x+bbox_w] = resized_text
        else:
            warped_text_full = None
    
    # 폴리곤 마스크 생성
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [src_points.astype(np.int32)], 255)
    mask = safe_gaussian_blur(mask, (5, 5), 0)
    mask = mask.astype(np.float32) / 255.0
    mask = np.stack([mask, mask, mask], axis=2)
    print(f"[DEBUG] composite_signboard: mask 생성 후 min()={mask.min()}, max()={mask.max()}, sum()={mask.sum()}")
    
    # 주간 버전: 자연스러운 블렌딩
    # 검은색 부분은 건물 사진을 투과 (프레임바/맨벽 등 투명 배경 처리)
    # 전면프레임은 배경이 있을 수 있으므로 transparency_mask 적용 안 함
    if installation_type == "전면프레임":
        # 전면프레임: 배경이 있으므로 투명도 마스크 사용 안 함 (전체 간판 영역 사용)
        # 하지만 전후광채널 처리에서 transparency_mask를 사용하므로, 전면프레임일 때도 생성 (전체 마스크)
        sys.stdout.write(f"[composite_signboard] 전면프레임 감지 - transparency_mask 전체 영역으로 설정\n")
        sys.stdout.flush()
        print(f"[composite_signboard] 전면프레임 감지 - transparency_mask 전체 영역으로 설정", flush=True)
        transparency_mask = np.ones((h, w, 3), dtype=np.float32)  # 전면프레임은 전체 영역 사용
        combined_mask = mask
    else:
        # 프레임바/맨벽: 검은색 마스크 생성 (밝기 임계값) - 투명 배경 처리
        gray_sign = cv2.cvtColor(warped_sign, cv2.COLOR_BGR2GRAY)
        brightness_threshold = 30  # 밝기 30 이하는 투명으로 처리
        transparency_mask = (gray_sign > brightness_threshold).astype(np.float32)
        transparency_mask = np.stack([transparency_mask, transparency_mask, transparency_mask], axis=2)
        
        # 폴리곤 마스크와 투명도 마스크를 결합
        combined_mask = mask * transparency_mask
    
    day_result = building_photo.copy().astype(np.float32)
    # warped_sign과 combined_mask가 제대로 생성되었는지 확인
    if warped_sign is None or warped_sign.size == 0:
        print(f"[ERROR] composite_signboard: warped_sign이 비어있음: warped_sign={warped_sign}")
        warped_sign = np.zeros((h, w, 3), dtype=np.uint8)
    if combined_mask is None or combined_mask.size == 0:
        print(f"[ERROR] composite_signboard: combined_mask가 비어있음: combined_mask={combined_mask}")
        combined_mask = mask
    print(f"[DEBUG] composite_signboard: building_photo.shape={building_photo.shape}, warped_sign.shape={warped_sign.shape}, combined_mask.shape={combined_mask.shape}")
    print(f"[DEBUG] composite_signboard: warped_sign.min()={warped_sign.min()}, warped_sign.max()={warped_sign.max()}, warped_sign.sum()={warped_sign.sum()}")
    print(f"[DEBUG] composite_signboard: combined_mask.min()={combined_mask.min()}, combined_mask.max()={combined_mask.max()}, combined_mask.sum()={combined_mask.sum()}")
    day_result = day_result * (1 - combined_mask) + warped_sign.astype(np.float32) * combined_mask
    day_result = day_result.astype(np.uint8)
    print(f"[DEBUG] composite_signboard: day_result.shape={day_result.shape}, day_result.min()={day_result.min()}, day_result.max()={day_result.max()}")
    # day_result에서 warped_sign 영역 확인
    if combined_mask.sum() > 0:
        mask_area = day_result[combined_mask[:,:,0] > 0.5]
        if mask_area.size > 0:
            print(f"[DEBUG] composite_signboard: mask 영역 day_result.min()={mask_area.min()}, max()={mask_area.max()}, mean()={mask_area.mean()}")
        # warped_sign의 mask 영역도 확인
        warped_mask_area = warped_sign[combined_mask[:,:,0] > 0.5]
        if warped_mask_area.size > 0:
            print(f"[DEBUG] composite_signboard: mask 영역 warped_sign.min()={warped_mask_area.min()}, max()={warped_mask_area.max()}, mean()={warped_mask_area.mean()}")
        # building_photo의 mask 영역도 확인
        building_mask_area = building_photo[combined_mask[:,:,0] > 0.5]
        if building_mask_area.size > 0:
            print(f"[DEBUG] composite_signboard: mask 영역 building_photo.min()={building_mask_area.min()}, max()={building_mask_area.max()}, mean()={building_mask_area.mean()}")
    
    # 야간 버전: 배경 어둡게
    # building_photo_night가 주어지면 그걸 기준으로 사용 (멀티 간판에서 이미 어둡게 된 야간 이미지)
    night_src = building_photo_night if building_photo_night is not None else building_photo
    if pre_darkened:
        # 이미 한 번 어둡게 처리된 야간 이미지 위에 추가 합성
        night_base = night_src.copy().astype(np.float32)
    else:
        night_base = night_src.copy().astype(np.float32) * 0.25  # 전체 배경 어둡게
    
    # 검은색 부분 투명도 처리 (야간에도 적용)
    # gray_sign과 transparency_mask는 이미 위에서 계산됨
    
    # 전광/전후광 채널 전용 야간 합성
    # (후광채널은 아래 일반 분기에서 별도로 처리)
    if sign_type in ["전광채널", "전후광채널"]:
        night_result = None
        night_front = None
        night_back = None

        # ---- 1) 텍스트 방식 (text_layer가 있는 경우) ----
        if text_layer is not None:
            # 텍스트/배경 분리
            bg_layer = signboard_image.copy()

            # text_layer 크기가 signboard_image와 다를 수 있으므로 리사이즈
            if text_layer.shape[:2] != signboard_image.shape[:2]:
                text_layer_resized = cv2.resize(text_layer, (signboard_image.shape[1], signboard_image.shape[0]))
            else:
                text_layer_resized = text_layer

            # 텍스트 마스크 생성 (전광/후광/전후광 공통)
            text_mask = (text_layer_resized.sum(axis=2) > 0).astype(np.float32)
            text_mask_3 = np.stack([text_mask, text_mask, text_mask], axis=2)

            # 배경만 추출 (텍스트 제외)
            bg_only = bg_layer * (1 - text_mask_3)

            # 배경/텍스트를 각각 건물 사진 크기로 변환
            if len(polygon_points) == 4 and M is not None:
                warped_bg = cv2.warpPerspective(bg_only, M, (w, h))
                warped_text = cv2.warpPerspective(text_layer_resized, M, (w, h))
                text_mask_warped = cv2.warpPerspective(text_mask_3, M, (w, h))
            else:
                warped_bg = np.zeros((h, w, 3), dtype=np.float32)
                if bbox_w > 0 and bbox_h > 0:
                    resized_bg = cv2.resize(bg_only, (bbox_w, bbox_h))
                    warped_bg[min_y:min_y+bbox_h, min_x:min_x+bbox_w] = resized_bg

                warped_text = warped_text_full if warped_text_full is not None else np.zeros((h, w, 3), dtype=np.uint8)
                text_mask_warped = (warped_text.sum(axis=2) > 0).astype(np.float32)
                text_mask_warped = np.stack([text_mask_warped, text_mask_warped, text_mask_warped], axis=2)

            # ----- 전광/전후광용 night_front 계산 -----
            warped_bg_dark = warped_bg.astype(np.float32) * 0.25
            base_night_front = night_base * (1 - combined_mask) + warped_bg_dark * combined_mask
            
            # 전광채널과 전후광채널은 다르게 처리
            if sign_type == "전광채널":
                # 전광채널: night_front는 배경만 (텍스트 제외)
                # 텍스트는 나중에 앞면만 별도로 추가
                night_front = base_night_front
            else:
                # 전후광채널: 텍스트 포함
                text_contrib = warped_text.astype(np.float32) * text_mask_warped * transparency_mask
                night_front = np.maximum(base_night_front, text_contrib)

            # ----- 후광용 night_back 계산 -----
            if sign_type in ["후광채널", "전후광채널"]:
                # text_mask_warped가 제대로 생성되었는지 확인
                if text_mask_warped is not None and text_mask_warped.size > 0:
                    # 1채널 마스크 (텍스트 영역만 1)
                    # text_mask_warped가 3채널이면 첫 번째 채널 사용, 아니면 그대로 사용
                    if len(text_mask_warped.shape) == 3 and text_mask_warped.shape[2] == 3:
                        text_mask_1ch = text_mask_warped[:, :, 0].astype(np.float32)
                    elif len(text_mask_warped.shape) == 2:
                        text_mask_1ch = text_mask_warped.astype(np.float32)
                    else:
                        # 예외 처리: text_mask_warped 형식이 다를 경우
                        text_mask_1ch = np.zeros((h, w), dtype=np.float32)
                else:
                    # text_mask_warped가 없으면 night_back 생성 안 함
                    text_mask_1ch = None
                
                if text_mask_1ch is not None:
                    # 텍스트 마스크를 uint8로 변환
                    text_mask_uint8 = (text_mask_1ch * 255).astype(np.uint8)
                    
                    # Distance Transform: 글자 바깥쪽에서의 거리 계산
                    text_mask_inv = 255 - text_mask_uint8
                    dist_transform = cv2.distanceTransform(text_mask_inv, cv2.DIST_L2, 5)
                    
                    # 글자 윤곽선 주변에 glow 적용
                    # 제일 밝은 부분(0-2px)은 줄이고, 그라디언트 범위(2-15px)는 넓히기
                    max_dist = 15.0
                    inner_dist = 2.0
                    
                    glow_mask = np.zeros_like(dist_transform, dtype=np.float32)
                    bright_mask = (dist_transform > 0) & (dist_transform <= inner_dist)
                    glow_mask[bright_mask] = 0.6 * (1.0 - (dist_transform[bright_mask] / inner_dist))
                    
                    gradient_mask = (dist_transform > inner_dist) & (dist_transform <= max_dist)
                    if gradient_mask.any():
                        glow_mask[gradient_mask] = 0.6 * (1.0 - ((dist_transform[gradient_mask] - inner_dist) / (max_dist - inner_dist)))
                    
                    glow_mask[text_mask_1ch > 0.5] = 0
                    
                    # 부드러운 blur 적용 (더 타이트하게)
                    glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                    glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                    
                    # 따뜻한 흰색 LED 색상 적용
                    glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)
                    glow_mask_3d = glow_mask[:, :, np.newaxis]
                    backlight_glow = (glow_mask_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * 3.5).clip(0, 255).astype(np.float32)

                    base_night_back = night_base * (1 - combined_mask)
                    signboard_dark = warped_sign.astype(np.float32) * combined_mask * 0.25 if warped_sign is not None else base_night_back
                    night_back = base_night_back + signboard_dark + backlight_glow
                else:
                    # text_mask_warped가 없으면 night_back 생성 안 함 (None 유지)
                    night_back = None

            # ----- 최종 분기 -----
            if sign_type == "전광채널":
                # 전광채널 야간: 주간 결과에 야간 효과만 적용. 주간 결과 이미지에서 앞면 부분만 야간 효과 제거
                # 모든 설치방식(맨벽, 프레임바, 프레임판)에 동일하게 적용
                
                # 1) 주간 결과 전체를 어둡게 만듦
                warped_sign_dark = warped_sign.astype(np.float32) * 0.25
                night_result_base = night_base.astype(np.float32) * (1 - combined_mask) + warped_sign_dark * combined_mask
                
                # 2) 주간 결과에서 앞면 부분만 추출 - warped_text_full의 마스크 사용 (정확한 텍스트 앞면 영역)
                # warped_text_full은 text_layer를 warped한 것으로, 앞면만 포함하므로 정확함
                if warped_text_full is not None:
                    front_mask_full = (warped_text_full.sum(axis=2) > 0).astype(np.float32)
                    front_mask_3ch = np.stack([front_mask_full, front_mask_full, front_mask_full], axis=2)
                else:
                    # warped_text_full이 없으면 text_mask_warped 사용
                    front_mask_3ch = text_mask_warped.astype(np.float32)
                
                # 주간 결과에서 앞면 부분만 추출 (주간 결과 이미지 그대로 사용)
                day_front_from_sign = warped_sign.astype(np.float32) * front_mask_3ch
                
                # 앞면 부분만 주간 색상으로 복원 (나머지는 어두운 야간 색상 유지)
                night_result = night_result_base * (1 - front_mask_3ch) + day_front_from_sign

            elif sign_type == "후광채널":
                # 후광채널: 기존 night_back 로직 그대로 사용
                if night_back is not None:
                    night_result = night_back

            elif sign_type == "전후광채널":
                # 전후광채널: 후광 효과 + 글자 윗면만 주간 색상으로 복원
                if night_back is not None:
                    # 1) 후광 효과를 기본으로 사용 (night_back)
                    night_result = night_back.astype(np.float32)
                    
                    # 2) 글자 윗면(앞면) 부분만 주간 색상으로 복원 (전광 효과)
                    if warped_text_full is not None:
                        # warped_text_full은 text_layer를 warped한 것으로, 앞면만 포함
                        front_mask_full = (warped_text_full.sum(axis=2) > 0).astype(np.float32)
                        front_mask_3ch = np.stack([front_mask_full, front_mask_full, front_mask_full], axis=2)
                    elif text_mask_warped is not None and len(text_mask_warped.shape) >= 2:
                        # text_mask_warped가 3채널이면 그대로, 1채널이면 3채널로 변환
                        if len(text_mask_warped.shape) == 2:
                            front_mask_3ch = np.stack([text_mask_warped, text_mask_warped, text_mask_warped], axis=2)
                        else:
                            front_mask_3ch = text_mask_warped.astype(np.float32)
                    else:
                        # text_mask_warped도 없으면 기본 마스크 생성
                        front_mask_3ch = combined_mask.astype(np.float32)
                    
                    # 주간 결과에서 앞면 부분만 추출
                    if warped_sign is not None:
                        day_front_from_sign = warped_sign.astype(np.float32) * front_mask_3ch
                        # 앞면 부분만 주간 색상으로 복원 (나머지는 후광 효과 유지)
                        night_result = night_result * (1 - front_mask_3ch) + day_front_from_sign
                else:
                    # night_back이 None인 경우: text_layer가 없거나 text_mask_warped가 없는 경우
                    # 기본 야간 처리 후 이미지 업로드 방식으로 넘어감
                    pass  # night_result는 None으로 유지하여 이미지 업로드 방식으로 처리

        # ---- 2) 텍스트 레이어가 없을 때 (이미지 업로드 방식) ----
        if night_result is None:
            # 이미지 업로드 방식: 기존 로직 유지 (전/후/전후 광)
            base_night = night_base * (1 - combined_mask)
            image_contrib = warped_sign.astype(np.float32) * combined_mask

            if sign_type == "전후광채널":
                # 로고 마스크 생성 (밝은 부분 감지)
                gray_sign = cv2.cvtColor(warped_sign, cv2.COLOR_BGR2GRAY)
                logo_mask = (gray_sign > 10).astype(np.float32)

                logo_mask_1ch = logo_mask
                # 로고 마스크를 distance transform으로 처리 (글자 윤곽선 따라)
                logo_mask_uint8 = (logo_mask_1ch * 255).astype(np.uint8)
                # 로고 바깥쪽에서의 거리 계산
                logo_mask_inv = 255 - logo_mask_uint8
                dist_transform = cv2.distanceTransform(logo_mask_inv, cv2.DIST_L2, 5)
                
                # 로고 윤곽선 주변에 glow 적용
                # 제일 밝은 부분(0-2px)은 줄이고, 그라디언트 범위(2-15px)는 넓히기
                max_dist = 15.0
                inner_dist = 2.0
                
                glow_mask = np.zeros_like(dist_transform, dtype=np.float32)
                bright_mask = (dist_transform > 0) & (dist_transform <= inner_dist)
                glow_mask[bright_mask] = 0.6 * (1.0 - (dist_transform[bright_mask] / inner_dist))
                
                gradient_mask = (dist_transform > inner_dist) & (dist_transform <= max_dist)
                if gradient_mask.any():
                    glow_mask[gradient_mask] = 0.6 * (1.0 - ((dist_transform[gradient_mask] - inner_dist) / (max_dist - inner_dist)))
                
                glow_mask[logo_mask_1ch > 0.5] = 0
                
                # 부드러운 blur 적용 (더 타이트하게)
                glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                
                # 따뜻한 흰색 LED 색상 적용
                glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)
                glow_mask_3d = glow_mask[:, :, np.newaxis]
                backlight_glow = (glow_mask_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * 3.5).clip(0, 255).astype(np.float32)

                # 후광 효과 적용
                logo_mask_3ch = np.stack([logo_mask, logo_mask, logo_mask], axis=2)
                signboard_dark = warped_sign.astype(np.float32) * combined_mask * 0.25
                backlight_glow_masked = backlight_glow * (1 - logo_mask_3ch)
                night_with_backlight = base_night + signboard_dark + backlight_glow_masked
                
                # 로고 영역에서 야간 효과를 80% 제거 (주간 밝기로 80% 복원) - 전광 효과
                day_logo = warped_sign.astype(np.float32) * logo_mask_3ch
                logo_restore_mask = logo_mask_3ch * 0.8  # 80% 복원
                
                # 후광 효과 + 로고 영역 전광 효과 합성
                night_result = night_with_backlight * (1 - logo_restore_mask) + day_logo * logo_restore_mask
            else:
                night_result = base_night + image_contrib

        night_result = np.clip(night_result, 0, 255).astype(np.uint8)

    else:
        # 다른 간판 종류: 전체 간판에 발광 강도 적용
        if sign_type == "후광채널":
            # 후광채널: 글자 뒤에서만 빛나는 효과
            # 글자는 어두운 실루엣, 뒤쪽만 밝게 (진짜 후광 느낌)
            if text_layer is not None and warped_text_full is not None:
                # warped_text_full은 이미 건물 사진 크기로 변환된 텍스트 레이어
                # 텍스트 마스크 생성 (건물 사진 크기에서)
                text_mask_warped = (warped_text_full.sum(axis=2) > 0).astype(np.float32)
                
                # 글자 뒤에서 빛나는 효과 - 글자 윤곽선을 따라 정확하게 빛나도록
                # 1) 텍스트 마스크를 uint8로 변환
                text_mask_uint8 = (text_mask_warped * 255).astype(np.uint8)
                
                # 2) Distance Transform: 글자에서의 거리 계산 (글자 바깥쪽만)
                # 글자 마스크를 invert해서 글자 바깥쪽에서의 거리 계산
                text_mask_inv = 255 - text_mask_uint8
                dist_transform = cv2.distanceTransform(text_mask_inv, cv2.DIST_L2, 5)
                
                # 3) 글자 윤곽선 주변에 glow 적용
                # 제일 밝은 부분(0-2px)은 줄이고, 그라디언트 범위(2-15px)는 넓히기
                max_dist = 15.0  # 그라디언트 범위 확장
                inner_dist = 2.0  # 제일 밝은 부분 범위
                
                glow_mask = np.zeros_like(dist_transform, dtype=np.float32)
                # 제일 밝은 부분(0-2px): 밝기 제한 (0.6 정도)
                bright_mask = (dist_transform > 0) & (dist_transform <= inner_dist)
                glow_mask[bright_mask] = 0.6 * (1.0 - (dist_transform[bright_mask] / inner_dist))
                
                # 그라디언트 부분(2-15px): 점진적으로 옅어짐
                gradient_mask = (dist_transform > inner_dist) & (dist_transform <= max_dist)
                if gradient_mask.any():
                    # 2px에서 0.6, 15px에서 0.0으로 선형 감소
                    glow_mask[gradient_mask] = 0.6 * (1.0 - ((dist_transform[gradient_mask] - inner_dist) / (max_dist - inner_dist)))
                
                # 글자 내부는 제외 (원본 마스크가 1인 곳은 0으로)
                glow_mask[text_mask_warped > 0.5] = 0
                
                # 4) 부드러운 blur 적용 (윤곽선 따라 자연스럽게, 더 타이트하게)
                glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)  # 두 번째 blur
                
                # 5) 따뜻한 흰색 LED 색상 적용
                glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)
                glow_mask_3d = glow_mask[:, :, np.newaxis]
                backlight_glow = (glow_mask_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * 3.5).clip(0, 255).astype(np.float32)
                
                # 배경은 어둡게, 글자 뒤에서만 빛나는 효과 추가
                base_night = night_base * (1 - combined_mask)
                signboard_dark = warped_sign.astype(np.float32) * combined_mask * 0.25

                # 기본 야간 이미지 (배경 + 후광)
                night_with_backlight = base_night + signboard_dark + backlight_glow

                # 글자 영역을 어두운 실루엣으로 (주간 밝기의 20% 정도)
                text_dark = warped_sign.astype(np.float32) * combined_mask * 0.2
                text_mask_3ch = np.stack([text_mask_warped, text_mask_warped, text_mask_warped], axis=2)
                bg_mask_3ch = 1.0 - text_mask_3ch

                night_result = night_with_backlight * bg_mask_3ch + text_dark * text_mask_3ch
                night_result = np.clip(night_result, 0, 255).astype(np.uint8)
            else:
                # 이미지 업로드 방식: 로고 윤곽을 따라 후광 효과 적용
                # 투명 처리된 이미지의 경우 검은색(0,0,0)이 아닌 부분이 로고 영역
                # 로고 마스크 생성 (밝은 부분 감지)
                gray_sign = cv2.cvtColor(warped_sign, cv2.COLOR_BGR2GRAY)
                # 검은색이 아닌 부분을 로고로 간주 (밝기 10 이상)
                logo_mask = (gray_sign > 10).astype(np.float32)
                
                # 로고 마스크를 distance transform으로 처리해서 후광 효과 생성 (글자 윤곽선 따라)
                logo_mask_uint8 = (logo_mask * 255).astype(np.uint8)
                # 로고 바깥쪽에서의 거리 계산
                logo_mask_inv = 255 - logo_mask_uint8
                dist_transform = cv2.distanceTransform(logo_mask_inv, cv2.DIST_L2, 5)
                
                # 로고 윤곽선 주변에 glow 적용
                # 제일 밝은 부분(0-2px)은 줄이고, 그라디언트 범위(2-15px)는 넓히기
                max_dist = 15.0
                inner_dist = 2.0
                
                glow_mask = np.zeros_like(dist_transform, dtype=np.float32)
                bright_mask = (dist_transform > 0) & (dist_transform <= inner_dist)
                glow_mask[bright_mask] = 0.6 * (1.0 - (dist_transform[bright_mask] / inner_dist))
                
                gradient_mask = (dist_transform > inner_dist) & (dist_transform <= max_dist)
                if gradient_mask.any():
                    glow_mask[gradient_mask] = 0.6 * (1.0 - ((dist_transform[gradient_mask] - inner_dist) / (max_dist - inner_dist)))
                
                glow_mask[logo_mask > 0.5] = 0
                
                # 부드러운 blur 적용 (더 타이트하게)
                glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                glow_mask = safe_gaussian_blur(glow_mask, (19, 19), 8)
                
                # 따뜻한 흰색 LED 색상 적용
                glow_color_bgr = np.array([220, 245, 255], dtype=np.float32)
                glow_mask_3d = glow_mask[:, :, np.newaxis]
                backlight_glow = (glow_mask_3d * glow_color_bgr[np.newaxis, np.newaxis, :] * 3.5).clip(0, 255).astype(np.float32)
                
                # 배경은 어둡게, 로고 뒤에서만 빛나는 효과 추가
                base_night = night_base * (1 - combined_mask)
                # 간판 배경은 어둡게
                signboard_dark = warped_sign.astype(np.float32) * combined_mask * 0.25
                
                # 로고 영역에서 야간 효과를 절반 제거 (후광 때문에 로고가 더 밝게 보이도록)
                logo_mask_3ch = np.stack([logo_mask, logo_mask, logo_mask], axis=2)
                # 주간 결과 이미지에서 로고 부분 추출
                day_logo = day_result.astype(np.float32) * logo_mask_3ch
                # 로고 영역에서 야간 효과를 50% 제거 (주간 밝기로 50% 복원)
                logo_restore_mask = logo_mask_3ch * 0.5  # 50%만 복원
                night_with_logo_restore = base_night + signboard_dark + backlight_glow
                # 로고 영역을 50% 주간 밝기로 복원
                night_result = night_with_logo_restore * (1 - logo_restore_mask) + day_logo * logo_restore_mask
                night_result = np.clip(night_result, 0, 255).astype(np.uint8)
        elif sign_type == "플렉스_LED":
            # LED 플렉스: 내부 LED 백라이트로 야간에도 밝게 유지
            # 복잡한 glow 없이 단순하게 원본 밝기 유지
            night_result = night_base * (1 - combined_mask) + warped_sign.astype(np.float32) * combined_mask
            night_result = np.clip(night_result, 0, 255).astype(np.uint8)
            
        elif sign_type in ["플렉스_기본", "플렉스"]:
            # 기본 플렉스: LED 없음 → 비조명 간판처럼 야간에 어두워짐
            glow_intensity = 0.3  # 스카시와 동일하게 어둡게
            night_result = night_base * (1 - combined_mask) + warped_sign.astype(np.float32) * combined_mask * glow_intensity
            night_result = np.clip(night_result, 0, 255).astype(np.uint8)
        elif sign_type == "스카시" or sign_type.startswith("스카시_"):
            # 비조명: 야간에는 전체를 어둡게(배경과 동일 수준)
            glow_intensity = 0.3
            night_result = night_base * (1 - combined_mask) + warped_sign.astype(np.float32) * combined_mask * glow_intensity
        elif sign_type == "시트시공" or installation_type == "유리창시트시공":
            # 시트시공: 비조명 간판이므로 야간에 어두워짐
            glow_intensity = 0.3
            night_result = night_base * (1 - combined_mask) + warped_sign.astype(np.float32) * combined_mask * glow_intensity
        else:
            glow_intensity = 1.8
            night_result = night_base * (1 - combined_mask) + warped_sign.astype(np.float32) * combined_mask * glow_intensity

    # 조명 합성 (간판 표면 집중)
    if lights_enabled and lights:
        print(f"[DEBUG] 조명 처리 시작: {len(lights)}개의 조명")
        # 간판 영역 마스크: 투명도 고려하지 않고 폴리곤 마스크만 사용!
        # combined_mask는 투명한 배경을 제외하므로, 조명 계산에는 전체 폴리곤 사용
        signboard_mask_single = mask[:, :, 0]  # 폴리곤 영역 전체
        
        # 간판의 실제 위치 확인
        signboard_ys, signboard_xs = np.where(signboard_mask_single > 0.5)
        signboard_y_center = h // 2  # 기본값
        if len(signboard_ys) > 0:
            signboard_y_min = signboard_ys.min()
            signboard_y_max = signboard_ys.max()
            signboard_y_center = (signboard_y_min + signboard_y_max) // 2
            print(f"[DEBUG] 간판 Y 위치: min={signboard_y_min}, max={signboard_y_max}, center={signboard_y_center}")
        
        for light in lights:
            print(f"[DEBUG] 조명 처리 중: intensity={light.get('intensity')}, radius={light.get('radius')}")
            
            # 로그 파일에도 저장
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"\n=== 조명 처리 시작 ===\n")
                f.write(f"조명 데이터: {light}\n")
            
            if not light.get("enabled", True):
                continue
            lx = float(light.get("x", 0.5))
            ly = float(light.get("y", 0.5))
            intensity = float(light.get("intensity", 1.0))
            radius = float(light.get("radius", 150))
            temperature = float(light.get("temperature", 0.5))  # 0=warm, 1=cool

            cx = int(lx * w)
            cy = int(ly * h)  # 사용자가 설정한 위치 그대로 사용
            rad = int(radius)
            
            print(f"[DEBUG] 이미지 크기: h={h}, w={w}")
            print(f"[DEBUG] 조명 위치: cx={cx}, cy={cy}, rad={rad}")
            print(f"[DEBUG] signboard_mask_single 범위: min={signboard_mask_single.min():.3f}, max={signboard_mask_single.max():.3f}")
            print(f"[DEBUG] signboard_mask_single에서 0이 아닌 픽셀 수: {np.sum(signboard_mask_single > 0.1)}")

            # 조명 색온도
            warm = np.array([255, 220, 200], dtype=np.float32)
            cool = np.array([200, 210, 255], dtype=np.float32)
            light_color = warm * (1 - temperature) + cool * temperature

            # 조명 마스크 (타원형: 위에서 아래로 비추는 형태)
            # 프론트엔드와 동일하게
            mask_light = np.zeros((h, w), dtype=np.float32)
            light_width = rad * 2.0  # 가로 반경
            light_height = rad * 2.4  # 세로 반경
            
            # 파일에 로그 저장 (light_width 정의 후)
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"이미지 크기: h={h}, w={w}\n")
                if len(signboard_ys) > 0:
                    f.write(f"간판 Y 위치: min={signboard_y_min}, max={signboard_y_max}, center={signboard_y_center}\n")
                f.write(f"조명 위치: cx={cx}, cy={cy}, rad={rad}\n")
                f.write(f"조명 크기: width={light_width}, height={light_height}\n")
                f.write(f"간판 픽셀 수: {np.sum(signboard_mask_single > 0.1)}\n")
            
            for i in range(h):
                for j in range(w):
                    # 조명에서의 거리
                    dx = j - cx
                    dy = i - cy
                    
                    # 타원형 거리 계산 (프론트엔드와 동일)
                    dist = np.sqrt((dx / (light_width / 2))**2 + (dy / (light_height / 2))**2)
                    
                    if dist < 1.0:
                        # 타원형 안에 있으면 균일하게 1.0 (프론트엔드와 동일)
                        mask_light[i, j] = 1.0
            
            print(f"[DEBUG] mask_light 범위: min={mask_light.min():.3f}, max={mask_light.max():.3f}")
            print(f"[DEBUG] mask_light에서 0이 아닌 픽셀 수: {np.sum(mask_light > 0.01)}")
            
            # ===== 구버전 (간판과의 교집합) =====
            # light_on_signboard = mask_light * signboard_mask_single
            
            # ===== 신버전 (타원형의 아래쪽 절반만, 프론트엔드와 동일) =====
            # 조명 중심(cy)부터 아래쪽만 적용
            mask_lower = np.zeros((h, w), dtype=np.float32)
            mask_lower[cy:, :] = 1.0  # cy부터 아래쪽만
            light_on_signboard = mask_light * mask_lower  # 타원의 아래쪽 절반만
            
            # intensity 적용: 야간 효과를 얼마나 제거할지
            # intensity = 0 → 야간 그대로 (제거 안함)
            # intensity = 1 → 완전히 주간으로 복원
            # intensity > 1 → 더 강하게 (최대 3까지)
            restore_strength = np.clip(light_on_signboard * intensity, 0, 1)
            restore_strength_3ch = np.stack([restore_strength, restore_strength, restore_strength], axis=2)
            
            # 야간 효과 제거: 조명이 비추는 간판 부분을 주간 이미지로 교체
            print(f"[DEBUG] restore_strength 범위: min={restore_strength.min():.3f}, max={restore_strength.max():.3f}, mean={restore_strength.mean():.3f}")
            print(f"[DEBUG] 조명이 적용되는 픽셀 수: {np.sum(restore_strength > 0.1)}")
            
            # 파일에도 저장
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"restore_strength 최대값: {restore_strength.max():.3f}\n")
                f.write(f"조명 적용 픽셀 수: {np.sum(restore_strength > 0.1)}\n")
                f.write(f"---\n")
            
            night_result = night_result.astype(np.float32) * (1 - restore_strength_3ch) + day_result.astype(np.float32) * restore_strength_3ch
            
            # 조명 색온도 약하게 추가 (분위기)
            light_tint = light_color * restore_strength_3ch * 0.08
            night_result = night_result + light_tint
            
            print(f"[DEBUG] 조명 처리 완료")
            
            night_result = np.clip(night_result, 0, 255)
    
    night_result = np.clip(night_result, 0, 255).astype(np.uint8)

    # 전면프레임-전후광채널 디버그: 실제 들어온 값 확인 및 이미지 저장 (예외 처리 포함)
    try:
        debug_logger.info(f"[composite_signboard 반환 직전] installation_type='{installation_type}' (repr: {repr(installation_type)}), sign_type='{sign_type}' (repr: {repr(sign_type)})")
        debug_logger.info(f"[composite_signboard 반환 직전] 조건 체크: installation_type == '전면프레임' = {installation_type == '전면프레임'}, sign_type == '전후광채널' = {sign_type == '전후광채널'}")
        
        if installation_type == "전면프레임" and sign_type == "전후광채널":
            debug_dir = os.path.join(os.path.dirname(__file__), "debug_images")
            os.makedirs(debug_dir, exist_ok=True)
            import time
            timestamp = int(time.time() * 1000)
            day_path = os.path.join(debug_dir, f"composite_day_{timestamp}.png")
            night_path = os.path.join(debug_dir, f"composite_night_{timestamp}.png")
            cv2.imwrite(day_path, day_result)
            cv2.imwrite(night_path, night_result)
            debug_logger.info(f"[composite_signboard] 디버그 이미지 저장 완료: day_result.shape={day_result.shape}, night_result.shape={night_result.shape}, day_result.mean()={day_result.mean():.2f}, night_result.mean()={night_result.mean():.2f}, day_path={day_path}, night_path={night_path}")
        else:
            debug_logger.info(f"[composite_signboard] 디버그 이미지 저장 스킵: 조건 불일치 (installation_type='{installation_type}', sign_type='{sign_type}')")
    except Exception as e:
        debug_logger.error(f"[composite_signboard] 이미지 저장 중 오류: {e}", exc_info=True)
    
    return day_result, night_result

# 오류 로그 파일 생성 함수 (전역)
import datetime
log_file = "error_log.txt"

def log_error(message, error=None):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n[{timestamp}] {message}\n")
            if error:
                import traceback
                f.write(f"Error: {str(error)}\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
            f.write("-" * 80 + "\n")
    except Exception as e:
        print(f"[로그 기록 실패] {e}")

@app.post("/api/generate-simulation")
async def generate_simulation(
    building_photo: str = Form(...),
    polygon_points: str = Form(...),
    signboard_input_type: str = Form("text"),
    text: str = Form(""),
    logo: str = Form(""),
    logo_type: str = Form("channel"),
    signboard_image: str = Form(""),
    installation_type: str = Form("맨벽"),
    sign_type: str = Form(...),
    bg_color: str = Form(...),
    text_color: str = Form(...),
    text_direction: str = Form("horizontal"),
    font_size: int = Form(100),
    font_family: str = Form("malgun"),
    font_weight: str = Form("400"),
    text_position_x: int = Form(50),
    text_position_y: int = Form(50),
    orientation: str = Form("auto"),
    flip_horizontal: str = Form("false"),
    flip_vertical: str = Form("false"),
    rotate90: int = Form(0),
    rotation: float = Form(0.0),  # 회전 각도 (도 단위, -180 ~ 180)
    remove_white_bg: str = Form("false"),  # 흰색 배경 투명 처리
    lights: str = Form("[]"),
    lights_enabled: str = Form("true"),
    # 복수 간판용: 프론트에서 JSON 문자열로 전달
    signboards: str = Form(None)
):
    # 최상단에 로그 출력 (함수 진입 시 즉시)
    sys.stdout.write(f"[API 진입] generate_simulation 호출: installation_type={installation_type}, sign_type={sign_type}, bg_color={bg_color}, text_color={text_color}\n")
    sys.stdout.flush()
    logger.info(f"[API] generate_simulation 호출됨: installation_type={installation_type}, sign_type={sign_type}, bg_color={bg_color}, text_color={text_color}")
    print(f"[API] generate_simulation 호출됨: installation_type={installation_type}, sign_type={sign_type}, bg_color={bg_color}, text_color={text_color}", flush=True)
    
    try:
        # 진입 로그 (복수 간판 디버깅용)
        log_error(f"[ENTRY] signboards raw: {str(signboards)[:200]}")

        # Base64 이미지 디코딩
        building_img = base64_to_image(building_photo)

        # 조명 정보 파싱
        lights_list = json.loads(lights) if lights else []
        lights_on = lights_enabled.lower() != "false"
        
        print(f"[DEBUG] lights_enabled 값: {lights_enabled}")
        print(f"[DEBUG] lights_on 계산 결과: {lights_on}")
        print(f"[DEBUG] lights_list: {lights_list}")
        print(f"[DEBUG] lights_list 길이: {len(lights_list)}")

        # 복수 간판 모드: signboards JSON이 전달된 경우
        if signboards:
            try:
                signboards_data = json.loads(signboards)
            except Exception as e:
                log_error("[ERROR] signboards JSON 파싱 실패", e)
                return JSONResponse(status_code=400, content={"error": "잘못된 signboards 형식입니다."})

            log_error(f"[MULTI] 전달된 간판 개수: {len(signboards_data)}")

            current_day = building_img.copy()
            current_night = None

            # 여러 간판을 순차적으로 합성 (앞에서부터 쌓아가기)
            for idx, sb in enumerate(signboards_data):
                try:
                    sb_points = sb.get("polygon_points", [])
                    if not sb_points:
                        log_error(f"[MULTI] index={idx} 폴리곤 없음, 스킵")
                        continue

                    sb_signboard_input_type = sb.get("signboard_input_type", "text")
                    sb_text = sb.get("text", "")
                    sb_logo = sb.get("logo", "")
                    sb_logo_type = sb.get("logo_type", "channel")
                    sb_signboard_image = sb.get("signboard_image", "")
                    sb_installation_type = sb.get("installation_type", "맨벽")
                    sb_sign_type = sb.get("sign_type", sign_type)
                    sb_bg_color = sb.get("bg_color", bg_color)
                    sb_text_color = sb.get("text_color", text_color)
                    sb_text_direction = sb.get("text_direction", text_direction)
                    sb_font_size = int(sb.get("font_size", font_size))
                    sb_font_family = sb.get("font_family", font_family)
                    sb_font_weight = sb.get("font_weight", font_weight)
                    sb_text_position_x = int(sb.get("text_position_x", text_position_x))
                    sb_text_position_y = int(sb.get("text_position_y", text_position_y))
                    sb_orientation = sb.get("orientation", orientation)
                    sb_flip_horizontal = str(sb.get("flip_horizontal", flip_horizontal))
                    sb_flip_vertical = str(sb.get("flip_vertical", flip_vertical))
                    sb_rotate90 = int(sb.get("rotate90", rotate90))
                    sb_rotation = float(sb.get("rotation", rotation))
                    sb_remove_white_bg = str(sb.get("remove_white_bg", remove_white_bg))

                    # 디버깅용 로그
                    log_error(f"[MULTI] index={idx}, type={sb_signboard_input_type}, text={sb_text}, sign_type={sb_sign_type}")

                    # 이하 로직은 기존 단일 간판 처리와 동일하게, sb_* 값을 사용

                    # 폴리곤 점 파싱
                    points = sb_points

                    # 4점인 경우: 실제 변 길이 계산 (정확한 방향 파악)
                    if len(points) == 4:
                        ordered = order_points(points)
                        top_width = np.sqrt((ordered[1][0] - ordered[0][0])**2 + (ordered[1][1] - ordered[0][1])**2)
                        left_height = np.sqrt((ordered[3][0] - ordered[0][0])**2 + (ordered[3][1] - ordered[0][1])**2)
                        region_width = int(top_width)
                        region_height = int(left_height)
                    else:
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        region_width = int(max(xs) - min(xs))
                        region_height = int(max(ys) - min(ys))

                    region_width = max(300, region_width)
                    region_height = max(100, region_height)

                    if sb_orientation == "vertical":
                        region_width, region_height = region_height, region_width
                    elif sb_orientation == "horizontal":
                        pass

                    auto_direction = analyze_polygon_shape(points)
                    final_direction = auto_direction if sb_text_direction == "auto" else sb_text_direction

                    # ===== 복수 간판용 자동 글자 크기 (단일 간판 로직과 동일) =====
                    if sb_installation_type == "유리창시트시공":
                        base_ratio = 0.9
                    elif sb_installation_type == "프레임바":
                        base_ratio = 0.7
                    else:
                        base_ratio = 0.85

                    auto_font_size = int(region_height * base_ratio)
                    auto_font_size = max(20, min(auto_font_size, int(region_height * 0.98)))

                    # 슬라이더를 배율(%)로 사용
                    if sb_font_size != 100:
                        scale_factor = sb_font_size / 100.0
                        scale_factor = max(0.3, min(3.0, scale_factor))
                        final_font_size = int(auto_font_size * scale_factor)
                    else:
                        final_font_size = auto_font_size

                    if sb_signboard_input_type == "image" and sb_signboard_image:
                        uploaded_img = base64_to_image(sb_signboard_image)

                        if sb_rotate90 == 90:
                            uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_CLOCKWISE)
                        elif sb_rotate90 == 180:
                            uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_180)
                        elif sb_rotate90 == 270:
                            uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)

                        if sb_flip_horizontal.lower() == "true":
                            uploaded_img = cv2.flip(uploaded_img, 1)
                        if sb_flip_vertical.lower() == "true":
                            uploaded_img = cv2.flip(uploaded_img, 0)

                        if sb_rotate90 == 0 and sb_flip_horizontal.lower() == "false" and sb_flip_vertical.lower() == "false":
                            h_img, w_img = uploaded_img.shape[:2]
                            img_ratio = w_img / h_img
                            region_ratio = region_width / region_height

                            if sb_orientation == "auto":
                                if (img_ratio > 1 and region_ratio < 1) or (img_ratio < 1 and region_ratio > 1):
                                    uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                            elif sb_orientation == "vertical":
                                if img_ratio > 1:
                                    uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                            elif sb_orientation == "horizontal":
                                if img_ratio < 1:
                                    uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_CLOCKWISE)

                        # 흰색 배경 투명 처리
                        if sb_remove_white_bg.lower() == "true":
                            image_rgba = remove_white_background(uploaded_img)
                            # RGBA를 BGR로 변환 (투명 부분은 검은색으로)
                            image_rgb = image_rgba[:, :, :3]
                            alpha = image_rgba[:, :, 3:4] / 255.0
                            # 투명 부분을 검은색으로 처리 (composite_signboard의 transparency_mask가 처리)
                            uploaded_img = (image_rgb * alpha + (1 - alpha) * 0).astype(np.uint8)
                            uploaded_img = cv2.cvtColor(uploaded_img, cv2.COLOR_RGB2BGR)
                        
                        signboard_img = cv2.resize(uploaded_img, (region_width, region_height))
                        text_layer = None
                        actual_text_width = None
                        actual_text_height = None
                    else:
                        signboard_img, text_layer = render_signboard(
                            sb_text, sb_logo, sb_logo_type, sb_installation_type, sb_sign_type,
                            sb_bg_color, sb_text_color, final_direction, final_font_size,
                            sb_text_position_x, sb_text_position_y, region_width, region_height,
                            building_photo=building_img, polygon_points=points,
                            font_family=sb_font_family, font_weight=sb_font_weight
                        )

                        from PIL import Image, ImageDraw, ImageFont
                        font = get_korean_font(final_font_size)
                        draw_temp = ImageDraw.Draw(Image.new('RGB', (region_width, region_height)))
                        if final_direction == "vertical":
                            text_vertical = '\n'.join(list(sb_text))
                            bbox = draw_temp.multiline_textbbox((0, 0), text_vertical, font=font)
                        else:
                            bbox = draw_temp.textbbox((0, 0), sb_text, font=font)
                        actual_text_width = bbox[2] - bbox[0]
                        actual_text_height = bbox[3] - bbox[1]

                    rotation_value = 0.0
                    try:
                        rotation_value = float(sb_rotation)
                    except (ValueError, TypeError):
                        rotation_value = 0.0

                    rotation_float = rotation_value

                    if abs(rotation_float) > 0.01:
                        try:
                            original_h, original_w = signboard_img.shape[:2]
                            signboard_pil = Image.fromarray(cv2.cvtColor(signboard_img, cv2.COLOR_BGR2RGB))
                            rotated_pil = signboard_pil.rotate(
                                -rotation_float,
                                expand=True,
                                fillcolor=(0, 0, 0),
                                resample=Image.Resampling.BILINEAR
                            )
                            signboard_img_rotated = cv2.cvtColor(np.array(rotated_pil), cv2.COLOR_RGB2BGR)
                            signboard_img = signboard_img_rotated

                            if text_layer is not None:
                                text_pil = Image.fromarray(cv2.cvtColor(text_layer, cv2.COLOR_BGR2RGB))
                                rotated_text_pil = text_pil.rotate(-rotation_float, expand=True, fillcolor=(0, 0, 0))
                                text_layer = cv2.cvtColor(np.array(rotated_text_pil), cv2.COLOR_RGB2BGR)
                        except Exception as e:
                            log_error("회전 적용 중 오류 발생", e)

                    # 현재 누적된 day/night에 이 간판 합성
                    # - 주간: 항상 current_day 기준으로 추가 합성
                    # - 야간: 처음 한 번만 배경을 어둡게 하고, 이후에는 이미 어두운 current_night 위에만 간판 추가
                    base_day = current_day
                    base_night = current_night if current_night is not None else building_img
                    pre_dark = current_night is not None

                    day_sim, night_sim = composite_signboard(
                        base_day,
                        signboard_img,
                        points,
                        sb_sign_type,
                        text_layer,
                        lights_list,
                        lights_on,
                        building_photo_night=base_night,
                        pre_darkened=pre_dark,
                        installation_type=sb_installation_type,
                    )
                    current_day = day_sim
                    current_night = night_sim

                except Exception as e:
                    log_error(f"[ERROR] 복수 간판 처리 중 오류 (index={idx})", e)
                    continue

            if current_night is None:
                # 간판이 하나도 제대로 처리되지 않은 경우
                day_sim = building_img
                night_sim = building_img
            else:
                day_sim = current_day
                night_sim = current_night

            day_base64 = image_to_base64(day_sim)
            night_base64 = image_to_base64(night_sim)

            response_data = {
                "day_simulation": day_base64,
                "night_simulation": night_base64
            }

            return JSONResponse(content=response_data)

        # 단일 간판 모드 (기존 로직 유지)

        # rotation 값을 문자열에서 float로 변환
        rotation_value = 0.0
        if rotation is not None:
            try:
                if isinstance(rotation, str):
                    rotation_value = float(rotation)
                else:
                    rotation_value = float(rotation)
            except (ValueError, TypeError):
                rotation_value = 0.0
                print(f"[WARNING] rotation 값을 변환할 수 없음: {rotation}")
        
        print(f"[DEBUG] API 요청 받음 - rotation (원본): {rotation}, rotation (변환): {rotation_value}, rotate90: {rotate90}, type: {type(rotation)}")
        log_error(f"API 요청 받음 - rotation: {rotation}, rotation_value: {rotation_value}, rotate90: {rotate90}")

        # 폴리곤 점 파싱
        points = json.loads(polygon_points)
        
        # 4점인 경우: 실제 변 길이 계산 (정확한 방향 파악)
        if len(points) == 4:
            # 점들을 정렬 (좌상, 우상, 우하, 좌하)
            ordered = order_points(points)
            
            # 상단 변 길이 (좌상 -> 우상)
            top_width = np.sqrt((ordered[1][0] - ordered[0][0])**2 + (ordered[1][1] - ordered[0][1])**2)
            # 좌측 변 길이 (좌상 -> 좌하)
            left_height = np.sqrt((ordered[3][0] - ordered[0][0])**2 + (ordered[3][1] - ordered[0][1])**2)
            
            region_width = int(top_width)
            region_height = int(left_height)
        else:
            # n점인 경우: 바운딩 박스 사용
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            region_width = int(max(xs) - min(xs))
            region_height = int(max(ys) - min(ys))
        
        # 최소 크기 보장
        region_width = max(300, region_width)
        region_height = max(100, region_height)
        
        # 간판 방향 처리
        if orientation == "vertical":
            # 세로 강제: width와 height를 swap
            region_width, region_height = region_height, region_width
        elif orientation == "horizontal":
            # 가로 강제: 그대로 유지
            pass
        # orientation == "auto": 계산된 값 그대로 사용
        
        # 영역 형태 분석 (가로/세로/비스듬함)
        auto_direction = analyze_polygon_shape(points)
        final_direction = auto_direction if text_direction == "auto" else text_direction
        
        # ===== 글자 자동 크기 계산 (영역을 최대한 가득 채우기) =====
        # 설치 방식에 따라 기본으로 채우는 정도만 다르게 설정
        # - 유리창시트시공: 거의 가득 (0.9)
        # - 프레임바: 막대 안에 여유를 조금 두고 (0.7)
        # - 그 외 대부분: 꽉 차게 (0.85)
        if installation_type == "유리창시트시공":
            base_ratio = 0.9
        elif installation_type == "프레임바":
            base_ratio = 0.7
        else:
            base_ratio = 0.85

        auto_font_size = int(region_height * base_ratio)
        # 최소/최대 가드
        auto_font_size = max(20, min(auto_font_size, int(region_height * 0.98)))
        
        # ===== 슬라이더 font_size를 "배율(%)"로 해석 =====
        # 100 → 기본, 50 → 0.5배, 200 → 2배
        if font_size != 100:
            scale_factor = font_size / 100.0
            scale_factor = max(0.3, min(3.0, scale_factor))  # 30%~300% 범위 제한
            final_font_size = int(auto_font_size * scale_factor)
        else:
            final_font_size = auto_font_size
        
        # 간판 렌더링 (텍스트 or 이미지)
        if signboard_input_type == "image" and signboard_image:
            # 이미지 업로드 방식
            uploaded_img = base64_to_image(signboard_image)
            
            # 사용자 지정 변환 적용 (우선순위: 회전 → 좌우반전 → 상하반전)
            
            # 1. 회전 (90도 단위)
            if rotate90 == 90:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_CLOCKWISE)
            elif rotate90 == 180:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_180)
            elif rotate90 == 270:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # 2. 좌우반전
            if flip_horizontal.lower() == "true":
                uploaded_img = cv2.flip(uploaded_img, 1)  # 1 = 좌우반전
            
            # 3. 상하반전
            if flip_vertical.lower() == "true":
                uploaded_img = cv2.flip(uploaded_img, 0)  # 0 = 상하반전
            
            # orientation이 지정되어 있고, 사용자가 직접 변환하지 않은 경우에만 자동 회전
            if rotate90 == 0 and flip_horizontal.lower() == "false" and flip_vertical.lower() == "false":
                h_img, w_img = uploaded_img.shape[:2]
                img_ratio = w_img / h_img
                region_ratio = region_width / region_height
                
                # orientation 처리
                if orientation == "auto":
                    # 자동: 비율이 비슷하면 그대로, 많이 다르면 회전
                    if (img_ratio > 1 and region_ratio < 1) or (img_ratio < 1 and region_ratio > 1):
                        uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                elif orientation == "vertical":
                    # 세로 강제: 이미지가 가로로 길면 반시계방향 회전
                    if img_ratio > 1:
                        uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                elif orientation == "horizontal":
                    # 가로 강제: 이미지가 세로로 길면 시계방향 회전
                    if img_ratio < 1:
                        uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_CLOCKWISE)
            
            # 흰색 배경 투명 처리
            if remove_white_bg.lower() == "true":
                image_rgba = remove_white_background(uploaded_img)
                # RGBA를 BGR로 변환 (투명 부분은 검은색으로)
                image_rgb = image_rgba[:, :, :3]
                alpha = image_rgba[:, :, 3:4] / 255.0
                # 투명 부분을 검은색으로 처리 (composite_signboard의 transparency_mask가 처리)
                uploaded_img = (image_rgb * alpha + (1 - alpha) * 0).astype(np.uint8)
                uploaded_img = cv2.cvtColor(uploaded_img, cv2.COLOR_RGB2BGR)
            
            # 영역 크기에 맞춰 리사이즈
            signboard_img = cv2.resize(uploaded_img, (region_width, region_height))
            text_layer = None
        else:
            # 텍스트 방식 (영역 크기에 맞게)
            logger.info(f"[API] render_signboard 호출: installation_type={installation_type}, sign_type={sign_type}, bg_color={bg_color}, text_color={text_color}")
            print(f"[API] render_signboard 호출: installation_type={installation_type}, sign_type={sign_type}, bg_color={bg_color}, text_color={text_color}", flush=True)
            signboard_img, text_layer = render_signboard(
                text, logo, logo_type, installation_type, sign_type, 
                bg_color, text_color, final_direction, final_font_size, 
                text_position_x, text_position_y, region_width, region_height,
                building_photo=building_img, polygon_points=points,
                font_family=font_family, font_weight=font_weight
            )
            
            # 실제 텍스트 크기 계산 (render_combined_signboard 내부에서 계산된 값 사용)
            # render_combined_signboard 함수 내부에서 text_width, text_height를 계산하므로
            # 여기서도 동일한 방식으로 계산
            from PIL import Image, ImageDraw, ImageFont
            font = get_korean_font(final_font_size)
            draw_temp = ImageDraw.Draw(Image.new('RGB', (region_width, region_height)))
            if final_direction == "vertical":
                text_vertical = '\n'.join(list(text))
                bbox = draw_temp.multiline_textbbox((0, 0), text_vertical, font=font)
            else:
                bbox = draw_temp.textbbox((0, 0), text, font=font)
            actual_text_width = bbox[2] - bbox[0]
            actual_text_height = bbox[3] - bbox[1]
        
        # 회전 적용 (rotation 각도가 있으면)
        # rotation_value는 위에서 이미 변환됨
        rotation_float = rotation_value
        print(f"[DEBUG] 회전 체크 - rotation_float: {rotation_float}, abs: {abs(rotation_float)}, > 0.01: {abs(rotation_float) > 0.01}")
        log_error(f"회전 체크 - rotation_float: {rotation_float}")
        
        if abs(rotation_float) > 0.01:  # 0.01도 이상일 때만 회전 적용
            try:
                print(f"[DEBUG] 회전 적용 시작 - rotation: {rotation_float}도")
                log_error(f"회전 적용 시작 - rotation: {rotation_float}도")
                
                # 회전 전 크기 저장
                original_h, original_w = signboard_img.shape[:2]
                print(f"[DEBUG] 회전 전 이미지 크기: {original_w}x{original_h}")
                
                # PIL Image로 변환하여 회전 (더 정확함)
                signboard_pil = Image.fromarray(cv2.cvtColor(signboard_img, cv2.COLOR_BGR2RGB))
                # 회전 (음수로 회전하여 시계방향 회전, expand=True로 크기 자동 조정)
                # fillcolor를 투명하게 하지 않고 검은색으로 해서 배경이 보이지 않도록
                rotated_pil = signboard_pil.rotate(
                    -rotation_float, 
                    expand=True, 
                    fillcolor=(0, 0, 0),
                    resample=Image.Resampling.BILINEAR
                )
                # RGB를 BGR로 변환
                signboard_img_rotated = cv2.cvtColor(np.array(rotated_pil), cv2.COLOR_RGB2BGR)
                
                # 회전된 이미지로 교체
                signboard_img = signboard_img_rotated
                print(f"[DEBUG] 회전된 이미지로 교체 완료")
                
                # 회전 후 크기 확인
                rotated_h, rotated_w = signboard_img.shape[:2]
                print(f"[DEBUG] 회전 후 이미지 크기: {rotated_w}x{rotated_h}")
                
                # text_layer도 회전 (전광채널인 경우)
                if text_layer is not None:
                    text_pil = Image.fromarray(cv2.cvtColor(text_layer, cv2.COLOR_BGR2RGB))
                    rotated_text_pil = text_pil.rotate(-rotation_float, expand=True, fillcolor=(0, 0, 0))
                    text_layer = cv2.cvtColor(np.array(rotated_text_pil), cv2.COLOR_RGB2BGR)
                    print(f"[DEBUG] text_layer 회전 완료")
                
                print(f"[DEBUG] 회전 적용 완료 - 최종 크기: {rotated_w}x{rotated_h}")
                log_error(f"회전 적용 완료 - 크기: {rotated_w}x{rotated_h}")
            except Exception as e:
                import traceback
                print(f"[DEBUG] 회전 적용 오류: {e}")
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                log_error(f"회전 적용 중 오류 발생", e)
        else:
            print(f"[DEBUG] 회전 적용 안 함 - rotation: {rotation}, rotation_float: {rotation_float}")
            log_error(f"회전 적용 안 함 - rotation: {rotation}")
        
        # 이미지 합성
        day_sim, night_sim = composite_signboard(building_img, signboard_img, points, sign_type, text_layer, lights_list, lights_on, installation_type=installation_type)
        
        # 전면프레임-전후광채널 디버그: API 응답 직전에 이미지 저장 (무조건 실행)
        try:
            if installation_type == "전면프레임" and sign_type == "전후광채널":
                debug_dir = os.path.join(os.path.dirname(__file__), "debug_images")
                os.makedirs(debug_dir, exist_ok=True)
                import time
                timestamp = int(time.time() * 1000)
                cv2.imwrite(os.path.join(debug_dir, f"api_day_{timestamp}.png"), day_sim)
                cv2.imwrite(os.path.join(debug_dir, f"api_night_{timestamp}.png"), night_sim)
                debug_logger.info(f"[API 응답 직전] 디버그 이미지 저장 완료: day_sim.shape={day_sim.shape}, night_sim.shape={night_sim.shape}, day_sim.mean()={day_sim.mean():.2f}, night_sim.mean()={night_sim.mean():.2f}")
        except Exception as e:
            debug_logger.error(f"[API 응답 직전] 이미지 저장 실패: {e}", exc_info=True)
        
        # Base64로 인코딩
        day_base64 = image_to_base64(day_sim)
        night_base64 = image_to_base64(night_sim)
        
        # 실제 텍스트 크기 정보 포함
        response_data = {
            "day_simulation": day_base64,
            "night_simulation": night_base64
        }
        
        # 텍스트 방식인 경우 실제 텍스트 크기 정보 추가
        if signboard_input_type == "text" and text:
            try:
                if 'actual_text_width' in locals() and 'actual_text_height' in locals():
                    response_data["text_width"] = actual_text_width
                    response_data["text_height"] = actual_text_height
                    response_data["signboard_width"] = region_width
                    response_data["signboard_height"] = region_height
            except:
                pass  # 변수가 없으면 무시
        
        return JSONResponse(response_data)
    
    except Exception as e:
        import traceback
        # 오류 로그 파일에 기록
        try:
            log_error(f"API 오류 발생", e)
        except:
            pass  # 로그 기록 실패해도 계속 진행
        
        return JSONResponse(
            {"error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

@app.post("/api/generate-hq")
async def generate_hq(
    building_photo: str = Form(...),
    polygon_points: str = Form(...),
    signboard_input_type: str = Form("text"),
    text: str = Form(""),
    logo: str = Form(""),
    logo_type: str = Form("channel"),
    signboard_image: str = Form(""),
    installation_type: str = Form("맨벽"),
    sign_type: str = Form(...),
    bg_color: str = Form(...),
    text_color: str = Form(...),
    text_direction: str = Form("horizontal"),
    font_size: int = Form(100),
    text_position_x: int = Form(50),
    text_position_y: int = Form(50),
    orientation: str = Form("auto"),
    flip_horizontal: str = Form("false"),
    flip_vertical: str = Form("false"),
    rotate90: int = Form(0),
    rotation: float = Form(0.0),
    remove_white_bg: str = Form("false"),
    lights: str = Form("[]"),
    lights_enabled: str = Form("true"),
    signboards: str = Form(None)
):
    """
    Phase 1 (CG 생성) + Phase 2 (pix2pix 개선) - AI 고품질 모드
    """
    try:
        # 1. pix2pix 모델 확인
        ai_engine = get_pix2pix_engine()
        if ai_engine is None:
            return JSONResponse(
                status_code=503,
                content={"error": "Pix2pix 모델을 사용할 수 없습니다. 모델 파일과 의존성을 확인하세요."}
            )
        
        # 2. Phase 1: 간판 이미지 생성 (건물에 합성하기 전의 순수 간판)
        building_img = base64_to_image(building_photo)
        points = json.loads(polygon_points)
        
        # 간판 영역 크기 계산 (기존 generate_simulation 로직 재사용)
        if len(points) == 4:
            ordered = order_points(points)
            top_width = np.sqrt((ordered[1][0] - ordered[0][0])**2 + (ordered[1][1] - ordered[0][1])**2)
            left_height = np.sqrt((ordered[3][0] - ordered[0][0])**2 + (ordered[3][1] - ordered[0][1])**2)
            region_width = int(top_width)
            region_height = int(left_height)
        else:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            region_width = int(max(xs) - min(xs))
            region_height = int(max(ys) - min(ys))
        
        region_width = max(300, region_width)
        region_height = max(100, region_height)
        
        if orientation == "vertical":
            region_width, region_height = region_height, region_width
        
        # Phase 1 간판 렌더링 (순수 간판만, 건물 배경 없음)
        if signboard_input_type == "image" and signboard_image:
            uploaded_img = base64_to_image(signboard_image)
            # 회전/플립 처리 (기존 로직 재사용)
            if rotate90 == 90:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_CLOCKWISE)
            elif rotate90 == 180:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_180)
            elif rotate90 == 270:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            if flip_horizontal.lower() == "true":
                uploaded_img = cv2.flip(uploaded_img, 1)
            if flip_vertical.lower() == "true":
                uploaded_img = cv2.flip(uploaded_img, 0)
            
            phase1_signboard = cv2.resize(uploaded_img, (region_width, region_height))
        else:
            # 텍스트/로고로 간판 생성 (Pix2Pix 추론용: 배경색 포함)
            phase1_signboard, _ = render_signboard(
                text, logo, logo_type, installation_type, sign_type,
                bg_color, text_color, text_direction, font_size,
                text_position_x, text_position_y, region_width, region_height,
                use_actual_bg_for_training=True,  # True로 변경: 학습과 동일한 형태
                lights_enabled=(lights_enabled.lower() == "true"),
                building_photo=building_img, polygon_points=points
            )
        
        # 3. pix2pix로 개선 (원본 크기 그대로)
        logger.info(f"[AI 고품질] pix2pix 추론 시작: 간판 크기 {phase1_signboard.shape[1]}x{phase1_signboard.shape[0]}")
        
        # 디버그: phase1_signboard 이미지 저장 (글자가 제대로 그려졌는지 확인)
        debug_path = os.path.join(os.path.dirname(__file__), "debug_input.png")
        cv2.imwrite(debug_path, phase1_signboard)
        logger.info(f"[AI 고품질] 디버그 이미지 저장: {debug_path}, shape={phase1_signboard.shape}, min={phase1_signboard.min()}, max={phase1_signboard.max()}, mean={phase1_signboard.mean():.2f}")
        
        enhanced_signboard = ai_engine.enhance(phase1_signboard)
        logger.info(f"[AI 고품질] pix2pix 추론 완료: 결과 크기 {enhanced_signboard.shape}")
        
        # 3-1. 맨벽/프레임바일 때 배경을 검정으로 변경 (합성용)
        if installation_type in ["맨벽", "프레임바"]:
            # 배경색을 BGR로 변환
            bg_rgb = hex_to_rgb(bg_color) if bg_color.startswith('#') else (107, 45, 143)
            bg_bgr = (bg_rgb[2], bg_rgb[1], bg_rgb[0])  # RGB -> BGR
            
            # 배경색과 유사한 픽셀 찾기
            diff = np.abs(enhanced_signboard.astype(np.float32) - np.array(bg_bgr, dtype=np.float32))
            similarity = np.sum(diff, axis=2) < 50  # 임계값: 50 (필요시 조정 가능)
            
            # 배경 영역을 검정으로 변경
            enhanced_signboard[similarity] = [0, 0, 0]
            logger.info(f"[AI 고품질] 배경 검정 처리 완료: {similarity.sum()} 픽셀")
        
        # 4. 건물 사진에 합성 (기존 composite_signboard 로직 재사용, 리사이즈 불필요)
        lights_list = json.loads(lights) if lights else []
        lights_on = lights_enabled.lower() != "false"
        
        final_day, final_night = composite_signboard(
            building_img, enhanced_signboard, points, sign_type,
            text_layer=None, lights=lights_list, lights_enabled=lights_on,
            installation_type=installation_type
        )
        
        # 6. Base64로 인코딩하여 반환
        return {
            "day_simulation": image_to_base64(final_day),
            "night_simulation": image_to_base64(final_night) if final_night is not None else image_to_base64(final_day),
            "processing_time": 0  # TODO: 실제 처리 시간 측정
        }
        
    except Exception as e:
        logger.error(f"AI 고품질 생성 실패: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/generate-flat-design")
async def generate_flat_design_api(
    building_photo: str = Form(...),  # 원본 건물 사진
    polygon_points: str = Form(...),
    signboard_input_type: str = Form("text"),
    text: str = Form(""),
    logo: str = Form(""),
    logo_type: str = Form("channel"),
    signboard_image: str = Form(""),
    installation_type: str = Form("맨벽"),
    sign_type: str = Form(...),
    bg_color: str = Form(...),
    text_color: str = Form(...),
    text_direction: str = Form("horizontal"),
    font_size: int = Form(100),
    text_position_x: int = Form(50),
    text_position_y: int = Form(50),
    orientation: str = Form("auto"),
    flip_horizontal: str = Form("false"),
    flip_vertical: str = Form("false"),
    rotate90: int = Form(0),
    rotation: float = Form(0.0),
    lights_enabled: str = Form("true"),
    show_dimensions: str = Form("true"),  # 치수 표시 여부
    region_width_mm: float = Form(None),  # 실제 영역 너비 (mm, 선택사항)
    region_height_mm: float = Form(None),  # 실제 영역 높이 (mm, 선택사항)
    mode: str = Form("day"),  # 주간/야간 모드 ("day" 또는 "night")
):
    """
    평면 시안 생성: 원본 건물 사진에서 폴리곤 영역을 정면으로 펴서 간판 시안 합성
    """
    try:
        # 1. 원본 건물 사진 디코딩
        building_img = base64_to_image(building_photo)
        
        # 2. 폴리곤 포인트 파싱
        points = json.loads(polygon_points)
        
        # 3. 간판 영역 크기 계산
        if len(points) == 4:
            ordered = order_points(points)
            top_width = np.sqrt((ordered[1][0] - ordered[0][0])**2 + (ordered[1][1] - ordered[0][1])**2)
            left_height = np.sqrt((ordered[3][0] - ordered[0][0])**2 + (ordered[3][1] - ordered[0][1])**2)
            region_width = int(top_width)
            region_height = int(left_height)
        else:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            region_width = int(max(xs) - min(xs))
            region_height = int(max(ys) - min(ys))
        
        region_width = max(300, region_width)
        region_height = max(100, region_height)
        
        if orientation == "vertical":
            region_width, region_height = region_height, region_width
        
        # 4. 간판 이미지 생성
        text_layer = None
        if signboard_input_type == "image" and signboard_image:
            uploaded_img = base64_to_image(signboard_image)
            # 회전/플립 처리
            if rotate90 == 90:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_CLOCKWISE)
            elif rotate90 == 180:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_180)
            elif rotate90 == 270:
                uploaded_img = cv2.rotate(uploaded_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            if flip_horizontal.lower() == "true":
                uploaded_img = cv2.flip(uploaded_img, 1)
            if flip_vertical.lower() == "true":
                uploaded_img = cv2.flip(uploaded_img, 0)
            
            signboard_img = cv2.resize(uploaded_img, (region_width, region_height))
        else:
            # 텍스트/로고로 간판 생성 (흰색 배경 옵션 사용)
            signboard_img, text_layer = render_signboard(
                text, logo, logo_type, installation_type, sign_type,
                bg_color, text_color, text_direction, font_size,
                text_position_x, text_position_y, region_width, region_height,
                use_actual_bg_for_training=False,
                lights_enabled=(lights_enabled.lower() == "true"),
                white_background=True,  # 흰색 배경 강제
                building_photo=building_img, polygon_points=points
            )
            # text_layer가 BGR 형식이면 RGBA로 변환 필요
            if text_layer is not None:
                # text_layer가 이미 RGBA인지 확인
                if len(text_layer.shape) == 3 and text_layer.shape[2] == 3:
                    # BGR -> RGB -> RGBA 변환 (알파 채널 추가)
                    h, w = text_layer.shape[:2]
                    text_layer_rgb = cv2.cvtColor(text_layer, cv2.COLOR_BGR2RGB)
                    text_layer_rgba = np.zeros((h, w, 4), dtype=np.uint8)
                    text_layer_rgba[:, :, :3] = text_layer_rgb
                    # 알파 채널: 텍스트가 있는 부분만 불투명
                    gray = cv2.cvtColor(text_layer, cv2.COLOR_BGR2GRAY)
                    text_layer_rgba[:, :, 3] = (gray > 10).astype(np.uint8) * 255
                    text_layer = text_layer_rgba
                elif len(text_layer.shape) == 3 and text_layer.shape[2] == 4:
                    # 이미 RGBA인 경우, BGR -> RGB 변환 필요
                    text_layer_rgb = cv2.cvtColor(text_layer[:, :, :3], cv2.COLOR_BGR2RGB)
                    text_layer_rgba = np.zeros((text_layer.shape[0], text_layer.shape[1], 4), dtype=np.uint8)
                    text_layer_rgba[:, :, :3] = text_layer_rgb
                    text_layer_rgba[:, :, 3] = text_layer[:, :, 3]  # 알파 채널 유지
                    text_layer = text_layer_rgba
        
        # 5. 평면 시안 생성 (두 가지 모드: design_only, with_context)
        night_mode = (mode.lower() == "night")
        design_only, with_context, dimensions = generate_dual_flat_design(
            building_photo=building_img,  # 원본 건물 사진 전달
            polygon_points=points,
            signboard_image=signboard_img,
            text_layer=text_layer,  # 알파 블렌딩용 (전광채널/후광채널/전후광채널인 경우만)
            frame_line_color=(180, 180, 180),  # 회색 프레임
            background_color=(255, 255, 255),    # 흰색 배경
            padding_ratio=0.1,                    # 10% 여백
            show_dimensions=(show_dimensions.lower() == "true"),  # 치수 표시
            region_width_mm=region_width_mm if region_width_mm else None,  # 사용자 입력 치수 (mm)
            region_height_mm=region_height_mm if region_height_mm else None,  # 사용자 입력 치수 (mm)
            region_width_px=region_width,  # 실제 영역 크기 전달 (픽셀)
            region_height_px=region_height,  # 실제 영역 크기 전달 (픽셀)
            night_mode=night_mode,  # 야간 모드
            sign_type=sign_type  # 간판 종류 (발광 효과용)
        )
        
        # 6. Base64로 인코딩하여 반환
        return {
            "design_only": image_to_base64(design_only),
            "with_context": image_to_base64(with_context),
            "dimensions": dimensions,
            "width": design_only.shape[1],
            "height": design_only.shape[0],
            "region_width": region_width,
            "region_height": region_height
        }
        
    except Exception as e:
        logger.error(f"평면 시안 생성 실패: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

# AI 브랜딩 시스템 초기화
if AI_BRANDING_AVAILABLE:
    try:
        branding_system = AIBrandingSystem()
        logger.info("AI 브랜딩 시스템 초기화 완료")
    except Exception as e:
        logger.error(f"AI 브랜딩 시스템 초기화 실패: {e}")
        branding_system = None
else:
    branding_system = None
    logger.warning("AI 브랜딩 시스템을 사용할 수 없습니다 (openai 모듈 없음)")

@app.post("/api/ai-suggest-names")
async def ai_suggest_names(
    industry: str = Form(...),
    mood: str = Form(...),
    target_customer: str = Form(""),
    count: int = Form(5)
):
    """AI 상호명 제안 엔드포인트"""
    
    if not branding_system:
        return JSONResponse(
            {"error": "AI 브랜딩 시스템이 초기화되지 않았습니다."},
            status_code=500
        )
    
    try:
        logger.info(f"상호명 생성 요청: industry={industry}, mood={mood}")
        
        names = branding_system.generate_business_names(
            industry=industry,
            mood=mood,
            target_customer=target_customer,
            count=count
        )
        
        if not names:
            return JSONResponse(
                {"error": "상호명 생성에 실패했습니다."},
                status_code=500
            )
        
        logger.info(f"상호명 {len(names)}개 생성 완료")
        
        return JSONResponse({
            "success": True,
            "names": names,
            "request_info": {
                "industry": industry,
                "mood": mood,
                "target_customer": target_customer,
                "count": len(names)
            }
        })
        
    except Exception as e:
        logger.error(f"상호명 생성 오류: {e}")
        return JSONResponse(
            {"error": f"상호명 생성 중 오류 발생: {str(e)}"},
            status_code=500
        )

@app.post("/api/ai-suggest-style")
async def ai_suggest_style(
    business_name: str = Form(...),
    industry: str = Form(...)
):
    """AI 간판 스타일 추천 엔드포인트"""
    
    if not branding_system:
        return JSONResponse(
            {"error": "AI 브랜딩 시스템이 초기화되지 않았습니다."},
            status_code=500
        )
    
    try:
        logger.info(f"스타일 추천 요청: business_name={business_name}, industry={industry}")
        
        style = branding_system.suggest_signboard_style(
            name=business_name,
            industry=industry
        )
        
        if not style:
            return JSONResponse(
                {"error": "스타일 추천에 실패했습니다."},
                status_code=500
            )
        
        logger.info(f"스타일 추천 완료: {style.get('recommended_style', 'N/A')}")
        
        return JSONResponse({
            "success": True,
            "style_recommendation": style,
            "business_name": business_name,
            "industry": industry
        })
        
    except Exception as e:
        logger.error(f"스타일 추천 오류: {e}")
        return JSONResponse(
            {"error": f"스타일 추천 중 오류 발생: {str(e)}"},
            status_code=500
        )

@app.post("/api/ai-suggest-colors")
async def ai_suggest_colors(
    business_name: str = Form(...),
    industry: str = Form(...),
    mood: str = Form(...)
):
    """AI 브랜드 색상 추천 엔드포인트"""
    
    if not branding_system:
        return JSONResponse(
            {"error": "AI 브랜딩 시스템이 초기화되지 않았습니다."},
            status_code=500
        )
    
    try:
        logger.info(f"색상 추천 요청: business_name={business_name}")
        
        colors = branding_system.generate_brand_colors(
            business_name=business_name,
            industry=industry,
            mood=mood
        )
        
        if not colors:
            return JSONResponse(
                {"error": "색상 추천에 실패했습니다."},
                status_code=500
            )
        
        logger.info(f"색상 추천 완료")
        
        return JSONResponse({
            "success": True,
            "color_recommendation": colors,
            "business_name": business_name,
            "industry": industry,
            "mood": mood
        })
        
    except Exception as e:
        logger.error(f"색상 추천 오류: {e}")
        return JSONResponse(
            {"error": f"색상 추천 중 오류 발생: {str(e)}"},
            status_code=500
        )

@app.post("/api/ai-branding-complete")
async def ai_branding_complete(
    industry: str = Form(...),
    mood: str = Form(...),
    target_customer: str = Form(""),
    business_name: str = Form(...)
):
    """완전한 AI 브랜딩 패키지 (선택된 상호명 + 색상)

    프론트엔드에서 이미 선택된 상호명(business_name)을 보내주면,
    해당 이름에 맞는 색상만 추천한다.
    (이전에 하던 것처럼 백엔드에서 상호명을 다시 생성하지 않는다.)
    """
    
    if not branding_system:
        return JSONResponse(
            {"error": "AI 브랜딩 시스템이 초기화되지 않았습니다."},
            status_code=500
        )
    
    try:
        selected_name = business_name.strip()
        if not selected_name:
            return JSONResponse(
                {"error": "유효하지 않은 상호명입니다."},
                status_code=400
            )
        
        logger.info(f"완전 브랜딩 요청: industry={industry}, mood={mood}, name={selected_name}")
        
        # 색상 추천만 수행
        colors = branding_system.generate_brand_colors(
            business_name=selected_name,
            industry=industry,
            mood=mood
        )
        
        logger.info(f"완전 브랜딩 완료: {selected_name}")
        
        return JSONResponse({
            "success": True,
            "branding_package": {
                "business_name": selected_name,
                "color_recommendation": colors,
                "industry": industry,
                "mood": mood,
                "target_customer": target_customer
            }
        })
        
    except Exception as e:
        logger.error(f"완전 브랜딩 오류: {e}")
        return JSONResponse(
            {"error": f"브랜딩 패키지 생성 중 오류 발생: {str(e)}"},
            status_code=500
        )

@app.post("/api/ai-generate-logo")
async def ai_generate_logo(
    business_name: str = Form(...),
    industry: str = Form(...),
    mood: str = Form(""),
    primary_color: str = Form("#000000"),
    text_color: str = Form("#FFFFFF"),
    accent_color: str = Form("#FF00FF"),
):
    """DALL-E 3를 사용한 간판용 로고 생성 엔드포인트"""

    if not branding_system:
        return JSONResponse(
            {"error": "AI 브랜딩 시스템이 초기화되지 않았습니다."},
            status_code=500,
        )

    try:
        colors = {
            "primary_color": primary_color,
            "text_color": text_color,
            "accent_color": accent_color,
        }

        logo = branding_system.generate_logo(
            business_name=business_name,
            industry=industry,
            mood=mood,
            colors=colors,
        )

        if not logo:
            return JSONResponse(
                {"error": "로고 생성에 실패했습니다."},
                status_code=500,
            )

        return JSONResponse(
            {
                "success": True,
                "logo": logo,
                "business_name": business_name,
                "industry": industry,
                "mood": mood,
            }
        )

    except Exception as e:
        logger.error(f"로고 생성 오류: {e}")
        return JSONResponse(
            {"error": f"로고 생성 중 오류 발생: {str(e)}"},
            status_code=500,
        )

@app.get("/")
async def root():
    return {
        "message": "Signboard Simulation API",
        "ai_branding_available": branding_system is not None,
        "endpoints": {
            "ai_suggest_names": "/api/ai-suggest-names",
            "ai_suggest_style": "/api/ai-suggest-style", 
            "ai_suggest_colors": "/api/ai-suggest-colors",
            "ai_branding_complete": "/api/ai-branding-complete",
            "generate_simulation": "/api/generate-simulation"
        }
    }

if __name__ == "__main__":
    import os
    # 현재 파일의 디렉토리를 reload 디렉토리로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        reload_dirs=[current_dir]  # 백엔드 디렉토리 감시
    )
