import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import ImageUploader from './components/ImageUploader';
import SignboardForm from './components/SignboardForm';
import ResultViewer from './components/ResultViewer';

function App() {
  const [buildingImage, setBuildingImage] = useState(null);
  const [selectedArea, setSelectedArea] = useState(null);
  const [formData, setFormData] = useState({
    signboardInputType: 'text', // 'text' or 'image'
    text: '',
    logo: null,
    logoType: 'channel',
    signboardImage: null, // 간판 이미지 (이미지 방식)
    installationType: '맨벽',
    signType: '전광채널',
    bgColor: '#6B2D8F',
    textColor: '#FFFFFF',
    textDirection: 'horizontal',
    fontSize: 100,
    originalFontSize: 100, // 원본 fontSize (간판 편집 박스 크기 계산용)
    textPositionX: 50,
    textPositionY: 50,
    orientation: 'auto', // 'auto', 'horizontal', 'vertical'
    flipHorizontal: false, // 좌우반전
    flipVertical: false, // 상하반전
    rotate90: 0, // 0, 90, 180, 270
    rotation: 0.0 // 회전 각도 (도 단위, -180 ~ 180)
  });
  const [lights, setLights] = useState([]);
  const [lightsEnabled, setLightsEnabled] = useState(true);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const isFirstRender = useRef(true);

  // 조명 켜기/끄기 시 자동 반영
  useEffect(() => {
    // 첫 렌더링 시에는 실행하지 않음
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    
    // 시뮬레이션 결과가 있을 때만 자동 반영
    if (results) {
      handleGenerate();
    }
  }, [lightsEnabled]);

  const handleApplyLights = async () => {
    // 조명 반영하기: 현재 조명 상태로 재생성
    console.log('[프론트엔드] 조명 반영하기 버튼 클릭');
    console.log('[프론트엔드] 현재 lights:', lights);
    console.log('[프론트엔드] lightsEnabled:', lightsEnabled);
    await handleGenerate();
  };

  const handleGenerate = async () => {
    if (!buildingImage || !selectedArea) {
      alert('건물 사진을 업로드하고 간판 영역을 선택해주세요.');
      return;
    }

    if (formData.signboardInputType === 'text' && !formData.text.trim()) {
      alert('상호명을 입력해주세요.');
      return;
    }

    if (formData.signboardInputType === 'image' && !formData.signboardImage) {
      alert('간판 이미지를 업로드해주세요.');
      return;
    }

    setLoading(true);

    try {
      // 이미지를 base64로 변환
      const buildingBase64 = await imageToBase64(buildingImage);
      let logoBase64 = '';
      let signboardImageBase64 = '';
      
      if (formData.logo) {
        logoBase64 = await imageToBase64(formData.logo);
      }

      if (formData.signboardImage) {
        signboardImageBase64 = await imageToBase64(formData.signboardImage);
      }

      // 선택된 영역을 점 배열로 변환
      let points;
      if (selectedArea.type === 'polygon') {
        // 폴리곤: 점 배열 그대로 사용
        points = selectedArea.points.map(p => [p.x, p.y]);
      } else {
        // 사각형 (하위 호환성)
        points = [
          [selectedArea.x, selectedArea.y],
          [selectedArea.x + selectedArea.width, selectedArea.y],
          [selectedArea.x + selectedArea.width, selectedArea.y + selectedArea.height],
          [selectedArea.x, selectedArea.y + selectedArea.height]
        ];
      }

      // API 호출
      const formDataToSend = new FormData();
      formDataToSend.append('building_photo', buildingBase64);
      formDataToSend.append('polygon_points', JSON.stringify(points));
      formDataToSend.append('signboard_input_type', formData.signboardInputType);
      formDataToSend.append('text', formData.text || '');
      formDataToSend.append('logo', logoBase64);
      formDataToSend.append('signboard_image', signboardImageBase64);
      formDataToSend.append('installation_type', formData.installationType || '맨벽');
      formDataToSend.append('sign_type', formData.signType);
      formDataToSend.append('bg_color', formData.bgColor);
      formDataToSend.append('text_color', formData.textColor);
      formDataToSend.append('text_direction', formData.textDirection || 'horizontal');
      formDataToSend.append('font_size', String(parseInt(formData.fontSize) || 100));
      formDataToSend.append('text_position_x', String(parseInt(formData.textPositionX) || 50));
      formDataToSend.append('text_position_y', String(parseInt(formData.textPositionY) || 50));
      formDataToSend.append('logo_type', formData.logoType || 'channel');
      formDataToSend.append('orientation', formData.orientation || 'auto');
      formDataToSend.append('flip_horizontal', formData.flipHorizontal ? 'true' : 'false');
      formDataToSend.append('flip_vertical', formData.flipVertical ? 'true' : 'false');
      formDataToSend.append('rotate90', String(parseInt(formData.rotate90) || 0));
      formDataToSend.append('rotation', String(parseFloat(formData.rotation) || 0.0));
      formDataToSend.append('lights', JSON.stringify(lights || []));
      formDataToSend.append('lights_enabled', lightsEnabled ? 'true' : 'false');
      
      console.log('[프론트엔드] API 요청 직전 - lights:', JSON.stringify(lights));
      console.log('[프론트엔드] API 요청 직전 - lights_enabled:', lightsEnabled);

      const response = await fetch('http://localhost:8000/api/generate-simulation', {
        method: 'POST',
        body: formDataToSend
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      console.log('[프론트엔드] API 응답 받음');
      console.log('[프론트엔드] setResults 호출 전 - results:', results);
      setResults(data);
      console.log('[프론트엔드] setResults 호출 후');
    } catch (error) {
      console.error('Error:', error);
      alert('시뮬레이션 생성 중 오류가 발생했습니다: ' + error.message);
    } finally {
      setLoading(false);
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
              selectedArea={selectedArea}
              onAreaChange={setSelectedArea}
            />
            
            <SignboardForm
              formData={formData}
              onFormDataChange={setFormData}
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
              originalSignboards={[{ id: 0, formData }]}
              selectedArea={selectedArea}
              onRegenerateWithTransforms={async (transforms) => {
                if (!buildingImage || !selectedArea) return;
                setLoading(true);
                try {
                  const buildingBase64 = await imageToBase64(buildingImage);
                  let logoBase64 = '';
                  if (formData.logo) logoBase64 = await imageToBase64(formData.logo);
                  let signboardImageBase64 = '';
                  if (formData.signboardImage) signboardImageBase64 = await imageToBase64(formData.signboardImage);
                  
                  let points;
                  if (selectedArea.type === 'polygon') {
                    points = selectedArea.points.map(p => [p.x, p.y]);
                  } else {
                    points = [
                      [selectedArea.x, selectedArea.y],
                      [selectedArea.x + selectedArea.width, selectedArea.y],
                      [selectedArea.x + selectedArea.width, selectedArea.y + selectedArea.height],
                      [selectedArea.x, selectedArea.y + selectedArea.height]
                    ];
                  }

                  const updatedFormData = { ...formData };
                  // transforms는 배열 형태로 전달됨
                  if (Array.isArray(transforms) && transforms.length > 0) {
                    const transform = transforms[0];
                    if (transform) {
                      if (transform.fontSize !== undefined) {
                        // fontSize가 변경되면 originalFontSize도 현재 값으로 업데이트
                        // (다음에 간판 편집을 열 때 현재 크기를 기준으로 박스가 표시되도록)
                        updatedFormData.fontSize = transform.fontSize;
                        updatedFormData.originalFontSize = transform.fontSize; // 현재 fontSize를 originalFontSize로 저장
                      }
                      // rotation 값을 rotate90으로 변환 (90도 단위로만 지원하는 경우)
                      // 또는 rotation 파라미터로 직접 전달
                      if (transform.rotation !== undefined) {
                        // rotation을 그대로 전달 (백엔드에서 처리)
                        updatedFormData.rotation = transform.rotation;
                        console.log('[회전 적용] rotation 값 설정:', transform.rotation);
                      }
                    }
                  }

                  const formDataToSend = new FormData();
                  formDataToSend.append('building_photo', buildingBase64);
                  formDataToSend.append('polygon_points', JSON.stringify(points));
                  formDataToSend.append('signboard_input_type', updatedFormData.signboardInputType);
                  formDataToSend.append('text', updatedFormData.text || '');
                  formDataToSend.append('logo', logoBase64);
                  formDataToSend.append('signboard_image', signboardImageBase64);
                  formDataToSend.append('installation_type', updatedFormData.installationType || '맨벽');
                  formDataToSend.append('sign_type', updatedFormData.signType);
                  formDataToSend.append('bg_color', updatedFormData.bgColor);
                  formDataToSend.append('text_color', updatedFormData.textColor);
                  formDataToSend.append('text_direction', updatedFormData.textDirection || 'horizontal');
                  formDataToSend.append('font_size', String(parseInt(updatedFormData.fontSize) || 100));
                  formDataToSend.append('text_position_x', String(parseInt(updatedFormData.textPositionX) || 50));
                  formDataToSend.append('text_position_y', String(parseInt(updatedFormData.textPositionY) || 50));
                  formDataToSend.append('logo_type', updatedFormData.logoType || 'channel');
                  formDataToSend.append('orientation', updatedFormData.orientation || 'auto');
                  formDataToSend.append('flip_horizontal', updatedFormData.flipHorizontal ? 'true' : 'false');
                  formDataToSend.append('flip_vertical', updatedFormData.flipVertical ? 'true' : 'false');
                  formDataToSend.append('rotate90', String(parseInt(updatedFormData.rotate90) || 0));
                  const rotationValue = updatedFormData.rotation !== undefined ? parseFloat(updatedFormData.rotation) : 0.0;
                  formDataToSend.append('rotation', String(rotationValue));
                  console.log('[회전 전송] rotation 값:', rotationValue, 'updatedFormData.rotation:', updatedFormData.rotation);
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
                  setFormData(updatedFormData);
                } catch (error) {
                  console.error('Error:', error);
                  alert('오류가 발생했습니다: ' + error.message);
                } finally {
                  setLoading(false);
                }
              }}
              onApplyTextPositions={async (textPositions) => {
                if (!buildingImage || !selectedArea) return;
                setLoading(true);
                try {
                  const buildingBase64 = await imageToBase64(buildingImage);
                  let logoBase64 = '';
                  if (formData.logo) logoBase64 = await imageToBase64(formData.logo);
                  let signboardImageBase64 = '';
                  if (formData.signboardImage) signboardImageBase64 = await imageToBase64(formData.signboardImage);
                  
                  let points;
                  if (selectedArea.type === 'polygon') {
                    points = selectedArea.points.map(p => [p.x, p.y]);
                  } else {
                    points = [
                      [selectedArea.x, selectedArea.y],
                      [selectedArea.x + selectedArea.width, selectedArea.y],
                      [selectedArea.x + selectedArea.width, selectedArea.y + selectedArea.height],
                      [selectedArea.x, selectedArea.y + selectedArea.height]
                    ];
                  }

                  const updatedFormData = { ...formData };
                  if (textPositions[0]) {
                    updatedFormData.textPositionX = textPositions[0].x;
                    updatedFormData.textPositionY = textPositions[0].y;
                  }

                  const formDataToSend = new FormData();
                  formDataToSend.append('building_photo', buildingBase64);
                  formDataToSend.append('polygon_points', JSON.stringify(points));
                  formDataToSend.append('signboard_input_type', updatedFormData.signboardInputType);
                  formDataToSend.append('text', updatedFormData.text || '');
                  formDataToSend.append('logo', logoBase64);
                  formDataToSend.append('signboard_image', signboardImageBase64);
                  formDataToSend.append('installation_type', updatedFormData.installationType || '맨벽');
                  formDataToSend.append('sign_type', updatedFormData.signType);
                  formDataToSend.append('bg_color', updatedFormData.bgColor);
                  formDataToSend.append('text_color', updatedFormData.textColor);
                  formDataToSend.append('text_direction', updatedFormData.textDirection || 'horizontal');
                  formDataToSend.append('font_size', String(parseInt(updatedFormData.fontSize) || 100));
                  formDataToSend.append('text_position_x', String(parseInt(updatedFormData.textPositionX) || 50));
                  formDataToSend.append('text_position_y', String(parseInt(updatedFormData.textPositionY) || 50));
                  formDataToSend.append('logo_type', updatedFormData.logoType || 'channel');
                  formDataToSend.append('orientation', updatedFormData.orientation || 'auto');
                  formDataToSend.append('flip_horizontal', updatedFormData.flipHorizontal ? 'true' : 'false');
                  formDataToSend.append('flip_vertical', updatedFormData.flipVertical ? 'true' : 'false');
                  formDataToSend.append('rotate90', String(parseInt(updatedFormData.rotate90) || 0));
                  const rotationValue = updatedFormData.rotation !== undefined ? parseFloat(updatedFormData.rotation) : 0.0;
                  formDataToSend.append('rotation', String(rotationValue));
                  console.log('[회전 전송] rotation 값:', rotationValue, 'updatedFormData.rotation:', updatedFormData.rotation);
                  formDataToSend.append('lights', JSON.stringify(lights || []));
                  formDataToSend.append('lights_enabled', lightsEnabled ? 'true' : 'false');

                  const response = await fetch('http://localhost:8000/api/generate-simulation', {
                    method: 'POST',
                    body: formDataToSend
                  });

                  const data = await response.json();
                  if (data.error) throw new Error(data.error);
                  
                  setResults(data);
                  setFormData(updatedFormData);
                } catch (error) {
                  console.error('Error:', error);
                  alert('오류가 발생했습니다: ' + error.message);
                } finally {
                  setLoading(false);
                }
              }}
            />
            
            <SignboardForm
              formData={formData}
              onFormDataChange={setFormData}
              section="advanced"
            />
          </motion.div>
        </div>

        {/* 시안 생성하기 버튼 (전체 너비) */}
        <motion.button
          onClick={handleGenerate}
          disabled={loading}
          whileHover={{ scale: loading ? 1 : 1.02 }}
          whileTap={{ scale: loading ? 1 : 0.98 }}
          className="w-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg px-8 py-4 text-white font-semibold shadow-lg disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed transition-all"
        >
          {loading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              생성 중...
            </span>
          ) : (
            '🎨 시안 생성하기'
          )}
        </motion.button>
      </div>
    </div>
  );
}

export default App;
