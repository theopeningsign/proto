import React, { useRef, useEffect, useState } from 'react';

const ImageUploader = ({ image, onImageUpload, selectedArea, onAreaChange, signboards = [], currentSignboardId }) => {
  const canvasRef = useRef(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [points, setPoints] = useState([]); // 현재 편집 중인 점들 (폴리곤/사각형 공통)
  const [isComplete, setIsComplete] = useState(false);
  const [draggingPointIndex, setDraggingPointIndex] = useState(null); // 드래그 중인 점 인덱스 (폴리곤 모드)
  const [hoveredPointIndex, setHoveredPointIndex] = useState(null); // hover 중인 점

  // 영역 선택 모드: polygon(점찍기) | rect(사각형 드래그)
  const [selectionMode, setSelectionMode] = useState('polygon');
  const [isRectSelecting, setIsRectSelecting] = useState(false);
  const [rectStart, setRectStart] = useState(null);
  
  // 줌/팬 기능
  const [scale, setScale] = useState(1); // 줌 레벨
  const [offset, setOffset] = useState({ x: 0, y: 0 }); // 팬 오프셋
  const [isPanning, setIsPanning] = useState(false); // 팬 드래그 중
  const [panStart, setPanStart] = useState({ x: 0, y: 0 }); // 팬 시작 위치

  useEffect(() => {
    if (image) {
      const url = URL.createObjectURL(image);
      setImageUrl(url);
      // 새 이미지 로드 시 줌/팬 리셋
      setScale(1);
      setOffset({ x: 0, y: 0 });
      return () => URL.revokeObjectURL(url);
    } else {
      setImageUrl(null);
      setPoints([]);
      setIsComplete(false);
      setScale(1);
      setOffset({ x: 0, y: 0 });
    }
  }, [image]);

  // selectedArea 변경 시 points 업데이트
  useEffect(() => {
    if (selectedArea && selectedArea.type === 'polygon') {
      setPoints(selectedArea.points);
      setIsComplete(true);
      setSelectionMode('polygon');
    } else if (selectedArea && selectedArea.type === 'rect') {
      const { x, y, width, height } = selectedArea;
      const rectPoints = [
        { x, y },
        { x: x + width, y },
        { x: x + width, y: y + height },
        { x, y: y + height },
      ];
      setPoints(rectPoints);
      setIsComplete(true);
      setSelectionMode('rect');
    } else if (!selectedArea) {
      setPoints([]);
      setIsComplete(false);
    }
  }, [selectedArea]);

  // 휠 이벤트 고정 (페이지 스크롤 방지)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const wheelHandler = (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleWheel(e);
    };

    // passive: false로 등록해야 preventDefault가 작동함
    canvas.addEventListener('wheel', wheelHandler, { passive: false });

    return () => {
      canvas.removeEventListener('wheel', wheelHandler);
    };
  }, [scale, offset]);

  useEffect(() => {
    if (!imageUrl || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      
      // 캔버스 클리어
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // transform 적용 (줌/팬)
      ctx.save();
      ctx.translate(offset.x, offset.y);
      ctx.scale(scale, scale);
      
      // 이미지 그리기
      ctx.drawImage(img, 0, 0);
      
      ctx.restore();

      // 다른 간판들의 폴리곤 먼저 그리기 (읽기 전용)
      if (signboards && signboards.length > 0) {
        signboards.forEach(signboard => {
          if (signboard.id !== currentSignboardId && signboard.selectedArea && signboard.selectedArea.type === 'polygon') {
            drawPolygon(ctx, signboard.selectedArea.points, true, true); // 읽기 전용
          }
        });
      }

      // 현재 편집 중인 폴리곤 그리기
      if (points.length > 0) {
        drawPolygon(ctx, points, isComplete, false);
      }
    };

    img.src = imageUrl;
  }, [imageUrl, points, isComplete, hoveredPointIndex, draggingPointIndex, scale, offset, signboards, currentSignboardId]);

  const drawPolygon = (ctx, pts, complete, readonly = false) => {
    if (pts.length === 0) return;

    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(scale, scale);

    // 선 그리기
    if (readonly) {
      // 읽기 전용: 회색으로 표시
      ctx.strokeStyle = '#999999';
      ctx.lineWidth = 2 / scale;
      ctx.setLineDash([5 / scale, 5 / scale]); // 점선
    } else {
      ctx.strokeStyle = complete ? '#FFD700' : '#00BFFF';
      ctx.lineWidth = 3 / scale;
      ctx.setLineDash([]);
    }
    
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(pts[i].x, pts[i].y);
    }
    
    if (complete && pts.length > 2) {
      ctx.closePath();
      if (readonly) {
        ctx.fillStyle = 'rgba(150, 150, 150, 0.1)';
      } else {
        ctx.fillStyle = 'rgba(255, 215, 0, 0.15)';
      }
      ctx.fill();
    }
    
    ctx.stroke();

    // 점 그리기 (읽기 전용이 아닐 때만)
    if (!readonly) {
      const handleSize = 10 / scale;
      pts.forEach((pt, idx) => {
        const isHovered = hoveredPointIndex === idx;
        const isDragging = draggingPointIndex === idx;
        
        const size = (isHovered || isDragging) ? handleSize * 1.5 : handleSize;
        
        if (isDragging) {
          ctx.fillStyle = '#FF4500';
        } else if (isHovered) {
          ctx.fillStyle = '#FF69B4';
        } else {
          ctx.fillStyle = complete ? '#FFD700' : '#00BFFF';
        }
        
        ctx.fillRect(pt.x - size/2, pt.y - size/2, size, size);
        
        ctx.fillStyle = '#FFFFFF';
        ctx.font = `bold ${14 / scale}px Arial`;
        ctx.fillText(idx + 1, pt.x + 10 / scale, pt.y - 10 / scale);
      });
    } else {
      // 읽기 전용: 작은 회색 점만 표시
      const smallSize = 5 / scale;
      pts.forEach((pt) => {
        ctx.fillStyle = '#999999';
        ctx.fillRect(pt.x - smallSize/2, pt.y - smallSize/2, smallSize, smallSize);
      });
    }
    
    ctx.restore();
  };

  const getCanvasCoords = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // 캔버스 스케일 고려
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    // transform (줌/팬) 고려
    const canvasX = x * scaleX;
    const canvasY = y * scaleY;
    
    // 역변환: 화면 좌표 -> 원본 이미지 좌표
    const imageX = (canvasX - offset.x) / scale;
    const imageY = (canvasY - offset.y) / scale;
    
    return { x: imageX, y: imageY };
  };

  const getPointAtPosition = (x, y) => {
    const handleSize = 15; // 클릭 가능 영역
    for (let i = 0; i < points.length; i++) {
      const pt = points[i];
      const dist = Math.sqrt((x - pt.x)**2 + (y - pt.y)**2);
      if (dist < handleSize) {
        return i;
      }
    }
    return -1;
  };

  const handleCanvasMouseDown = (e) => {
    if (!imageUrl) return;

    // 우클릭 또는 Ctrl+클릭: 팬 모드
    if (e.button === 2 || e.ctrlKey) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      e.preventDefault();
      return;
    }

    const { x, y } = getCanvasCoords(e);

    // 사각형 모드
    if (selectionMode === 'rect') {
      const pointIndex = getPointAtPosition(x, y);

      if (isComplete && pointIndex !== -1 && points.length === 4) {
        // 이미 선택된 사각형의 모서리 클릭 → 그 코너를 드래그로 수정
        setDraggingPointIndex(pointIndex);
        setIsRectSelecting(false);
        e.preventDefault();
        return;
      }

      // 새 사각형 드래그 시작
      setIsRectSelecting(true);
      setIsComplete(false);
      setRectStart({ x, y });
      const rectPoints = [
        { x, y },
        { x, y },
        { x, y },
        { x, y },
      ];
      setPoints(rectPoints);
      return;
    }

    // 폴리곤 모드
    const pointIndex = getPointAtPosition(x, y);

    if (pointIndex !== -1) {
      // 기존 점 클릭 → 드래그 시작
      setDraggingPointIndex(pointIndex);
      e.preventDefault();
    } else if (!isComplete) {
      // 빈 공간 클릭 → 새 점 추가
      setPoints([...points, { x, y }]);
    }
  };

  const handleCanvasMouseMove = (e) => {
    if (!imageUrl) return;

    // 팬 드래그 중
    if (isPanning) {
      setOffset({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y
      });
      return;
    }

    const { x, y } = getCanvasCoords(e);

    if (selectionMode === 'rect') {
      if (isRectSelecting && rectStart) {
        // 새 사각형 드래그 중: 시작/현재 위치로 직사각형 계산
        const x1 = rectStart.x;
        const y1 = rectStart.y;
        const x2 = x;
        const y2 = y;
        const minX = Math.min(x1, x2);
        const maxX = Math.max(x1, x2);
        const minY = Math.min(y1, y2);
        const maxY = Math.max(y1, y2);
        const rectPoints = [
          { x: minX, y: minY },
          { x: maxX, y: minY },
          { x: maxX, y: maxY },
          { x: minX, y: maxY },
        ];
        setPoints(rectPoints);
        return;
      }

      if (draggingPointIndex !== null && points.length === 4) {
        // 이미 선택된 사각형의 코너를 드래그해서 크기 수정
        // 대각선 반대편 코너를 anchor로 두고, 나머지 두 점은 자동 보정
        const anchorIndex = (draggingPointIndex + 2) % 4;
        const anchor = points[anchorIndex];

        const x1 = anchor.x;
        const y1 = anchor.y;
        const x2 = x;
        const y2 = y;

        const minX = Math.min(x1, x2);
        const maxX = Math.max(x1, x2);
        const minY = Math.min(y1, y2);
        const maxY = Math.max(y1, y2);

        const rectPoints = [
          { x: minX, y: minY },
          { x: maxX, y: minY },
          { x: maxX, y: maxY },
          { x: minX, y: maxY },
        ];
        setPoints(rectPoints);
        return;
      }
    }

    // 폴리곤 모드
    if (draggingPointIndex !== null) {
      // 드래그 중: 점 위치 업데이트
      const newPoints = [...points];
      newPoints[draggingPointIndex] = { x, y };
      setPoints(newPoints);
    } else {
      // hover 감지
      const pointIndex = getPointAtPosition(x, y);
      setHoveredPointIndex(pointIndex);
    }
  };

  const handleCanvasMouseUp = () => {
    if (selectionMode === 'rect' && points.length === 4) {
      // 사각형 선택/수정 완료 → rect 영역으로 onAreaChange 호출
      const xs = points.map(p => p.x);
      const ys = points.map(p => p.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = maxX - minX;
      const height = maxY - minY;

      if (width > 0 && height > 0) {
        setIsComplete(true);
        onAreaChange({
          type: 'rect',
          x: minX,
          y: minY,
          width,
          height,
        });
      }
    }

    setIsRectSelecting(false);
    setDraggingPointIndex(null);
    setIsPanning(false);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    // 마우스 위치 (버튼 클릭 시에는 캔버스 중심)
    const mouseX = e.clientX === 0 ? rect.width / 2 : e.clientX - rect.left;
    const mouseY = e.clientY === 0 ? rect.height / 2 : e.clientY - rect.top;
    
    // 줌 전 마우스 위치의 이미지 좌표
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const canvasX = mouseX * scaleX;
    const canvasY = mouseY * scaleY;
    const imageX = (canvasX - offset.x) / scale;
    const imageY = (canvasY - offset.y) / scale;
    
    // 줌 배율 계산 (최소 0.1배, 최대 10배)
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.1, Math.min(10, scale * delta));
    
    // 줌 후 마우스 위치가 같은 이미지 좌표를 가리키도록 offset 조정
    const newOffsetX = canvasX - imageX * newScale;
    const newOffsetY = canvasY - imageY * newScale;
    
    setScale(newScale);
    setOffset({ x: newOffsetX, y: newOffsetY });
  };

  const handleResetZoom = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  const handleCompleteSelection = () => {
    if (selectionMode === 'rect') {
      // 사각형 모드에서는 드래그로 이미 선택 완료되므로 별도 완료 버튼 필요 없음
      return;
    }

    if (points.length < 3) {
      alert('최소 3개 이상의 점을 선택해주세요.');
      return;
    }
    
    setIsComplete(true);
    
    // 폴리곤 데이터를 상위 컴포넌트에 전달
    onAreaChange({
      type: 'polygon',
      points: points
    });
  };

  const handleResetSelection = () => {
    setPoints([]);
    setIsComplete(false);
    setIsRectSelecting(false);
    setRectStart(null);
    onAreaChange(null);
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith('image/')) {
      onImageUpload(file);
      setPoints([]);
      setIsComplete(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      onImageUpload(file);
      setPoints([]);
      setIsComplete(false);
    }
  };

  return (
    <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-6">
      <h2 className="text-xl font-semibold mb-4 text-white">건물 사진 업로드</h2>
      
      {!imageUrl ? (
        <div
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer ${
            isDragging ? 'border-blue-500 bg-blue-500/10' : 'border-white/20 hover:border-blue-500'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input').click()}
        >
          <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-gray-400">클릭하거나 드래그해서 이미지 업로드</p>
          <p className="text-gray-500 text-sm mt-2">JPG, PNG, GIF 등</p>
          <input
            id="file-input"
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
      ) : (
        <div>
          <div className="mb-4 relative">
            {/* 선택 모드 토글 */}
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => {
                  setSelectionMode('polygon');
                  handleResetSelection();
                }}
                className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
                  selectionMode === 'polygon'
                    ? 'bg-blue-500 border-blue-500 text-white'
                    : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
                }`}
              >
                🔺 점찍기(다각형)
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectionMode('rect');
                  handleResetSelection();
                }}
                className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
                  selectionMode === 'rect'
                    ? 'bg-emerald-500 border-emerald-500 text-white'
                    : 'bg-white/5 border-white/20 text-gray-300 hover:border-emerald-500'
                }`}
              >
                ▭ 사각형 드래그
              </button>
            </div>
            <canvas
              ref={canvasRef}
              onMouseDown={handleCanvasMouseDown}
              onMouseMove={handleCanvasMouseMove}
              onMouseUp={handleCanvasMouseUp}
              onMouseLeave={() => { setHoveredPointIndex(null); setDraggingPointIndex(null); setIsPanning(false); }}
              onContextMenu={(e) => e.preventDefault()}
              className={`max-w-full h-auto border border-white/20 rounded-lg ${
                isPanning ? 'cursor-grabbing' :
                draggingPointIndex !== null ? 'cursor-grabbing' : 
                hoveredPointIndex !== null ? 'cursor-grab' :
                isComplete ? 'cursor-default' :
                selectionMode === 'rect' ? 'cursor-crosshair' : 'cursor-crosshair'
              }`}
              style={{ maxHeight: '500px' }}
            />
            
            {/* 줌 컨트롤 */}
            <div className="absolute top-3 right-3 flex flex-col gap-2 bg-black/50 backdrop-blur-sm rounded-lg p-2">
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
            <div className="absolute bottom-3 left-3 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-2 text-xs text-gray-300">
              <div>💡 <strong>마우스 휠</strong>: 확대/축소</div>
              <div>💡 <strong>우클릭 드래그</strong>: 이미지 이동</div>
            </div>
          </div>

          <div className="space-y-3">
            {/* 상태 표시 */}
            <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
              <span className="text-sm text-gray-300">
                {selectionMode === 'polygon' ? (
                  isComplete 
                    ? `✓ 영역 선택 완료 (${points.length}개 점)` 
                    : `점 클릭: ${points.length}개 (최소 3개)`
                ) : (
                  isComplete
                    ? '✓ 사각형 영역 선택 완료'
                    : '드래그해서 사각형 영역을 선택하세요'
                )}
              </span>
              {!isComplete && points.length >= 3 && (
                <span className="text-xs text-green-400">→ 영역 완료 버튼을 누르세요</span>
              )}
            </div>

            {/* 버튼들 */}
            <div className="flex gap-3">
              {selectionMode === 'polygon' ? (
                !isComplete ? (
                  <>
                    <button
                      onClick={handleCompleteSelection}
                      disabled={points.length < 3}
                      className="flex-1 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg px-6 py-3 text-white font-semibold disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed hover:scale-105 transition-transform"
                    >
                      영역 완료
                    </button>
                    <button
                      onClick={handleResetSelection}
                      className="px-6 py-3 bg-white/5 border border-white/20 rounded-lg text-white hover:bg-white/10 transition-colors"
                    >
                      다시 선택
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={handleResetSelection}
                      className="flex-1 px-6 py-3 bg-white/5 border border-white/20 rounded-lg text-white hover:bg-white/10 transition-colors"
                    >
                      영역 다시 선택
                    </button>
                    <button
                      onClick={() => {
                        setImageUrl(null);
                        onImageUpload(null);
                        setPoints([]);
                        setIsComplete(false);
                      }}
                      className="px-6 py-3 bg-red-500/80 hover:bg-red-500 rounded-lg text-white transition-colors"
                    >
                      사진 변경
                    </button>
                  </>
                )
              ) : (
                <>
                  <button
                    onClick={handleResetSelection}
                    className="flex-1 px-6 py-3 bg-white/5 border border-white/20 rounded-lg text-white hover:bg-white/10 transition-colors"
                  >
                    영역 다시 선택
                  </button>
                  <button
                    onClick={() => {
                      setImageUrl(null);
                      onImageUpload(null);
                      setPoints([]);
                      setIsComplete(false);
                    }}
                    className="px-6 py-3 bg-red-500/80 hover:bg-red-500 rounded-lg text-white transition-colors"
                  >
                    사진 변경
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageUploader;
