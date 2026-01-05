"""
labels.json의 cropped_photo 경로 수정 스크립트

cropped_photo 경로를 "cropped_photos/파일명" 형식으로 통일합니다.
"""

import json
from pathlib import Path

def main():
    # labels.json 경로
    script_dir = Path(__file__).parent
    labels_path = script_dir / "phase2_data" / "real_photos" /"labels.json"
    
    if not labels_path.exists():
        print(f"❌ labels.json을 찾을 수 없습니다: {labels_path}")
        return
    
    print(f"📂 labels.json 로드 중: {labels_path}")
    
    # labels.json 로드
    with open(labels_path, 'r', encoding='utf-8') as f:
        labels = json.load(f)
    
    # 통계
    total_entries = 0
    fixed_count = 0
    
    # cropped_photo 경로 수정
    for sign_type_key in labels:
        for time_type in labels[sign_type_key]:
            for entry in labels[sign_type_key][time_type]:
                total_entries += 1
                
                if "cropped_photo" in entry:
                    old_path = entry["cropped_photo"]
                    
                    # 파일명만 추출
                    filename = Path(old_path).name
                    
                    # 새 경로 생성
                    new_path = f"cropped_photos/{filename}"
                    
                    # 경로가 다르면 수정
                    if old_path != new_path:
                        print(f"  수정: {old_path} → {new_path}")
                        entry["cropped_photo"] = new_path
                        fixed_count += 1
    
    # 저장
    print(f"\n💾 labels.json 저장 중...")
    with open(labels_path, 'w', encoding='utf-8') as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 완료!")
    print(f"   총 항목: {total_entries}")
    print(f"   수정된 항목: {fixed_count}")
    print(f"   수정되지 않은 항목: {total_entries - fixed_count}")

if __name__ == "__main__":
    main()