import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const AIBrandingTab = ({ onBrandingComplete, savedBrandings, onSaveBranding }) => {
  const [step, setStep] = useState(1); // 1: 입력, 2: 상호명 선택, 3: 완성
  const [formData, setFormData] = useState({
    industry: '',
    mood: '',
    targetCustomer: ''
  });
  const [loading, setLoading] = useState(false);
  const [nameOptions, setNameOptions] = useState([]);
  const [selectedNameIndex, setSelectedNameIndex] = useState(null);
  const [brandingResult, setBrandingResult] = useState(null);
  const [error, setError] = useState('');
  const [logoLoading, setLogoLoading] = useState(false);
  const [logoError, setLogoError] = useState('');
  const [logoImage, setLogoImage] = useState(null);

  // Step 1: 업종/컨셉 입력
  const handleInputSubmit = async () => {
    if (!formData.industry || !formData.mood) {
      setError('업종과 분위기를 모두 입력해주세요.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams();
      params.append('industry', formData.industry);
      params.append('mood', formData.mood);
      params.append('target_customer', formData.targetCustomer);
      params.append('count', '5');
      
      const response = await axios.post('http://localhost:8000/api/ai-suggest-names', params);

      if (response.data.success) {
        setNameOptions(response.data.names);
        setStep(2);
      } else {
        setError('상호명 생성에 실패했습니다.');
      }
    } catch (err) {
      setError('서버 연결에 실패했습니다. 백엔드가 실행 중인지 확인해주세요.');
      console.error('API 호출 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: 조건은 그대로 두고 상호명만 다시 제안받기
  const handleRegenerateNames = async () => {
    if (!formData.industry || !formData.mood) {
      setError('업종과 분위기를 모두 입력해주세요.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams();
      params.append('industry', formData.industry);
      params.append('mood', formData.mood);
      params.append('target_customer', formData.targetCustomer);
      params.append('count', '5');

      const response = await axios.post('http://localhost:8000/api/ai-suggest-names', params);

      if (response.data.success) {
        setNameOptions(response.data.names);
        // 이미 Step 2이므로 step은 그대로 두거나 명시적으로 유지
        setStep(2);
      } else {
        setError('상호명 재생성에 실패했습니다.');
      }
    } catch (err) {
      setError('서버 연결에 실패했습니다. 백엔드가 실행 중인지 확인해주세요.');
      console.error('상호 재생성 API 호출 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: 상호명 선택 후 완전한 브랜딩 패키지 생성
  const handleNameSelection = async (index) => {
    setSelectedNameIndex(index);
    setLoading(true);
    setError('');

    try {
      const selectedOption = nameOptions[index];

      const params = new URLSearchParams();
      params.append('industry', formData.industry);
      params.append('mood', formData.mood);
      params.append('target_customer', formData.targetCustomer);
      params.append('business_name', selectedOption.name);
      
      const response = await axios.post('http://localhost:8000/api/ai-branding-complete', params);

      if (response.data.success) {
        // 백엔드에서 받은 패키지 + 프론트에서 선택한 상호 정보 결합
        const basePackage = response.data.branding_package;
        const fullPackage = {
          ...basePackage,
          all_name_suggestions: nameOptions,
          selected_name_info: selectedOption,
        };

        setBrandingResult(fullPackage);
        setStep(3);
        
        // 브랜딩 결과를 저장 (라이브러리용)
        const brandingAsset = {
          id: Date.now(),
          ...fullPackage,
          createdAt: new Date().toISOString()
        };
        onSaveBranding(brandingAsset);
      } else {
        setError('브랜딩 패키지 생성에 실패했습니다.');
      }
    } catch (err) {
      setError('브랜딩 패키지 생성 중 오류가 발생했습니다.');
      console.error('브랜딩 패키지 생성 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep(1);
    setFormData({ industry: '', mood: '', targetCustomer: '' });
    setNameOptions([]);
    setSelectedNameIndex(null);
    setBrandingResult(null);
    setError('');
    setLogoLoading(false);
    setLogoError('');
    setLogoImage(null);
  };

  // 라이브러리에서 기존 브랜딩을 다시 불러와서 Step 3 화면으로 표시
  const handleLoadBrandingFromLibrary = (branding) => {
    if (!branding) return;
    setBrandingResult(branding);
    setStep(3);
    setError('');
  };

  // 완성된 브랜딩 정보를 기반으로 AI 로고 생성
  const handleGenerateLogo = async () => {
    if (!brandingResult) return;

    setLogoLoading(true);
    setLogoError('');

    try {
      const params = new URLSearchParams();
      params.append('business_name', brandingResult.business_name);
      params.append('industry', formData.industry);
      params.append('mood', formData.mood);
      params.append(
        'primary_color',
        brandingResult.color_recommendation?.primary_color || '#000000'
      );
      params.append(
        'text_color',
        brandingResult.color_recommendation?.text_color || '#FFFFFF'
      );
      params.append(
        'accent_color',
        brandingResult.color_recommendation?.accent_color || '#FF00FF'
      );

      const response = await axios.post(
        'http://localhost:8000/api/ai-generate-logo',
        params
      );

      if (response.data.success && response.data.logo?.image_base64) {
        setLogoImage(`data:image/png;base64,${response.data.logo.image_base64}`);
      } else {
        setLogoError('로고 생성에 실패했습니다.');
      }
    } catch (err) {
      console.error('AI 로고 생성 오류:', err);
      setLogoError('AI 로고 생성 중 오류가 발생했습니다.');
    } finally {
      setLogoLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Progress indicator */}
      <div className="flex items-center justify-center space-x-4 mb-8">
        {[1, 2, 3].map((stepNum) => (
          <div key={stepNum} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                stepNum === step
                  ? 'bg-blue-500 text-white'
                  : stepNum < step
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-600 text-gray-300'
              }`}
            >
              {stepNum < step ? '✓' : stepNum}
            </div>
            {stepNum < 3 && (
              <div
                className={`w-16 h-1 mx-2 ${
                  stepNum < step ? 'bg-green-500' : 'bg-gray-600'
                }`}
              />
            )}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {/* Step 1: 업종/컨셉 입력 */}
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6"
          >
            <h2 className="text-2xl font-bold text-white mb-6">
              어떤 사업을 시작하시나요?
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  업종 *
                </label>
                <input
                  type="text"
                  placeholder="예: 이탈리안 레스토랑, 카페, 치킨집, 헤어샵"
                  value={formData.industry}
                  onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  분위기/컨셉 *
                </label>
                <input
                  type="text"
                  placeholder="예: 고급스럽고 로맨틱한, 따뜻하고 아늑한, 활기차고 친근한"
                  value={formData.mood}
                  onChange={(e) => setFormData({ ...formData, mood: e.target.value })}
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  타겟 고객 (선택사항)
                </label>
                <input
                  type="text"
                  placeholder="예: 20-40대 커플, 20-30대 직장인, 전 연령층"
                  value={formData.targetCustomer}
                  onChange={(e) => setFormData({ ...formData, targetCustomer: e.target.value })}
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-300">
                {error}
              </div>
            )}

            <button
              onClick={handleInputSubmit}
              disabled={loading}
              className="w-full mt-6 px-6 py-3 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white font-semibold transition-colors"
            >
              {loading ? '상호명 생성 중...' : 'AI 상호명 제안받기'}
            </button>
          </motion.div>
        )}

        {/* Step 2: 상호명 선택 */}
        {step === 2 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6"
          >
            <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6 gap-3">
              <h2 className="text-2xl font-bold text-white">
                마음에 드는 상호명을 선택하세요
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={handleRegenerateNames}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 rounded-lg text-white text-sm transition-colors"
                >
                  {loading ? '다시 생성 중...' : '상호 다시 제안받기'}
                </button>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-white text-sm transition-colors"
                >
                  다시 입력
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {nameOptions.map((option, index) => (
                <motion.button
                  key={index}
                  onClick={() => handleNameSelection(index)}
                  disabled={loading}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="p-4 bg-white/10 hover:bg-white/20 border border-white/20 hover:border-blue-500/50 rounded-xl text-left transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="text-xl font-bold text-white mb-2">
                    {option.name}
                  </div>
                  <div className="text-sm text-gray-300 mb-2">
                    {option.reason}
                  </div>
                  <div className="text-xs text-blue-300">
                    느낌: {option.vibe}
                  </div>
                </motion.button>
              ))}
            </div>

            {loading && (
              <div className="mt-6 text-center">
                <div className="inline-flex items-center space-x-2 text-blue-400">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400"></div>
                  <span>완전한 브랜딩 패키지 생성 중...</span>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-300">
                {error}
              </div>
            )}
          </motion.div>
        )}

        {/* Step 3: 완성된 브랜딩 패키지 */}
        {step === 3 && brandingResult && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6"
          >
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-white">
                브랜딩 완성! 🎉
              </h2>
              <button
                onClick={handleReset}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-white transition-colors"
              >
                새로 만들기
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* 선택된 상호명 정보 */}
              <div className="bg-white/10 rounded-xl p-4">
                <h3 className="text-lg font-semibold text-white mb-3">
                  선택된 상호명
                </h3>
                <div className="text-3xl font-bold text-blue-400 mb-2">
                  {brandingResult.business_name}
                </div>
                <div className="text-sm text-gray-300">
                  {brandingResult.selected_name_info?.reason}
                </div>
              </div>

              {/* 브랜드 색상 */}
              <div className="bg-white/10 rounded-xl p-4">
                <h3 className="text-lg font-semibold text-white mb-3">
                  브랜드 색상
                </h3>
                <div className="flex space-x-3 mb-2">
                  <div 
                    className="w-8 h-8 rounded border-2 border-white/20"
                    style={{ backgroundColor: brandingResult.color_recommendation?.primary_color }}
                  />
                  <div 
                    className="w-8 h-8 rounded border-2 border-white/20"
                    style={{ backgroundColor: brandingResult.color_recommendation?.text_color }}
                  />
                  <div 
                    className="w-8 h-8 rounded border-2 border-white/20"
                    style={{ backgroundColor: brandingResult.color_recommendation?.accent_color }}
                  />
                </div>
                <div className="text-sm text-gray-300">
                  {brandingResult.color_recommendation?.mood_match}
                </div>
              </div>

              {/* 액션 버튼 */}
              <div className="bg-white/10 rounded-xl p-4">
                <h3 className="text-lg font-semibold text-white mb-3">
                  다음 단계
                </h3>
                <div className="space-y-3">
                  <button
                    onClick={handleGenerateLogo}
                    disabled={logoLoading}
                    className="w-full px-4 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white font-semibold transition-colors"
                  >
                    {logoLoading ? 'AI 로고 생성 중...' : 'AI 로고 시안 생성하기'}
                  </button>
                  <button
                    onClick={() => onBrandingComplete?.(brandingResult)}
                    className="w-full px-4 py-3 bg-purple-500 hover:bg-purple-600 rounded-lg text-white font-semibold transition-colors"
                  >
                    간판 제작하러 가기 →
                  </button>
                  {logoError && (
                    <div className="mt-2 p-2 bg-red-500/20 border border-red-500/50 rounded-lg text-xs text-red-300">
                      {logoError}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* 생성된 로고 미리보기 */}
            {logoImage && (
              <div className="mt-6 bg-white/10 rounded-xl p-4 flex flex-col md:flex-row gap-4 items-center">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-white mb-2">
                    AI 로고 시안
                  </h3>
                  <p className="text-sm text-gray-300">
                    이 로고는 실제 간판용을 가정하고 생성된 시안입니다. 마음에 들지 않으면
                    프롬프트를 조정해 다시 시도할 수 있습니다.
                  </p>
                </div>
                <div className="w-48 h-48 bg-black/40 rounded-xl flex items-center justify-center overflow-hidden border border-white/20">
                  <img
                    src={logoImage}
                    alt="AI Logo"
                    className="max-w-full max-h-full object-contain"
                  />
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 저장된 브랜딩 자산 미리보기 */}
      {savedBrandings.length > 0 && (
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            브랜딩 라이브러리 ({savedBrandings.length}개)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {savedBrandings.slice(0, 3).map((branding) => (
              <button
                key={branding.id}
                type="button"
                onClick={() => handleLoadBrandingFromLibrary(branding)}
                className="p-3 bg-white/10 rounded-lg text-left w-full hover:bg-white/15 border border-transparent hover:border-blue-400/60 transition-colors"
              >
                <div className="font-semibold text-white">
                  {branding.business_name}
                </div>
                <div className="text-xs text-gray-400">
                  {branding.industry} • {new Date(branding.createdAt).toLocaleDateString()}
                </div>
              </button>
            ))}
            {savedBrandings.length > 3 && (
              <div className="p-3 bg-white/10 rounded-lg flex items-center justify-center text-gray-400">
                +{savedBrandings.length - 3}개 더...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AIBrandingTab;
