import React, { useState } from 'react';

const SignboardForm = ({ formData, onFormDataChange, section = 'full' }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleChange = (field, value) => {
    onFormDataChange({
      ...formData,
      [field]: value
    });
  };

  const handleLogoUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleChange('logo', file);
    }
  };

  const showBasic = section === 'full' || section === 'basic';
  const showAdvanced = section === 'full' || section === 'advanced';

  return (
    <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-6">
      {section === 'advanced' ? (
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="w-full flex items-center justify-between mb-6 text-white hover:text-blue-400 transition-colors"
        >
          <h2 className="text-xl font-semibold">세부 옵션</h2>
          <span className="text-2xl">{isCollapsed ? '▶' : '▼'}</span>
        </button>
      ) : (
        <h2 className="text-xl font-semibold mb-6 text-white">
          {section === 'basic' ? '간판 정보' : '간판 정보'}
        </h2>
      )}
      
      {(!isCollapsed || section !== 'advanced') && (
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {showBasic && (
        <>
        {/* 간판 타입 선택 */}
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            간판 만들기 방식 *
          </label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => handleChange('signboardInputType', 'text')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.signboardInputType === 'text'
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
              }`}
            >
              📝 텍스트로 만들기
            </button>
            <button
              type="button"
              onClick={() => handleChange('signboardInputType', 'image')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.signboardInputType === 'image'
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
              }`}
            >
              🖼️ 이미지 업로드
            </button>
          </div>
        </div>

        {/* 텍스트 방식 */}
        {formData.signboardInputType === 'text' && (
          <>
            {/* 상호명 */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                상호명 *
              </label>
              <input
                type="text"
                value={formData.text}
                onChange={(e) => handleChange('text', e.target.value)}
                placeholder="예: 간판의품격"
                className="w-full bg-transparent border border-white/20 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition-colors"
              />
            </div>

            {/* 로고 업로드 */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                로고 이미지 (선택)
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={handleLogoUpload}
                className="w-full bg-white/5 border border-white/20 rounded-lg px-4 py-2 text-white text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-500 file:text-white hover:file:bg-blue-600 transition-colors"
              />
              {formData.logo && (
                <p className="mt-2 text-sm text-gray-400">
                  선택됨: {formData.logo.name}
                </p>
              )}
            </div>
          </>
        )}

        {/* 이미지 업로드 방식 */}
        {formData.signboardInputType === 'image' && (
          <>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                간판 이미지 업로드 *
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => handleChange('signboardImage', e.target.files[0])}
                className="w-full bg-white/5 border border-white/20 rounded-lg px-4 py-2 text-white text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-500 file:text-white hover:file:bg-purple-600 transition-colors"
              />
              {formData.signboardImage && (
                <p className="mt-2 text-sm text-gray-400">
                  선택됨: {formData.signboardImage.name}
                </p>
              )}
              <p className="mt-2 text-xs text-gray-500">
                💡 이미지가 선택한 영역에 자동으로 맞춰집니다
              </p>
            </div>

            {/* 이미지 변환 옵션 */}
            {formData.signboardImage && (
              <div className="md:col-span-2 bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                <label className="block text-sm font-medium text-blue-300 mb-3">
                  🔄 이미지 변환 (방향이 이상하면 조정하세요!)
                </label>
                
                {/* 반전 옵션 */}
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.flipHorizontal || false}
                      onChange={(e) => handleChange('flipHorizontal', e.target.checked)}
                      className="w-4 h-4 accent-blue-500"
                    />
                    <span className="text-sm text-gray-300">↔️ 좌우반전</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.flipVertical || false}
                      onChange={(e) => handleChange('flipVertical', e.target.checked)}
                      className="w-4 h-4 accent-blue-500"
                    />
                    <span className="text-sm text-gray-300">↕️ 상하반전</span>
                  </label>
                </div>

                {/* 회전 옵션 */}
                <div>
                  <label className="block text-xs text-gray-400 mb-2">회전</label>
                  <div className="grid grid-cols-4 gap-2">
                    {[0, 90, 180, 270].map((angle) => (
                      <button
                        key={angle}
                        type="button"
                        onClick={() => handleChange('rotate90', angle)}
                        className={`px-3 py-2 rounded-lg border text-xs transition-colors ${
                          (formData.rotate90 || 0) === angle
                            ? 'bg-blue-500 border-blue-500 text-white'
                            : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
                        }`}
                      >
                        {angle === 0 ? '없음' : `${angle}°`}
                      </button>
                    ))}
                  </div>
                </div>

                <p className="mt-3 text-xs text-blue-300/70">
                  💡 변환은 순서대로 적용: 회전 → 좌우반전 → 상하반전
                </p>
              </div>
            )}
          </>
        )}

        {/* 설치 방식 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            설치 방식 *
          </label>
          <select
            value={formData.installationType}
            onChange={(e) => handleChange('installationType', e.target.value)}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-4 py-3 text-white focus:border-blue-500 focus:outline-none transition-colors"
          >
            <option value="맨벽" className="bg-gray-800">맨벽 (벽에 직접 시공)</option>
            <option value="프레임바" className="bg-gray-800">프레임바 (바 위에 부착)</option>
            <option value="전면프레임" className="bg-gray-800">전면프레임 (프레임 위 부착)</option>
            <option value="파사드" className="bg-gray-800">파사드 (외벽 전체)</option>
          </select>
        </div>

        {/* 간판 종류 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            간판 종류 *
          </label>
          <select
            value={formData.signType}
            onChange={(e) => handleChange('signType', e.target.value)}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-4 py-3 text-white focus:border-blue-500 focus:outline-none transition-colors"
          >
            <option value="전광채널" className="bg-gray-800">전광채널 (앞면 발광)</option>
            <option value="후광채널" className="bg-gray-800">후광채널 (뒷면 발광)</option>
            <option value="전후광채널" className="bg-gray-800">전후광채널 (앞+뒤 발광)</option>
            <option value="스카시" className="bg-gray-800">스카시 (비조명 입체)</option>
            <option value="플렉스" className="bg-gray-800">플렉스 (천 재질)</option>
          </select>
        </div>
        </>
        )}

        {showAdvanced && (
        <>
        {/* 로고 발광 여부 */}
        {formData.logo && (
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              로고 타입
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => handleChange('logoType', 'channel')}
                className={`flex-1 px-4 py-2 rounded-lg border text-sm transition-colors ${
                  formData.logoType === 'channel'
                    ? 'bg-blue-500 border-blue-500 text-white'
                    : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
                }`}
              >
                채널 (발광)
              </button>
              <button
                type="button"
                onClick={() => handleChange('logoType', 'scashi')}
                className={`flex-1 px-4 py-2 rounded-lg border text-sm transition-colors ${
                  formData.logoType === 'scashi'
                    ? 'bg-blue-500 border-blue-500 text-white'
                    : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
                }`}
              >
                스카시 (비발광)
              </button>
            </div>
          </div>
        )}

        {/* 배경색 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            배경색 *
          </label>
          <div className="flex items-center gap-4">
            <input
              type="color"
              value={formData.bgColor}
              onChange={(e) => handleChange('bgColor', e.target.value)}
              className="w-16 h-12 border border-white/20 rounded-lg cursor-pointer bg-transparent"
            />
            <input
              type="text"
              value={formData.bgColor}
              onChange={(e) => handleChange('bgColor', e.target.value)}
              className="flex-1 bg-transparent border border-white/20 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition-colors"
              placeholder="#6B2D8F"
            />
          </div>
        </div>

        {/* 글자색 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            글자색 *
          </label>
          <div className="flex items-center gap-4">
            <input
              type="color"
              value={formData.textColor}
              onChange={(e) => handleChange('textColor', e.target.value)}
              className="w-16 h-12 border border-white/20 rounded-lg cursor-pointer bg-transparent"
            />
            <input
              type="text"
              value={formData.textColor}
              onChange={(e) => handleChange('textColor', e.target.value)}
              className="flex-1 bg-transparent border border-white/20 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition-colors"
              placeholder="#FFFFFF"
            />
          </div>
        </div>

        {/* 글자 방향 */}
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            글자 방향
          </label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => handleChange('textDirection', 'horizontal')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.textDirection === 'horizontal'
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
              }`}
            >
              가로쓰기
            </button>
            <button
              type="button"
              onClick={() => handleChange('textDirection', 'vertical')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.textDirection === 'vertical'
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-blue-500'
              }`}
            >
              세로쓰기
            </button>
          </div>
        </div>

        {/* 간판 방향 (가로/세로) */}
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            간판 방향 (프레임 방향)
          </label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => handleChange('orientation', 'auto')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.orientation === 'auto'
                  ? 'bg-purple-500 border-purple-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-purple-500'
              }`}
            >
              🤖 자동
            </button>
            <button
              type="button"
              onClick={() => handleChange('orientation', 'horizontal')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.orientation === 'horizontal'
                  ? 'bg-purple-500 border-purple-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-purple-500'
              }`}
            >
              ↔️ 가로
            </button>
            <button
              type="button"
              onClick={() => handleChange('orientation', 'vertical')}
              className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${
                formData.orientation === 'vertical'
                  ? 'bg-purple-500 border-purple-500 text-white'
                  : 'bg-white/5 border-white/20 text-gray-300 hover:border-purple-500'
              }`}
            >
              ↕️ 세로
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            💡 자동: 선택한 영역에 맞춰 최적의 방향 선택 | 가로/세로: 강제로 지정
          </p>
        </div>
        </>
        )}
      </div>
      )}
    </div>
  );
};

export default SignboardForm;
