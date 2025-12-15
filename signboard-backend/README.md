# 간판 시안 생성기 - 백엔드

FastAPI + OpenCV + Pillow로 구현된 간판 시안 생성 API 서버입니다.

## 설치 및 실행

### 가상환경 생성 및 활성화

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 패키지 설치

```bash
pip install -r requirements.txt
```

### 서버 실행

```bash
python main.py
```

또는

```bash
uvicorn main:app --reload
```

API 서버가 http://localhost:8000 에서 실행됩니다.

## API 엔드포인트

### POST /api/generate-simulation

간판 시뮬레이션을 생성합니다.

**요청 파라미터:**
- `building_photo`: 건물 사진 (base64)
- `four_points`: 간판 위치 4개 점 (JSON 문자열)
- `text`: 상호명
- `logo`: 로고 이미지 (base64, 선택)
- `sign_type`: 간판 종류
- `bg_color`: 배경색 (hex)
- `text_color`: 글자색 (hex)

**응답:**
```json
{
  "day_simulation": "data:image/png;base64,...",
  "night_simulation": "data:image/png;base64,..."
}
```




