"""
AI 브랜딩 시스템 - 상호명 생성 및 스타일 추천
"""

import os
import json
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv
import openai

# 환경변수 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

class AIBrandingSystem:
    def __init__(self):
        """AI 브랜딩 시스템 초기화"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 환경변수에 설정되지 않았습니다.")
        
        # OpenAI 클라이언트 초기화 (구버전)
        openai.api_key = self.api_key
        # 최신 GPT-4o-mini 사용 (간판 브랜딩에 특화된 프롬프트와 함께 사용)
        self.model = "gpt-4o-mini"
    
    def generate_business_names(
        self, 
        industry: str, 
        mood: str, 
        target_customer: str = "", 
        count: int = 5
    ) -> List[Dict]:
        """상호명 생성"""
        
        prompt = f"""
당신은 20년 경력의 간판 제작 전문가이자 브랜딩 컨설턴트입니다.
실제 간판으로 제작 가능하고, 업종이 명확히 연상되는 상호명을 제안하세요.

## 입력 정보
- 업종: {industry}
- 컨셉/분위기: {mood}
- 타겟 연령층: {target_customer if target_customer else "전 연령"}

## 필수 조건 (반드시 지켜주세요)
1. 사용할 수 있는 문자:
   - 한글, 영어, 한영 혼합, 라틴어/외래어 모두 허용
2. 글자 수는 공백 포함 최대 15자 이내로 제한
3. 상호명만 보고 업종이 3초 내 떠올라야 함
4. 실제 간판 제작 가능 (목재/철판/채널문자/네온 모두 적합)
5. 너무 추상적이거나 감성 카페 느낌 금지

## 피해야 할 사항
- 유아 브랜드/패션 브랜드로 오해될 이름
- 기존 유명 프랜차이즈와 유사한 이름
- 장식 없이는 의미 전달 안 되는 약한 이름
- 음식점이라면 '맛/불/식재료' 이미지 필수

## 좋은 예시 (참고용)
- 고깃집: "불향", "숯고을" (× "더테이블", "감성고기")
- 카페: "콩볶는집", "원두막" (× "아틀리에", "컴포즈")
- 미용실: "가위손", "헤어뱅크" (× "라비앙로즈", "쁘띠")

## 나쁜 예시 (이런 건 안 돼요)
- "루나틱" (업종 불명)
- "아뜰리에봉봉" (너무 길고 프랜차이즈 같음)
- "더" (한 글자, 업종 연상 불가)

## 출력 형식
{count}개의 상호명을 다음 JSON 형식으로만 응답하세요:

{{
  "names": [
    {{
      "name": "상호명",
      "reason": "이 업종에 적합한 이유 (간판 제작 관점 포함)",
      "vibe": "느낌 (예: 육향, 전통, 모던, 로컬)"
    }}
  ]
}}

중요: 설명 없이 JSON만 출력하세요.
"""
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 전문 브랜딩 컨설턴트입니다. 창의적이고 기억하기 쉬운 상호명을 제안합니다."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # 창의성 높임
                max_tokens=1500
            )
            
            content = response['choices'][0]['message']['content']
            logger.info(f"GPT 응답 원본: {content}")
            
            # JSON 파싱
            # 때로 GPT가 ```json으로 감싸서 응답할 수 있음
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            result = json.loads(content)
            return result.get("names", [])
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}, GPT 응답: {content}")
            return []
        except Exception as e:
            logger.error(f"상호명 생성 오류: {e}")
            return []
    
    def suggest_signboard_style(self, name: str, industry: str) -> Dict:
        """상호명에 맞는 간판 스타일 추천"""
        
        prompt = f"""
상호명 '{name}' ({industry})에 가장 적합한 간판 스타일을 추천해주세요.

고려사항:
1. 상호명의 글자 수와 형태
2. 업종 특성
3. 시각적 임팩트
4. 제작 비용 효율성

다음 중에서 선택하고 이유를 설명해주세요:
- channel_metal: 금속 채널 간판 (고급스러움, 내구성)
- channel_acrylic: 아크릴 채널 간판 (모던함, 밝음)  
- flex_basic: 플렉스 기본 (경제적, 다양한 색상)
- flex_backlit: 플렉스 후광 (밝음, 시인성)
- neon_classic: 네온사인 (개성적, 눈에 띔)

추천 색상 조합도 제안해주세요.

JSON 형식으로 응답:
{{
  "recommended_style": "스타일코드",
  "style_name": "스타일 한글명",
  "reason": "추천 이유",
  "color_bg": "#배경색",
  "color_text": "#글자색",
  "alternative": "대안 스타일",
  "confidence": 4.2
}}
"""
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 일관성 높임
                max_tokens=800
            )
            
            content = response['choices'][0]['message']['content']
            logger.info(f"스타일 추천 GPT 응답: {content}")
            
            # JSON 파싱
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"스타일 추천 오류: {e}")
            return {}

    def generate_brand_colors(self, business_name: str, industry: str, mood: str) -> Dict:
        """브랜드에 맞는 색상 조합 생성"""
        
        prompt = f"""
'{business_name}' ({industry}, {mood}) 브랜드에 어울리는 색상 조합을 추천해주세요.

고려사항:
1. 업종별 색상 심리학
2. 분위기와 어울리는 색상
3. 간판에서 시인성이 좋은 조합
4. 브랜드 일관성

추천해주세요:
- 메인 색상 (배경)
- 텍스트 색상
- 포인트 색상 (선택사항)

JSON 형식으로 응답:
{{
  "primary_color": "#색상코드",
  "text_color": "#색상코드", 
  "accent_color": "#색상코드",
  "color_names": ["메인색상명", "텍스트색상명", "포인트색상명"],
  "mood_match": "색상이 주는 느낌",
  "contrast_score": 4.5
}}
"""
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=600
            )
            
            content = response['choices'][0]['message']['content']
            
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"색상 생성 오류: {e}")
            return {}

    def generate_logo(
        self,
        business_name: str,
        industry: str,
        mood: str,
        colors: Optional[Dict] = None,
    ) -> Dict:
        """DALL-E 3를 사용해 간판용 로고 이미지를 생성"""

        if colors is None:
            colors = {}

        primary_color = colors.get("primary_color", "#000000")
        text_color = colors.get("text_color", "#FFFFFF")
        accent_color = colors.get("accent_color", "#FF00FF")

        prompt = f"""
[Task] Professional minimalist logo icon design.
[Visual Style] Flat 2D vector graphic. Pure minimalist aesthetic. 
[Canvas] Single symbol centered on a solid white (#FFFFFF) background. 
[Colors] Use ONLY two solid colors: {primary_color} and {text_color}. No gradients, no shading, no 3D effects.
[Concept] A highly simplified abstract mark of stationery (like a pen, paper, or notebook) made of maximum 2 geometric shapes. 
[Strict Constraints] 
- NO text, letters, or numbers.
- NO realistic details, NO shadows, NO lighting, NO reflections.
- Thick, bold, clean lines only.
- Perfectly flat 2D. No 3D perspectives or mockups.
- Output ONLY the symbol itself on a plain white background.
"""

        try:
            response = openai.Image.create(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024",
                response_format="b64_json",
            )

            data = response["data"][0]
            image_b64 = data.get("b64_json")

            if not image_b64:
                logger.error("로고 생성 응답에 이미지 데이터가 없습니다.")
                return {}

            return {
                "image_base64": image_b64,
                "prompt": prompt,
                "primary_color": primary_color,
                "text_color": text_color,
                "accent_color": accent_color,
            }

        except Exception as e:
            logger.error(f"로고 생성 오류: {e}")
            return {}

# 테스트 함수들
def test_branding_system():
    """시스템 테스트"""
    
    branding = AIBrandingSystem()
    
    print("AI 브랜딩 시스템 테스트")
    print("=" * 50)
    
    # 테스트 케이스
    test_cases = [
        {
            "industry": "이탈리안 레스토랑",
            "mood": "고급스럽고 로맨틱한",
            "target": "20-40대 커플, 가족"
        },
        {
            "industry": "카페",
            "mood": "따뜻하고 아늑한",
            "target": "20-30대 직장인, 학생"
        },
        {
            "industry": "치킨집",
            "mood": "활기차고 친근한", 
            "target": "전 연령층"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*20} 테스트 {i} {'='*20}")
        print(f"입력:")
        print(f"  업종: {case['industry']}")
        print(f"  분위기: {case['mood']}")
        print(f"  타겟: {case['target']}")
        print()
        
        # 상호명 생성
        print("상호명 생성 중...")
        names = branding.generate_business_names(
            case['industry'], 
            case['mood'], 
            case['target']
        )
        
        if names:
            print("상호명 제안:")
            for j, name_info in enumerate(names, 1):
                print(f"  {j}. {name_info.get('name', 'N/A')}")
                print(f"     이유: {name_info.get('reason', 'N/A')}")
                print(f"     느낌: {name_info.get('vibe', 'N/A')}")
                print(f"     평점: {name_info.get('rating', 'N/A')}")
                print()
            
            # 첫 번째 상호명으로 스타일 추천
            if names:
                selected_name = names[0]['name']
                print(f"'{selected_name}' 간판 스타일 추천 중...")
                style = branding.suggest_signboard_style(selected_name, case['industry'])
                
                if style:
                    print("스타일 추천:")
                    print(f"  추천: {style.get('style_name', 'N/A')}")
                    print(f"  코드: {style.get('recommended_style', 'N/A')}")
                    print(f"  이유: {style.get('reason', 'N/A')}")
                    print(f"  배경색: {style.get('color_bg', 'N/A')}")
                    print(f"  글자색: {style.get('color_text', 'N/A')}")
                    print(f"  대안: {style.get('alternative', 'N/A')}")
                    print()
                
                # 색상 조합 생성
                print(f"'{selected_name}' 브랜드 색상 추천 중...")
                colors = branding.generate_brand_colors(
                    selected_name, 
                    case['industry'], 
                    case['mood']
                )
                
                if colors:
                    print("색상 조합:")
                    print(f"  메인: {colors.get('primary_color', 'N/A')}")
                    print(f"  텍스트: {colors.get('text_color', 'N/A')}")
                    print(f"  포인트: {colors.get('accent_color', 'N/A')}")
                    print(f"  느낌: {colors.get('mood_match', 'N/A')}")
        else:
            print("상호명 생성 실패")

if __name__ == "__main__":
    test_branding_system()
