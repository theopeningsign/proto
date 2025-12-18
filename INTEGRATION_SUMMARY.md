# 간판편집에 상호 위치 이동 통합 - 구현 계획

## 개요
간판편집(파란색 박스)에서 박스 이동 시 텍스트 위치만 변경하도록 통합

## 수정할 파일

### 1. SignboardTransform.js
**변경사항:**
- Props 추가: `selectedArea`, `textSizeInfo`
- `handleMouseMove`의 `move` 모드에서 `textPositionX/Y` 계산 추가
- 초기화 시 `textPositionX/Y` 설정

**핵심 로직:**
```javascript
// 박스 중심을 이미지 좌표로 변환
const boxCenterX = (newX / 100) * imageSize.width;
const boxCenterY = (newY / 100) * imageSize.height;

// 간판 영역 내에서의 텍스트 중심 위치
const textCenterX = boxCenterX - signboardX;
const textCenterY = boxCenterY - signboardY;

// textPositionX/Y 계산 (0-100%)
const availableWidth = signboardWidth - textWidth;
const availableHeight = signboardHeight - textHeight;

textPositionX = availableWidth > 0 
  ? ((textCenterX - textWidth / 2) / availableWidth) * 100 
  : 50;
```

### 2. ResultViewer.js
**변경사항:**
- `SignboardTransform`에 `selectedArea={selectedArea}` 추가
- `SignboardTransform`에 `textSizeInfo={textSizeInfo}` 추가

### 3. App.js
**변경사항:**
- `onRegenerateWithTransforms`에서 `textPositionX/Y` 처리 추가

```javascript
if (transform.textPositionX !== undefined) {
  updatedFormData.textPositionX = transform.textPositionX;
}
if (transform.textPositionY !== undefined) {
  updatedFormData.textPositionY = transform.textPositionY;
}
```

## 검수 포인트

1. **좌표 변환 정확도**
   - 박스 중심 → 이미지 좌표 변환
   - 간판 영역 기준 변환
   - 텍스트 크기 계산

2. **텍스트 크기 계산**
   - `textSizeInfo` 우선 사용
   - 없으면 `fontSize` 기반 추정

3. **경계 처리**
   - 0-100% 범위 제한
   - 간판 영역 밖으로 나가는 경우 처리

4. **초기화**
   - `textPositionX/Y` 초기값 설정
   - `formData`에서 가져오기

## 예상 문제점

1. **좌표 변환 오차**
   - 줌/팬이 적용된 상태에서의 정확도
   - 퍼센트 ↔ 픽셀 변환 정확도

2. **텍스트 크기 추정**
   - `textSizeInfo`가 없을 때의 추정 정확도
   - `fontSize`와 실제 텍스트 크기 차이

3. **상태 동기화**
   - `transforms` 상태와 `formData` 동기화
   - 적용하기 후 재생성 시 상태 관리

## 테스트 시나리오

1. 박스 이동 → 텍스트 위치 변경 확인
2. 박스 크기 조절 → 글자 크기 변경 확인
3. 회전 → 텍스트 회전 확인
4. 적용하기 → 재생성 후 위치 유지 확인
5. 다시 간판편집 열기 → 박스 위치 정확도 확인
