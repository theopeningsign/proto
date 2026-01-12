# Phase 2 학습 데이터 폴더 구조

이 폴더는 Phase 2 (AI 품질 개선) 학습을 위한 데이터를 저장합니다.

## 📁 폴더 구조

### `real_photos/`
실제 촬영한 간판 사진을 저장합니다.

**구조:**
```
real_photos/
├── channel/     # 채널 간판 실제 사진
│   ├── day/     # 주간 사진
│   └── night/   # 야간 사진
├── scasi/       # 스카시 간판 실제 사진
│   ├── day/
│   └── night/
└── flex/        # 플렉스 간판 실제 사진
    ├── day/
    └── night/
```

**요구사항:**
- 해상도: 최소 1920x1080 이상 권장
- 형식: JPG, PNG
- 파일명: `{간판타입}_{번호}_{day|night}.jpg` (예: `channel_001_day.jpg`)

---

### `phase1_output/`
Phase 1 (Rule-based)로 생성한 이미지를 저장합니다.

**구조:**
```
phase1_output/
├── channel/     # 채널 간판 Phase 1 결과
├── scasi/       # 스카시 간판 Phase 1 결과
└── flex/        # 플렉스 간판 Phase 1 결과
```

**용도:**
- 실제 사진과 페어링하기 전 Phase 1 결과 저장
- 학습 데이터 생성 전 검증용
- Phase 1 품질 평가용

**파일명 규칙:**
- `{간판타입}_{번호}_{day|night}.png` (예: `channel_001_day.png`)
- 실제 사진과 동일한 번호 사용

---

### `paired_data/`
학습용 페어 데이터 (Phase 1 결과 ↔ 실제 사진)를 저장합니다.

**구조:**
```
paired_data/
├── train/       # 학습용 데이터 (80%)
│   ├── input/   # Phase 1 결과 (입력)
│   └── target/  # 실제 사진 (목표)
└── test/        # 테스트용 데이터 (20%)
    ├── input/
    └── target/
```

**페어링 규칙:**
- `input/`의 파일명과 `target/`의 파일명이 일치해야 함
- 예: `input/channel_001_day.png` ↔ `target/channel_001_day.jpg`

**데이터 분할:**
- train: 전체 데이터의 80%
- test: 전체 데이터의 20%
- 랜덤 분할 또는 시간순 분할

---

## 📊 데이터 수집 계획

### 목표 데이터량:
- **채널 간판**: 주간 50장, 야간 50장
- **스카시 간판**: 주간 50장, 야간 50장
- **플렉스 간판**: 주간 50장, 야간 50장
- **총 300장** (주간 150장 + 야간 150장)

### Phase 1 생성량:
- 각 실제 사진에 대응하는 Phase 1 결과 생성
- 총 300장 (실제 사진과 1:1 매칭)

### 학습 데이터:
- train: 240장 (80%)
- test: 60장 (20%)

---

## 🔄 데이터 준비 워크플로우

### Step 1: 실제 사진 수집
1. `real_photos/{간판타입}/{day|night}/`에 실제 사진 저장
2. 파일명 규칙 준수
3. 메타데이터 기록 (labels.json)

### Step 2: Phase 1 결과 생성
1. 실제 사진과 동일한 조건으로 Phase 1 실행
2. `phase1_output/{간판타입}/`에 저장
3. 파일명 일치 확인

### Step 3: 페어링 및 분할
1. Phase 1 결과와 실제 사진을 페어링
2. `paired_data/train/`과 `paired_data/test/`로 분할
3. 파일명 일치 확인

### Step 4: 학습 준비
1. `paired_data/train/`과 `paired_data/test/`를 모델에 입력
2. 학습 시작

---

## 📝 labels.json 형식

```json
{
  "channel": {
    "day": [
      {
        "id": "channel_001_day",
        "real_photo": "real_photos/channel/day/channel_001_day.jpg",
        "phase1_output": "phase1_output/channel/channel_001_day.png",
        "sign_type": "channel",
        "time": "day",
        "date_collected": "2024-01-15",
        "location": "서울시 강남구",
        "notes": "은행 간판"
      }
    ],
    "night": [...]
  },
  "scasi": {...},
  "flex": {...}
}
```

---

## 🚀 다음 단계

1. **실제 사진 수집** (Week 5-6)
   - 각 간판 타입별로 주간/야간 사진 촬영
   - 최소 50장씩 목표

2. **Phase 1 결과 생성** (Week 6)
   - 실제 사진과 동일한 조건으로 Phase 1 실행
   - 자동화 스크립트 작성

3. **데이터 검증** (Week 6)
   - 페어링 정확도 확인
   - 품질 검수

4. **학습 시작** (Week 7)
   - Pix2Pix 모델 학습
   - 품질 평가

---

## 📌 주의사항

- **파일 크기**: 이미지 파일은 용량이 크므로 `.gitignore`에 포함됨
- **백업**: 중요한 데이터는 별도로 백업 권장
- **버전 관리**: `labels.json`만 git에 포함 (이미지는 제외)
- **개인정보**: 실제 사진에 개인정보가 포함되지 않도록 주의

---

생성일: 2024-01-XX
