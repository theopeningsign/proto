# 간판 시안 생성 웹 애플리케이션

건물 사진에 간판을 합성하여 주간/야간 시뮬레이션을 생성하는 웹 애플리케이션입니다.

## 프로젝트 구조

```
proto/
├── signboard-backend/     # FastAPI 백엔드
│   ├── main.py           # API 서버
│   └── requirements.txt  # Python 패키지
└── signboard-frontend/   # React 프론트엔드
    ├── src/
    │   ├── App.js
    │   └── components/
    └── package.json
```

## 빠른 시작

### 방법 1: 자동 시작 스크립트 (권장)

**Windows (PowerShell):**
```powershell
.\start-dev.ps1
```

**Windows (CMD):**
```cmd
start-dev.bat
```

이 스크립트가 백엔드와 프론트엔드를 자동으로 시작합니다.

### 방법 2: 수동 시작

#### 1. 백엔드 서버 실행

```bash
cd signboard-backend

# 가상환경 활성화
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 서버 실행
python main.py
```

백엔드가 `http://localhost:8000`에서 실행됩니다.

#### 2. 프론트엔드 서버 실행 (새 터미널)

```bash
cd signboard-frontend

# 패키지 설치 (최초 1회)
npm install

# 개발 서버 실행
npm start
```

프론트엔드가 `http://localhost:3000`에서 실행됩니다.

## 사용 방법

1. **건물 사진 업로드**: 메인 페이지에서 건물 사진을 업로드합니다.
2. **간판 추가**: "간판 추가" 버튼을 클릭하여 간판을 추가합니다.
3. **간판 설정**: 각 간판마다 텍스트, 종류, 색상 등을 설정합니다.
4. **위치 선택**: 이미지에서 간판 위치의 4개 꼭지점을 클릭합니다.
5. **시뮬레이션 생성**: "시안 생성하기" 버튼을 클릭합니다.
6. **결과 확인**: 주간/야간 시뮬레이션 결과를 확인하고 다운로드할 수 있습니다.

## 주요 기능

- ✅ 여러 간판/시트시공 동시 추가
- ✅ 사진 업로드 및 4개 점 선택
- ✅ 간판 정보 입력 (상호명, 로고, 종류, 색상)
- ✅ 간판 렌더링 (간판 종류별 효과)
- ✅ 원근 변환을 통한 이미지 합성
- ✅ 주간/야간 버전 생성
- ✅ 결과 비교 및 다운로드

## 기술 스택

### 백엔드
- FastAPI
- OpenCV (이미지 처리)
- Pillow (텍스트/로고 렌더링)
- NumPy

### 프론트엔드
- React
- Tailwind CSS
- Framer Motion (애니메이션)
- Axios

## API 엔드포인트

### POST /api/generate-simulation

간판 시뮬레이션을 생성합니다.

**요청:**
- `building_photo`: 건물 사진 (base64)
- `signboards`: 간판 리스트 (JSON)

**응답:**
```json
{
  "day_simulation": "data:image/png;base64,...",
  "night_simulation": "data:image/png;base64,..."
}
```

## 문제 해결

### 백엔드 서버가 시작되지 않을 때
- 가상환경이 활성화되었는지 확인
- `pip install -r requirements.txt` 실행

### CORS 에러가 발생할 때
- 백엔드 서버가 `http://localhost:8000`에서 실행 중인지 확인
- `signboard-backend/main.py`의 CORS 설정 확인

### 프론트엔드가 시작되지 않을 때
- `npm install` 실행
- 포트 3000이 사용 중인지 확인

## 다음 단계 (향후 개선)

- [ ] 로고 이미지 실제 배치 기능
- [ ] 더 정교한 발광 효과
- [ ] 간판 크기 조절 기능
- [ ] 히스토리 저장 기능
