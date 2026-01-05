"""
Phase 2 학습용 Input/Target pair 생성 스크립트.

실제 간판 사진(real_photos)과 labels.json을 기반으로:
- 실제 사진에서 배경색/텍스트색을 추출하고
- 동일 옵션으로 Phase 1 간판 이미지를 생성한 뒤
- 학습용 pair (Phase1 input / 실제 target)를 저장한다.

사용 예시:

    python generate_pairs.py \
        --real phase2_data/real_photos \
        --output phase2_data/paired_data \
        --labels phase2_data/labels.json \
        --split 0.8

출력 구조:

phase2_data/paired_data/
  ├── train/
  │   ├── input/   (Phase 1 생성 PNG)
  │   └── target/  (실제 사진 JPG)
  ├── test/
  │   ├── input/
  │   └── target/
  └── pairs_metadata.json
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, Tuple, List

import cv2
import numpy as np
from sklearn.cluster import KMeans

from main import render_signboard


# 라벨링에서 사용한 sign_type_key → (Phase 1 sign_type, installation_type) 매핑
SIGN_TYPE_MAP = {
    # 전광채널 (Front-lit Channel)
    "channel_front_wall": ("전광채널", "맨벽"),
    "channel_front_frame_bar": ("전광채널", "프레임바"),
    "channel_front_frame_plate": ("전광채널", "전면프레임"),
    # 후광채널 (Back-lit Channel)
    "channel_back_wall": ("후광채널", "맨벽"),
    "channel_back_frame_bar": ("후광채널", "프레임바"),
    "channel_back_frame_plate": ("후광채널", "전면프레임"),
    # 전후광채널 (Front/Back-lit Channel)
    "channel_front_back_wall": ("전후광채널", "맨벽"),
    "channel_front_back_frame_bar": ("전후광채널", "프레임바"),
    "channel_front_back_frame_plate": ("전후광채널", "전면프레임"),
    # 스카시
    "scasi_wall": ("스카시", "맨벽"),
    "scasi_frame_bar": ("스카시", "프레임바"),
    "scasi_frame_plate": ("스카시", "전면프레임"),
    # 플렉스
    "flex_led_frame_plate": ("플렉스_LED", "전면프레임"),
    "flex_basic_frame_plate": ("플렉스_기본", "전면프레임"),
    # 하위 호환성: 기존 channel_wall 등도 지원 (전광으로 매핑)
    "flex_frame_plate": ("플렉스_기본", "전면프레임"),  # 기존 → 기본으로
    "channel_wall": ("전광채널", "맨벽"),
    "channel_frame_bar": ("전광채널", "프레임바"),
    "channel_frame_plate": ("전광채널", "전면프레임"),
}


def rgb_to_hex(color_bgr: np.ndarray) -> str:
    """
    BGR(0-255) numpy 배열을 HEX 문자열(#RRGGBB)로 변환.
    """
    b, g, r = [int(x) for x in color_bgr]
    return f"#{r:02x}{g:02x}{b:02x}"


def extract_colors_v2(image_path: Path) -> Tuple[str, str]:
    """
    개선된 색상 추출 알고리즘 (v2)
    
    개선 사항:
    1. 가장자리 10% 제외 (건물/하늘 제거)
    2. KMeans 3색 추출
    3. 픽셀 수 기준 정렬 (가장 많은 색 = 배경, 가장 적은 색 = 텍스트)
    4. 실패 시 fallback
    
    실패 시 기본값 반환 (#6b2d8f 배경, #ffffff 텍스트)
    """
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"[WARN] 이미지 로드 실패: {image_path}, 기본값 사용")
            return "#6b2d8f", "#ffffff"
        
        h, w = img.shape[:2]
        if h < 50 or w < 50:
            print(f"[WARN] 이미지 너무 작음: {w}x{h}, 기본값 사용")
            return "#6b2d8f", "#ffffff"
        
        # 가장자리 10% 제외 (건물/하늘 제거)
        margin_y = int(h * 0.1)
        margin_x = int(w * 0.1)
        cropped = img[margin_y:h-margin_y, margin_x:w-margin_x]
        
        # 유효 영역 체크
        if cropped.size == 0:
            print(f"[WARN] 크롭 영역 없음, 기본값 사용")
            return "#6b2d8f", "#ffffff"
        
        # KMeans 3색 추출
        pixels = cropped.reshape(-1, 3).astype(np.float32)
        
        if pixels.shape[0] < 100:
            print(f"[WARN] 픽셀 수 부족: {pixels.shape[0]}, 평균색 사용")
            mean_color = np.mean(pixels, axis=0)
            bg_hex = rgb_to_hex(mean_color)
            text_hex = "#ffffff" if np.mean(mean_color) < 128 else "#000000"
            return bg_hex, text_hex
        
        # 3개 색상 추출 (최소 2개)
        n_clusters = min(3, max(2, pixels.shape[0] // 100))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        colors = kmeans.cluster_centers_  # BGR
        labels = kmeans.labels_
        
        # 각 색상의 픽셀 수 계산
        counts = [np.sum(labels == i) for i in range(n_clusters)]
        
        # 픽셀 수로 정렬 (많은 순)
        sorted_indices = np.argsort(counts)[::-1]
        sorted_colors = colors[sorted_indices]
        sorted_counts = [counts[i] for i in sorted_indices]
        
        # 가장 많은 색 = 배경
        bg_color = sorted_colors[0]
        
        # 가장 적은 색 = 텍스트
        text_color = sorted_colors[-1]
        
        bg_hex = rgb_to_hex(bg_color)
        text_hex = rgb_to_hex(text_color)
        
        # 디버그 출력 (간단하게)
        total_pixels = sum(sorted_counts)
        bg_pct = (sorted_counts[0] / total_pixels * 100) if total_pixels > 0 else 0
        text_pct = (sorted_counts[-1] / total_pixels * 100) if total_pixels > 0 else 0
        print(f"  [COLOR-V2] bg={bg_hex} ({bg_pct:.1f}%), text={text_hex} ({text_pct:.1f}%)")
        
        return bg_hex, text_hex
        
    except Exception as e:
        print(f"[ERROR] 색상 추출 실패: {e}, 기본값 사용")
        return "#6b2d8f", "#ffffff"


def extract_colors(image_path: Path) -> Tuple[str, str]:
    """
    실제 사진에서 배경색, 텍스트색 추출.

    - 이미지를 읽고 중앙 50% 영역을 간판 영역으로 가정
    - KMeans(n_clusters=2)로 대표 색상 2개 추출
    - 더 밝은 색을 배경, 더 어두운 색을 텍스트로 사용
    
    실패 시 기본값 반환 (#6b2d8f 배경, #ffffff 텍스트)
    """
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"[WARN] 이미지를 읽을 수 없습니다: {image_path}, 기본값 사용")
            return "#6b2d8f", "#ffffff"

        h, w = img.shape[:2]
        if h < 10 or w < 10:
            print(f"[WARN] 이미지 크기가 너무 작습니다: {image_path} ({w}x{h}), 기본값 사용")
            return "#6b2d8f", "#ffffff"

        # 중앙 50% 영역 크롭
        y1, y2 = h // 4, 3 * h // 4
        x1, x2 = w // 4, 3 * w // 4
        signboard = img[y1:y2, x1:x2]

        # K-means 위한 데이터 준비
        pixels = signboard.reshape(-1, 3).astype(np.float32)

        # 너무 작은 경우 대비
        if pixels.shape[0] < 10:
            mean_color = np.mean(signboard.reshape(-1, 3), axis=0)
            bg_hex = rgb_to_hex(mean_color)
            # 텍스트색은 단순 대비색으로 설정
            text_hex = "#ffffff" if np.mean(mean_color) < 128 else "#000000"
            return bg_hex, text_hex

        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        kmeans.fit(pixels)
        colors = kmeans.cluster_centers_  # BGR

        brightness = [np.mean(c) for c in colors]
        if brightness[0] > brightness[1]:
            bg_color = colors[0]
            text_color = colors[1]
        else:
            bg_color = colors[1]
            text_color = colors[0]

        bg_hex = rgb_to_hex(bg_color)
        text_hex = rgb_to_hex(text_color)
        return bg_hex, text_hex
    
    except Exception as e:
        print(f"[WARN] 색상 추출 중 오류 발생: {e}, 기본값 사용")
        return "#6b2d8f", "#ffffff"


def center_crop_and_resize(
    img: np.ndarray, size: int = 512
) -> np.ndarray:
    """
    이미지를 중앙 기준으로 정사각형 크롭 후 size x size 로 리사이즈.
    (BGR 이미지 입력, BGR 출력)
    """
    h, w = img.shape[:2]
    # 정사각형 중앙 크롭
    side = min(h, w)
    y1 = (h - side) // 2
    x1 = (w - side) // 2
    cropped = img[y1 : y1 + side, x1 : x1 + side]
    resized = cv2.resize(cropped, (size, size), interpolation=cv2.INTER_AREA)
    return resized


def load_labels(labels_path: Path) -> List[Dict]:
    """
    labels.json을 읽어서 개별 샘플 리스트로 평탄화.

    반환되는 각 엔트리 예시:
    {
      "sign_type_key": "channel_wall",
      "sign_type": "channel",
      "installation_type": "wall",
      "time": "day",
      "real_photo": "phase2_data/real_photos/channel_wall/day/....jpg",
      "id": "channel_wall_xxx_day",
      ...
    }
    """
    if not labels_path.exists():
        abs_path = labels_path.resolve()
        error_msg = (
            f"labels.json을 찾을 수 없습니다: {labels_path}\n"
            f"절대 경로: {abs_path}\n\n"
            f"해결 방법:\n"
            f"1. label_tool_gui.py를 실행하여 라벨링을 먼저 완료하세요.\n"
            f"   python label_tool_gui.py --input phase2_data/real_photos/unlabeled/\n"
            f"2. 또는 --labels 옵션으로 올바른 labels.json 경로를 지정하세요."
        )
        raise FileNotFoundError(error_msg)

    with labels_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    samples: List[Dict] = []
    for sign_type_key, time_dict in raw.items():
        for time_key, entries in time_dict.items():
            for entry in entries:
                # labels.json 안에 이미 정보가 있을 수 있지만, 없을 경우를 대비해 보정
                e = dict(entry)
                e.setdefault("sign_type_key", sign_type_key)
                e.setdefault("time", time_key)
                # sign_type과 installation_type이 없으면 sign_type_key에서 추출
                if "sign_type" not in e:
                    parts = sign_type_key.split('_', 1)
                    e["sign_type"] = parts[0]
                    if len(parts) > 1:
                        e["installation_type"] = parts[1]
                samples.append(e)
    return samples


def generate_phase1_image(
    text: str,
    sign_type_key: str,
    bg_color: str,
    text_color: str,
    width: int = 512,
    height: int = 512,
    lights_enabled: bool = False,
) -> np.ndarray:
    """
    Phase 1 간판 이미지를 생성.

    - sign_type_key: 'channel_wall' / 'channel_frame_bar' / ... / 'flex_frame_plate'
    - bg_color, text_color: '#RRGGBB' 형식
    """
    if sign_type_key not in SIGN_TYPE_MAP:
        raise ValueError(f"알 수 없는 sign_type_key: {sign_type_key}")

    sign_type_value, installation_type = SIGN_TYPE_MAP[sign_type_key]

    # render_signboard는 BGR numpy 배열을 반환
    day_img, _ = render_signboard(
        text=text,
        logo_path="",
        logo_type="channel",  # 기본값
        installation_type=installation_type,
        sign_type=sign_type_value,
        bg_color=bg_color,
        text_color=text_color,
        text_direction="horizontal",
        font_size=100,
        text_position_x=50,
        text_position_y=50,
        width=width,
        height=height,
        use_actual_bg_for_training=True,  # 학습 데이터용: 실제 배경색 사용
        lights_enabled=lights_enabled,  # 조명 효과 적용 여부
    )

    if day_img is None:
        raise RuntimeError("render_signboard 결과가 None 입니다.")

    return day_img


def build_pairs(
    real_root: Path,
    output_root: Path,
    labels_path: Path,
    split_ratio: float,
    default_text: str = "간판",
    use_v2_extractor: bool = False,
) -> None:
    """
    전체 pipeline:
    - labels.json 로드
    - 각 real_photo에 대해 색상 추출 + Phase1 생성
    - 중앙 크롭/리사이즈 (512x512)
    - train/test 로 split 후 저장
    - pairs_metadata.json 저장
    
    Args:
        use_v2_extractor: True면 extract_colors_v2 사용, False면 extract_colors 사용
    """
    samples = load_labels(labels_path)
    if not samples:
        print("[WARN] labels.json에 샘플이 없습니다.")
        return

    print(f"[INFO] labels.json 에서 {len(samples)}개 샘플 로드")

    # 절대 경로 보정
    resolved_samples: List[Dict] = []
    for s in samples:
        real_rel = s.get("real_photo")
        if not real_rel:
            continue
        real_path = (labels_path.parent / real_rel).resolve()
        if not real_path.exists():
            print(f"[WARN] 실제 사진을 찾을 수 없어 스킵: {real_path}")
            continue
        s["real_path"] = real_path
        resolved_samples.append(s)

    if not resolved_samples:
        print("[WARN] 사용할 수 있는 실제 사진이 없습니다.")
        return

    # 셔플 + train/test 분리
    random.seed(42)
    random.shuffle(resolved_samples)

    total = len(resolved_samples)
    train_count = int(total * split_ratio)
    train_samples = resolved_samples[:train_count]
    test_samples = resolved_samples[train_count:]

    print(
        f"[INFO] 총 {total}개 → train {len(train_samples)}개, test {len(test_samples)}개 (split={split_ratio})"
    )

    # 출력 디렉토리 생성
    for subset in ["train", "test"]:
        (output_root / subset / "input").mkdir(parents=True, exist_ok=True)
        (output_root / subset / "target").mkdir(parents=True, exist_ok=True)

    metadata: Dict[str, Dict] = {}

    def process_subset(subset_name: str, subset_samples: List[Dict], start_index: int) -> int:
        index = start_index
        for s in subset_samples:
            index += 1
            pair_id = f"{index:04d}"

            sign_type_key = s.get("sign_type_key") or s.get("sign_type")  # 하위 호환성
            time_key = s.get("time", "day")
            real_path: Path = s["real_path"]

            print(f"\n[{subset_name.upper()}] [{pair_id}] {real_path.name}")
            print(f"  - sign_type_key={sign_type_key}, time={time_key}")

            # 실제 이미지 로드
            real_img = cv2.imread(str(real_path))
            if real_img is None:
                print(f"  [WARN] 실제 사진 로드 실패, 스킵: {real_path}")
                continue

            try:
                # 색상 추출 (v2 선택 가능)
                if use_v2_extractor:
                    bg_hex, text_hex = extract_colors_v2(real_path)
                else:
                    bg_hex, text_hex = extract_colors(real_path)
                    print(f"  - colors: bg={bg_hex}, text={text_hex}")
            except Exception as e:
                print(f"  [WARN] 색상 추출 실패({e}), 기본 색상 사용")
                bg_hex, text_hex = "#6b2d8f", "#ffffff"

            try:
                # Phase1 생성 - 실제 텍스트 사용
                actual_text = s.get("text", default_text)
                print(f"  - text: {actual_text}")
                phase1_img = generate_phase1_image(
                    text=actual_text,
                    sign_type_key=sign_type_key,
                    bg_color=bg_hex,
                    text_color=text_hex,
                    width=512,
                    height=512,
                )
            except Exception as e:
                print(f"  [ERROR] Phase1 생성 실패, 스킵: {e}")
                continue

            # 전처리: 중앙 크롭 + 리사이즈 (실제/Phase1 모두)
            real_cropped = center_crop_and_resize(real_img, size=512)
            phase1_cropped = center_crop_and_resize(phase1_img, size=512)

            # 저장 경로
            subset_dir = output_root / subset_name
            input_path = subset_dir / "input" / f"{pair_id}.png"
            target_path = subset_dir / "target" / f"{pair_id}.jpg"

            # 저장
            cv2.imwrite(str(input_path), phase1_cropped)
            cv2.imwrite(str(target_path), real_cropped)

            print(f"  - saved input : {input_path.relative_to(output_root)}")
            print(f"  - saved target: {target_path.relative_to(output_root)}")

            # 메타데이터 기록 (pair_id 기준)
            metadata[pair_id] = {
                "sign_type_key": sign_type_key,
                "sign_type": s.get("sign_type"),
                "installation_type": s.get("installation_type"),
                "time": time_key,
                "bg_color": bg_hex,
                "text_color": text_hex,
                "real_photo": str(real_path.relative_to(labels_path.parent)),
                "phase1_input": str(input_path.relative_to(output_root)),
                "phase1_target": str(target_path.relative_to(output_root)),
            }

        return index

    print("\n[INFO] Train 세트 생성 시작...")
    current_index = 0
    current_index = process_subset("train", train_samples, current_index)

    print("\n[INFO] Test 세트 생성 시작...")
    current_index = process_subset("test", test_samples, current_index)

    # 메타데이터 저장
    meta_path = output_root / "pairs_metadata.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("\n[INFO] 완료!")
    print(f"  - 총 pair 수: {len(metadata)}")
    print(f"  - 메타데이터: {meta_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 학습용 Input/Target pair 생성")
    parser.add_argument(
        "--real",
        type=str,
        required=False,
        default="phase2_data/real_photos",
        help="실제 사진이 있는 루트 폴더 (기본: phase2_data/real_photos)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=False,
        default="phase2_data/paired_data",
        help="pair 데이터를 저장할 폴더 (기본: phase2_data/paired_data)",
    )
    parser.add_argument(
        "--labels",
        type=str,
        required=False,
        default="phase2_data/labels.json",
        help="labels.json 경로 (기본: phase2_data/labels.json)",
    )
    parser.add_argument(
        "--split",
        type=float,
        required=False,
        default=0.8,
        help="train 비율 (0~1, 기본: 0.8)",
    )
    parser.add_argument(
        "--use-v2-extractor",
        action="store_true",
        help="개선된 색상 추출 알고리즘 (v2) 사용",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 현재 작업 디렉토리를 기준으로 상대 경로 해석
    # 스크립트가 있는 디렉토리 기준으로 경로 설정
    script_dir = Path(__file__).parent
    os.chdir(script_dir)  # 스크립트 디렉토리로 이동
    
    real_root = Path(args.real).resolve()
    output_root = Path(args.output).resolve()
    labels_path = Path(args.labels).resolve()

    print("[INFO] 설정")
    print(f"  - real_root : {real_root}")
    print(f"  - output_root: {output_root}")
    print(f"  - labels     : {labels_path}")
    print(f"  - split      : {args.split}")
    print(f"  - color_extractor: {'v2 (개선)' if args.use_v2_extractor else 'v1 (기본)'}")
    
    # labels.json 파일 존재 여부 확인
    if not labels_path.exists():
        # real_photos 안에 있을 수도 있으니 확인
        alternative_path = real_root.parent / "real_photos" / "labels.json"
        if alternative_path.exists():
            print(f"\n[INFO] labels.json을 다른 위치에서 발견했습니다:")
            print(f"  {alternative_path}")
            print(f"  이 경로를 사용합니다.")
            labels_path = alternative_path
        else:
            print(f"\n[ERROR] labels.json 파일이 없습니다!")
            print(f"  찾은 경로: {labels_path}")
            print(f"  대체 경로: {alternative_path}")
            print(f"\n[안내] 먼저 라벨링을 완료해주세요:")
            print(f"  python label_tool_gui.py --input phase2_data/real_photos/unlabeled/")
            print(f"\n또는 --labels 옵션으로 labels.json 경로를 지정하세요:")
            print(f"  python generate_pairs.py --labels phase2_data/real_photos/labels.json")
            sys.exit(1)

    build_pairs(
        real_root=real_root,
        output_root=output_root,
        labels_path=labels_path,
        split_ratio=args.split,
        use_v2_extractor=args.use_v2_extractor,
    )


if __name__ == "__main__":
    main()



