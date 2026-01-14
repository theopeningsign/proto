# Pix2Pix 모델 설정 가이드

## 📋 필수 요구사항

### 1. PyTorch 설치

```bash
# CPU 버전 (테스트용)
pip install torch torchvision

# GPU 버전 (CUDA 11.8 예시)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 2. Pix2Pix 라이브러리 설치 (선택적, 권장)

pix2pix 모델을 사용하기 위해 `pytorch-CycleGAN-and-pix2pix` 라이브러리가 필요합니다.

#### 방법 1: Git 클론 (권장)

```bash
cd signboard-backend
git clone https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix.git
```

이렇게 하면 `signboard-backend/pytorch-CycleGAN-and-pix2pix/` 폴더에 라이브러리가 설치됩니다.

#### 방법 2: 직접 설치

```bash
pip install git+https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix.git
```

## 📁 모델 파일 위치

학습된 모델 체크포인트는 다음 위치에 있어야 합니다:

```
signboard-backend/
└── checkpoints/
    └── signboard_pix2pix_v1/
        └── 140_net_G.pth  ✅ (이미 저장됨)
```

## 🧪 테스트

### 1. 모델 로드 테스트

```bash
cd signboard-backend
python -c "from pix2pix_inference import SignboardAIEngine; engine = SignboardAIEngine('checkpoints/signboard_pix2pix_v1/140_net_G.pth'); print('✅ 모델 로드 성공!')"
```

### 2. 백엔드 서버 실행

```bash
cd signboard-backend
python main.py
```

서버가 시작되면 로그에 다음 메시지가 표시됩니다:
- `Pix2pix 모델 로드 완료: ...` (성공 시)
- `Pix2pix 모델 로드 실패: ...` (실패 시)

## 🔧 문제 해결

### 문제 1: "pytorch-CycleGAN-and-pix2pix 라이브러리를 찾을 수 없습니다"

**해결 방법:**
1. `signboard-backend/` 폴더에 `pytorch-CycleGAN-and-pix2pix` 폴더가 있는지 확인
2. 없다면 위의 "방법 1"로 Git 클론 실행

### 문제 2: "체크포인트 파일을 찾을 수 없습니다"

**해결 방법:**
1. `checkpoints/signboard_pix2pix_v1/140_net_G.pth` 파일이 존재하는지 확인
2. 파일 경로가 올바른지 확인

### 문제 3: "알 수 없는 체크포인트 형식"

**해결 방법:**
- 모델이 다른 아키텍처로 학습되었을 수 있습니다
- `pix2pix_inference.py`의 `_load_model` 메서드에서 모델 아키텍처를 수정해야 할 수 있습니다
- 학습 시 사용한 `--netG` 옵션을 확인하세요 (기본값: `resnet_9blocks`)

## 📝 참고사항

- 모델 로드는 서버 시작 시 1회만 수행됩니다 (싱글톤 패턴)
- GPU가 있으면 자동으로 사용하고, 없으면 CPU로 동작합니다
- 모델 파일 크기: 약 212MB (140_net_G.pth)
