# 간판편집에 상호 위치 이동 통합 계획

## 목표
간판편집(파란색 박스)에서 박스 이동 시 텍스트 위치만 변경하도록 통합

## 현재 구조
- `SignboardTransform`: 간판편집 박스 (크기, 회전, 이동)
- `ResultViewer`: 상호 위치 편집 (보라색 박스, 별도 기능)

## 수정 계획

### 1. SignboardTransform.js 수정

**추가할 props:**
```javascript
selectedArea: null,  // 간판 영역 정보
imageSize: { width: 1, height: 1 },  // 이미지 크기
textSizeInfo: null  // 텍스트 크기 정보 (선택적)
```

**박스 이동 시 텍스트 위치 계산:**
```javascript
if (dragMode === 'move') {
  // 박스 중심 위치를 이미지 좌표로 변환
  const boxCenterX = (transform.x / 100) * imageSize.width;
  const boxCenterY = (transform.y / 100) * imageSize.height;
  
  // 간판 영역 계산
  let signboardX, signboardY, signboardWidth, signboardHeight;
  if (selectedArea.type === 'polygon' && selectedArea.points.length >= 4) {
    const xs = selectedArea.points.map(p => p.x);
    const ys = selectedArea.points.map(p => p.y);
    signboardX = Math.min(...xs);
    signboardY = Math.min(...ys);
    signboardWidth = Math.max(...xs) - signboardX;
    signboardHeight = Math.max(...ys) - signboardY;
  } else {
    signboardX = selectedArea.x;
    signboardY = selectedArea.y;
    signboardWidth = selectedArea.width;
    signboardHeight = selectedArea.height;
  }
  
  // 텍스트 크기 계산 (textSizeInfo 또는 추정)
  let textWidth, textHeight;
  if (textSizeInfo && textSizeInfo.text_width && textSizeInfo.text_height) {
    const scaleX = imageSize.width / textSizeInfo.signboard_width;
    const scaleY = imageSize.height / textSizeInfo.signboard_height;
    textWidth = textSizeInfo.text_width * scaleX;
    textHeight = textSizeInfo.text_height * scaleY;
  } else {
    // 폴백: 현재 fontSize 기반 추정
    const currentFontSize = transform.fontSize || 100;
    textWidth = signboardWidth * 0.5 * Math.sqrt(currentFontSize / 100);
    textHeight = signboardHeight * 0.4 * Math.sqrt(currentFontSize / 100);
  }
  
  // 간판 영역 내에서의 텍스트 중심 위치
  const textCenterX = boxCenterX - signboardX;
  const textCenterY = boxCenterY - signboardY;
  
  // textPositionX/Y 계산 (0-100%)
  const availableWidth = signboardWidth - textWidth;
  const availableHeight = signboardHeight - textHeight;
  
  const textPositionX = availableWidth > 0 
    ? ((textCenterX - textWidth / 2) / availableWidth) * 100 
    : 50;
  const textPositionY = availableHeight > 0 
    ? ((textCenterY - textHeight / 2) / availableHeight) * 100 
    : 50;
  
  // 0-100% 범위로 제한
  const clampedX = Math.max(0, Math.min(100, textPositionX));
  const clampedY = Math.max(0, Math.min(100, textPositionY));
  
  updateTransform(selectedId, {
    x: transform.x + dx,
    y: transform.y + dy,
    textPositionX: clampedX,
    textPositionY: clampedY,
    originalWidth: transform.originalWidth,
    originalHeight: transform.originalHeight,
    originalFontSize: transform.originalFontSize
  });
}
```

### 2. ResultViewer.js 수정

**SignboardTransform에 props 전달:**
```javascript
<SignboardTransform
  key={`${originalSignboards[0]?.formData?.fontSize || 100}-${originalSignboards[0]?.formData?.rotation || 0}`}
  signboards={...}
  originalSignboards={originalSignboards}
  imageSize={imageSize}
  selectedArea={selectedArea}  // 추가
  textSizeInfo={textSizeInfo}  // 추가 (선택적)
  onTransformChange={setPendingTransforms}
  onApply={handleApplyTransforms}
/>
```

### 3. App.js 수정

**onRegenerateWithTransforms에서 textPositionX/Y 처리:**
```javascript
if (transform.textPositionX !== undefined) {
  updatedFormData.textPositionX = transform.textPositionX;
}
if (transform.textPositionY !== undefined) {
  updatedFormData.textPositionY = transform.textPositionY;
}
```

## 장점
1. 하나의 인터페이스로 모든 조절 가능
2. 기존 간판편집 드래그 로직 재사용 (이미 작동함)
3. 코드 중복 감소

## 주의사항
1. 좌표 변환 정확도 확인 필요
2. 간판 영역 밖으로 나가는 경우 처리
3. 텍스트 크기 계산 정확도
