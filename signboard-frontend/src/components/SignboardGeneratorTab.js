import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import ImageUploader from './ImageUploader';
import SignboardForm from './SignboardForm';
import ResultViewer from './ResultViewer';

const SignboardGeneratorTab = ({ savedBrandings }) => {
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
    fontFamily: 'malgun',  // 기본: 맑은 고딕
    fontWeight: '400',  // 기본: 일반 (400 = regular)
    textPositionX: 50,
    textPositionY: 50,
    orientation: 'auto',
    flipHorizontal: false,
    flipVertical: false,
    rotate90: 0,
    rotation: 0.0,
    removeWhiteBg: false,
    // 치수 필드 추가 (평면도용)
    width_mm: null,  // null이면 자동 계산
    height_mm: null   // null이면 자동 계산
  });

  // 독립 사용을 위해 기본 간판 초기화
  const [signboards, setSignboards] = useState(() => {
    const defaultId = 1; // 간단한 ID 사용
    return [{
      id: defaultId,
      name: '간판 1',
      selectedArea: null,
      formData: createDefaultFormData()
    }];
  });
  
  const [currentSignboardId, setCurrentSignboardId] = useState(1);
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

    if (signboards.length === 0) {
      alert('간판 영역을 선택해주세요.');
      return;
    }

    // 현재 활성 간판이 있는지 확인
    const currentSignboard = getCurrentSignboard();
    if (!currentSignboard) {
      alert('활성화된 간판을 선택해주세요.');
      return;
    }

    if (!currentSignboard.selectedArea) {
      alert('간판 영역을 선택해주세요.');
      return;
    }

    if (!currentSignboard.formData.text) {
      alert('간판 텍스트를 입력해주세요.');
      return;
    }

    setLoading(true);
    setLoadingPhase(mode);
    setLoadingProgress(0);
    setResults(null);

    try {
      const formData = new FormData();
      formData.append('building_image', buildingImage);
      formData.append('text', currentSignboard.formData.text);
      formData.append('font_size', currentSignboard.formData.fontSize);
      formData.append('font_color', currentSignboard.formData.textColor);
      formData.append('bg_color', currentSignboard.formData.bgColor);
      formData.append('sign_type', currentSignboard.formData.signType);
      formData.append('installation_type', currentSignboard.formData.installationType);
      formData.append('x', currentSignboard.selectedArea.x);
      formData.append('y', currentSignboard.selectedArea.y);
      formData.append('width', currentSignboard.selectedArea.width);
      formData.append('height', currentSignboard.selectedArea.height);
      formData.append('text_direction', currentSignboard.formData.textDirection);
      formData.append('flip_horizontal', currentSignboard.formData.flipHorizontal);
      formData.append('flip_vertical', currentSignboard.formData.flipVertical);
      formData.append('rotate_90', currentSignboard.formData.rotate90);
      formData.append('rotation', currentSignboard.formData.rotation);
      formData.append('remove_white_bg', currentSignboard.formData.removeWhiteBg);

      if (currentSignboard.formData.logo) {
        formData.append('logo', currentSignboard.formData.logo);
      }

      // 조명 정보 추가
      if (lightsEnabled && lights.length > 0) {
        formData.append('lights', JSON.stringify(lights));
        formData.append('lights_enabled', 'true');
      } else {
        formData.append('lights_enabled', 'false');
      }

      // 로딩 진행률 시뮬레이션
      const interval = setInterval(() => {
        setLoadingProgress((prev) => Math.min(prev + Math.random() * 10, 85));
      }, 500);

      const response = await fetch('http://localhost:8000/api/generate-simulation', {
        method: 'POST',
        body: formData,
      });

      clearInterval(interval);
      setLoadingProgress(100);

      if (response.ok) {
        const result = await response.json();
        setResults(result);
      } else {
        throw new Error('시뮬레이션 생성에 실패했습니다.');
      }
    } catch (error) {
      console.error('API 호출 오류:', error);
      alert('시뮬레이션 생성 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
      setLoadingPhase(null);
      setLoadingProgress(0);
    }
  };

  // 브랜딩 자산 적용 함수
  const applyBrandingAsset = (brandingAsset) => {
    if (!currentSignboardId) return;
    
    setSignboards((prev) =>
      prev.map((sb) =>
        sb.id === currentSignboardId
          ? {
              ...sb,
              formData: {
                ...sb.formData,
                text: brandingAsset.business_name,
                bgColor: brandingAsset.color_recommendation?.primary_color || sb.formData.bgColor,
                textColor: brandingAsset.color_recommendation?.text_color || sb.formData.textColor
              }
            }
          : sb
      )
    );
  };

  // 이미지를 base64로 변환하는 헬퍼 함수
  const imageToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      if (typeof file === 'string') {
        // 이미 base64 문자열인 경우
        resolve(file);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  // 평면도 생성 함수
  const handleFlatDesignGenerate = async (mode = 'day') => {
    console.log('[평면도 생성] 함수 호출됨 - handleFlatDesignGenerate');
    console.log('[평면도 생성] buildingImage:', buildingImage);
    console.log('[평면도 생성] currentSignboardId:', currentSignboardId);
    console.log('[평면도 생성] signboards:', signboards);
    
    if (!buildingImage) {
      console.log('[평면도 생성] buildingImage 없음');
      alert('건물 사진을 업로드해주세요.');
      return;
    }

    const currentSignboard = getCurrentSignboard();
    console.log('[평면도 생성] currentSignboard:', currentSignboard);
    
    if (!currentSignboard) {
      console.log('[평면도 생성] currentSignboard 없음');
      alert('활성화된 간판을 선택해주세요.');
      return;
    }

    if (!currentSignboard.selectedArea) {
      console.log('[평면도 생성] selectedArea 없음');
      alert('간판 영역을 선택해주세요.');
      return;
    }

    console.log('[평면도 생성] 검증 통과, API 호출 시작');
    setLoading(true);
    setLoadingPhase('flat');

    try {
      console.log('[평면도 생성] buildingImage 변환 시작');
      const buildingBase64 = await imageToBase64(buildingImage);
      console.log('[평면도 생성] buildingImage 변환 완료');
      
      const formDataToSend = new FormData();
      formDataToSend.append('building_photo', buildingBase64);
      
      // 폴리곤 포인트 변환
      let points;
      if (currentSignboard.selectedArea.type === 'polygon') {
        points = currentSignboard.selectedArea.points.map((p) => [p.x, p.y]);
      } else {
        points = [
          [currentSignboard.selectedArea.x, currentSignboard.selectedArea.y],
          [currentSignboard.selectedArea.x + currentSignboard.selectedArea.width, currentSignboard.selectedArea.y],
          [currentSignboard.selectedArea.x + currentSignboard.selectedArea.width, currentSignboard.selectedArea.y + currentSignboard.selectedArea.height],
          [currentSignboard.selectedArea.x, currentSignboard.selectedArea.y + currentSignboard.selectedArea.height]
        ];
      }
      formDataToSend.append('polygon_points', JSON.stringify(points));
      console.log('[평면도 생성] 폴리곤 포인트:', points);

      // 간판 정보 추가
      const sbForm = currentSignboard.formData;
      formDataToSend.append('signboard_input_type', sbForm.signboardInputType || 'text');
      formDataToSend.append('text', sbForm.text || '');
      
      if (sbForm.logo) {
        const logoBase64 = await imageToBase64(sbForm.logo);
        formDataToSend.append('logo', logoBase64);
      } else {
        formDataToSend.append('logo', '');
      }
      
      formDataToSend.append('logo_type', sbForm.logoType || 'channel');
      
      if (sbForm.signboardImage) {
        const signboardImageBase64 = await imageToBase64(sbForm.signboardImage);
        formDataToSend.append('signboard_image', signboardImageBase64);
      } else {
        formDataToSend.append('signboard_image', '');
      }
      
      formDataToSend.append('installation_type', sbForm.installationType || '맨벽');
      formDataToSend.append('sign_type', sbForm.signType || '전광채널');
      formDataToSend.append('bg_color', sbForm.bgColor || '#6B2D8F');
      formDataToSend.append('text_color', sbForm.textColor || '#FFFFFF');
      formDataToSend.append('text_direction', sbForm.textDirection || 'horizontal');
      formDataToSend.append('font_size', sbForm.fontSize || 100);
      formDataToSend.append('text_position_x', sbForm.textPositionX || 50);
      formDataToSend.append('text_position_y', sbForm.textPositionY || 50);
      formDataToSend.append('orientation', sbForm.orientation || 'auto');
      formDataToSend.append('flip_horizontal', sbForm.flipHorizontal ? 'true' : 'false');
      formDataToSend.append('flip_vertical', sbForm.flipVertical ? 'true' : 'false');
      formDataToSend.append('rotate90', sbForm.rotate90 || 0);
      formDataToSend.append('rotation', sbForm.rotation || 0.0);
      formDataToSend.append('lights_enabled', 'false');
      formDataToSend.append('show_dimensions', 'true');
      formDataToSend.append('mode', mode || 'day');  // 주간/야간 모드

      // 치수 값 추가 (있으면 전달, 없으면 생략)
      if (sbForm.width_mm) {
        formDataToSend.append('region_width_mm', sbForm.width_mm);
      }
      if (sbForm.height_mm) {
        formDataToSend.append('region_height_mm', sbForm.height_mm);
      }

      console.log('[평면도 생성] API 호출 시작:', 'http://localhost:8000/api/generate-flat-design');
      const response = await fetch('http://localhost:8000/api/generate-flat-design', {
        method: 'POST',
        body: formDataToSend
      });

      console.log('[평면도 생성] API 응답 상태:', response.status, response.statusText);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('[평면도 생성] API 에러 응답:', errorText);
        throw new Error(`서버 오류: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[평면도 생성] API 응답 데이터:', data);
      
      if (data.error) {
        throw new Error(data.error);
      }

      if (!data.design_only || !data.with_context) {
        throw new Error('평면도 이미지가 응답에 없습니다.');
      }

      // results에 두 가지 모드의 평면도 추가 (results가 null이어도 처리)
      setResults(prev => {
        if (prev) {
          return {
            ...prev,
            flat_design: data.design_only,  // 기본값: design_only (하위 호환성)
            flat_design_only: data.design_only,  // 흰색 배경 + 간판만
            flat_design_with_context: data.with_context,  // 건물 외벽 + 간판 합성
            flat_design_dimensions: data.dimensions || {}  // 치수 정보
          };
        } else {
          return {
            day_simulation: '',
            night_simulation: '',
            flat_design: data.design_only,
            flat_design_only: data.design_only,
            flat_design_with_context: data.with_context,
            flat_design_dimensions: data.dimensions || {}
          };
        }
      });
      
      console.log('[평면도 생성] 완료!');

    } catch (error) {
      console.error('[평면도 생성] 에러 발생:', error);
      alert(`평면도 생성 실패: ${error.message}\n\n브라우저 콘솔을 확인해주세요.`);
    } finally {
      setLoading(false);
      setLoadingPhase(null);
    }
  };

  return (
    <div className="space-y-8">
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
              if (currentSignboardId) {
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
            onSignboardSelect={setCurrentSignboardId}
            onLightsChange={setLights}
            lightsEnabled={lightsEnabled}
          />

          {/* 브랜딩 자산 선택 섹션 */}
          {savedBrandings.length > 0 && (
            <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6">
              <h3 className="text-lg font-semibold text-white mb-4">
                브랜딩 라이브러리에서 선택
              </h3>
              <div className="grid grid-cols-1 gap-3 max-h-40 overflow-y-auto">
                {savedBrandings.map((branding) => (
                  <button
                    key={branding.id}
                    onClick={() => applyBrandingAsset(branding)}
                    className="p-3 bg-white/10 hover:bg-white/20 border border-white/20 hover:border-purple-500/50 rounded-lg text-left transition-all"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="font-semibold text-white">
                          {branding.business_name}
                        </div>
                        <div className="text-xs text-gray-400">
                          {branding.industry} • {branding.style_recommendation?.style_name}
                        </div>
                      </div>
                      <div className="flex space-x-1">
                        <div 
                          className="w-4 h-4 rounded border border-white/30"
                          style={{ backgroundColor: branding.color_recommendation?.primary_color }}
                        />
                        <div 
                          className="w-4 h-4 rounded border border-white/30"
                          style={{ backgroundColor: branding.color_recommendation?.text_color }}
                        />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 간판 관리 */}
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6 mb-6">
            <h3 className="text-lg font-semibold text-white mb-4">간판 관리</h3>
            
            <div className="flex flex-wrap gap-2 mb-4">
              {signboards.map((signboard) => (
                <button
                  key={signboard.id}
                  onClick={() => setCurrentSignboardId(signboard.id)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    currentSignboardId === signboard.id
                      ? 'bg-blue-500 text-white'
                      : 'bg-white/10 text-gray-300 hover:bg-white/20'
                  }`}
                >
                  {signboard.name}
                  {signboards.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSignboard(signboard.id);
                      }}
                      className="ml-2 text-red-400 hover:text-red-300"
                    >
                      ×
                    </button>
                  )}
                </button>
              ))}
              
              <button
                onClick={() => {
                  const newId = Math.max(...signboards.map(s => s.id)) + 1;
                  const newSignboard = {
                    id: newId,
                    name: `간판 ${signboards.length + 1}`,
                    selectedArea: null,
                    formData: createDefaultFormData()
                  };
                  setSignboards(prev => [...prev, newSignboard]);
                  setCurrentSignboardId(newId);
                }}
                className="px-3 py-2 bg-green-500/20 border border-green-500/50 rounded-lg text-green-300 text-sm font-medium hover:bg-green-500/30 transition-all"
              >
                + 간판 추가
              </button>
            </div>
            
            <div className="text-sm text-gray-400">
              현재: {getCurrentSignboard()?.name || '선택된 간판 없음'} 
              {getCurrentSignboard()?.selectedArea ? ' (영역 선택됨)' : ' (영역 선택 필요)'}
            </div>
          </div>

          <SignboardForm
            formData={getCurrentSignboard()?.formData || createDefaultFormData()}
            onFormDataChange={(newFormData) => {
              if (currentSignboardId) {
                setSignboards(prev => 
                  prev.map(sb => 
                    sb.id === currentSignboardId 
                      ? { ...sb, formData: newFormData }
                      : sb
                  )
                );
              }
            }}
          />
        </motion.div>

        {/* 오른쪽: 결과 뷰어 */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="space-y-6"
        >
          <ResultViewer
            results={results}
            loading={loading}
            loadingPhase={loadingPhase}
            loadingProgress={loadingProgress}
            onQuickGenerate={handleQuickGenerate}
            onAIGenerate={handleAIGenerate}
            onApplyLights={handleApplyLights}
            lightsEnabled={lightsEnabled}
            onLightsEnabledChange={setLightsEnabled}
            onShowComingSoon={() => setShowComingSoonModal(true)}
            onFlatDesignGenerate={(() => {
              console.log('[SignboardGeneratorTab] onFlatDesignGenerate prop 전달 시점');
              console.log('[SignboardGeneratorTab] handleFlatDesignGenerate 존재:', typeof handleFlatDesignGenerate);
              console.log('[SignboardGeneratorTab] handleFlatDesignGenerate 값:', handleFlatDesignGenerate);
              return handleFlatDesignGenerate;
            })()}
          />
        </motion.div>
      </div>

      {/* Coming Soon Modal */}
      {showComingSoonModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={() => setShowComingSoonModal(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-white/10 backdrop-blur-lg border border-white/20 rounded-2xl p-8 max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="text-4xl mb-4">🚧</div>
              <h3 className="text-2xl font-bold text-white mb-4">곧 출시됩니다!</h3>
              <p className="text-gray-300 mb-6">
                AI 고품질 변환 기능이 현재 개발 중입니다.
                <br />
                출시 알림을 받으시겠습니까?
              </p>
              <div className="flex gap-3">
                <button
                  className="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white font-medium transition-colors"
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
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
};

export default SignboardGeneratorTab;
