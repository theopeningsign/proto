import React, { useState, useRef, useEffect } from 'react';

const SignboardTransform = ({ 
  signboards = [], 
  originalSignboards = [],
  imageSize = { width: 1, height: 1 },
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
          
          initialTransforms[signboard.id] = {
            x: (centerX / imageSize.width) * 100,
            y: (centerY / imageSize.height) * 100,
            width: (baseWidth / imageSize.width) * 100,
            height: (baseHeight / imageSize.height) * 100,
            rotation: 0,
            scale: 1,
            fontSize: currentFontSize,
            originalFontSize: originalFontSize, // 원본 fontSize 저장
            originalWidth: baseWidth,
            originalHeight: baseHeight
          };
          prevFontSizesRef.current[signboard.id] = currentFontSize;
          hasChanges = true;
        } else {
          // existingTransform이 있고, 간판 편집을 다시 열었을 때
          // storedOriginalFontSize (formData에서 가져온 원본) 대비 현재 fontSize의 비율로 박스 크기 재계산
          if (Math.abs(storedOriginalFontSize - currentFontSize) > 0.1) {
            const fontSizeRatio = currentFontSize / storedOriginalFontSize;
            
            // 원본 박스 크기 (originalWidth, originalHeight 기준)에 비율 적용
            const baseWidth = existingTransform.originalWidth || (existingTransform.width * imageSize.width / 100);
            const baseHeight = existingTransform.originalHeight || (existingTransform.height * imageSize.height / 100);
            
            const adjustedWidth = (baseWidth * fontSizeRatio / imageSize.width) * 100;
            const adjustedHeight = (baseHeight * fontSizeRatio / imageSize.height) * 100;
            
            initialTransforms[signboard.id] = {
              ...existingTransform,
              width: adjustedWidth,
              height: adjustedHeight,
              fontSize: currentFontSize,
              originalFontSize: storedOriginalFontSize // formData의 originalFontSize 유지
            };
            prevFontSizesRef.current[signboard.id] = currentFontSize;
            hasChanges = true;
          } else if (!prevFontSize) {
            // transform은 있지만 prevFontSize가 없는 경우 (첫 렌더링)
            prevFontSizesRef.current[signboard.id] = currentFontSize;
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
      updateTransform(selectedId, {
        x: transform.x + dx,
        y: transform.y + dy
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
        fontSize: newFontSize // fontSize도 함께 업데이트
      });
    } else if (dragMode === 'rotate') {
      // 회전
      const centerX = transform.x;
      const centerY = transform.y;
      const angle = Math.atan2(y - centerY, x - centerX) * (180 / Math.PI);
      updateTransform(selectedId, {
        rotation: angle
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

