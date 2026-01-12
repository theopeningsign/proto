import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import ImageUploader from './components/ImageUploader';
import SignboardForm from './components/SignboardForm';
import ResultViewer from './components/ResultViewer';

function App() {
  const [buildingImage, setBuildingImage] = useState(null);
  // 蹂듭닔 媛꾪뙋 ?곹깭: 媛?媛꾪뙋蹂??곸뿭 + ?듭뀡
  const createDefaultFormData = () => ({
    signboardInputType: 'text',
    text: '',
    logo: null,
    logoType: 'channel',
    signboardImage: null,
    installationType: '留⑤꼍',
    signType: '?꾧킅梨꾨꼸',
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
      alert('媛꾪뙋? 理쒖냼 1媛??댁긽 ?덉뼱???⑸땲??');
      return;
    }

    const newSignboards = signboards.filter((sb) => sb.id !== signboardId);
    setSignboards(newSignboards);

    // ??젣??媛꾪뙋???꾩옱 ?좏깮??媛꾪뙋?대㈃ ?ㅻⅨ 媛꾪뙋?쇰줈 ?꾪솚
    if (currentSignboardId === signboardId) {
      if (newSignboards.length > 0) {
        setCurrentSignboardId(newSignboards[0].id);
      } else {
        setCurrentSignboardId(null);
      }
    }
  };

  // 議곕챸 耳쒓린/?꾧린 ???먮룞 諛섏쁺
  useEffect(() => {
    // 泥??뚮뜑留??쒖뿉???ㅽ뻾?섏? ?딆쓬
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    
    // ?쒕??덉씠??寃곌낵媛 ?덉쓣 ?뚮쭔 ?먮룞 諛섏쁺 (湲곕낯 紐⑤뱶濡?
    if (results) {
      handleGenerate('basic');
    }
  }, [lightsEnabled]);

  const handleApplyLights = async () => {
    // 議곕챸 諛섏쁺?섍린: ?꾩옱 議곕챸 ?곹깭濡??ъ깮??(湲곕낯 紐⑤뱶濡?
    console.log('[?꾨줎?몄뿏?? 議곕챸 諛섏쁺?섍린 踰꾪듉 ?대┃');
    console.log('[?꾨줎?몄뿏?? ?꾩옱 lights:', lights);
    console.log('[?꾨줎?몄뿏?? lightsEnabled:', lightsEnabled);
    await handleGenerate('basic');
  };

  // Phase 1留??ㅽ뻾 (鍮좊Ⅸ ?앹꽦)
  const handleQuickGenerate = async () => {
    await handleGenerate('basic');
  };

  // Phase 1 + Phase 2 ?ㅽ뻾 (AI 怨좏뭹吏?
  const handleAIGenerate = async () => {
    await handleGenerate('ai');
  };

  // 怨듯넻 ?앹꽦 ?⑥닔
  const handleGenerate = async (mode = 'basic') => {
    if (!buildingImage) {
      alert('嫄대Ъ ?ъ쭊???낅줈?쒗빐二쇱꽭??');
      return;
    }

    if (!signboards.length) {
      alert('媛꾪뙋???섎굹 ?댁긽 異붽??섍퀬 ?곸뿭???좏깮?댁＜?몄슂.');
      return;
    }

    setLoadingPhase(mode);
    setLoadingProgress(0);

    // 媛?媛꾪뙋蹂??좏슚??寃??    for (const sb of signboards) {
      if (!sb.selectedArea) {
        alert('紐⑤뱺 媛꾪뙋?????媛꾪뙋 ?곸뿭???좏깮?댁＜?몄슂.');
        return;
      }
      if (sb.formData.signboardInputType === 'text' && !sb.formData.text.trim()) {
        alert('紐⑤뱺 媛꾪뙋???곹샇紐낆쓣 ?낅젰?댁＜?몄슂.');
        return;
      }
      if (sb.formData.signboardInputType === 'image' && !sb.formData.signboardImage) {
        alert('?대?吏 媛꾪뙋??寃쎌슦 媛꾪뙋 ?대?吏瑜??낅줈?쒗빐二쇱꽭??');
        return;
      }
    }

    setLoading(true);

    try {
      // ?대?吏瑜?base64濡?蹂??      const buildingBase64 = await imageToBase64(buildingImage);
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

        // ?좏깮???곸뿭????諛곗뿴濡?蹂??        let points;
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
          installation_type: sbForm.installationType || '留⑤꼍',
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

      // API ?몄텧 (蹂듭닔 媛꾪뙋)
      const formDataToSend = new FormData();
      formDataToSend.append('building_photo', buildingBase64);
      // 湲곗〈 諛깆뿏???쒓렇?덉쿂 ?좎???(泥?媛꾪뙋 ?대━怨??꾨떖, ?ㅼ젣 泥섎━??signboards?먯꽌)
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

      // 諛깆뿏??湲곗〈 ?쒓렇?덉쿂 ?좎?瑜??꾪빐 泥?踰덉㎏ 媛꾪뙋 ?뺣낫瑜??④퍡 ?꾩넚
      const firstForm = signboards[0].formData;
      formDataToSend.append('signboard_input_type', firstForm.signboardInputType);
      formDataToSend.append('text', firstForm.text || '');
      formDataToSend.append('logo', signboardsPayload[0].logo || '');
      formDataToSend.append('signboard_image', signboardsPayload[0].signboard_image || '');
      formDataToSend.append('installation_type', firstForm.installationType || '留⑤꼍');
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
      
      console.log('[?꾨줎?몄뿏?? API ?붿껌 吏곸쟾 - lights:', JSON.stringify(lights));
      console.log('[?꾨줎?몄뿏?? API ?붿껌 吏곸쟾 - lights_enabled:', lightsEnabled);

      // Phase 1 吏꾪뻾 ?곹깭 ?낅뜲?댄듃
      setLoadingProgress(30);

      // Phase 1: 湲곕낯 ?앹꽦
      const response = await fetch('http://localhost:8000/api/generate-simulation', {
        method: 'POST',
        body: formDataToSend
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      console.log('[?꾨줎?몄뿏?? Phase 1 ?꾨즺');
      setLoadingProgress(70);

      // Phase 2: AI 怨좏뭹吏?紐⑤뱶??寃쎌슦
      if (mode === 'ai') {
        try {
          setLoadingProgress(80);
          
          // Phase 2 API ?몄텧 (?섏쨷??援ы쁽)
          const aiResponse = await fetch('http://localhost:8000/api/generate-hq', {
            method: 'POST',
            body: formDataToSend
          });

          const aiData = await aiResponse.json();
          
          if (aiData.error) {
            console.warn('AI 媛쒖꽑 ?ㅽ뙣, 湲곕낯 ?덉쭏濡??쒖떆:', aiData.error);
            // AI ?ㅽ뙣?대룄 Phase 1 寃곌낵???쒖떆
            setResults({
              ...data,
              ai_image: null,
              ai_error: aiData.error
            });
          } else {
            // AI ?깃났: AI 寃곌낵 ?ъ슜
            setResults({
              day_simulation: aiData.day_simulation || data.day_simulation,
              night_simulation: aiData.night_simulation || data.night_simulation,
              basic_day_simulation: data.day_simulation, // 鍮꾧탳??              basic_night_simulation: data.night_simulation, // 鍮꾧탳??              ai_image: aiData.ai_image,
              processing_time: aiData.processing_time
            });
          }
          
          setLoadingProgress(100);
        } catch (aiError) {
          console.error('AI 媛쒖꽑 以??ㅻ쪟:', aiError);
          // AI ?ㅽ뙣?대룄 Phase 1 寃곌낵???쒖떆
          setResults({
            ...data,
            ai_image: null,
            ai_error: aiError.message
          });
          setLoadingProgress(100);
        }
      } else {
        // Phase 1留? 湲곕낯 寃곌낵 ?ъ슜
        setResults(data);
        setLoadingProgress(100);
      }
      
      console.log('[?꾨줎?몄뿏?? API ?묐떟 諛쏆쓬');
      console.log('[?꾨줎?몄뿏?? setResults ?몄텧 ??- results:', results);
    } catch (error) {
      console.error('Error:', error);
      alert('?쒕??덉씠???앹꽦 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: ' + error.message);
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
        {/* ?ㅻ뜑 */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600 mb-4">
            媛꾪뙋 ?쒖븞 ?앹꽦湲?          </h1>
          <p className="text-gray-400 text-lg">AI濡?媛꾪뙋???ㅼ젣 嫄대Ъ???⑹꽦?대낫?몄슂</p>
        </motion.header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* ?쇱そ: 嫄대Ъ ?ъ쭊 ?낅줈??+ 媛꾪뙋 湲곕낯 ?뺣낫 */}
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
                  // 泥?媛꾪뙋 ?앹꽦
                  const newId = Date.now();
                  const newSignboard = {
                    id: newId,
                    name: `媛꾪뙋 1`,
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
            
            {/* 媛꾪뙋 ?좏깮/異붽? ??*/}
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
                      {sb.name || `媛꾪뙋 ${idx + 1}`}
                    </button>
                    {signboards.length > 1 && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSignboard(sb.id);
                        }}
                        className="px-1.5 py-1 rounded text-xs bg-red-500/80 hover:bg-red-500 text-white transition-colors"
                        title="媛꾪뙋 ??젣"
                      >
                        횞
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
                    name: `媛꾪뙋 ${newIndex}`,
                    selectedArea: null,
                    formData: createDefaultFormData()
                  };
                  setSignboards((prev) => [...prev, newSignboard]);
                  setCurrentSignboardId(newId);
                }}
                className="px-3 py-1 rounded-lg text-xs bg-emerald-500/80 hover:bg-emerald-500 text-white"
              >
                + 媛꾪뙋 異붽?
              </button>
            </div>

            <SignboardForm
              formData={getCurrentSignboard()?.formData || createDefaultFormData()}
              onFormDataChange={(updated) => {
                if (currentSignboardId === null) {
                  const newId = Date.now();
                  const newSignboard = {
                    id: newId,
                    name: `媛꾪뙋 1`,
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

          {/* ?ㅻⅨ履? ?쒕??덉씠??寃곌낵 + ?몃? ?듭뀡 */}
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

                  // 諛깆뿏?쒕줈 ?꾩넚??signboardsPayload ?ш뎄??                  const signboardsPayload = [];

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
                      installation_type: sbForm.installationType || '留⑤꼍',
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

                  // 諛깆뿏??湲곗〈 ?쒓렇?덉쿂 ?좎?瑜??꾪빐 泥?踰덉㎏ 媛꾪뙋 ?뺣낫瑜??④퍡 ?꾩넚
                  const firstForm = updatedSignboards[0].formData;
                  formDataToSend.append('signboard_input_type', firstForm.signboardInputType);
                  formDataToSend.append('text', firstForm.text || '');
                  formDataToSend.append('logo', signboardsPayload[0].logo || '');
                  formDataToSend.append('signboard_image', signboardsPayload[0].signboard_image || '');
                  formDataToSend.append('installation_type', firstForm.installationType || '留⑤꼍');
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

                  // FormData ?댁슜 ?뺤씤 (?붾쾭源낆슜)
                  console.log('[API ?붿껌] FormData rotation 媛??뺤씤:');
                  const rotationFormValue = formDataToSend.get('rotation');
                  console.log('  formDataToSend.get("rotation"):', rotationFormValue);

                  const response = await fetch('http://localhost:8000/api/generate-simulation', {
                    method: 'POST',
                    body: formDataToSend
                  });

                  const data = await response.json();
                  if (data.error) {
                    console.error('[API ?ㅻ쪟]', data.error);
                    if (data.traceback) {
                      console.error('[API Traceback]', data.traceback);
                    }
                    throw new Error(data.error);
                  }
                  
                  console.log('[API ?묐떟] ?깃났?곸쑝濡?諛쏆쓬');
                  setResults(data);
                } catch (error) {
                  console.error('Error:', error);
                  alert('?ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: ' + error.message);
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
                    name: `媛꾪뙋 1`,
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

        {/* ?쒖븞 ?앹꽦 踰꾪듉 2媛?(鍮좊Ⅸ ?앹꽦 / AI 怨좏뭹吏? */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 鍮좊Ⅸ ?앹꽦 踰꾪듉 (Phase 1留? */}
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
                ?앹꽦 以?..
              </span>
            ) : (
              <>
                <span className="text-lg">??鍮좊Ⅸ ?앹꽦</span>
                <span className="text-xs opacity-80">利됱떆 ??湲곕낯 ?덉쭏</span>
              </>
            )}
            {/* 吏꾪뻾瑜??쒖떆 */}
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

          {/* AI 怨좏뭹吏?踰꾪듉 (Phase 1 + Phase 2) - 以鍮?以??곹깭 */}
          <motion.button
            onClick={() => setShowComingSoonModal(true)}
            disabled={true}
            className="relative bg-gradient-to-br from-gray-600 to-gray-700 rounded-lg px-6 py-4 text-white font-semibold opacity-60 cursor-not-allowed transition-all flex flex-col items-center gap-1"
            title="AI ?덉쭏 媛쒖꽑 湲곕뒫? Phase 2?먯꽌 ?쒓났?⑸땲??(Week 7 異쒖떆 ?덉젙)"
          >
            {/* 以鍮?以?諛곗? */}
            <span className="absolute -top-2 -right-2 bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded-full">
              以鍮?以?            </span>
            
            <div className="flex items-center gap-2 text-lg">
              <span className="opacity-50">??/span>
              <span>AI 怨좏뭹吏?/span>
            </div>
            <span className="text-xs opacity-60">Week 7 異쒖떆 ?덉젙</span>
          </motion.button>
        </div>

        {/* 濡쒕뵫 ?곹깭 ?곸꽭 ?쒖떆 */}
        {loading && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-300">
                  {loadingPhase === 'basic' ? '??鍮좊Ⅸ ?앹꽦 以? : '??AI 怨좏뭹吏??앹꽦 以?}
                </span>
                <span className="text-gray-400">{loadingProgress}%</span>
              </div>
              
              {/* ?④퀎蹂?吏꾪뻾 ?곹깭 */}
              <div className="space-y-1 text-xs text-gray-400">
                {loadingPhase === 'basic' ? (
                  <>
                    <div className={loadingProgress >= 30 ? 'text-green-400' : ''}>
                      {loadingProgress >= 30 ? '?? : '??} 媛꾪뙋 ?뚮뜑留?                    </div>
                    <div className={loadingProgress >= 70 ? 'text-green-400' : loadingProgress >= 30 ? 'text-yellow-400' : ''}>
                      {loadingProgress >= 70 ? '?? : loadingProgress >= 30 ? '?? : '??} 嫄대Ъ ?⑹꽦
                    </div>
                    <div className={loadingProgress >= 100 ? 'text-green-400' : ''}>
                      {loadingProgress >= 100 ? '?? : '??} ?꾨즺
                    </div>
                  </>
                ) : (
                  <>
                    <div className={loadingProgress >= 30 ? 'text-green-400' : ''}>
                      {loadingProgress >= 30 ? '?? : '??} 媛꾪뙋 ?뚮뜑留?                    </div>
                    <div className={loadingProgress >= 70 ? 'text-green-400' : loadingProgress >= 30 ? 'text-yellow-400' : ''}>
                      {loadingProgress >= 70 ? '?? : loadingProgress >= 30 ? '?? : '??} 嫄대Ъ ?⑹꽦
                    </div>
                    <div className={loadingProgress >= 100 ? 'text-green-400' : loadingProgress >= 80 ? 'text-yellow-400' : ''}>
                      {loadingProgress >= 100 ? '?? : loadingProgress >= 80 ? '?? : '??} AI ?덉쭏 媛쒖꽑
                    </div>
                    <div className={loadingProgress >= 100 ? 'text-green-400' : ''}>
                      {loadingProgress >= 100 ? '?? : '??} ?꾨즺
                    </div>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* AI 怨좏뭹吏?以鍮?以?紐⑤떖 */}
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
                <span>??</span>
                <span>AI 怨좏뭹吏?紐⑤뱶 以鍮?以?/span>
              </h3>
              <p className="text-gray-300 mb-6 leading-relaxed">
                AI ?덉쭏 媛쒖꽑 湲곕뒫? ?꾩옱 媛쒕컻 以묒엯?덈떎.
                <br /><br />
                <strong className="text-white">異쒖떆 ?덉젙:</strong> Week 7 (??2二???
                <br /><br />
                <strong className="text-white">二쇱슂 湲곕뒫:</strong>
                <br />
                ??Phase 1 寃곌낵瑜??ㅼ궗 ?섏??쇰줈 媛쒖꽑
                <br />
                ???뷀뀒??異붽? (泥??띿뒪泥? 湲덉냽 諛섏궗 ??
                <br />
                ??泥섎━ ?쒓컙: 2-3珥?              </p>
              <div className="flex gap-3">
                <button
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
                  onClick={() => {
                    alert('?뚮┝ ?좎껌???꾨즺?섏뿀?듬땲??');
                    setShowComingSoonModal(false);
                  }}
                >
                  ?뚮┝ ?좎껌
                </button>
                <button
                  className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white font-medium transition-colors"
                  onClick={() => setShowComingSoonModal(false)}
                >
                  ?リ린
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
