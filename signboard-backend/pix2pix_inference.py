import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import cv2
import os
import sys
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# pytorch-CycleGAN-and-pix2pix 라이브러리 경로 추가 (선택적)
# 로컬에 설치되어 있지 않으면 직접 모델 구조 정의
PIX2PIX_LIB_AVAILABLE = False
try:
    # 여러 가능한 경로 시도
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'pytorch-CycleGAN-and-pix2pix'),
        os.path.join(os.path.dirname(__file__), '..', 'pytorch-CycleGAN-and-pix2pix'),
        'pytorch-CycleGAN-and-pix2pix'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            sys.path.insert(0, path)
            try:
                from models.networks import define_G
                PIX2PIX_LIB_AVAILABLE = True
                logger.info(f"pytorch-CycleGAN-and-pix2pix 라이브러리 로드 성공: {path}")
                break
            except ImportError:
                continue
except Exception as e:
    logger.warning(f"pytorch-CycleGAN-and-pix2pix 라이브러리를 찾을 수 없습니다: {e}")


class SignboardAIEngine:
    def __init__(self, checkpoint_path: str, device: str = None):
        """
        Args:
            checkpoint_path: 체크포인트 파일 경로 (예: 'checkpoints/signboard_pix2pix_v1/140_net_G.pth')
            device: 'cuda' or 'cpu' (None이면 자동 선택)
        """
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"체크포인트 파일을 찾을 수 없습니다: {checkpoint_path}")
        
        self.model = self._load_model(checkpoint_path)
        self.model.eval()
        logger.info(f"Pix2pix 모델 로드 완료: {checkpoint_path} (device: {self.device})")
    
    def _load_model(self, checkpoint_path: str):
        """Pix2pix Generator 모델 로드"""
        # 체크포인트 로드
        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        
        # 체크포인트 구조 확인
        if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
            state_dict = checkpoint['state_dict']
        else:
            state_dict = checkpoint
        
        # 모델 아키텍처 추론 (키 이름으로 판단)
        first_key = list(state_dict.keys())[0]
        
        # pytorch-CycleGAN-and-pix2pix 형식인지 확인
        if 'model.model.' in first_key or 'model.0.' in first_key:
            # 라이브러리 사용 가능하면 사용
            if PIX2PIX_LIB_AVAILABLE:
                # 기본 설정으로 모델 생성 (학습 시 사용한 설정과 동일해야 함)
                # 학습 노트북에서는 pix2pix 기본값(UNet + InstanceNorm)을 사용:
                #   netG=unet_256, norm=instance, load_size=512, crop_size=512
                try:
                    model = define_G(
                        input_nc=3,       # RGB 입력
                        output_nc=3,      # RGB 출력
                        ngf=64,           # generator filters
                        netG="unet_256",  # ✅ 학습 시 설정과 맞춤
                        norm="instance",  # ✅ pix2pix 기본값 (InstanceNorm)
                        use_dropout=False,
                        init_type="normal",
                        init_gain=0.02
                    )
                    # state_dict 키 이름 매핑 (pytorch-CycleGAN-and-pix2pix 형식)
                    if 'model.model.' in first_key:
                        # 모델이 DataParallel로 저장된 경우
                        new_state_dict = {}
                        for k, v in state_dict.items():
                            # 'model.model.' 제거
                            new_key = k.replace('model.model.', '')
                            new_state_dict[new_key] = v
                        model.load_state_dict(new_state_dict, strict=False)
                    else:
                        model.load_state_dict(state_dict, strict=False)
                    
                    model.to(self.device)
                    return model
                except Exception as e:
                    logger.warning(f"라이브러리로 모델 로드 실패, 직접 로드 시도: {e}")
            
            # 라이브러리 없이 직접 로드 시도
            # 체크포인트의 키 구조를 분석하여 모델 구조 추론
            # 일반적으로 resnet_9blocks 또는 unet_256 구조
            logger.warning("pytorch-CycleGAN-and-pix2pix 라이브러리가 없습니다. 직접 모델 구조를 정의해야 합니다.")
            raise ImportError(
                "pytorch-CycleGAN-and-pix2pix 라이브러리를 설치하거나, "
                "학습 시 사용한 정확한 모델 아키텍처를 구현해야 합니다.\n"
                "설치 방법: git clone https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix.git"
            )
        else:
            # 다른 형식의 체크포인트
            raise ValueError(f"알 수 없는 체크포인트 형식: {first_key}")
    
    def preprocess(self, img: np.ndarray) -> Tuple[torch.Tensor, Tuple[int, int, int, int, int, int]]:
        """
        OpenCV BGR 이미지를 pix2pix 입력 형식으로 변환 (512x512로 맞춤, 비율 유지)
        
        Args:
            img: OpenCV BGR 이미지 (numpy array, 어떤 크기든 가능)
        
        Returns:
            tuple: (tensor, (original_h, original_w, resized_h, resized_w, pad_top, pad_left))
        """
        original_h, original_w = img.shape[:2]
        original_ratio = original_w / original_h
        
        # 512x512 내에 비율 유지하며 맞추기
        if original_ratio > 1.0:  # 가로가 더 긴 경우
            new_w = 512
            new_h = int(512 / original_ratio)
        else:  # 세로가 더 긴 경우
            new_h = 512
            new_w = int(512 * original_ratio)
        
        # 4의 배수로 맞추기
        new_h = ((new_h + 3) // 4) * 4
        new_w = ((new_w + 3) // 4) * 4
        
        # BGR -> RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # PIL Image로 변환 및 리사이즈 (비율 유지)
        pil_img = Image.fromarray(img_rgb)
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        
        # 512x512로 패딩 추가 (중앙 정렬, 검은색 배경)
        padded_img = Image.new('RGB', (512, 512), (0, 0, 0))
        pad_left = (512 - new_w) // 2
        pad_top = (512 - new_h) // 2
        padded_img.paste(pil_img, (pad_left, pad_top))
        
        # Tensor로 변환 및 정규화
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])  # [-1, 1]
        ])
        
        tensor = transform(padded_img).unsqueeze(0)  # [1, 3, 512, 512]
        scale_info = (original_h, original_w, new_h, new_w, pad_top, pad_left)
        
        return tensor.to(self.device), scale_info
    
    def postprocess(self, tensor: torch.Tensor, scale_info: Tuple[int, int, int, int, int, int]) -> np.ndarray:
        """
        pix2pix 출력을 원본 크기로 복원
        
        Args:
            tensor: 모델 출력 [1, 3, H, W], 값 범위 [-1, 1]
            scale_info: (original_h, original_w, resized_h, resized_w, pad_top, pad_left)
        
        Returns:
            OpenCV BGR 이미지 (원본 크기, BGR)
        """
        original_h, original_w, resized_h, resized_w, pad_top, pad_left = scale_info
        
        # GPU -> CPU, 배치 차원 제거
        img_np = tensor.squeeze(0).cpu().numpy()  # [3, H, W]
        
        # CHW -> HWC
        img_np = np.transpose(img_np, (1, 2, 0))  # [H, W, 3]
        
        # [-1, 1] -> [0, 255]
        img_np = ((img_np + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
        
        # 패딩 제거 (있는 경우)
        if pad_top > 0 or pad_left > 0:
            img_np = img_np[pad_top:pad_top+resized_h, pad_left:pad_left+resized_w]
        
        # 원본 크기로 리사이즈
        img_np = cv2.resize(img_np, (original_w, original_h), interpolation=cv2.INTER_LANCZOS4)
        
        # RGB -> BGR
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        return img_bgr
    
    def enhance(self, phase1_signboard: np.ndarray) -> np.ndarray:
        """
        Phase 1 CG 간판 이미지를 실제 사진처럼 변환 (원본 크기 유지)
        
        Args:
            phase1_signboard: OpenCV BGR 이미지 (간판만, 어떤 크기든 가능)
        
        Returns:
            변환된 간판 이미지 (원본 크기, BGR)
        """
        # 입력 이미지 디버깅
        logger.info(f"[pix2pix] 입력 이미지: shape={phase1_signboard.shape}, min={phase1_signboard.min()}, max={phase1_signboard.max()}, mean={phase1_signboard.mean():.2f}")
        
        # 전처리 (4의 배수로 맞춤, 비율 유지)
        input_tensor, scale_info = self.preprocess(phase1_signboard)
        logger.info(f"[pix2pix] 전처리 후 텐서: shape={input_tensor.shape}, min={input_tensor.min().item():.3f}, max={input_tensor.max().item():.3f}, mean={input_tensor.mean().item():.3f}")
        
        # 추론
        with torch.no_grad():
            output_tensor = self.model(input_tensor)
        
        # 모델 출력 디버깅
        logger.info(f"[pix2pix] 모델 출력 텐서: shape={output_tensor.shape}, min={output_tensor.min().item():.3f}, max={output_tensor.max().item():.3f}, mean={output_tensor.mean().item():.3f}")
        
        # 후처리 (원본 크기로 복원)
        result = self.postprocess(output_tensor, scale_info)
        logger.info(f"[pix2pix] 후처리 후 결과: shape={result.shape}, min={result.min()}, max={result.max()}, mean={result.mean():.2f}")
        
        return result
