# 전면프레임-전광채널 렌더링 문제 수정 이력

## 문제 상황

**설정:**
- 설치방식: 전면프레임
- 간판종류: 전광채널
- 배경색: 흰색 (#ffffff), 검정색 (#000000), 기타 색상
- 글자색: 빨강 (#ff0000)

**발생 문제:**
1. 흰색 배경일 때: 글자가 빨강으로 보이지 않음 (평면적으로 보이고 색이 섞임)
2. 검정색 배경일 때: 글자가 투명해짐
3. 기타 색상 배경일 때: 글자색이 제대로 반영되지 않음
4. 글자 옆면과 그림자가 이상함
5. 글자가 떠 있는 것처럼 보임

---

## 수정 시도 내역

### 시도 1: Alpha 블렌딩 방식으로 변경 (cv2.add → alpha blending)

**위치:** `main.py` 1061-1084줄

**변경 내용:**
- 기존: `cv2.add` 사용 (배경색과 텍스트 색상이 섞임)
- 변경: Alpha 블렌딩으로 텍스트 레이어 합성
  - 그림자: 40% alpha 블렌딩
  - 옆면: Alpha 블렌딩
  - 앞면: Alpha 블렌딩

**코드:**
```python
if installation_type == "전면프레임":
    # 그림자 alpha (40%) 적용
    shadow_alpha = (shadow_layer_rgba[:, :, 3].astype(np.float32) / 255.0) * 0.4
    shadow_alpha_3ch = np.stack([shadow_alpha, shadow_alpha, shadow_alpha], axis=2)
    day_f = day_result.astype(np.float32)
    day_f = day_f * (1 - shadow_alpha_3ch) + shadow_layer_bgr.astype(np.float32) * shadow_alpha_3ch
    
    # 옆면 alpha 블렌딩
    side_alpha = (side_layer_rgba[:, :, 3].astype(np.float32) / 255.0)
    side_alpha_3ch = np.stack([side_alpha, side_alpha, side_alpha], axis=2)
    day_f = day_f * (1 - side_alpha_3ch) + side_layer_bgr.astype(np.float32) * side_alpha_3ch
    
    # 앞면 alpha 블렌딩
    text_alpha = (text_layer_rgba[:, :, 3].astype(np.float32) / 255.0)
    text_alpha_3ch = np.stack([text_alpha, text_alpha, text_alpha], axis=2)
    day_f = day_f * (1 - text_alpha_3ch) + text_layer_bgr.astype(np.float32) * text_alpha_3ch
    
    day_result = np.clip(day_f, 0, 255).astype(np.uint8)
```

**결과:** ❌ 여전히 글자색이 빨강으로 보이지 않음

---

### 시도 2: 옆면과 앞면 겹침 처리 (앞면 영역에서 옆면 제외)

**위치:** `main.py` 1069-1081줄

**변경 내용:**
- 옆면 블렌딩 시 앞면 영역을 마스크로 제외하여 옆면이 앞면을 가리지 않도록 함

**코드:**
```python
# 옆면 alpha 블렌딩 (앞면 영역 제외)
side_alpha = (side_layer_rgba[:, :, 3].astype(np.float32) / 255.0)
text_alpha_mask = (text_layer_rgba[:, :, 3].astype(np.float32) / 255.0)  # 앞면 마스크
# 앞면이 없는 영역에서만 옆면 적용
side_alpha = side_alpha * (1 - text_alpha_mask)
side_alpha_3ch = np.stack([side_alpha, side_alpha, side_alpha], axis=2)
day_f = day_f * (1 - side_alpha_3ch) + side_layer_bgr.astype(np.float32) * side_alpha_3ch
```

**결과:** ❌ 여전히 문제 지속

---

### 시도 3: Transparency Mask 예외 처리 (검정 배경 투명 문제 해결)

**위치:** `main.py` 1410-1413줄

**변경 내용:**
- 전면프레임은 `transparency_mask`를 적용하지 않음 (검정 배경이 투명해지는 문제 방지)

**코드:**
```python
# 전면프레임은 배경이 있을 수 있으므로 transparency_mask 적용 안 함
if installation_type == "전면프레임":
    # 전면프레임: 배경이 있으므로 투명도 마스크 사용 안 함 (전체 간판 영역 사용)
    combined_mask = mask
else:
    # 프레임바/맨벽: 검은색 마스크 생성 (밝기 임계값) - 투명 배경 처리
    gray_sign = cv2.cvtColor(warped_sign, cv2.COLOR_BGR2GRAY)
    brightness_threshold = 30  # 밝기 30 이하는 투명으로 처리
    transparency_mask = (gray_sign > brightness_threshold).astype(np.float32)
    transparency_mask = np.stack([transparency_mask, transparency_mask, transparency_mask], axis=2)
    combined_mask = mask * transparency_mask
```

**결과:** ❌ 여전히 모든 문제 지속 (검정 배경 투명, 흰색 배경 글자색 문제 모두 미해결)

---

### 시도 4: 채널별 반복문 방식으로 변경 (사용자 제안)

**위치:** `main.py` 1073-1108줄

**변경 내용:**
- 3채널을 한 번에 스택으로 처리하는 방식에서 채널별로 반복문을 사용하는 방식으로 변경
- 레이어 순서를 명확히 하여 앞면이 마지막에 불투명하게 덮어쓰도록 수정

**코드:**
```python
if installation_type == "전면프레임":
    # 1. 빈 캔버스 (배경색으로 초기화)
    canvas = day_result.astype(np.float32)
    
    # 2. 그림자 레이어 (알파 40%)
    shadow_alpha = shadow_layer_rgba[:, :, 3].astype(np.float32) / 255.0 * 0.4
    for c in range(3):
        canvas[:, :, c] = (
            canvas[:, :, c] * (1 - shadow_alpha) + 
            shadow_layer_bgr[:, :, c].astype(np.float32) * shadow_alpha
        )
    
    # 3. 옆면 레이어 (앞면 영역 제외)
    side_alpha = side_layer_rgba[:, :, 3].astype(np.float32) / 255.0
    text_mask = text_layer_rgba[:, :, 3].astype(np.float32) / 255.0
    
    # 앞면이 있는 곳은 옆면 알파를 0으로
    side_alpha_adjusted = side_alpha * (1 - text_mask)
    
    for c in range(3):
        canvas[:, :, c] = (
            canvas[:, :, c] * (1 - side_alpha_adjusted) + 
            side_layer_bgr[:, :, c].astype(np.float32) * side_alpha_adjusted
        )
    
    # 4. 앞면 레이어 (불투명, 마지막)
    text_alpha = text_layer_rgba[:, :, 3].astype(np.float32) / 255.0
    
    for c in range(3):
        # 앞면은 100% 불투명하게 덮어쓰기
        canvas[:, :, c] = (
            canvas[:, :, c] * (1 - text_alpha) + 
            text_layer_bgr[:, :, c].astype(np.float32) * text_alpha
        )
    
    day_result = np.clip(canvas, 0, 255).astype(np.uint8)
```

**결과:** ❌ 여전히 글자색이 빨강으로 보이지 않음

---

### 시도 5: add_3d_depth 함수 적용 제외

**위치:** `main.py` 1110-1111줄, 1124-1128줄

**변경 내용:**
- 전면프레임에서 `add_3d_depth` 함수를 호출하지 않도록 수정
- `add_3d_depth`가 이미 블렌딩된 결과를 다시 처리하면서 색상을 변형시킬 수 있음

**코드:**
```python
# 전면프레임 블록 안에서
day_result = np.clip(canvas, 0, 255).astype(np.uint8)

# 전면프레임은 add_3d_depth를 적용하지 않음 (이미 블렌딩 완료)
# add_3d_depth가 색상을 변형시킬 수 있으므로 스킵

# else 블록 (맨벽/프레임바)에서
# 맨벽/프레임바는 입체감 추가
if installation_type == "프레임바":
    day_result = add_3d_depth(day_result, depth=5)
elif installation_type == "맨벽":
    day_result = add_3d_depth(day_result, depth=5)
```

**결과:** ❌ 여전히 문제 지속

---

## 현재 코드 상태

**전면프레임-전광채널 텍스트 블렌딩 코드 (main.py 1073-1108줄):**

```python
if installation_type == "전면프레임":
    # 1. 빈 캔버스 (배경색으로 초기화)
    canvas = day_result.astype(np.float32)
    
    # 2. 그림자 레이어 (알파 40%)
    shadow_alpha = shadow_layer_rgba[:, :, 3].astype(np.float32) / 255.0 * 0.4
    for c in range(3):
        canvas[:, :, c] = (
            canvas[:, :, c] * (1 - shadow_alpha) + 
            shadow_layer_bgr[:, :, c].astype(np.float32) * shadow_alpha
        )
    
    # 3. 옆면 레이어 (앞면 영역 제외)
    side_alpha = side_layer_rgba[:, :, 3].astype(np.float32) / 255.0
    text_mask = text_layer_rgba[:, :, 3].astype(np.float32) / 255.0
    
    # 앞면이 있는 곳은 옆면 알파를 0으로
    side_alpha_adjusted = side_alpha * (1 - text_mask)
    
    for c in range(3):
        canvas[:, :, c] = (
            canvas[:, :, c] * (1 - side_alpha_adjusted) + 
            side_layer_bgr[:, :, c].astype(np.float32) * side_alpha_adjusted
        )
    
    # 4. 앞면 레이어 (불투명, 마지막)
    text_alpha = text_layer_rgba[:, :, 3].astype(np.float32) / 255.0
    
    for c in range(3):
        # 앞면은 100% 불투명하게 덮어쓰기
        canvas[:, :, c] = (
            canvas[:, :, c] * (1 - text_alpha) + 
            text_layer_bgr[:, :, c].astype(np.float32) * text_alpha
        )
    
    day_result = np.clip(canvas, 0, 255).astype(np.uint8)
    
    # 전면프레임은 add_3d_depth를 적용하지 않음 (이미 블렌딩 완료)
```

**텍스트 레이어 생성 코드 (main.py 1050-1054줄):**

```python
if sign_type == "전광채널":
    # 1) 텍스트 앞면(원본 색상)
    text_layer_rgba = extract_text_layer(text_to_render, font, text_rgb, (width, height), position)
    text_layer_bgr = cv2.cvtColor(text_layer_rgba, cv2.COLOR_RGBA2BGR)
```

**text_rgb 계산 코드 (main.py 1033줄):**

```python
text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
```

**hex_to_rgb 함수 (main.py 109-112줄):**

```python
def hex_to_rgb(hex_color: str) -> tuple:
    """Hex 색상을 RGB 튜플로 변환"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
```

**extract_text_layer 함수 (main.py 114-141줄):**

```python
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
        return np.array(text_img)
```

---

## 요약

1. ❌ **검정 배경 투명 문제**: transparency_mask 예외 처리 시도했으나 여전히 해결되지 않음
2. ❌ **흰색 배경에서 글자색 문제**: 모든 시도에도 불구하고 여전히 빨강으로 보이지 않음
3. ❌ **글자 떠보이는 문제**: 여전히 지속

**핵심 문제:** 
- 흰색 배경 + 빨강 글자 (#ff0000) 조합에서 글자가 빨강으로 표시되지 않음
- 검정 배경에서 글자가 투명해짐
- 모든 배경색에서 글자색이 제대로 반영되지 않음

**의심되는 원인:**
- `text_layer_bgr`의 색상 값 자체가 잘못되었을 가능성
- RGB → BGR 변환 과정에서 문제가 있을 가능성
- 블렌딩 공식에 문제가 있을 가능성
- 다른 곳에서 색상이 덮어씌워지고 있을 가능성

