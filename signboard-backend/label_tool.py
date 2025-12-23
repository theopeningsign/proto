"""
간판 사진 라벨링 도구

사용법:
    python label_tool.py --input real_photos/unlabeled/
    python label_tool.py --input real_photos/unlabeled/ --labels labels.json

기능:
    - 사진을 하나씩 보여주고 키보드로 분류
    - 자동으로 해당 폴더로 이동
    - labels.json에 메타데이터 저장
"""

import os
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from PIL import Image
import cv2

# 간판 타입 매핑
SIGN_TYPES = {
    '1': 'channel',
    '2': 'scasi',
    '3': 'flex'
}

# 시간대 매핑
TIME_TYPES = {
    'd': 'day',
    'n': 'night'
}

# 타입 한글명
SIGN_TYPE_NAMES = {
    'channel': '채널',
    'scasi': '스카시',
    'flex': '플렉스'
}

TIME_TYPE_NAMES = {
    'day': '주간',
    'night': '야간'
}


class LabelingTool:
    def __init__(self, input_dir, labels_file=None, output_base=None):
        """
        라벨링 도구 초기화
        
        Args:
            input_dir: 라벨링할 사진이 있는 폴더
            labels_file: labels.json 파일 경로 (없으면 자동 생성)
            output_base: 출력 기본 폴더 (없으면 input_dir의 상위 폴더)
        """
        self.input_dir = Path(input_dir)
        self.output_base = output_base or self.input_dir.parent
        
        # labels.json 경로
        if labels_file:
            self.labels_file = Path(labels_file)
        else:
            self.labels_file = self.output_base / "labels.json"
        
        # labels.json 로드
        self.labels = self.load_labels()
        
        # 되돌리기 히스토리
        self.undo_history = []
        
        # 이미지 파일 목록
        self.image_files = self.get_image_files()
        self.current_index = 0
        
        # 통계
        self.stats = {
            'total': len(self.image_files),
            'labeled': 0,
            'skipped': 0
        }
    
    def load_labels(self):
        """labels.json 로드"""
        if self.labels_file.exists():
            with open(self.labels_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 기본 구조 생성
            return {
                "channel": {"day": [], "night": []},
                "scasi": {"day": [], "night": []},
                "flex": {"day": [], "night": []}
            }
    
    def save_labels(self):
        """labels.json 저장"""
        self.labels_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.labels_file, 'w', encoding='utf-8') as f:
            json.dump(self.labels, f, ensure_ascii=False, indent=2)
    
    def get_image_files(self):
        """이미지 파일 목록 가져오기"""
        extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
        files = []
        for ext in extensions:
            files.extend(self.input_dir.glob(f'*{ext}'))
        return sorted(files)
    
    def show_image_info(self, image_path):
        """이미지 정보 표시 및 미리보기"""
        try:
            img = Image.open(image_path)
            width, height = img.size
            file_size = os.path.getsize(image_path) / 1024  # KB
            
            print("\n" + "=" * 60)
            print(f"파일: {image_path.name}")
            print(f"경로: {image_path}")
            print(f"크기: {width}x{height}px")
            print(f"용량: {file_size:.1f} KB")
            print("=" * 60)
            
            # OpenCV로 이미지 창 띄우기
            try:
                img_cv = cv2.imread(str(image_path))
                if img_cv is not None:
                    # 창 크기 조정 (너무 크면 화면에 맞춤)
                    max_width = 1200
                    max_height = 800
                    h, w = img_cv.shape[:2]
                    
                    if w > max_width or h > max_height:
                        scale = min(max_width / w, max_height / h)
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        img_cv = cv2.resize(img_cv, (new_w, new_h))
                    
                    cv2.imshow('간판 이미지 (분류 후 자동으로 닫힙니다)', img_cv)
                    cv2.waitKey(100)  # 창 표시 (100ms)
                    print("\n[이미지 창이 열렸습니다]")
                else:
                    print("\n[이미지 로드 실패]")
            except Exception as e:
                print(f"\n[이미지 미리보기 오류: {e}]")
                print("(파일 탐색기에서 직접 확인하세요)")
            
        except Exception as e:
            print(f"\n[이미지 정보 로드 오류: {e}]")
            print(f"파일: {image_path.name}")
    
    def show_ui(self, image_path):
        """UI 표시"""
        # 화면 클리어
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 진행상황
        progress = (self.current_index / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        print("\n" + "=" * 60)
        print(f"진행: {self.current_index + 1}/{self.stats['total']} ({progress:.1f}%)")
        print(f"라벨링 완료: {self.stats['labeled']} | 건너뛰기: {self.stats['skipped']}")
        print("=" * 60)
        
        # 이미지 정보
        self.show_image_info(image_path)
        
        # 안내
        print("\n" + "-" * 60)
        print("이 간판의 타입은?")
        print("  [1] 채널 간판")
        print("  [2] 스카시 간판")
        print("  [3] 플렉스 간판")
        print()
        print("시간대는?")
        print("  [D] 주간")
        print("  [N] 야간")
        print()
        print("  [S] 건너뛰기 (흐릿한 사진 등)")
        print("  [Z] 되돌리기 (이전 분류 취소)")
        print("  [Q] 종료 및 저장")
        print("-" * 60)
        print("\n입력: ", end='', flush=True)
    
    def move_file(self, source, sign_type, time_type):
        """파일을 해당 폴더로 이동"""
        # 목적지 폴더
        dest_dir = self.output_base / "real_photos" / sign_type / time_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성 (중복 방지)
        base_name = source.stem
        ext = source.suffix
        dest_file = dest_dir / f"{sign_type}_{base_name}_{time_type}{ext}"
        
        # 중복 시 번호 추가
        counter = 1
        while dest_file.exists():
            dest_file = dest_dir / f"{sign_type}_{base_name}_{time_type}_{counter}{ext}"
            counter += 1
        
        # 파일 이동
        shutil.move(str(source), str(dest_file))
        
        return dest_file
    
    def add_to_labels(self, image_path, sign_type, time_type, original_path):
        """labels.json에 추가"""
        # 고유 ID 생성
        file_id = f"{sign_type}_{image_path.stem}_{time_type}"
        
        entry = {
            "id": file_id,
            "real_photo": str(image_path.relative_to(self.output_base)),
            "sign_type": sign_type,
            "time": time_type,
            "date_labeled": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original_filename": original_path.name
        }
        
        self.labels[sign_type][time_type].append(entry)
    
    def undo_last(self):
        """마지막 분류 되돌리기"""
        if not self.undo_history:
            print("\n[되돌릴 항목이 없습니다]")
            input("계속하려면 Enter를 누르세요...")
            return False
        
        last_action = self.undo_history.pop()
        
        # 파일 되돌리기
        if last_action['dest_file'].exists():
            shutil.move(str(last_action['dest_file']), str(last_action['source_file']))
        
        # labels.json에서 제거
        sign_type = last_action['sign_type']
        time_type = last_action['time_type']
        labels_list = self.labels[sign_type][time_type]
        
        # 마지막 항목 제거
        if labels_list:
            labels_list.pop()
        
        # 통계 업데이트
        self.stats['labeled'] -= 1
        self.current_index -= 1
        
        print(f"\n[되돌림 완료: {last_action['source_file'].name}]")
        input("계속하려면 Enter를 누르세요...")
        return True
    
    def process_image(self, image_path):
        """이미지 처리"""
        self.show_ui(image_path)
        
        # 키보드 입력 받기
        while True:
            try:
                key = input().strip().lower()
                
                if key == 'q':
                    return 'quit'
                elif key == 's':
                    cv2.destroyAllWindows()
                    self.stats['skipped'] += 1
                    return 'skip'
                elif key == 'z':
                    cv2.destroyAllWindows()
                    if self.undo_last():
                        return 'undo'
                    continue
                elif key in SIGN_TYPES and key in ['1', '2', '3']:
                    # 간판 타입 선택됨
                    sign_type = SIGN_TYPES[key]
                    print(f"\n선택: {SIGN_TYPE_NAMES[sign_type]} 간판")
                    print("시간대를 선택하세요 [D] 주간 / [N] 야간: ", end='', flush=True)
                    
                    # 시간대 입력
                    time_key = input().strip().lower()
                    
                    if time_key in TIME_TYPES:
                        time_type = TIME_TYPES[time_key]
                        
                        # 이미지 창 닫기
                        cv2.destroyAllWindows()
                        
                        # 파일 이동
                        dest_file = self.move_file(image_path, sign_type, time_type)
                        
                        # labels.json에 추가
                        self.add_to_labels(dest_file, sign_type, time_type, image_path)
                        
                        # 되돌리기 히스토리에 추가
                        self.undo_history.append({
                            'source_file': image_path,
                            'dest_file': dest_file,
                            'sign_type': sign_type,
                            'time_type': time_type
                        })
                        
                        # 통계 업데이트
                        self.stats['labeled'] += 1
                        
                        print(f"\n[완료] {SIGN_TYPE_NAMES[sign_type]} 간판 ({TIME_TYPE_NAMES[time_type]})")
                        print(f"이동: {dest_file.relative_to(self.output_base)}")
                        input("계속하려면 Enter를 누르세요...")
                        return 'next'
                    else:
                        print("\n[잘못된 입력] D 또는 N을 입력하세요")
                        continue
                else:
                    print("\n[잘못된 입력] 1, 2, 3, D, N, S, Z, Q 중 하나를 입력하세요")
                    print("입력: ", end='', flush=True)
                    continue
                    
            except KeyboardInterrupt:
                cv2.destroyAllWindows()
                print("\n\n[중단됨] 저장하시겠습니까? (y/n): ", end='', flush=True)
                save = input().strip().lower()
                if save == 'y':
                    return 'quit'
                else:
                    continue
    
    def run(self):
        """라벨링 도구 실행"""
        if not self.image_files:
            print(f"[오류] {self.input_dir}에 이미지 파일이 없습니다.")
            return
        
        print("\n" + "=" * 60)
        print("간판 사진 라벨링 도구")
        print("=" * 60)
        print(f"입력 폴더: {self.input_dir}")
        print(f"출력 폴더: {self.output_base / 'real_photos'}")
        print(f"총 {self.stats['total']}개 파일")
        print("=" * 60)
        input("\n시작하려면 Enter를 누르세요...")
        
        # 각 이미지 처리
        while self.current_index < len(self.image_files):
            image_path = self.image_files[self.current_index]
            
            result = self.process_image(image_path)
            
            if result == 'quit':
                break
            elif result == 'next':
                self.current_index += 1
            elif result == 'skip':
                self.current_index += 1
            elif result == 'undo':
                # 인덱스는 undo_last()에서 이미 조정됨
                continue
        
        # 이미지 창 닫기
        cv2.destroyAllWindows()
        
        # labels.json 저장
        self.save_labels()
        
        # 최종 통계
        print("\n" + "=" * 60)
        print("라벨링 완료!")
        print("=" * 60)
        print(f"총 파일: {self.stats['total']}")
        print(f"라벨링 완료: {self.stats['labeled']}")
        print(f"건너뛰기: {self.stats['skipped']}")
        print(f"labels.json 저장: {self.labels_file}")
        print("=" * 60)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='간판 사진 라벨링 도구')
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='라벨링할 사진이 있는 폴더'
    )
    parser.add_argument(
        '--labels',
        type=str,
        default=None,
        help='labels.json 파일 경로 (기본: input 폴더의 상위/labels.json)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='출력 기본 폴더 (기본: input 폴더의 상위)'
    )
    
    args = parser.parse_args()
    
    # 도구 실행
    tool = LabelingTool(
        input_dir=args.input,
        labels_file=args.labels,
        output_base=args.output
    )
    tool.run()


if __name__ == "__main__":
    main()

