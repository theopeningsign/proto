"""
기존 라벨링된 사진들을 unlabeled 폴더로 되돌리는 스크립트

사용법:
    python reset_labels.py
"""

from pathlib import Path
import shutil

def reset_labels():
    """분류된 사진들을 모두 unlabeled로 이동"""
    script_dir = Path(__file__).parent
    photos_dir = script_dir / "phase2_data" / "real_photos"
    unlabeled_dir = photos_dir / "unlabeled"
    
    # unlabeled 디렉토리 생성
    unlabeled_dir.mkdir(parents=True, exist_ok=True)
    
    # 이동할 폴더들 (unlabeled, real_photos, labels.json 제외)
    exclude_dirs = {"unlabeled", "real_photos", "labels.json"}
    
    moved_count = 0
    
    # 모든 파일 찾기
    for item in photos_dir.iterdir():
        if item.name in exclude_dirs:
            continue
        
        if item.is_file():
            # 파일이면 직접 이동
            dest = unlabeled_dir / item.name
            if dest.exists():
                print(f"[스킵] 이미 존재: {item.name}")
            else:
                shutil.move(str(item), str(dest))
                print(f"[이동] {item.name}")
                moved_count += 1
        
        elif item.is_dir():
            # 디렉토리면 재귀적으로 파일 찾아서 이동
            for photo_file in item.rglob("*.*"):
                if photo_file.is_file() and photo_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                    # unlabeled에 파일명만으로 저장 (중복 방지)
                    dest = unlabeled_dir / photo_file.name
                    
                    # 중복 처리: 파일명 뒤에 숫자 추가
                    counter = 1
                    original_dest = dest
                    while dest.exists():
                        stem = original_dest.stem
                        suffix = original_dest.suffix
                        dest = unlabeled_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                    
                    shutil.move(str(photo_file), str(dest))
                    print(f"[이동] {photo_file.relative_to(photos_dir)} → {dest.name}")
                    moved_count += 1
            
            # 빈 디렉토리 삭제 시도
            try:
                item.rmdir()
                print(f"[삭제] 빈 폴더: {item.name}")
            except OSError:
                # 디렉토리가 비어있지 않으면 무시
                pass
    
    # real_photos 안의 파일들도 처리
    real_photos_subdir = photos_dir / "real_photos"
    if real_photos_subdir.exists():
        for photo_file in real_photos_subdir.rglob("*.*"):
            if photo_file.is_file() and photo_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                dest = unlabeled_dir / photo_file.name
                
                # 중복 처리
                counter = 1
                original_dest = dest
                while dest.exists():
                    stem = original_dest.stem
                    suffix = original_dest.suffix
                    dest = unlabeled_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                shutil.move(str(photo_file), str(dest))
                print(f"[이동] {photo_file.relative_to(photos_dir)} → {dest.name}")
                moved_count += 1
    
    # labels.json 백업 후 삭제
    labels_file = photos_dir / "labels.json"
    if labels_file.exists():
        backup_file = photos_dir / "labels.json.backup"
        if backup_file.exists():
            backup_file.unlink()
        shutil.move(str(labels_file), str(backup_file))
        print(f"[백업] labels.json → labels.json.backup")
    
    print(f"\n[완료] 총 {moved_count}개 파일을 unlabeled로 이동했습니다.")
    print(f"[폴더] unlabeled: {unlabeled_dir}")
    print(f"[백업] labels.json은 labels.json.backup으로 백업되었습니다.")


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("라벨링 초기화 스크립트")
    print("=" * 60)
    
    # --yes 옵션이 있으면 자동 실행
    auto_yes = '--yes' in sys.argv or '-y' in sys.argv
    
    if not auto_yes:
        print("\n⚠️  이 스크립트는 분류된 모든 사진을 unlabeled로 이동합니다.")
        response = input("계속하시겠습니까? (yes/no): ")
        if response.lower() not in ['yes', 'y', '예', 'ㅇ']:
            print("취소되었습니다.")
            sys.exit(0)
    
    reset_labels()

