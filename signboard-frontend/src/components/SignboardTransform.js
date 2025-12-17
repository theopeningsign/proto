import React, { useState, useRef, useEffect } from 'react';

const SignboardTransform = ({ 
  signboards = [], 
  originalSignboards = [],
  imageSize = { width: 1, height: 1 },
  selectedArea = null,
  textSizeInfo = null,
  onTransformChange,
  onApply,
  onSelectSignboard
}) => {
  const [selectedId, setSelectedId] = useState(null);
  const [transforms, setTransforms] = useState({});
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState(null); // 'move', 'resize', 'rotate'
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const prevFontSizesRef = useRef({}); // 이전 fontSize 추적

  // 각 간판의 초기 변환 상태 설정 - imageSize 기준 퍼센트로 저장
  // 현재 fontSize에 맞춰 박스 크기를 조정
  useEffect(() => {
    if (imageSize.width === 1 || imageSize.height === 1) return; // 이미지 크기가 아직 로드되지 않음
    
    const initialTransforms = {};
    let hasChanges = false;
    
    signboards.forEach((signboard) => {
      const existingTransform = transforms[signboard.id];
      const points = signboard.polygon_points || [];
      
      if (points.length >= 4) {
        // originalSignboards에서 현재 fontSize와 originalFontSize 가져오기
        const originalSignboard = originalSignboards.find(s => s.id === signboard.id);
        const currentFontSize = originalSignboard?.formData?.fontSize || 100;
        const storedOriginalFontSize = originalSignboard?.formData?.originalFontSize || currentFontSize;
        const prevFontSize = prevFontSizesRef.current[signboard.id];
        
        // 기존 transform이 있고, fontSize가 실제로 변경되었다면 박스 크기를 비례 조정
        if (existingTransform && prevFontSize && Math.abs(prevFontSize - currentFontSize) > 0.1) {
          // fontSize 비율 계산
          const fontSizeRatio = currentFontSize / prevFontSize;
          
          // 기존 박스 크기에 비율 적용
          const adjustedWidth = existingTransform.width * fontSizeRatio;
          const adjustedHeight = existingTransform.height * fontSizeRatio;
          
          initialTransforms[signboard.id] = {
            ...existingTransform,
            width: adjustedWidth,
            height: adjustedHeight,
            fontSize: currentFontSize
          };
          prevFontSizesRef.current[signboard.id] = currentFontSize;
          hasChanges = true;
        } else if (!existingTransform) {
          // 처음 초기화하는 경우 - 폴리곤 점으로부터 박스 크기 계산
          const xs = points.map(p => p[0]);
          const ys = points.map(p => p[1]);
          const minX = Math.min(...xs);
          const maxX = Math.max(...xs);
          const minY = Math.min(...ys);
          const maxY = Math.max(...ys);
          
          const centerX = (minX + maxX) / 2;
          const centerY = (minY + maxY) / 2;
          const baseWidth = maxX - minX;
          const baseHeight = maxY - minY;
          
          // 원본 fontSize 저장 (formData에서 가져오거나, 없으면 현재 fontSize 사용)
          const originalFontSize = storedOriginalFontSize;

          // 현재 fontSize가 원본 fontSize에서 얼마나 달라졌는지 비율 계산
          // 예) originalFontSize=100, currentFontSize=80 이면 ratio=0.8 → 박스도 0.8배
          const fontSizeRatio = originalFontSize !== 0 ? (currentFontSize / originalFontSize) : 1;
          
          // 박스 크기를 간판 영역(baseWidth/Height)에 fontSize 비율을 곱해서 설정
          const adjustedBaseWidth = baseWidth * fontSizeRatio;
          const adjustedBaseHeight = baseHeight * fontSizeRatio;
          
          initialTransforms[signboard.id] = {
            x: (centerX / imageSize.width) * 100,
            y: (centerY / imageSize.height) * 100,
            width: (adjustedBaseWidth / imageSize.width) * 100,
            height: (adjustedBaseHeight / imageSize.height) * 100,
            rotation: 0,
            scale: 1,
            fontSize: currentFontSize,
            originalFontSize: originalFontSize, // 원본 fontSize 저장 (기준값)
            originalWidth: baseWidth,           // 기준이 되는 원래 간판 영역 너비
            originalHeight: baseHeight          // 기준이 되는 원래 간판 영역 높이
          };
          prevFontSizesRef.current[signboard.id] = currentFontSize;
          hasChanges = true;
        } else {
          // existingTransform이 있고, 간판 편집을 다시 열었을 때
          // 사용자가 직접 조절한 박스 크기를 보존해야 함
          
          // fontSize가 변경되었을 때만 박스 크기를 재계산
          // (prevFontSize와 비교하여 실제로 변경되었는지 확인)
          if (prevFontSize && Math.abs(prevFontSize - currentFontSize) > 0.1) {
            // prevFontSize가 있고, fontSize가 변경되었을 때만 재계산
            const fontSizeRatio = currentFontSize / prevFontSize;
            
            // 기존 박스 크기에 비율 적용 (사용자가 조절한 크기를 기준으로)
            const adjustedWidth = existingTransform.width * fontSizeRatio;
            const adjustedHeight = existingTransform.height * fontSizeRatio;
            
            initialTransforms[signboard.id] = {
              ...existingTransform,
              width: adjustedWidth,
              height: adjustedHeight,
              fontSize: currentFontSize
            };
            prevFontSizesRef.current[signboard.id] = currentFontSize;
            hasChanges = true;
          } else {
            // fontSize가 변경되지 않았거나, prevFontSize가 없는 경우
            // 사용자가 조절한 박스 크기를 그대로 유지 (width/height는 건드리지 않음)
            
            // originalWidth/Height가 없으면 설정만 하고, width/height는 유지
            if (!existingTransform.originalWidth || !existingTransform.originalHeight) {
              const baseWidth = existingTransform.width * imageSize.width / 100;
              const baseHeight = existingTransform.height * imageSize.height / 100;
              initialTransforms[signboard.id] = {
                ...existingTransform, // 기존 width/height 그대로 유지
                originalWidth: baseWidth,
                originalHeight: baseHeight,
                originalFontSize: storedOriginalFontSize
              };
              hasChanges = true;
            } else {
              // originalWidth/Height가 이미 있으면 아무것도 하지 않음
              // 사용자가 조절한 박스 크기를 그대로 유지
            }
            
            if (!prevFontSize) {
              // transform은 있지만 prevFontSize가 없는 경우 (첫 렌더링)
              prevFontSizesRef.current[signboard.id] = currentFontSize;
            }
          }
        }
      }
    });
    
    // 변경사항이 있을 때만 업데이트 (무한 루프 방지)
    if (hasChanges && Object.keys(initialTransforms).length > 0) {
      setTransforms(prev => ({ ...prev, ...initialTransforms }));
    }
  }, [signboards, imageSize, originalSignboards]); // transforms를 의존성에서 제거하여 무한 루프 방지

  const getTransform = (id) => {
    return transforms[id] || { x: 0, y: 0, width: 100, height: 100, rotation: 0, scale: 1, fontSize: 100 };
  };

  const updateTransform = (id, updates) => {
    const newTransforms = {
      ...transforms,
      [id]: { ...getTransform(id), ...updates }
    };
    setTransforms(newTransforms);
    if (onTransformChange) {
      onTransformChange(newTransforms);
    }
  };

  const handleMouseDown = (e, id, mode) => {
    e.stopPropagation();
    setSelectedId(id);
    setIsDragging(true);
    setDragMode(mode);
    
    const rect = containerRef.current.getBoundingClientRect();
    // 퍼센트로 계산
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    
    setDragStart({ x, y, transform: getTransform(id) });
  };

  const handleMouseMove = (e) => {
    if (!isDragging || selectedId === null) return;

    const rect = containerRef.current.getBoundingClientRect();
    // 퍼센트로 계산
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    
    const dx = x - dragStart.x;
    const dy = y - dragStart.y;
    const transform = dragStart.transform;

    if (dragMode === 'move') {
      // 박스 이동: 박스 중심을 기준으로 텍스트 위치(textPositionX/Y) 재계산
      const newX = transform.x + dx;
      const newY = transform.y + dy;

      // 이미지 좌표계에서 박스 중심 (px)
      const boxCenterX = (newX / 100) * imageSize.width;
      const boxCenterY = (newY / 100) * imageSize.height;

      // 간판 영역(노란 박스) 계산 (px)
      let signboardX = 0;
      let signboardY = 0;
      let signboardWidth = imageSize.width;
      let signboardHeight = imageSize.height;

      if (selectedArea) {
        if (selectedArea.type === 'polygon' && selectedArea.points.length >= 4) {
          const xs = selectedArea.points.map(p => p.x);
          const ys = selectedArea.points.map(p => p.y);
          signboardX = Math.min(...xs);
          signboardY = Math.min(...ys);
          signboardWidth = Math.max(...xs) - signboardX;
          signboardHeight = Math.max(...ys) - signboardY;
        } else if (selectedArea.x !== undefined) {
          signboardX = selectedArea.x;
          signboardY = selectedArea.y;
          signboardWidth = selectedArea.width;
          signboardHeight = selectedArea.height;
        }
      }

      // 간판 영역 내에서의 텍스트 중심 위치 (px)
      const textCenterX = boxCenterX - signboardX;
      const textCenterY = boxCenterY - signboardY;

      // 간판 영역 내에서 0~100% 기준의 textPositionX/Y 계산
      // ※ 실제 텍스트 크기를 정확히 아는 경우에도, 사용자가 느끼기에
      //   "박스 중심이 간판 안에서 어디쯤이냐"가 더 직관적이어서
      //   텍스트 크기를 빼지 않고 단순 비율로 계산한다.
      let textPositionX = (signboardWidth > 0)
        ? (textCenterX / signboardWidth) * 100
        : 50;
      let textPositionY = (signboardHeight > 0)
        ? (textCenterY / signboardHeight) * 100
        : 50;

      // 0~100% 범위로 클램프
      textPositionX = Math.max(0, Math.min(100, textPositionX));
      textPositionY = Math.max(0, Math.min(100, textPositionY));

      updateTransform(selectedId, {
        x: newX,
        y: newY,
        textPositionX,
        textPositionY,
        // originalWidth/Height와 originalFontSize는 유지 (기준값)
        originalWidth: transform.originalWidth,
        originalHeight: transform.originalHeight,
        originalFontSize: transform.originalFontSize
      });
    } else if (dragMode === 'resize-se') {
      // 오른쪽 아래 모서리 - 퍼센트로 계산
      const newWidth = Math.max(2, transform.width + dx); // 최소 2%
      const newHeight = Math.max(2, transform.height + dy); // 최소 2%
      
      // 크기 변경 비율 계산 (fontSize 조정용)
      const widthScale = newWidth / transform.width;
      const heightScale = newHeight / transform.height;
      const avgScale = (widthScale + heightScale) / 2;
      
      // fontSize도 비례 조정
      const currentFontSize = transform.fontSize || 100;
      const newFontSize = Math.max(30, Math.min(200, currentFontSize * avgScale));
      
      updateTransform(selectedId, {
        width: newWidth,
        height: newHeight,
        x: transform.x + dx / 2,
        y: transform.y + dy / 2,
        fontSize: newFontSize, // fontSize도 함께 업데이트
        // originalWidth/Height와 originalFontSize는 유지 (기준값)
        originalWidth: transform.originalWidth,
        originalHeight: transform.originalHeight,
        originalFontSize: transform.originalFontSize
      });
    } else if (dragMode === 'rotate') {
      // 회전
      const centerX = transform.x;
      const centerY = transform.y;
      const angle = Math.atan2(y - centerY, x - centerX) * (180 / Math.PI);
      updateTransform(selectedId, {
        rotation: angle,
        // originalWidth/Height와 originalFontSize는 유지 (기준값)
        originalWidth: transform.originalWidth,
        originalHeight: transform.originalHeight,
        originalFontSize: transform.originalFontSize
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragMode(null);
  };

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, selectedId, dragStart]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 100 }}
      onClick={() => setSelectedId(null)}
    >
      {signboards.map((signboard) => {
        const transform = getTransform(signboard.id);
        const isSelected = selectedId === signboard.id;
        
        // transform이 이미 퍼센트로 저장되어 있음
        const leftPercent = transform.x - transform.width / 2;
        const topPercent = transform.y - transform.height / 2;
        const widthPercent = transform.width;
        const heightPercent = transform.height;

        return (
          <div
            key={signboard.id}
            style={{
              position: 'absolute',
              left: `${leftPercent}%`,
              top: `${topPercent}%`,
              width: `${widthPercent}%`,
              height: `${heightPercent}%`,
              transform: `rotate(${transform.rotation}deg)`,
              transformOrigin: 'center',
              border: isSelected ? '2px solid #3B82F6' : '2px dashed rgba(255,255,255,0.3)',
              cursor: 'move',
              pointerEvents: 'auto',
              zIndex: isSelected ? 10 : 1
            }}
            onMouseDown={(e) => handleMouseDown(e, signboard.id, 'move')}
            onClick={(e) => {
              e.stopPropagation();
              setSelectedId(signboard.id);
            }}
          >
            {/* 간판 정보 표시 */}
            <div className="absolute -top-6 left-0 bg-blue-500 text-white text-xs px-2 py-1 rounded whitespace-nowrap">
              {signboard.text || `간판 ${signboard.id + 1}`}
            </div>

            {/* Transform 핸들들 */}
            {isSelected && (
              <>
                {/* 모서리 핸들 (크기 조절) */}
                <div
                  className="absolute -right-2 -bottom-2 w-4 h-4 bg-blue-500 rounded-full cursor-se-resize"
                  onMouseDown={(e) => handleMouseDown(e, signboard.id, 'resize-se')}
                />
                
                {/* 회전 핸들 */}
                <div
                  className="absolute -top-8 left-1/2 -translate-x-1/2 w-4 h-4 bg-green-500 rounded-full cursor-grab"
                  onMouseDown={(e) => handleMouseDown(e, signboard.id, 'rotate')}
                />
              </>
            )}
          </div>
        );
      })}

      {/* Transform 정보는 상위 컴포넌트로 전달 */}
    </div>
  );
};

export default SignboardTransform;

