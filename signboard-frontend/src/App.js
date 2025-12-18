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
    rotation: 0.0
  });

  const [signboards, setSignboards] = useState([]); // {id, name, selectedArea, formData}
  const [currentSignboardId, setCurrentSignboardId] = useState(null);
  const [lights, setLights] = useState([]);
  const [lightsEnabled, setLightsEnabled] = useState(true);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const isFirstRender = useRef(true);

  const getCurrentSignboard = () =>
    signboards.find((sb) => sb.id === currentSignboardId) || null;

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
    if (!buildingImage) {
      alert('건물 사진을 업로드해주세요.');
      return;
    }

    if (!signboards.length) {
      alert('간판을 하나 이상 추가하고 영역을 선택해주세요.');
      return;
    }

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
          rotation: parseFloat(sbForm.rotation) || 0.0
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
                  <button
                    key={sb.id}
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
