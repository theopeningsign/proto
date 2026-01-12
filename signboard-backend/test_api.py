"""
AI 브랜딩 API 테스트 스크립트
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_root():
    """루트 엔드포인트 테스트"""
    print("=" * 50)
    print("루트 엔드포인트 테스트")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"상태 코드: {response.status_code}")
        print(f"응답:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"오류: {e}")

def test_ai_suggest_names():
    """상호명 제안 API 테스트"""
    print("\n" + "=" * 50)
    print("상호명 제안 API 테스트")
    print("=" * 50)
    
    data = {
        "industry": "카페",
        "mood": "따뜻하고 아늑한",
        "target_customer": "20-30대 직장인",
        "count": 3
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/ai-suggest-names", data=data)
        print(f"상태 코드: {response.status_code}")
        print(f"요청 데이터: {data}")
        print(f"응답:")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"오류: {e}")

def test_ai_suggest_style():
    """스타일 추천 API 테스트"""
    print("\n" + "=" * 50)
    print("스타일 추천 API 테스트")  
    print("=" * 50)
    
    data = {
        "business_name": "봄날",
        "industry": "카페"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/ai-suggest-style", data=data)
        print(f"상태 코드: {response.status_code}")
        print(f"요청 데이터: {data}")
        print(f"응답:")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"오류: {e}")

def test_ai_branding_complete():
    """완전한 브랜딩 패키지 API 테스트"""
    print("\n" + "=" * 50)
    print("완전한 브랜딩 패키지 API 테스트")
    print("=" * 50)
    
    data = {
        "industry": "이탈리안 레스토랑",
        "mood": "고급스럽고 로맨틱한",
        "target_customer": "20-40대 커플",
        "selected_name_index": 0
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/ai-branding-complete", data=data)
        print(f"상태 코드: {response.status_code}")
        print(f"요청 데이터: {data}")
        print(f"응답:")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    print("AI 브랜딩 API 테스트 시작")
    
    # 1. 루트 엔드포인트 테스트
    test_root()
    
    # 2. 상호명 제안 테스트
    test_ai_suggest_names()
    
    # 3. 스타일 추천 테스트
    test_ai_suggest_style()
    
    # 4. 완전한 브랜딩 패키지 테스트
    test_ai_branding_complete()
    
    print("\n" + "=" * 50)
    print("테스트 완료!")
    print("=" * 50)
