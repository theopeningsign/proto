import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import SignboardTransform from './SignboardTransform';

const ResultViewer = ({ results, loading, lights = [], onLightsChange = () => {}, lightsEnabled = true, onToggleEnabled = () => {}, onApplyLights = () => {}, originalSignboards = [], onRegenerateWithTransforms = () => {}, onApplyTextPositions = () => {}, selectedArea = null, textSizeInfo = null }) => {
  const [viewMode, setViewMode] = useState('day'); // 'day' | 'night'
  const [selectedLightId, setSelectedLightId] = useState(null);
  const [showTransform, setShowTransform] = useState(false);
  const [showTextEdit, setShowTextEdit] = useState(false);
  const [textPositions, setTextPositions] = useState({});
  const [draggingTextId, setDraggingTextId] = useState(null);
  const [imageSize, setImageSize] = useState({ width: 1, height: 1 });
  const containerRef = useRef(null);
  const draggingRef = useRef(null);
  const originalSignboardsRef = useRef(originalSignboards);
  const draggingTextIdRef = useRef(null); // 드래그 중인 ID를 ref로도 저장
  const imageRef = useRef(null);
  const scaleRef = useRef(1);
  const offsetRef = useRef({ x: 0, y: 0 });
  const selectedAreaRef = useRef(selectedArea);
  const imageSizeRef = useRef(imageSize);
  const textSizeInfoRef = useRef(textSizeInfo);
  
  // 줌/팬 기능
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // Helper: update lights safely
  const updateLight = (id, updates) => {
    onLightsChange(lights.map(l => (l.id === id ? { ...l, ...updates } : l)));
  };

  // 줌/팬 핸들러 - ImageUploader와 동일한 방식
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const container = containerRef.current;
    if (!container) return;
    
    const rect = container.getBoundingClientRect();
    const mouseX = e.clientX === 0 ? rect.width / 2 : e.clientX - rect.left;
    const mouseY = e.clientY === 0 ? rect.height / 2 : e.clientY - rect.top;
    
    // 줌 전 마우스 위치의 이미지 좌표
    const imageX = (mouseX - offset.x) / scale;
    const imageY = (mouseY - offset.y) / scale;
    
    // 줌 배율 계산 (최소 0.1배, 최대 10배)
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.1, Math.min(10, scale * delta));
    
    // 줌 후 마우스 위치가 같은 이미지 좌표를 가리키도록 offset 조정
    const newOffsetX = mouseX - imageX * newScale;
    const newOffsetY = mouseY - imageY * newScale;
    
    setScale(newScale);
    setOffset({ x: newOffsetX, y: newOffsetY });
    scaleRef.current = newScale;
    offsetRef.current = { x: newOffsetX, y: newOffsetY };
  }, [scale, offset]);

  const handleResetZoom = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
    scaleRef.current = 1;
    offsetRef.current = { x: 0, y: 0 };
  };

  const handlePanStart = (e) => {
    if (e.button === 2 || e.ctrlKey) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      e.preventDefault();
    }
  };

  const handlePanMove = (e) => {
    if (isPanning) {
      const newOffset = {
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y
      };
      setOffset(newOffset);
      offsetRef.current = newOffset;
    }
  };

  const handlePanEnd = () => {
    setIsPanning(false);
  };

  // Add light at center-top by default
  const addLight = () => {
    const newLight = {
      id: Date.now().toString(),
      x: 0.5,
      y: 0.2,
      intensity: 1.0,
      radius: 100, // 기본값: 100 (중간값)
      temperature: 0.5,
      enabled: true,
    };
    onLightsChange([...(lights || []), newLight]);
    setSelectedLightId(newLight.id);
    setViewMode('night'); // 조명은 야간 뷰에서 확인
  };

  const removeLight = (id) => {
    onLightsChange(lights.filter(l => l.id !== id));
    if (selectedLightId === id) setSelectedLightId(null);
  };

  // Drag handling (조명)
  const handleMouseDown = (e, id) => {
    e.stopPropagation();
    draggingRef.current = { id };
    setSelectedLightId(id);
  };

  const handleMouseMove = (e) => {
    if (!draggingRef.current || !containerRef.current) return;
    
    // 이미지 요소 찾기
    const imgElement = containerRef.current.querySelector('img');
    if (!imgElement) return;
    
    // 이미지의 실제 표시 영역 (줌/팬이 모두 적용된 최종 경계)
    const imgRect = imgElement.getBoundingClientRect();
    
    // 이미지 내에서의 마우스 위치
    const imageX = e.clientX - imgRect.left;
    const imageY = e.clientY - imgRect.top;
    
    // 정규화 (0~1)
    const x = imageX / imgRect.width;
    const y = imageY / imgRect.height;
    const clampedX = Math.min(1, Math.max(0, x));
    const clampedY = Math.min(1, Math.max(0, y));
    updateLight(draggingRef.current.id, { x: clampedX, y: clampedY });
  };

  const handleMouseUp = () => {
    draggingRef.current = null;
  };

  useEffect(() => {
    const up = () => handleMouseUp();
    const move = (e) => handleMouseMove(e);
    window.addEventListener('mouseup', up);
    window.addEventListener('mousemove', move);
    return () => {
      window.removeEventListener('mouseup', up);
      window.removeEventListener('mousemove', move);
    };
  });

  // 이미지 크기 추적
  useEffect(() => {
    if (results && containerRef.current) {
      const img = containerRef.current.querySelector('img');
      if (img) {
        img.onload = () => {
          setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
        };
        if (img.complete) {
          setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
        }
      }
    }
  }, [results]);

  // 마우스 휠 이벤트 등록
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const wheelHandler = (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleWheel(e);
    };

    // passive: false로 등록해야 preventDefault가 작동함
    container.addEventListener('wheel', wheelHandler, { passive: false });

    return () => {
      container.removeEventListener('wheel', wheelHandler);
    };
  }, [scale, offset, results, handleWheel]);

  // 텍스트 드래그 핸들러 (줌/팬 고려, 간판 영역 내 위치로 변환)
  const handleTextMouseDown = (e, id) => {
    console.log('[상호 편집] handleTextMouseDown 호출됨', id);
    if (!containerRef.current || !imageRef.current || !selectedArea) {
      console.log('[상호 편집] 필수 요소 없음', { containerRef: !!containerRef.current, imageRef: !!imageRef.current, selectedArea: !!selectedArea });
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    
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
    
    // 마우스 위치를 이미지 좌표로 변환 (줌/팬 고려)
    const containerRect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - containerRect.left;
    const mouseY = e.clientY - containerRect.top;
    
    // 줌/팬이 적용된 이미지 내에서의 실제 좌표
    const imageX = (mouseX - offset.x) / scale;
    const imageY = (mouseY - offset.y) / scale;
    
    // 마우스 위치는 텍스트 중심 위치로 간주
    // 간판 내에서의 텍스트 중심 위치
    const textCenterX = imageX - signboardX;
    const textCenterY = imageY - signboardY;
    
    // 현재 간판의 텍스트 크기 추정 (fontSize 기반) - ref 사용
    const sb = (originalSignboardsRef.current || []).find(s => s.id === id);
    const currentFontSize = sb?.formData?.fontSize || 100;
    const baseRatio = Math.sqrt(currentFontSize / 100);
    const estimatedTextWidth = signboardWidth * 0.5 * baseRatio;
    const estimatedTextHeight = signboardHeight * 0.4 * baseRatio;
    
    // 백엔드와 동일한 방식으로 text_position_x/y 계산
    // text_center_x = text_width/2 + (width - text_width) * (text_position_x / 100)
    // 따라서: text_position_x = ((text_center_x - text_width/2) / (width - text_width)) * 100
    const availableWidth = signboardWidth - estimatedTextWidth;
    const availableHeight = signboardHeight - estimatedTextHeight;
    
    const xInSignboard = availableWidth > 0 
      ? ((textCenterX - estimatedTextWidth / 2) / availableWidth) * 100 
      : 50;
    const yInSignboard = availableHeight > 0 
      ? ((textCenterY - estimatedTextHeight / 2) / availableHeight) * 100 
      : 50;
    
    console.log('[상호 편집] 드래그 시작, 위치:', { xInSignboard, yInSignboard });
    
    // ref에 즉시 저장 (상태 업데이트 전에)
    draggingTextIdRef.current = id;
    setDraggingTextId(id);
    
    // 초기 위치 설정
    setTextPositions((prev) => {
      const newPos = {
        ...prev,
        [id]: { 
          ...(prev[id] || {}), 
          x: Math.max(0, Math.min(100, xInSignboard)), 
          y: Math.max(0, Math.min(100, yInSignboard)) 
        },
      };
      console.log('[상호 편집] textPositions 업데이트:', newPos);
      return newPos;
    });
    
    // 이벤트 리스너 직접 등록 (상태 업데이트를 기다리지 않음)
    const handleMove = (e) => {
      // draggingTextIdRef.current가 0일 수 있으므로 null/undefined만 체크
      if (draggingTextIdRef.current === null || draggingTextIdRef.current === undefined || !containerRef.current || !imageRef.current || !selectedAreaRef.current) {
        console.log('[상호 편집] handleMove 조건 실패', {
          draggingTextId: draggingTextIdRef.current,
          containerRef: !!containerRef.current,
          imageRef: !!imageRef.current,
          selectedArea: !!selectedAreaRef.current
        });
        return;
      }
      const currentId = draggingTextIdRef.current;
      const currentSelectedArea = selectedAreaRef.current;
      const currentScale = scaleRef.current;
      const currentOffset = offsetRef.current;
      
      console.log('[상호 편집] handleTextMouseMove 호출됨 (직접 등록)', currentId);
      
      // 간판 영역 계산
      let signboardX, signboardY, signboardWidth, signboardHeight;
      if (currentSelectedArea.type === 'polygon' && currentSelectedArea.points.length >= 4) {
        const xs = currentSelectedArea.points.map(p => p.x);
        const ys = currentSelectedArea.points.map(p => p.y);
        signboardX = Math.min(...xs);
        signboardY = Math.min(...ys);
        signboardWidth = Math.max(...xs) - signboardX;
        signboardHeight = Math.max(...ys) - signboardY;
      } else {
        signboardX = currentSelectedArea.x;
        signboardY = currentSelectedArea.y;
        signboardWidth = currentSelectedArea.width;
        signboardHeight = currentSelectedArea.height;
      }
      
      // 마우스 위치를 이미지 좌표로 변환 (줌/팬 고려)
      // 이미지 요소를 직접 찾아서 그 위치를 기준으로 계산
      const imageElement = containerRef.current?.querySelector('img');
      if (!imageElement) {
        console.log('[상호 편집] 이미지 요소를 찾을 수 없음');
        return;
      }
      
      const imageRect = imageElement.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();
      
      // 마우스 위치를 이미지의 실제 화면 좌표로 변환
      const mouseX = e.clientX - imageRect.left;
      const mouseY = e.clientY - imageRect.top;
      
      // 이미지의 실제 크기 대비 비율로 변환 (ref 사용)
      const currentImageSize = imageSizeRef.current;
      const imageX = (mouseX / imageRect.width) * currentImageSize.width;
      const imageY = (mouseY / imageRect.height) * currentImageSize.height;
      
      // 마우스 위치는 텍스트 중심 위치로 간주
      // 간판 영역 내에서의 상대 위치
      const textCenterX = imageX - signboardX;
      const textCenterY = imageY - signboardY;
      
      console.log('[상호 편집] 좌표 계산:', {
        mouseX,
        mouseY,
        imageRect: { left: imageRect.left, top: imageRect.top, width: imageRect.width, height: imageRect.height },
        containerRect: { left: containerRect.left, top: containerRect.top, width: containerRect.width, height: containerRect.height },
        imageSize: currentImageSize,
        imageX,
        imageY,
        signboardX,
        signboardY,
        signboardWidth,
        signboardHeight,
        textCenterX,
        textCenterY
      });
      
      // 현재 간판의 실제 텍스트 크기 계산
      const sb = (originalSignboardsRef.current || []).find(s => s.id === currentId);
      
      let estimatedTextWidth, estimatedTextHeight;
      
      const currentTextSizeInfo = textSizeInfoRef.current;
      if (currentTextSizeInfo && currentTextSizeInfo.text_width && currentTextSizeInfo.text_height) {
        // 백엔드에서 받은 실제 텍스트 크기 사용
        const scaleX = imageSizeRef.current.width / currentTextSizeInfo.signboard_width;
        const scaleY = imageSizeRef.current.height / currentTextSizeInfo.signboard_height;
        estimatedTextWidth = currentTextSizeInfo.text_width * scaleX;
        estimatedTextHeight = currentTextSizeInfo.text_height * scaleY;
      } else {
        // 폴백: Canvas로 계산
        const currentFontSize = sb?.formData?.fontSize || 100;
        const text = sb?.formData?.text || '';
        const textDirection = sb?.formData?.textDirection || 'horizontal';
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const fontSizeInPx = (currentFontSize / 100) * (signboardHeight * 0.3);
        ctx.font = `${fontSizeInPx}px "Malgun Gothic", "맑은 고딕", sans-serif`;
        
        let textWidth, textHeight;
        if (textDirection === 'vertical') {
          const textVertical = text.split('').join('\n');
          const metrics = ctx.measureText(textVertical);
          textWidth = metrics.width;
          textHeight = text.length * fontSizeInPx * 1.2;
        } else {
          const metrics = ctx.measureText(text);
          textWidth = metrics.width;
          textHeight = fontSizeInPx * 1.2;
        }
        
        estimatedTextWidth = textWidth;
        estimatedTextHeight = textHeight;
      }
      
      const availableWidth = signboardWidth - estimatedTextWidth;
      const availableHeight = signboardHeight - estimatedTextHeight;
      
      // 텍스트 중심 위치를 0-100% 범위로 변환 (제한 없이 자유롭게 이동)
      const xInSignboard = availableWidth > 0 
        ? ((textCenterX - estimatedTextWidth / 2) / availableWidth) * 100 
        : 50;
      const yInSignboard = availableHeight > 0 
        ? ((textCenterY - estimatedTextHeight / 2) / availableHeight) * 100 
        : 50;
      
      // 0-100% 범위로만 제한 (간판 영역 밖으로 나가는 것은 허용)
      const clampedX = Math.max(0, Math.min(100, xInSignboard));
      const clampedY = Math.max(0, Math.min(100, yInSignboard));
      
      console.log('[상호 편집] 드래그 중 위치 업데이트:', { 
        xInSignboard, 
        yInSignboard, 
        clampedX, 
        clampedY,
        currentId,
        textCenterX,
        textCenterY,
        signboardWidth,
        signboardHeight,
        imageX,
        imageY,
        mouseX,
        mouseY
      });
      
      setTextPositions((prev) => {
        const newPos = {
          ...prev,
          [currentId]: { 
            x: clampedX, 
            y: clampedY 
          },
        };
        console.log('[상호 편집] textPositions 업데이트 (드래그 중):', {
          prev: JSON.parse(JSON.stringify(prev)),
          newPos: JSON.parse(JSON.stringify(newPos)),
          currentId: currentId,
          clampedX: clampedX,
          clampedY: clampedY,
          newPosString: JSON.stringify(newPos),
          newPosCurrentId: newPos[currentId]
        });
        return newPos;
      });
    };
    
    const handleUp = () => {
      console.log('[상호 편집] 드래그 종료');
      draggingTextIdRef.current = null;
      setDraggingTextId(null);
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
    
    console.log('[상호 편집] 이벤트 리스너 등록 (직접 등록)');
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
  };

  // originalSignboards를 ref로 저장하여 클로저 문제 방지
  useEffect(() => {
    originalSignboardsRef.current = originalSignboards;
    selectedAreaRef.current = selectedArea;
    scaleRef.current = scale;
    offsetRef.current = offset;
  }, [originalSignboards, selectedArea, scale, offset]);

  const handleTextMouseMove = useCallback((e) => {
    if (!draggingTextId || draggingTextId === null || !containerRef.current || !imageRef.current || !selectedArea) {
      return;
    }
    console.log('[상호 편집] handleTextMouseMove 호출됨', draggingTextId);
    
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
    
    // 마우스 위치를 이미지 좌표로 변환 (줌/팬 고려)
    const containerRect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - containerRect.left;
    const mouseY = e.clientY - containerRect.top;
    
    // 줌/팬이 적용된 이미지 내에서의 실제 좌표
    const imageX = (mouseX - offset.x) / scale;
    const imageY = (mouseY - offset.y) / scale;
    
    // 마우스 위치는 텍스트 중심 위치로 간주
    // 간판 내에서의 텍스트 중심 위치
    const textCenterX = imageX - signboardX;
    const textCenterY = imageY - signboardY;
    
    // 현재 간판의 텍스트 크기 추정 (fontSize 기반) - ref 사용
    const sb = (originalSignboardsRef.current || []).find(s => s.id === draggingTextId);
    const currentFontSize = sb?.formData?.fontSize || 100;
    const baseRatio = Math.sqrt(currentFontSize / 100);
    const estimatedTextWidth = signboardWidth * 0.5 * baseRatio;
    const estimatedTextHeight = signboardHeight * 0.4 * baseRatio;
    
    // 백엔드와 동일한 방식으로 text_position_x/y 계산
    // text_center_x = text_width/2 + (width - text_width) * (text_position_x / 100)
    // 따라서: text_position_x = ((text_center_x - text_width/2) / (width - text_width)) * 100
    const availableWidth = signboardWidth - estimatedTextWidth;
    const availableHeight = signboardHeight - estimatedTextHeight;
    
    const xInSignboard = availableWidth > 0 
      ? ((textCenterX - estimatedTextWidth / 2) / availableWidth) * 100 
      : 50;
    const yInSignboard = availableHeight > 0 
      ? ((textCenterY - estimatedTextHeight / 2) / availableHeight) * 100 
      : 50;
    
    console.log('[상호 편집] 드래그 중 위치 업데이트:', { xInSignboard, yInSignboard });
    setTextPositions((prev) => {
      const newPos = {
        ...prev,
        [draggingTextId]: { 
          ...(prev[draggingTextId] || {}), 
          x: Math.max(0, Math.min(100, xInSignboard)), 
          y: Math.max(0, Math.min(100, yInSignboard)) 
        },
      };
      return newPos;
    });
  }, [draggingTextId, selectedArea, scale, offset]);

  const handleTextMouseUp = () => {
    draggingTextIdRef.current = null;
    setDraggingTextId(null);
  };

  // 이제 handleTextMouseDown에서 직접 이벤트 리스너를 등록하므로
  // 이 useEffect는 제거하거나 백업용으로만 사용
  // useEffect(() => {
  //   if (draggingTextId !== null && draggingTextId !== undefined) {
  //     console.log('[상호 편집] 이벤트 리스너 등록, draggingTextId:', draggingTextId);
  //     window.addEventListener('mousemove', handleTextMouseMove);
  //     window.addEventListener('mouseup', handleTextMouseUp);
  //     return () => {
  //       console.log('[상호 편집] 이벤트 리스너 제거');
  //       window.removeEventListener('mousemove', handleTextMouseMove);
  //       window.removeEventListener('mouseup', handleTextMouseUp);
  //     };
  //   }
  // }, [draggingTextId, handleTextMouseMove, handleTextMouseUp]);

  const [pendingTransforms, setPendingTransforms] = useState({});

  const handleApplyTransforms = () => {
    console.log('Transform 적용:', pendingTransforms);
    console.log('Transform 상세:', JSON.stringify(pendingTransforms, null, 2));
    
    // 빈 객체 체크 개선
    const hasValidTransforms = Object.keys(pendingTransforms).some(id => {
      const transform = pendingTransforms[id];
      return transform && Object.keys(transform).length > 0;
    });
    
    if (!hasValidTransforms) {
      console.warn('적용할 transform이 없습니다. pendingTransforms:', pendingTransforms);
      alert('변경사항이 없습니다. 간판을 편집한 후 다시 시도해주세요.');
      return;
    }
    
    setShowTransform(false);
    if (onRegenerateWithTransforms) {
      // pendingTransforms는 객체 형태 { [id]: transform }이므로 배열로 변환
      const transformsArray = Object.keys(pendingTransforms)
        .filter(id => {
          const transform = pendingTransforms[id];
          return transform && Object.keys(transform).length > 0;
        })
        .map(id => ({
            id: parseInt(id),
            ...pendingTransforms[id]
          }));
      
      if (transformsArray.length === 0) {
        console.warn('적용할 transform이 없습니다.');
        alert('변경사항이 없습니다.');
        return;
      }
      
      console.log('변환된 transformsArray:', transformsArray);
      onRegenerateWithTransforms(transformsArray);
    }
  };

  // Color from temperature
  const tempToRGB = (t) => {
    const warm = [255, 220, 200];
    const cool = [200, 210, 255];
    return warm.map((w, i) => Math.round(w * (1 - t) + cool[i] * t));
  };

  if (loading) {
    return (
      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-12 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-gray-400">시뮬레이션 생성 중...</p>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-12 text-center">
        <div className="text-gray-400 mb-4">
          <svg className="mx-auto h-16 w-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <p className="text-gray-400">시뮬레이션 결과가 여기에 표시됩니다.</p>
      </div>
    );
  }

  const currentImage = viewMode === 'day' ? results.day_simulation : results.night_simulation;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-6"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-white">시뮬레이션 결과</h2>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              viewMode === 'day' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
            }`}
          >
            {viewMode === 'day' ? 'DAY' : 'NIGHT'}
          </span>
          <button
            onClick={() => {
              setShowTransform(!showTransform);
              if (!showTransform) {
                // 간판 편집 모드로 전환할 때 조명 편집 모드 비활성화
                setSelectedLightId(null);
                setShowTextEdit(false);
              }
            }}
            className={`px-3 py-1 text-sm rounded-lg transition-colors ${
              showTransform 
                ? 'bg-orange-500 text-white' 
                : 'bg-orange-500/80 hover:bg-orange-500 text-white'
            }`}
          >
            {showTransform ? '✓ 편집 중' : '✏️ 간판 편집'}
          </button>
          <button
            onClick={() => {
              const next = !showTextEdit;
              setShowTextEdit(next);
              if (next) {
                setShowTransform(false);
                const initial = {};
                (originalSignboards || []).forEach((sb) => {
                  initial[sb.id] = {
                    x: sb.formData?.textPositionX ?? 50,
                    y: sb.formData?.textPositionY ?? 50,
                  };
                });
                setTextPositions(initial);
              }
            }}
            className={`px-3 py-1 text-sm rounded-lg transition-colors ${
              showTextEdit 
                ? 'bg-purple-500 text-white' 
                : 'bg-purple-500/80 hover:bg-purple-500 text-white'
            }`}
          >
            {showTextEdit ? '✓ 상호 편집' : '✏️ 상호 위치'}
          </button>
          {/* Transform 모드일 때 적용 버튼 */}
          {showTransform && (
            <button
              onClick={handleApplyTransforms}
              className="px-6 py-2 bg-gradient-to-r from-green-500 to-blue-600 hover:from-green-600 hover:to-blue-700 text-white rounded-lg font-bold shadow-xl"
            >
              ✓ 적용하기
            </button>
          )}
          {showTextEdit && (
            <button
              onClick={() => onApplyTextPositions(textPositions)}
              className="px-6 py-2 bg-gradient-to-r from-green-500 to-blue-600 hover:from-green-600 hover:to-blue-700 text-white rounded-lg font-bold shadow-xl"
            >
              ✓ 적용하기
            </button>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input
              type="checkbox"
              checked={lightsEnabled}
              onChange={(e) => onToggleEnabled(e.target.checked)}
              className="accent-blue-500"
            />
            조명 켜기
          </label>
          <button
            onClick={addLight}
            className="px-3 py-1 text-sm bg-blue-500/80 hover:bg-blue-500 text-white rounded-lg transition-colors"
          >
            + 조명 추가
          </button>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-sm font-medium transition-colors ${viewMode === 'day' ? 'text-blue-400' : 'text-gray-500'}`}>주간</span>
          <span className={`text-sm font-medium transition-colors ${viewMode === 'night' ? 'text-purple-400' : 'text-gray-500'}`}>야간</span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="1"
          value={viewMode === 'day' ? 0 : 1}
          onChange={(e) => setViewMode(e.target.value === '0' ? 'day' : 'night')}
          className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500"
        />
      </div>

      <div className="mb-4 border-2 border-white/20 rounded-xl overflow-hidden bg-black/20 relative">
        <div
          ref={containerRef}
          className="relative overflow-hidden"
          style={{ cursor: isPanning ? 'grabbing' : 'default' }}
          onMouseDown={(e) => {
            handlePanStart(e);
            if (e.button === 0 && !e.ctrlKey) setSelectedLightId(null);
          }}
          onMouseMove={handlePanMove}
          onMouseUp={handlePanEnd}
          onMouseLeave={handlePanEnd}
          onWheel={handleWheel}
          onContextMenu={(e) => e.preventDefault()}
        >
          <img
            ref={imageRef}
            src={currentImage}
            alt={viewMode === 'day' ? '주간 시뮬레이션' : '야간 시뮬레이션'}
            className="w-full h-auto pointer-events-none select-none"
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
              transformOrigin: '0 0',
              transition: isPanning ? 'none' : 'transform 0.1s ease-out'
            }}
          />
          {/* 간판 편집 오버레이 */}
          {showTransform && !showTextEdit && originalSignboards.length > 0 && (
            <div 
              className="absolute inset-0 pointer-events-none" 
              style={{ 
                zIndex: 50,
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                transformOrigin: '0 0'
              }}
            >
              <SignboardTransform
                signboards={originalSignboards.map((sb, idx) => ({
                  id: idx,
                  polygon_points: selectedArea ? (selectedArea.type === 'polygon' 
                    ? selectedArea.points.map(p => [p.x, p.y])
                    : [[selectedArea.x, selectedArea.y], 
                       [selectedArea.x + selectedArea.width, selectedArea.y],
                       [selectedArea.x + selectedArea.width, selectedArea.y + selectedArea.height],
                       [selectedArea.x, selectedArea.y + selectedArea.height]])
                    : [],
                  text: sb.formData?.text || ''
                }))}
                originalSignboards={originalSignboards}
                imageSize={imageSize}
                onTransformChange={setPendingTransforms}
                onApply={handleApplyTransforms}
              />
            </div>
          )}
          {/* 상호 위치 편집 오버레이 - 박스 형태로 표시 */}
          {showTextEdit && !showTransform && selectedArea && (
            <div 
              className="absolute inset-0 pointer-events-none" 
              style={{ 
                zIndex: 50,
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                transformOrigin: '0 0'
              }}
            >
              {/* 간판 영역 표시 (이동 가능 범위) */}
              {(() => {
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
                
                const signboardXPercent = (signboardX / imageSize.width) * 100;
                const signboardYPercent = (signboardY / imageSize.height) * 100;
                const signboardWidthPercent = (signboardWidth / imageSize.width) * 100;
                const signboardHeightPercent = (signboardHeight / imageSize.height) * 100;
                
                return (
                  <div
                    className="absolute pointer-events-none"
                    style={{
                      left: `${signboardXPercent}%`,
                      top: `${signboardYPercent}%`,
                      width: `${signboardWidthPercent}%`,
                      height: `${signboardHeightPercent}%`,
                      border: '2px dashed rgba(255, 255, 0, 0.6)', // 노란색 점선 테두리
                      backgroundColor: 'rgba(255, 255, 0, 0.1)', // 반투명 노란색 배경
                      borderRadius: '4px',
                      boxShadow: '0 0 0 2px rgba(255, 255, 255, 0.3)',
                    }}
                    title="텍스트 이동 가능 범위"
                  />
                );
              })()}
              {(originalSignboards || []).map((sb) => {
                const pos = textPositions[sb.id] || { x: sb.formData?.textPositionX ?? 50, y: sb.formData?.textPositionY ?? 50 };
                console.log('[상호 편집] 박스 렌더링:', { 
                  sbId: sb.id, 
                  pos, 
                  textPositions: textPositions[sb.id],
                  textPositionsAll: textPositions,
                  posX: pos.x,
                  posY: pos.y,
                  formDataX: sb.formData?.textPositionX,
                  formDataY: sb.formData?.textPositionY
                });
                const currentFontSize = sb.formData?.fontSize || 100;
                
                // 간판 영역(selectedArea) 기준으로 박스 크기 계산
                let signboardWidth, signboardHeight, signboardX, signboardY;
                
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
                
                // 백엔드에서 받은 실제 텍스트 크기 사용 (가장 정확함)
                let finalTextWidth, finalTextHeight;
                
                if (textSizeInfo && textSizeInfo.text_width && textSizeInfo.text_height) {
                  // 백엔드에서 계산한 실제 텍스트 크기 사용
                  // 백엔드의 text_width, text_height는 간판 크기 기준이므로, 이미지 크기로 변환
                  const scaleX = imageSize.width / textSizeInfo.signboard_width;
                  const scaleY = imageSize.height / textSizeInfo.signboard_height;
                  // 백엔드에서 계산한 정확한 크기 사용 (여유 공간 없이)
                  finalTextWidth = textSizeInfo.text_width * scaleX;
                  finalTextHeight = textSizeInfo.text_height * scaleY;
                } else {
                  // 백엔드 정보가 없으면 Canvas로 계산 (폴백)
                  const text = sb.formData?.text || '';
                  const textDirection = sb.formData?.textDirection || 'horizontal';
                  
                  const canvas = document.createElement('canvas');
                  const ctx = canvas.getContext('2d');
                  const fontSizeInPx = (currentFontSize / 100) * (signboardHeight * 0.3);
                  ctx.font = `${fontSizeInPx}px "Malgun Gothic", "맑은 고딕", sans-serif`;
                  
                  let textWidth, textHeight;
                  if (textDirection === 'vertical') {
                    const textVertical = text.split('').join('\n');
                    const metrics = ctx.measureText(textVertical);
                    textWidth = metrics.width;
                    textHeight = text.length * fontSizeInPx * 1.2;
                  } else {
                    const metrics = ctx.measureText(text);
                    textWidth = metrics.width;
                    textHeight = fontSizeInPx * 1.2;
                  }
                  
                  finalTextWidth = textWidth;
                  finalTextHeight = textHeight;
                }
                
                // 이미지 크기 대비 퍼센트 값
                const textWidthPx = (finalTextWidth / imageSize.width) * 100;
                const textHeightPx = (finalTextHeight / imageSize.height) * 100;
                
                // 백엔드와 동일한 방식으로 텍스트 중심 위치 계산
                // text_position_x가 0이면 텍스트 중심이 간판 왼쪽 끝 + text_width/2
                // text_position_x가 50이면 텍스트 중심이 간판 중앙
                // text_position_x가 100이면 텍스트 중심이 간판 오른쪽 끝 - text_width/2
                // 프론트엔드에서는: text_center_x = text_width/2 + (signboardWidth - text_width) * (pos.x / 100)
                const textCenterX = finalTextWidth / 2 + (signboardWidth - finalTextWidth) * (pos.x / 100);
                const textCenterY = finalTextHeight / 2 + (signboardHeight - finalTextHeight) * (pos.y / 100);
                
                // 텍스트 중심 위치를 이미지 전체 기준으로 변환
                const textXInImage = (signboardX + textCenterX) / imageSize.width * 100;
                const textYInImage = (signboardY + textCenterY) / imageSize.height * 100;
                
                return (
                  <div
                    key={sb.id}
                    className="absolute cursor-move"
                    style={{
                      left: `${textXInImage}%`,
                      top: `${textYInImage}%`,
                      width: `${textWidthPx}%`,
                      height: `${textHeightPx}%`,
                      transform: 'translate(-50%, -50%)',
                      border: '2px solid #A855F7', // 보라색 테두리
                      backgroundColor: 'rgba(168, 85, 247, 0.15)', // 반투명 보라색 배경
                      borderRadius: '4px',
                      boxShadow: '0 0 0 2px rgba(255, 255, 255, 0.5)',
                      zIndex: 100, // 다른 요소 위에 표시
                      pointerEvents: 'auto', // 드래그 가능하도록
                    }}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      handleTextMouseDown(e, sb.id);
                    }}
                    title="드래그해서 텍스트 위치 조절"
                  >
                    {/* 텍스트 라벨 */}
                    <div className="absolute -top-6 left-0 bg-purple-500 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                      {sb.formData?.text || `상호 ${sb.id + 1}`}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {/* 조명 오버레이: 야간에서만 표시, 편집 모드가 아닐 때만 */}
          {viewMode === 'night' && lightsEnabled && !showTransform && !showTextEdit && (
            <div 
              className="absolute inset-0 pointer-events-none"
              style={{
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                transformOrigin: '0 0'
              }}
            >
              {lights.map((light) => {
                const { id, x, y, radius = 50, intensity = 1, temperature = 0.5, enabled = true } = light;
                if (!enabled) return null;
                const color = tempToRGB(temperature);
                // 표시용 반경
                const displayRadius = radius * 0.4;
                const width = displayRadius * 2.0;
                const height = displayRadius * 2.4;
                const alpha = Math.min(0.7, 0.45 * intensity);
                
                // 균일한 타원형 조명 (백엔드와 동일)
                const solidColor = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
                
                return (
                  <div key={id}>
                    {/* 조명 기구 아이콘 (더 선명하게) */}
                    <div
                      className="absolute pointer-events-none"
                      style={{
                        left: `${x * 100}%`,
                        top: `${y * 100}%`,
                        transform: 'translate(-50%, -50%)',
                        width: '30px',
                        height: '20px',
                      }}
                    >
                      <svg viewBox="0 0 30 20" className="w-full h-full">
                        <path
                          d="M5 0 L10 8 L20 8 L25 0 Z"
                          fill="#3a3a3a"
                          stroke="#666"
                          strokeWidth="2"
                        />
                        <ellipse cx="15" cy="10" rx="8" ry="3" fill="#2a2a2a" stroke="#555" strokeWidth="1.5" />
                      </svg>
                    </div>
                    
                    {/* 타원형 중심이 y, 아래쪽 절반만 표시 (백엔드와 동일) */}
                    <div
                      className="absolute"
                      style={{
                        left: `${x * 100}%`,
                        top: `${y * 100}%`,
                        width: `${width}px`,
                        height: `${height}px`,  // 전체 타원 (radius * 2.4)
                        marginLeft: `${-width / 2}px`,
                        marginTop: `${-height / 2}px`,  // 중심을 y에 맞춤!
                        borderRadius: '50%',
                        background: solidColor,
                        opacity: 0.5,
                        clipPath: 'polygon(0 50%, 100% 50%, 100% 100%, 0 100%)',  // 아래쪽 절반만
                      }}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {/* 드래그 핸들 (조명 기구 클릭) - 편집 모드가 아닐 때만 */}
          {viewMode === 'night' && !showTransform && !showTextEdit && (
            <div 
              className="absolute inset-0"
              style={{
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                transformOrigin: '0 0'
              }}
            >
              {lights.map((light) => {
                const { id, x, y, enabled = true } = light;
                if (!enabled && !lightsEnabled) return null;
                return (
                  <div
                    key={id}
                    onMouseDown={(e) => handleMouseDown(e, id)}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedLightId(id);
                    }}
                    className={`absolute cursor-move transition-all ${
                      selectedLightId === id ? 'ring-2 ring-purple-400' : ''
                    }`}
                    style={{
                      left: `${x * 100}%`,
                      top: `${y * 100}%`,
                      width: '40px',
                      height: '30px',
                      marginLeft: '-20px',
                      marginTop: '-15px',
                      borderRadius: '4px',
                    }}
                    title="드래그해서 위치 이동 / 클릭해서 설정"
                  />
                );
              })}
            </div>
          )}
          
          {/* 줌 컨트롤 */}
          <div className="absolute top-3 right-3 flex flex-col gap-2 bg-black/50 backdrop-blur-sm rounded-lg p-2 pointer-events-auto">
            <div className="text-xs text-white text-center font-mono">
              {Math.round(scale * 100)}%
            </div>
            <button
              onClick={() => handleWheel({ deltaY: -100, preventDefault: () => {}, clientX: 0, clientY: 0 })}
              className="px-2 py-1 bg-white/10 hover:bg-white/20 text-white rounded text-sm"
              title="확대 (또는 마우스 휠 위)"
            >
              🔍+
            </button>
            <button
              onClick={() => handleWheel({ deltaY: 100, preventDefault: () => {}, clientX: 0, clientY: 0 })}
              className="px-2 py-1 bg-white/10 hover:bg-white/20 text-white rounded text-sm"
              title="축소 (또는 마우스 휠 아래)"
            >
              🔍-
            </button>
            <button
              onClick={handleResetZoom}
              className="px-2 py-1 bg-blue-500/80 hover:bg-blue-500 text-white rounded text-xs"
              title="원래 크기로"
            >
              리셋
            </button>
          </div>
          
          {/* 도움말 */}
          <div className="absolute bottom-3 left-3 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-2 text-xs text-gray-300 pointer-events-none">
            <div>💡 <strong>마우스 휠</strong>: 확대/축소</div>
            <div>💡 <strong>우클릭 드래그</strong>: 이미지 이동</div>
          </div>
        </div>
      </div>

      {/* 선택된 조명 퀵 설정 */}
      {viewMode === 'night' && selectedLightId && (
        <div className="mb-4 bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-gray-200">
          <div className="flex items-center justify-between mb-3">
            <div className="font-semibold">선택한 조명</div>
            <button
              onClick={() => removeLight(selectedLightId)}
              className="text-red-400 hover:text-red-300 text-sm"
            >
              삭제
            </button>
          </div>
          {lights
            .filter((l) => l.id === selectedLightId)
            .map((light) => (
              <div key={light.id} className="grid grid-cols-2 gap-3">
                <label className="space-y-1">
                  <div>밝기 (현재: {light.intensity.toFixed(2)})</div>
                  <input
                    type="range"
                    min="0"
                    max="3"
                    step="0.05"
                    value={light.intensity}
                    onChange={(e) => updateLight(light.id, { intensity: parseFloat(e.target.value) })}
                    className="w-full accent-blue-500"
                  />
                </label>
                <label className="space-y-1">
                  <div>반경 (현재: {light.radius}px)</div>
                  <input
                    type="range"
                    min="50"
                    max="200"
                    step="10"
                    value={light.radius}
                    onChange={(e) => updateLight(light.id, { radius: parseFloat(e.target.value) })}
                    className="w-full accent-blue-500"
                  />
                </label>
                <label className="space-y-1 col-span-2">
                  <div>색온도 (0=따뜻, 1=차가움)</div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={light.temperature}
                    onChange={(e) => updateLight(light.id, { temperature: parseFloat(e.target.value) })}
                    className="w-full accent-amber-400"
                  />
                </label>
              </div>
            ))}
        </div>
      )}

      {/* 조명 반영하기 버튼 */}
      {lights.length > 0 && (
        <div className="mb-4">
          <button
            onClick={onApplyLights}
            className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white font-semibold py-3 px-4 rounded-lg transition-all hover:scale-105 shadow-lg"
          >
            🔦 조명 반영하기 (비교 보기/다운로드에 적용)
          </button>
          <p className="mt-2 text-xs text-amber-300/70 text-center">
            💡 조명을 추가하거나 수정한 후 이 버튼을 눌러주세요!
          </p>
        </div>
      )}

      <div className="flex gap-3 mb-6">
        <button
          onClick={() => {
            const link = document.createElement('a');
            link.href = results.day_simulation;
            link.download = 'day_simulation.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
          }}
          className="flex-1 bg-blue-500/80 hover:bg-blue-500 text-white font-medium py-3 px-4 rounded-lg transition-all hover:scale-105"
        >
          주간 다운로드
        </button>
        <button
          onClick={() => {
            const link = document.createElement('a');
            link.href = results.night_simulation;
            link.download = 'night_simulation.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
          }}
          className="flex-1 bg-purple-500/80 hover:bg-purple-500 text-white font-medium py-3 px-4 rounded-lg transition-all hover:scale-105"
        >
          야간 다운로드
        </button>
      </div>

      <div className="pt-6 border-t border-white/10">
        <h3 className="text-lg font-semibold mb-4 text-white">비교 보기</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-black/20 rounded-lg p-2">
            <p className="text-xs text-blue-400 mb-2 text-center font-medium">주간</p>
            <img
              src={results.day_simulation}
              alt="주간"
              className="w-full h-auto rounded border border-white/10"
            />
          </div>
          <div className="bg-black/20 rounded-lg p-2">
            <p className="text-xs text-purple-400 mb-2 text-center font-medium">야간</p>
            <img
              src={results.night_simulation}
              alt="야간"
              className="w-full h-auto rounded border border-white/10"
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ResultViewer;
