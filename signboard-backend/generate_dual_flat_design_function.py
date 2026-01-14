# 이 파일은 generate_dual_flat_design 함수의 코드입니다.
# main.py에 추가할 함수 코드입니다.

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
    
    Returns:
        (design_only_image, with_context_image, dimensions_dict)
        - design_only_image: 흰색 배경 + 간판만 (BGR)
        - with_context_image: 건물 외벽 + 간판 합성 (BGR)
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
    
    # 알파 블렌딩 (text_layer가 있으면 사용)
    if text_layer is not None:
        # text_layer를 간판 크기에 맞게 리사이즈
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
        # text_layer 사용 (알파 채널)
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
        tip_length = 0.04  # Gemini 제안: 0.04로 증가
        
        # 치수선 오프셋 (프레임 외부)
        dim_offset = 15  # 프레임에서 15px 떨어진 곳에 그리기
        
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
