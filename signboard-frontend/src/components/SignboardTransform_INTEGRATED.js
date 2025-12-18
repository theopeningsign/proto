// 간판편집에 상호 위치 이동 통합 버전
// 이 파일은 검수용이며, 실제 적용은 SignboardTransform.js에 반영 예정

import React, { useState, useRef, useEffect } from 'react';

const SignboardTransform = ({ 
  signboards = [], 
  originalSignboards = [],
  imageSize = { width: 1, height: 1 },
  selectedArea = null,  // 추가: 간판 영역 정보
  textSizeInfo = null,  // 추가: 텍스트 크기 정보 (선택적)
  onTransformChange,
  onApply,
  onSelectSignboard
}) => {
  const [selectedId, setSelectedId] = useState(null);
  const [transforms, setTransforms] = useState({});
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const prevFontSizesRef = useRef({});

  // ... (기존 useEffect 로직은 동일) ...

  const handleMouseMove = (e) => {
    if (!isDragging || selectedId === null) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    
    const dx = x - dragStart.x;
    const dy = y - dragStart.y;
    const transform = dragStart.transform;

    if (dragMode === 'move') {
      // 박스 위치 업데이트
      const newX = transform.x + dx;
      const newY = transform.y + dy;
      
      // 텍스트 위치 계산 (selectedArea가 있을 때만)
      let textPositionX = transform.textPositionX;
      let textPositionY = transform.textPositionY;
      
      if (selectedArea && imageSize.width > 1 && imageSize.height > 1) {
        // 박스 중심 위치를 이미지 좌표로 변환
        const boxCenterX = (newX / 100) * imageSize.width;
        const boxCenterY = (newY / 100) * imageSize.height;
        
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
        
        // 텍스트 크기 계산
        let textWidth, textHeight;
        if (textSizeInfo && textSizeInfo.text_width && textSizeInfo.text_height) {
          // 백엔드에서 받은 정확한 크기 사용
          const scaleX = imageSize.width / textSizeInfo.signboard_width;
          const scaleY = imageSize.height / textSizeInfo.signboard_height;
          textWidth = textSizeInfo.text_width * scaleX;
          textHeight = textSizeInfo.text_height * scaleY;
        } else {
          // 폴백: fontSize 기반 추정
          const currentFontSize = transform.fontSize || 100;
          const baseRatio = Math.sqrt(currentFontSize / 100);
          textWidth = signboardWidth * 0.5 * baseRatio;
          textHeight = signboardHeight * 0.4 * baseRatio;
        }
        
        // 간판 영역 내에서의 텍스트 중심 위치
        const textCenterX = boxCenterX - signboardX;
        const textCenterY = boxCenterY - signboardY;
        
        // textPositionX/Y 계산 (0-100%)
        const availableWidth = signboardWidth - textWidth;
        const availableHeight = signboardHeight - textHeight;
        
        textPositionX = availableWidth > 0 
          ? ((textCenterX - textWidth / 2) / availableWidth) * 100 
          : 50;
        textPositionY = availableHeight > 0 
          ? ((textCenterY - textHeight / 2) / availableHeight) * 100 
          : 50;
        
        // 0-100% 범위로 제한
        textPositionX = Math.max(0, Math.min(100, textPositionX));
        textPositionY = Math.max(0, Math.min(100, textPositionY));
      }
      
      updateTransform(selectedId, {
        x: newX,
        y: newY,
        textPositionX: textPositionX,
        textPositionY: textPositionY,
        originalWidth: transform.originalWidth,
        originalHeight: transform.originalHeight,
        originalFontSize: transform.originalFontSize
      });
    } else if (dragMode === 'resize-se') {
      // ... (기존 resize 로직 동일) ...
    } else if (dragMode === 'rotate') {
      // ... (기존 rotate 로직 동일) ...
    }
  };

  // ... (나머지 코드는 동일) ...
};

export default SignboardTransform;
