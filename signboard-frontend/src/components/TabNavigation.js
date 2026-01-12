import React from 'react';
import { motion } from 'framer-motion';

const TabNavigation = ({ activeTab, onTabChange }) => {
  const tabs = [
    {
      id: 'branding',
      name: 'AI 브랜딩',
      icon: '🤖',
      description: '상호명·로고 생성'
    },
    {
      id: 'signboard', 
      name: '간판 생성기',
      icon: '🎨',
      description: '시안 제작'
    }
  ];

  return (
    <div className="mb-8">
      <div className="flex border-b border-white/10">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`relative flex-1 px-6 py-4 text-left transition-all duration-300 ${
              activeTab === tab.id
                ? 'text-white border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{tab.icon}</span>
              <div>
                <div className="font-semibold text-lg">{tab.name}</div>
                <div className="text-sm opacity-75">{tab.description}</div>
              </div>
            </div>
            
            {/* Active indicator */}
            {activeTab === tab.id && (
              <motion.div
                layoutId="activeTab"
                className="absolute inset-0 bg-white/5 backdrop-blur-lg border border-white/10 rounded-t-xl"
                initial={false}
                transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
              />
            )}
          </button>
        ))}
      </div>
      
      {/* Tab descriptions */}
      <div className="mt-4 px-6 py-3 bg-white/5 backdrop-blur-lg border border-white/10 rounded-lg">
        {activeTab === 'branding' && (
          <p className="text-gray-300 text-sm">
            💡 업종과 컨셉을 입력하면 AI가 상호명과 로고를 제안해드립니다. 
            생성된 브랜딩 자산은 라이브러리에 저장되어 간판 제작 시 활용할 수 있습니다.
          </p>
        )}
        {activeTab === 'signboard' && (
          <p className="text-gray-300 text-sm">
            🏗️ 건물 사진을 업로드하고 간판 정보를 입력하면 실제 건물에 합성된 시안을 확인할 수 있습니다.
            AI 브랜딩에서 생성한 자산을 불러올 수도 있습니다.
          </p>
        )}
      </div>
    </div>
  );
};

export default TabNavigation;

