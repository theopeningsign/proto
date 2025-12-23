import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import ImageUploader from './components/ImageUploader';
import SignboardForm from './components/SignboardForm';
import ResultViewer from './components/ResultViewer';

function App() {
  const [buildingImage, setBuildingImage] = useState(null);
  // 복수 간판 상태: 각 간판별 영역 + 옵션
  const createDefaultFormData = () => ({
    signboardInputType: 'text',
    text: '',
    logo: null,
    logoType: 'channel',
    signboardImage: null,
    installationType: '맨벽',
    signType: '전광채널',
    bgColor: '#6B2D8F',
    textColor: '#FFFFFF',
    textDirection: 'horizontal',
    fontSize: 100,
    originalFontSize: 100,
    textPositionX: 50,
    textPositionY: 50,
    orientation: 'auto',
    flipHorizontal: false,
    flipVertical: false,
    rotate90: 0,
    rotation: 0.0,
    removeWhiteBg: false
  });

  const [signboards, setSignboards] = useState([]); // {id, name, selectedArea, formData}
  const [currentSignboardId, setCurrentSignboardId] = useState(null);
  const [lights, setLights] = useState([]);
  const [lightsEnabled, setLightsEnabled] = useState(true);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(null); // 'basic' or 'ai'
  const [loadingProgress, setLoadingProgress] = useState(0); // 0-100
  const [showComingSoonModal, setShowComingSoonModal] = useState(false);
  const isFirstRender = useRef(true);

  const getCurrentSignboard = () =>
    signboards.find((sb) => sb.id === currentSignboardId) || null;

  const handleDeleteSignboard = (signboardId) => {
    if (signboards.length <= 1) {
      alert('간판은 최소 1개 이상 있어야 합니다.');
      return;
    }

    const newSignboards = signboards.filter((sb) => sb.id !== signboardId);
    setSignboards(newSignboards);

    // 삭제된 간판이 현재 선택된 간판이면 다른 간판으로 전환
    if (currentSignboardId === signboardId) {
      if (newSignboards.length > 0) {
        setCurrentSignboardId(newSignboards[0].id);
      } else {
        setCurrentSignboardId(null);
      }
    }
  };

  // 조명 켜기/끄기 시 자동 반영
  useEffect(() => {
    // 첫 렌더링 시에는 실행하지 않음
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    
    // 시뮬레이션 결과가 있을 때만 자동 반영 (기본 모드로)
    if (results) {
      handleGenerate('basic');
    }
  }, [lightsEnabled]);

  const handleApplyLights = async () => {
    // 조명 반영하기: 현재 조명 상태로 재생성 (기본 모드로)
    console.log('[프론트엔드] 조명 반영하기 버튼 클릭');
    console.log('[프론트엔드] 현재 lights:', lights);
    console.log('[프론트엔드] lightsEnabled:', lightsEnabled);
    await handleGenerate('basic');
  };

  // Phase 1만 실행 (빠른 생성)
  const handleQuickGenerate = async () => {
    await handleGenerate('basic');
  };

  // Phase 1 + Phase 2 실행 (AI 고품질)
  const handleAIGenerate = async () => {
    await handleGenerate('ai');
  };

  // 공통 생성 함수
  const handleGenerate = async (mode = 'basic') => {
    if (!buildingImage) {
      alert('건물 사진을 업로드해주세요.');
      return;
    }

    if (!signboards.length) {
      alert('간판을 하나 이상 추가하고 영역을 선택해주세요.');
      return;
    }

    setLoadingPhase(mode);
    setLoadingProgress(0);

    // 각 간판별 유효성 검사
    for (const sb of signboards) {
      if (!sb.selectedArea) {
        alert('모든 간판에 대해 간판 영역을 선택해주세요.');
        return;
      }
      if (sb.formData.signboardInputType === 'text' && !sb.formData.text.trim()) {
        alert('모든 간판의 상호명을 입력해주세요.');
        return;
      }
      if (sb.formData.signboardInputType === 'image' && !sb.formData.signboardImage) {
        alert('이미지 간판의 경우 간판 이미지를 업로드해주세요.');
        return;
      }
    }

    setLoading(true);

    try {
      // 이미지를 base64로 변환
      const buildingBase64 = await imageToBase64(buildingImage);
      const signboardsPayload = [];

      for (const sb of signboards) {
        const sbForm = sb.formData;

        let logoBase64 = '';
        let signboardImageBase64 = '';

        if (sbForm.logo) {
          logoBase64 = await imageToBase64(sbForm.logo);
        }

        if (sbForm.signboardImage) {
          signboardImageBase64 = await imageToBase64(sbForm.signboardImage);
        }

        // 선택된 영역을 점 배열로 변환
        let points;
        if (sb.selectedArea.type === 'polygon') {
          points = sb.selectedArea.points.map((p) => [p.x, p.y]);
        } else {
          points = [
            [sb.selectedArea.x, sb.selectedArea.y],
            [sb.selectedArea.x + sb.selectedArea.width, sb.selectedArea.y],
            [sb.selectedArea.x + sb.selectedArea.width, sb.selectedArea.y + sb.selectedArea.height],
            [sb.selectedArea.x, sb.selectedArea.y + sb.selectedArea.height]
          ];
        }

        signboardsPayload.push({
          polygon_points: points,
          signboard_input_type: sbForm.signboardInputType,
          text: sbForm.text || '',
          logo: logoBase64,
          signboard_image: signboardImageBase64,
          installation_type: sbForm.installationType || '맨벽',
          sign_type: sbForm.signType,
          bg_color: sbForm.bgColor,
          text_color: sbForm.textColor,
          text_direction: sbForm.textDirection || 'horizontal',
          font_size: parseInt(sbForm.fontSize) || 100,
          text_position_x: parseInt(sbForm.textPositionX) || 50,
          text_position_y: parseInt(sbForm.textPositionY) || 50,
          logo_type: sbForm.logoType || 'channel',
          orientation: sbForm.orientation || 'auto',
          flip_horizontal: sbForm.flipHorizontal ? 'true' : 'false',
          flip_vertical: sbForm.flipVertical ? 'true' : 'false',
          rotate90: parseInt(sbForm.rotate90) || 0,
          rotation: parseFloat(sbForm.rotation) || 0.0,
          remove_white_bg: sbForm.removeWhiteBg ? 'true' : 'false'
        });
      }

      // API 호출 (복수 간판)
      const formDataToSend = new FormData();
      formDataToSend.append('building_photo', buildingBase64);
      // 기존 백엔드 시그니처 유지용 (첫 간판 폴리곤 전달, 실제 처리는 signboards에서)
      const firstArea = signboards[0].selectedArea;
      let firstPoints;
      if (firstArea.type === 'polygon') {
        firstPoints = firstArea.points.map((p) => [p.x, p.y]);
      } else {
        firstPoints = [
          [firstArea.x, firstArea.y],
          [firstArea.x + firstArea.width, firstArea.y],
          [firstArea.x + firstArea.width, firstArea.y + firstArea.height],
          [firstArea.x, firstArea.y + firstArea.height]
        ];
      }
      formDataToSend.append('polygon_points', JSON.stringify(firstPoints));
      formDataToSend.append('signboards', JSON.stringify(signboardsPayload));

      // 백엔드 기존 시그니처 유지를 위해 첫 번째 간판 정보를 함께 전송
      const firstForm = signboards[0].formData;
      formDataToSend.append('signboard_input_type', firstForm.signboardInputType);
      formDataToSend.append('text', firstForm.text || '');
      formDataToSend.append('logo', signboardsPayload[0].logo || '');
      formDataToSend.append('signboard_image', signboardsPayload[0].signboard_image || '');
      formDataToSend.append('installation_type', firstForm.installationType || '맨벽');
      formDataToSend.append('sign_type', firstForm.signType);
      formDataToSend.append('bg_color', firstForm.bgColor);
      formDataToSend.append('text_color', firstForm.textColor);
      formDataToSend.append('text_direction', firstForm.textDirection || 'horizontal');
      formDataToSend.append('font_size', String(parseInt(firstForm.fontSize) || 100));
      formDataToSend.append('text_position_x', String(parseInt(firstForm.textPositionX) || 50));
      formDataToSend.append('text_position_y', String(parseInt(firstForm.textPositionY) || 50));
      formDataToSend.append('logo_type', firstForm.logoType || 'channel');
      formDataToSend.append('orientation', firstForm.orientation || 'auto');
      formDataToSend.append('flip_horizontal', firstForm.flipHorizontal ? 'true' : 'false');
      formDataToSend.append('flip_vertical', firstForm.flipVertical ? 'true' : 'false');
      formDataToSend.append('rotate90', String(parseInt(firstForm.rotate90) || 0));
      formDataToSend.append('rotation', String(parseFloat(firstForm.rotation) || 0.0));
      formDataToSend.append('remove_white_bg', firstForm.removeWhiteBg ? 'true' : 'false');
      formDataToSend.append('lights', JSON.stringify(lights || []));
      formDataToSend.append('lights_enabled', lightsEnabled ? 'true' : 'false');
      
      console.log('[프론트엔드] API 요청 직전 - lights:', JSON.stringify(lights));
      console.log('[프론트엔드] API 요청 직전 - lights_enabled:', lightsEnabled);

      // Phase 1 진행 상태 업데이트
      setLoadingProgress(30);

      // Phase 1: 기본 생성
      const response = await fetch('http://localhost:8000/api/generate-simulation', {
        method: 'POST',
        body: formDataToSend
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      console.log('[프론트엔드] Phase 1 완료');
      setLoadingProgress(70);

      // Phase 2: AI 고품질 모드인 경우
      if (mode === 'ai') {
        try {
          setLoadingProgress(80);
          
          // Phase 2 API 호출 (나중에 구현)
          const aiResponse = await fetch('http://localhost:8000/api/generate-hq', {
            method: 'POST',
            body: formDataToSend
          });

          const aiData = await aiResponse.json();
          
          if (aiData.error) {
            console.warn('AI 개선 실패, 기본 품질로 표시:', aiData.error);
            // AI 실패해도 Phase 1 결과는 표시
            setResults({
              ...data,
              ai_image: null,
              ai_error: aiData.error
            });
          } else {
            // AI 성공: AI 결과 사용
            setResults({
              day_simulation: aiData.day_simulation || data.day_simulation,
              night_simulation: aiData.night_simulation || data.night_simulation,
              basic_day_simulation: data.day_simulation, // 비교용
              basic_night_simulation: data.night_simulation, // 비교용
              ai_image: aiData.ai_image,
              processing_time: aiData.processing_time
            });
          }
          
          setLoadingProgress(100);
        } catch (aiError) {
          console.error('AI 개선 중 오류:', aiError);
          // AI 실패해도 Phase 1 결과는 표시
          setResults({
            ...data,
            ai_image: null,
            ai_error: aiError.message
          });
          setLoadingProgress(100);
        }
      } else {
        // Phase 1만: 기본 결과 사용
        setResults(data);
        setLoadingProgress(100);
      }
      
      console.log('[프론트엔드] API 응답 받음');
      console.log('[프론트엔드] setResults 호출 전 - results:', results);
    } catch (error) {
      console.error('Error:', error);
      alert('시뮬레이션 생성 중 오류가 발생했습니다: ' + error.message);
    } finally {
      setLoading(false);
      setLoadingPhase(null);
      setLoadingProgress(0);
    }
  };

  const imageToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black">
      <div className="max-w-7xl mx-auto px-4 py-12">
        {/* 헤더 */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600 mb-4">
            간판 시안 생성기
          </h1>
          <p className="text-gray-400 text-lg">AI로 간판을 실제 건물에 합성해보세요</p>
        </motion.header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* 왼쪽: 건물 사진 업로드 + 간판 기본 정보 */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="space-y-6"
          >
            <ImageUploader
              image={buildingImage}
              onImageUpload={setBuildingImage}
              selectedArea={getCurrentSignboard()?.selectedArea || null}
              onAreaChange={(area) => {
                if (currentSignboardId === null) {
                  // 첫 간판 생성
                  const newId = Date.now();
                  const newSignboard = {
                    id: newId,
                    name: `간판 1`,
                    selectedArea: area,
                    formData: createDefaultFormData()
                  };
                  setSignboards([newSignboard]);
                  setCurrentSignboardId(newId);
                } else {
                  setSignboards((prev) =>
                    prev.map((sb) =>
                      sb.id === currentSignboardId ? { ...sb, selectedArea: area } : sb
                    )
                  );
                }
              }}
              signboards={signboards.map((sb) => ({
                id: sb.id,
                selectedArea: sb.selectedArea
              }))}
              currentSignboardId={currentSignboardId}
            />
            
            {/* 간판 선택/추가 탭 */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-3 flex items-center justify-between">
              <div className="flex flex-wrap gap-2">
                {signboards.map((sb, idx) => (
                  <div
                    key={sb.id}
                    className="flex items-center gap-1"
                  >
                    <button
                      type="button"
                      onClick={() => setCurrentSignboardId(sb.id)}
                      className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
                        currentSignboardId === sb.id
                          ? 'bg-blue-500 border-blue-400 text-white'
                          : 'bg-black/40 border-white/20 text-gray-200 hover:border-blue-400'
                      }`}
                    >
                      {sb.name || `간판 ${idx + 1}`}
                    </button>
                    {signboards.length > 1 && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSignboard(sb.id);
                        }}
                        className="px-1.5 py-1 rounded text-xs bg-red-500/80 hover:bg-red-500 text-white transition-colors"
                        title="간판 삭제"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => {
                  const newId = Date.now();
                  const newIndex = signboards.length + 1;
                  const newSignboard = {
                    id: newId,
                    name: `간판 ${newIndex}`,
                    selectedArea: null,
                    formData: createDefaultFormData()
                  };
                  setSignboards((prev) => [...prev, newSignboard]);
                  setCurrentSignboardId(newId);
                }}
                className="px-3 py-1 rounded-lg text-xs bg-emerald-500/80 hover:bg-emerald-500 text-white"
              >
                + 간판 추가
              </button>
            </div>

            <SignboardForm
              formData={getCurrentSignboard()?.formData || createDefaultFormData()}
              onFormDataChange={(updated) => {
                if (currentSignboardId === null) {
                  const newId = Date.now();
                  const newSignboard = {
                    id: newId,
                    name: `간판 1`,
                    selectedArea: null,
                    formData: updated
                  };
                  setSignboards([newSignboard]);
                  setCurrentSignboardId(newId);
                } else {
                  setSignboards((prev) =>
                    prev.map((sb) =>
                      sb.id === currentSignboardId ? { ...sb, formData: updated } : sb
                    )
                  );
                }
              }}
              section="basic"
            />
          </motion.div>

          {/* 오른쪽: 시뮬레이션 결과 + 세부 옵션 */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="space-y-6"
          >
            <ResultViewer
              results={results}
              textSizeInfo={results ? {
                text_width: results.text_width,
                text_height: results.text_height,
                signboard_width: results.signboard_width,
                signboard_height: results.signboard_height
              } : null}
              loading={loading}
              lights={lights}
              onLightsChange={setLights}
              lightsEnabled={lightsEnabled}
              onToggleEnabled={setLightsEnabled}
              onApplyLights={handleApplyLights}
              signboards={signboards}
              onRegenerateWithTransforms={async (transforms) => {
                if (!buildingImage || !signboards.length) return;
                setLoading(true);
                try {
                  const buildingBase64 = await imageToBase64(buildingImage);
                  // transforms: [{id, ...transform}]
                  const updatedSignboards = signboards.map((sb) => {
                    const t = Array.isArray(transforms)
                      ? transforms.find((tr) => tr.id === sb.id)
                      : null;
                    if (!t) return sb;
                    const updatedFormData = { ...sb.formData };
                    if (t.fontSize !== undefined) {
                      updatedFormData.fontSize = t.fontSize;
                    }
                    if (t.textPositionX !== undefined) {
                      updatedFormData.textPositionX = t.textPositionX;
                    }
                    if (t.textPositionY !== undefined) {
                      updatedFormData.textPositionY = t.textPositionY;
                    }
                    if (t.rotation !== undefined) {
                      updatedFormData.rotation = t.rotation;
                    }
                    return { ...sb, formData: updatedFormData };
                  });

                  setSignboards(updatedSignboards);

                  // 백엔드로 전송할 signboardsPayload 재구성
                  const signboardsPayload = [];

                  for (const sb of updatedSignboards) {
                    const sbForm = sb.formData;

                    let logoBase64 = '';
                    let signboardImageBase64 = '';

                    if (sbForm.logo) {
                      logoBase64 = await imageToBase64(sbForm.logo);
                    }
                    if (sbForm.signboardImage) {
                      signboardImageBase64 = await imageToBase64(sbForm.signboardImage);
                    }

                    let points;
                    if (sb.selectedArea.type === 'polygon') {
                      points = sb.selectedArea.points.map((p) => [p.x, p.y]);
                    } else {
                      points = [
                        [sb.selectedArea.x, sb.selectedArea.y],
                        [sb.selectedArea.x + sb.selectedArea.width, sb.selectedArea.y],
                        [sb.selectedArea.x + sb.selectedArea.width, sb.selectedArea.y + sb.selectedArea.height],
                        [sb.selectedArea.x, sb.selectedArea.y + sb.selectedArea.height]
                      ];
                    }

                    signboardsPayload.push({
                      polygon_points: points,
                      signboard_input_type: sbForm.signboardInputType,
                      text: sbForm.text || '',
                      logo: logoBase64,
                      signboard_image: signboardImageBase64,
                      installation_type: sbForm.installationType || '맨벽',
                      sign_type: sbForm.signType,
                      bg_color: sbForm.bgColor,
                      text_color: sbForm.textColor,
                      text_direction: sbForm.textDirection || 'horizontal',
                      font_size: parseInt(sbForm.fontSize) || 100,
                      text_position_x: parseInt(sbForm.textPositionX) || 50,
                      text_position_y: parseInt(sbForm.textPositionY) || 50,
                      logo_type: sbForm.logoType || 'channel',
                      orientation: sbForm.orientation || 'auto',
                      flip_horizontal: sbForm.flipHorizontal ? 'true' : 'false',
                      flip_vertical: sbForm.flipVertical ? 'true' : 'false',
                      rotate90: parseInt(sbForm.rotate90) || 0,
                      rotation: parseFloat(sbForm.rotation) || 0.0
                    });
                  }

                  const formDataToSend = new FormData();
                  formDataToSend.append('building_photo', buildingBase64);
                  const firstArea = updatedSignboards[0].selectedArea;
                  let firstPoints;
                  if (firstArea.type === 'polygon') {
                    firstPoints = firstArea.points.map((p) => [p.x, p.y]);
                  } else {
                    firstPoints = [
                      [firstArea.x, firstArea.y],
                      [firstArea.x + firstArea.width, firstArea.y],
                      [firstArea.x + firstArea.width, firstArea.y + firstArea.height],
                      [firstArea.x, firstArea.y + firstArea.height]
                    ];
                  }
                  formDataToSend.append('polygon_points', JSON.stringify(firstPoints));
                  formDataToSend.append('signboards', JSON.stringify(signboardsPayload));

                  // 백엔드 기존 시그니처 유지를 위해 첫 번째 간판 정보를 함께 전송
                  const firstForm = updatedSignboards[0].formData;
                  formDataToSend.append('signboard_input_type', firstForm.signboardInputType);
                  formDataToSend.append('text', firstForm.text || '');
                  formDataToSend.append('logo', signboardsPayload[0].logo || '');
                  formDataToSend.append('signboard_image', signboardsPayload[0].signboard_image || '');
                  formDataToSend.append('installation_type', firstForm.installationType || '맨벽');
                  formDataToSend.append('sign_type', firstForm.signType);
                  formDataToSend.append('bg_color', firstForm.bgColor);
                  formDataToSend.append('text_color', firstForm.textColor);
                  formDataToSend.append('text_direction', firstForm.textDirection || 'horizontal');
                  formDataToSend.append('font_size', String(parseInt(firstForm.fontSize) || 100));
                  formDataToSend.append('text_position_x', String(parseInt(firstForm.textPositionX) || 50));
                  formDataToSend.append('text_position_y', String(parseInt(firstForm.textPositionY) || 50));
                  formDataToSend.append('logo_type', firstForm.logoType || 'channel');
                  formDataToSend.append('orientation', firstForm.orientation || 'auto');
                  formDataToSend.append('flip_horizontal', firstForm.flipHorizontal ? 'true' : 'false');
                  formDataToSend.append('flip_vertical', firstForm.flipVertical ? 'true' : 'false');
                  formDataToSend.append('rotate90', String(parseInt(firstForm.rotate90) || 0));
                  const rotationValue = firstForm.rotation !== undefined ? parseFloat(firstForm.rotation) : 0.0;
                  formDataToSend.append('rotation', String(rotationValue));
                  formDataToSend.append('lights', JSON.stringify(lights || []));
                  formDataToSend.append('lights_enabled', lightsEnabled ? 'true' : 'false');

                  // FormData 내용 확인 (디버깅용)
                  console.log('[API 요청] FormData rotation 값 확인:');
                  const rotationFormValue = formDataToSend.get('rotation');
                  console.log('  formDataToSend.get("rotation"):', rotationFormValue);

                  const response = await fetch('http://localhost:8000/api/generate-simulation', {
                    method: 'POST',
                    body: formDataToSend
                  });

                  const data = await response.json();
                  if (data.error) {
                    console.error('[API 오류]', data.error);
                    if (data.traceback) {
                      console.error('[API Traceback]', data.traceback);
                    }
                    throw new Error(data.error);
                  }
                  
                  console.log('[API 응답] 성공적으로 받음');
                  setResults(data);
                } catch (error) {
                  console.error('Error:', error);
                  alert('오류가 발생했습니다: ' + error.message);
                } finally {
                  setLoading(false);
                }
              }}
            />
            
            <SignboardForm
              formData={getCurrentSignboard()?.formData || createDefaultFormData()}
              onFormDataChange={(updated) => {
                if (currentSignboardId === null) {
                  const newId = Date.now();
                  const newSignboard = {
                    id: newId,
                    name: `간판 1`,
                    selectedArea: null,
                    formData: updated
                  };
                  setSignboards([newSignboard]);
                  setCurrentSignboardId(newId);
                } else {
                  setSignboards((prev) =>
                    prev.map((sb) =>
                      sb.id === currentSignboardId ? { ...sb, formData: updated } : sb
                    )
                  );
                }
              }}
              section="advanced"
            />
          </motion.div>
        </div>

        {/* 시안 생성 버튼 2개 (빠른 생성 / AI 고품질) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 빠른 생성 버튼 (Phase 1만) */}
          <motion.button
            onClick={handleQuickGenerate}
            disabled={loading}
            whileHover={{ scale: loading ? 1 : 1.02 }}
            whileTap={{ scale: loading ? 1 : 0.98 }}
            className="relative bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg px-6 py-4 text-white font-semibold shadow-lg disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed transition-all flex flex-col items-center gap-1"
          >
            {loading && loadingPhase === 'basic' ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                생성 중...
              </span>
            ) : (
              <>
                <span className="text-lg">⚡ 빠른 생성</span>
                <span className="text-xs opacity-80">즉시 • 기본 품질</span>
              </>
            )}
            {/* 진행률 표시 */}
            {loading && loadingPhase === 'basic' && loadingProgress > 0 && (
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-blue-300/30 rounded-b-lg overflow-hidden">
                <motion.div
                  className="h-full bg-blue-200"
                  initial={{ width: 0 }}
                  animate={{ width: `${loadingProgress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            )}
          </motion.button>

          {/* AI 고품질 버튼 (Phase 1 + Phase 2) - 준비 중 상태 */}
          <motion.button
            onClick={() => setShowComingSoonModal(true)}
            disabled={true}
            className="relative bg-gradient-to-br from-gray-600 to-gray-700 rounded-lg px-6 py-4 text-white font-semibold opacity-60 cursor-not-allowed transition-all flex flex-col items-center gap-1"
            title="AI 품질 개선 기능은 Phase 2에서 제공됩니다 (Week 7 출시 예정)"
          >
            {/* 준비 중 배지 */}
            <span className="absolute -top-2 -right-2 bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded-full">
              준비 중
            </span>
            
            <div className="flex items-center gap-2 text-lg">
              <span className="opacity-50">✨</span>
              <span>AI 고품질</span>
            </div>
            <span className="text-xs opacity-60">Week 7 출시 예정</span>
          </motion.button>
        </div>

        {/* 로딩 상태 상세 표시 */}
        {loading && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-300">
                  {loadingPhase === 'basic' ? '⚡ 빠른 생성 중' : '✨ AI 고품질 생성 중'}
                </span>
                <span className="text-gray-400">{loadingProgress}%</span>
              </div>
              
              {/* 단계별 진행 상태 */}
              <div className="space-y-1 text-xs text-gray-400">
                {loadingPhase === 'basic' ? (
                  <>
                    <div className={loadingProgress >= 30 ? 'text-green-400' : ''}>
                      {loadingProgress >= 30 ? '✓' : '○'} 간판 렌더링
                    </div>
                    <div className={loadingProgress >= 70 ? 'text-green-400' : loadingProgress >= 30 ? 'text-yellow-400' : ''}>
                      {loadingProgress >= 70 ? '✓' : loadingProgress >= 30 ? '⏳' : '○'} 건물 합성
                    </div>
                    <div className={loadingProgress >= 100 ? 'text-green-400' : ''}>
                      {loadingProgress >= 100 ? '✓' : '○'} 완료
                    </div>
                  </>
                ) : (
                  <>
                    <div className={loadingProgress >= 30 ? 'text-green-400' : ''}>
                      {loadingProgress >= 30 ? '✓' : '○'} 간판 렌더링
                    </div>
                    <div className={loadingProgress >= 70 ? 'text-green-400' : loadingProgress >= 30 ? 'text-yellow-400' : ''}>
                      {loadingProgress >= 70 ? '✓' : loadingProgress >= 30 ? '⏳' : '○'} 건물 합성
                    </div>
                    <div className={loadingProgress >= 100 ? 'text-green-400' : loadingProgress >= 80 ? 'text-yellow-400' : ''}>
                      {loadingProgress >= 100 ? '✓' : loadingProgress >= 80 ? '⏳' : '○'} AI 품질 개선
                    </div>
                    <div className={loadingProgress >= 100 ? 'text-green-400' : ''}>
                      {loadingProgress >= 100 ? '✓' : '○'} 완료
                    </div>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* AI 고품질 준비 중 모달 */}
        {showComingSoonModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowComingSoonModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-gray-800 rounded-2xl p-6 max-w-md mx-4 border border-gray-700"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <span>🚀</span>
                <span>AI 고품질 모드 준비 중</span>
              </h3>
              <p className="text-gray-300 mb-6 leading-relaxed">
                AI 품질 개선 기능은 현재 개발 중입니다.
                <br /><br />
                <strong className="text-white">출시 예정:</strong> Week 7 (약 2주 후)
                <br /><br />
                <strong className="text-white">주요 기능:</strong>
                <br />
                • Phase 1 결과를 실사 수준으로 개선
                <br />
                • 디테일 추가 (천 텍스처, 금속 반사 등)
                <br />
                • 처리 시간: 2-3초
              </p>
              <div className="flex gap-3">
                <button
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
                  onClick={() => {
                    alert('알림 신청이 완료되었습니다!');
                    setShowComingSoonModal(false);
                  }}
                >
                  알림 신청
                </button>
                <button
                  className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white font-medium transition-colors"
                  onClick={() => setShowComingSoonModal(false)}
                >
                  닫기
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default App;
