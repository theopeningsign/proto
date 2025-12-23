"""
간판 Pair 생성 & 보정 도구 (GUI)

기능:
1. 자동 생성: labels.json 읽어서 pair 자동 생성
2. 결과 확인: 생성된 pair 썸네일 그리드
3. 수동 보정: 색상 수정 및 재생성
4. 통계: 성공률 및 분포

사용법:
    python signboard_pair_tool.py
"""

import os
import json
import sys
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from PIL import Image, ImageTk
import cv2
import numpy as np

# generate_pairs.py에서 필요한 함수들 import
from generate_pairs import (
    extract_colors_v2,
    extract_colors,
    generate_phase1_image,
    center_crop_and_resize,
    load_labels,
    SIGN_TYPE_MAP,
    rgb_to_hex,
)
from main import render_signboard


class PairGeneratorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("간판 Pair 생성 & 보정 도구 v2.0")
        self.root.geometry("1400x900")
        
        # 데이터 경로
        self.script_dir = Path(__file__).parent
        self.labels_path = self.script_dir / "phase2_data" / "labels.json"
        self.real_photos_root = self.script_dir / "phase2_data" / "real_photos"
        self.output_root = self.script_dir / "phase2_data" / "paired_data"
        
        # 상태 변수
        self.samples: List[Dict] = []
        self.generated_pairs: Dict[str, Dict] = {}  # pair_id -> metadata
        self.current_pair_index = 0
        self.current_pair_id = None
        self.use_v2_extractor = True
        self.is_generating = False
        
        # GUI 초기화
        self.setup_gui()
        
        # labels.json 로드 시도
        self.load_samples()
    
    def setup_gui(self):
        """GUI 설정"""
        # 탭 생성
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 탭 1: 자동 생성
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="자동 생성")
        self.create_generate_tab()
        
        # 탭 2: 결과 확인
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="결과 확인")
        self.create_review_tab()
        
        # 탭 3: 수동 보정
        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="수동 보정")
        self.create_fix_tab()
        
        # 탭 4: 통계
        self.tab4 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab4, text="통계")
        self.create_stats_tab()
    
    def create_generate_tab(self):
        """자동 생성 탭"""
        # 상단: 설정
        config_frame = ttk.LabelFrame(self.tab1, text="설정", padding="10")
        config_frame.pack(fill='x', padx=10, pady=10)
        
        # labels.json 경로
        ttk.Label(config_frame, text="labels.json:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.labels_path_var = tk.StringVar(value=str(self.labels_path))
        labels_entry = ttk.Entry(config_frame, textvariable=self.labels_path_var, width=60)
        labels_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(config_frame, text="찾기", command=self.browse_labels_file).grid(row=0, column=2, padx=5, pady=5)
        
        # 출력 폴더
        ttk.Label(config_frame, text="출력 폴더:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.output_path_var = tk.StringVar(value=str(self.output_root))
        output_entry = ttk.Entry(config_frame, textvariable=self.output_path_var, width=60)
        output_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(config_frame, text="찾기", command=self.browse_output_folder).grid(row=1, column=2, padx=5, pady=5)
        
        config_frame.columnconfigure(1, weight=1)
        
        # 옵션
        options_frame = ttk.LabelFrame(self.tab1, text="옵션", padding="10")
        options_frame.pack(fill='x', padx=10, pady=10)
        
        self.v2_extractor_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="v2 색상 추출 사용 (권장)",
            variable=self.v2_extractor_var
        ).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        ttk.Label(options_frame, text="Train/Test 비율:").grid(row=0, column=1, padx=5, pady=5)
        self.split_var = tk.DoubleVar(value=0.8)
        split_scale = ttk.Scale(options_frame, from_=0.5, to=0.9, variable=self.split_var, orient='horizontal', length=200)
        split_scale.grid(row=0, column=2, padx=5, pady=5)
        self.split_label = ttk.Label(options_frame, text="80%")
        self.split_label.grid(row=0, column=3, padx=5, pady=5)
        split_scale.configure(command=lambda v: self.split_label.config(text=f"{float(v)*100:.0f}%"))
        
        # 상태 표시
        status_frame = ttk.LabelFrame(self.tab1, text="상태", padding="10")
        status_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 샘플 정보
        self.sample_info_label = ttk.Label(status_frame, text="labels.json을 로드하세요.", font=('맑은 고딕', 10))
        self.sample_info_label.pack(anchor='w', pady=5)
        
        # 진행률
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100, length=600)
        self.progress_bar.pack(fill='x', pady=10)
        
        self.progress_label = ttk.Label(status_frame, text="대기 중...", font=('맑은 고딕', 10))
        self.progress_label.pack(anchor='w', pady=5)
        
        # 로그
        log_frame = ttk.LabelFrame(status_frame, text="로그", padding="5")
        log_frame.pack(fill='both', expand=True, pady=10)
        
        self.log_text = tk.Text(log_frame, height=15, wrap='word', font=('Consolas', 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        log_scrollbar.pack(side='right', fill='y')
        
        # 버튼
        button_frame = ttk.Frame(self.tab1)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="샘플 다시 로드", command=self.load_samples).pack(side='left', padx=5)
        self.generate_button = ttk.Button(button_frame, text="▶ 자동 생성 시작", command=self.start_generation)
        self.generate_button.pack(side='left', padx=5)
        ttk.Button(button_frame, text="중지", command=self.stop_generation).pack(side='left', padx=5)
    
    def create_review_tab(self):
        """결과 확인 탭"""
        # 필터
        filter_frame = ttk.Frame(self.tab2)
        filter_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(filter_frame, text="필터:", font=('맑은 고딕', 10, 'bold')).pack(side='left', padx=5)
        self.filter_var = tk.StringVar(value="전체")
        ttk.Radiobutton(filter_frame, text="전체", variable=self.filter_var, value="전체", command=self.refresh_review).pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="문제있음만", variable=self.filter_var, value="문제", command=self.refresh_review).pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="정상", variable=self.filter_var, value="정상", command=self.refresh_review).pack(side='left', padx=5)
        
        # 캔버스 프레임
        canvas_frame = ttk.Frame(self.tab2)
        canvas_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 스크롤 가능한 캔버스
        self.review_canvas = tk.Canvas(canvas_frame, bg='white')
        review_scrollbar_v = ttk.Scrollbar(canvas_frame, orient='vertical', command=self.review_canvas.yview)
        review_scrollbar_h = ttk.Scrollbar(canvas_frame, orient='horizontal', command=self.review_canvas.xview)
        self.review_canvas.configure(yscrollcommand=review_scrollbar_v.set, xscrollcommand=review_scrollbar_h.set)
        
        self.review_canvas.pack(side='left', fill='both', expand=True)
        review_scrollbar_v.pack(side='right', fill='y')
        review_scrollbar_h.pack(side='bottom', fill='x')
        
        # 그리드 프레임 (캔버스 위에)
        self.review_grid_frame = ttk.Frame(self.review_canvas)
        self.review_canvas_window = self.review_canvas.create_window((0, 0), window=self.review_grid_frame, anchor='nw')
        
        # 캔버스 스크롤 영역 업데이트
        self.review_grid_frame.bind('<Configure>', lambda e: self.review_canvas.configure(scrollregion=self.review_canvas.bbox('all')))
        self.review_canvas.bind('<Configure>', self._on_canvas_configure)
        
        # 상태
        self.review_status_label = ttk.Label(self.tab2, text="생성된 pair가 없습니다.", font=('맑은 고딕', 10))
        self.review_status_label.pack(pady=5)
    
    def create_fix_tab(self):
        """수동 보정 탭"""
        # 상단: 네비게이션
        nav_frame = ttk.Frame(self.tab3)
        nav_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(nav_frame, text="← 이전", command=self.prev_pair).pack(side='left', padx=5)
        self.pair_info_label = ttk.Label(nav_frame, text="Pair 없음", font=('맑은 고딕', 11, 'bold'))
        self.pair_info_label.pack(side='left', padx=20)
        ttk.Button(nav_frame, text="다음 →", command=self.next_pair).pack(side='left', padx=5)
        
        # 이미지 표시 영역
        image_frame = ttk.Frame(self.tab3)
        image_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # TARGET (왼쪽)
        target_frame = ttk.LabelFrame(image_frame, text="TARGET (실제 사진)", padding="10")
        target_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.target_label = ttk.Label(target_frame, text="이미지 없음")
        self.target_label.pack(fill='both', expand=True)
        
        ttk.Button(target_frame, text="확대", command=lambda: self.zoom_image('target')).pack(pady=5)
        ttk.Button(target_frame, text="Target에서 색상 추출", command=self.extract_from_target).pack(pady=5)
        
        # INPUT (오른쪽)
        input_frame = ttk.LabelFrame(image_frame, text="INPUT (Phase 1 생성)", padding="10")
        input_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.input_label = ttk.Label(input_frame, text="이미지 없음")
        self.input_label.pack(fill='both', expand=True)
        
        ttk.Button(input_frame, text="확대", command=lambda: self.zoom_image('input')).pack(pady=5)
        
        # 색상 조정 영역
        color_frame = ttk.LabelFrame(self.tab3, text="색상 조정", padding="10")
        color_frame.pack(fill='x', padx=10, pady=10)
        
        # 배경색
        bg_frame = ttk.Frame(color_frame)
        bg_frame.pack(fill='x', pady=5)
        ttk.Label(bg_frame, text="배경색:", font=('맑은 고딕', 10)).pack(side='left', padx=5)
        self.bg_color_var = tk.StringVar(value="#6b2d8f")
        bg_entry = ttk.Entry(bg_frame, textvariable=self.bg_color_var, width=10)
        bg_entry.pack(side='left', padx=5)
        self.bg_color_button = tk.Button(bg_frame, text="🎨", command=lambda: self.choose_color('bg'), width=3)
        self.bg_color_button.pack(side='left', padx=5)
        
        # 텍스트색
        text_frame = ttk.Frame(color_frame)
        text_frame.pack(fill='x', pady=5)
        ttk.Label(text_frame, text="텍스트색:", font=('맑은 고딕', 10)).pack(side='left', padx=5)
        self.text_color_var = tk.StringVar(value="#ffffff")
        text_entry = ttk.Entry(text_frame, textvariable=self.text_color_var, width=10)
        text_entry.pack(side='left', padx=5)
        self.text_color_button = tk.Button(text_frame, text="🎨", command=lambda: self.choose_color('text'), width=3)
        self.text_color_button.pack(side='left', padx=5)
        
        # 버튼
        button_frame = ttk.Frame(self.tab3)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="💾 저장", command=self.save_current_pair).pack(side='left', padx=5)
        ttk.Button(button_frame, text="🔄 이 Pair만 재생성", command=self.regenerate_current_pair).pack(side='left', padx=5)
        ttk.Button(button_frame, text="✓ 괜찮음 - 다음으로", command=self.mark_ok_and_next).pack(side='left', padx=5)
        ttk.Button(button_frame, text="⚠️ 문제있음 표시", command=self.mark_problem).pack(side='left', padx=5)
    
    def create_stats_tab(self):
        """통계 탭"""
        stats_frame = ttk.Frame(self.tab4)
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 통계 라벨
        self.stats_label = ttk.Label(stats_frame, text="통계 데이터가 없습니다.\n자동 생성을 먼저 실행하세요.", font=('맑은 고딕', 12), justify='center')
        self.stats_label.pack(expand=True)
        
        ttk.Button(stats_frame, text="통계 새로고침", command=self.update_stats).pack(pady=10)
    
    # 유틸리티 메서드들
    def _get_relative_path(self, target_path: Path, base_path: Path) -> str:
        """상대 경로 계산 (경로가 base에 포함되지 않으면 phase2_data 기준으로)"""
        try:
            # 먼저 base_path 기준으로 시도
            return str(target_path.relative_to(base_path))
        except ValueError:
            # base에 포함되지 않으면 phase2_data 기준으로
            phase2_data = self.script_dir / "phase2_data"
            try:
                rel_path = str(target_path.relative_to(phase2_data))
                # real_photos가 이미 포함되어 있으면 그대로 반환
                if rel_path.startswith('real_photos'):
                    return rel_path
                # 아니면 real_photos를 추가
                return f"real_photos/{rel_path}" if rel_path else "real_photos"
            except ValueError:
                # 그것도 안되면 절대 경로에서 phase2_data 이후 부분 추출
                target_str = str(target_path)
                phase2_str = str(phase2_data)
                if phase2_str in target_str:
                    idx = target_str.index(phase2_str) + len(phase2_str)
                    rel = target_str[idx:].lstrip('\\/')
                    return rel if rel else target_path.name
                return target_path.name
    
    def log(self, message: str, level: str = "INFO"):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{timestamp}] [{level}] {message}\n")
        self.log_text.see('end')
        self.root.update_idletasks()
    
    def browse_labels_file(self):
        """labels.json 파일 선택"""
        path = filedialog.askopenfilename(
            title="labels.json 선택",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.labels_path_var.set(path)
            self.load_samples()
    
    def browse_output_folder(self):
        """출력 폴더 선택"""
        path = filedialog.askdirectory(title="출력 폴더 선택")
        if path:
            self.output_path_var.set(path)
    
    def load_samples(self):
        """labels.json 로드"""
        labels_path = Path(self.labels_path_var.get())
        
        if not labels_path.exists():
            # real_photos 안에 있을 수도 있음
            alternative_path = labels_path.parent / "real_photos" / "labels.json"
            if alternative_path.exists():
                labels_path = alternative_path
                self.labels_path_var.set(str(labels_path))
            else:
                messagebox.showerror("오류", f"labels.json을 찾을 수 없습니다:\n{labels_path}")
                return
        
        try:
            self.samples = load_labels(labels_path)
            self.labels_path = labels_path
            self.sample_info_label.config(text=f"✓ {len(self.samples)}개 샘플 로드 완료")
            self.log(f"{len(self.samples)}개 샘플 로드 완료")
        except Exception as e:
            messagebox.showerror("오류", f"labels.json 로드 실패: {e}")
            self.log(f"로드 실패: {e}", "ERROR")
    
    def start_generation(self):
        """자동 생성 시작"""
        if self.is_generating:
            messagebox.showwarning("경고", "이미 생성 중입니다.")
            return
        
        if not self.samples:
            messagebox.showwarning("경고", "먼저 labels.json을 로드하세요.")
            return
        
        # 스레드에서 실행
        self.is_generating = True
        self.generate_button.config(state='disabled')
        thread = threading.Thread(target=self.generate_pairs_thread, daemon=True)
        thread.start()
    
    def stop_generation(self):
        """생성 중지"""
        self.is_generating = False
        self.log("생성 중지 요청...")
    
    def generate_pairs_thread(self):
        """pair 생성 스레드"""
        try:
            self.use_v2_extractor = self.v2_extractor_var.get()
            output_root = Path(self.output_path_var.get())
            split_ratio = self.split_var.get()
            
            # 출력 폴더 생성
            for subset in ["train", "test"]:
                (output_root / subset / "input").mkdir(parents=True, exist_ok=True)
                (output_root / subset / "target").mkdir(parents=True, exist_ok=True)
            
            # 샘플 분리
            import random
            random.seed(42)
            shuffled = list(self.samples)
            random.shuffle(shuffled)
            
            total = len(shuffled)
            train_count = int(total * split_ratio)
            train_samples = shuffled[:train_count]
            test_samples = shuffled[train_count:]
            
            self.log(f"총 {total}개 → train {len(train_samples)}개, test {len(test_samples)}개")
            
            # 메타데이터
            metadata = {}
            pair_id = 0
            
            # Train 생성
            self.log("Train 세트 생성 시작...")
            for s in train_samples:
                if not self.is_generating:
                    break
                pair_id += 1
                self.generate_single_pair(s, "train", pair_id, output_root, metadata)
            
            # Test 생성
            if self.is_generating:
                self.log("Test 세트 생성 시작...")
                for s in test_samples:
                    if not self.is_generating:
                        break
                    pair_id += 1
                    self.generate_single_pair(s, "test", pair_id, output_root, metadata)
            
            # 메타데이터 저장
            if self.is_generating:
                meta_path = output_root / "pairs_metadata.json"
                with meta_path.open("w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                
                self.generated_pairs = metadata
                self.log(f"완료! 총 {len(metadata)}개 pair 생성")
                messagebox.showinfo("완료", f"생성 완료!\n총 {len(metadata)}개 pair")
                
                # 결과 확인 탭 새로고침
                self.root.after(0, self.refresh_review)
                self.root.after(0, self.update_stats)
        
        except Exception as e:
            self.log(f"오류 발생: {e}", "ERROR")
            messagebox.showerror("오류", f"생성 중 오류 발생:\n{e}")
        finally:
            self.is_generating = False
            self.root.after(0, lambda: self.generate_button.config(state='normal'))
    
    def generate_single_pair(self, sample: Dict, subset: str, pair_id: int, output_root: Path, metadata: Dict):
        """단일 pair 생성"""
        pair_id_str = f"{pair_id:04d}"
        sign_type_key = sample.get("sign_type_key") or sample.get("sign_type")
        time_key = sample.get("time", "day")
        real_rel = sample.get("real_photo")
        
        if not real_rel:
            self.log(f"[{pair_id_str}] real_photo 없음, 스킵", "WARN")
            return
        
        # 경로 해석: real_rel이 이미 real_photos로 시작하는지 확인
        real_rel_str = str(real_rel).replace('\\', '/')  # Windows 경로 정규화
        labels_parent = self.labels_path.parent
        phase2_data = self.script_dir / "phase2_data"
        real_photos_dir = phase2_data / "real_photos"
        
        # 실제 파일 구조: phase2_data/real_photos/real_photos/...
        # real_rel이 real_photos로 시작하면, phase2_data/real_photos/real_photos/... 형태로 경로 생성
        if real_rel_str.startswith('real_photos'):
            # real_photos/real_photos/... 형태로 경로 생성
            # Windows 경로 구분자를 처리하기 위해 Path 객체로 변환
            real_rel_path = Path(real_rel)  # Windows 경로도 자동 처리됨
            real_path = (real_photos_dir / real_rel_path).resolve()
        else:
            # real_photos 없이 시작하는 경우 (상대 경로)
            # labels_path.parent 기준으로 경로 생성
            real_path = (labels_parent / real_rel).resolve()
        
        # 파일이 없으면 대체 경로 시도
        if not real_path.exists():
            # phase2_data/real_photos/real_photos에서 직접 찾기
            if real_rel_str.startswith('real_photos'):
                # real_photos 이후 부분 추출
                parts = Path(real_rel).parts
                if 'real_photos' in parts:
                    idx = list(parts).index('real_photos')
                    rel_part = Path(*parts[idx+1:])  # real_photos 이후 부분
                    real_path = (real_photos_dir / "real_photos" / rel_part).resolve()
                else:
                    # real_photos가 없으면 그냥 real_photos/real_photos/real_rel
                    real_path = (real_photos_dir / "real_photos" / real_rel).resolve()
            else:
                # 파일명으로 검색
                filename = Path(real_rel).name
                found_files = list(real_photos_dir.rglob(filename))
                if found_files:
                    real_path = found_files[0].resolve()
            
            if not real_path.exists():
                self.log(f"[{pair_id_str}] 실제 사진 없음: {real_path} (원본 경로: {real_rel})", "WARN")
                return
        
        # 진행률 업데이트
        progress = (pair_id / len(self.samples)) * 100
        self.root.after(0, lambda: self.progress_var.set(progress))
        self.root.after(0, lambda: self.progress_label.config(text=f"진행: {pair_id}/{len(self.samples)} ({progress:.1f}%) - {real_path.name}"))
        
        self.log(f"[{subset.upper()}] [{pair_id_str}] {real_path.name}")
        
        # 실제 이미지 로드
        real_img = cv2.imread(str(real_path))
        if real_img is None:
            self.log(f"  실제 사진 로드 실패, 스킵", "WARN")
            return
        
        # 색상 추출
        try:
            if self.use_v2_extractor:
                bg_hex, text_hex = extract_colors_v2(real_path)
            else:
                bg_hex, text_hex = extract_colors(real_path)
            self.log(f"  색상: bg={bg_hex}, text={text_hex}")
        except Exception as e:
            self.log(f"  색상 추출 실패, 기본값 사용: {e}", "WARN")
            bg_hex, text_hex = "#6b2d8f", "#ffffff"
        
        # Phase1 생성
        try:
            phase1_img = generate_phase1_image(
                text="간판",
                sign_type_key=sign_type_key,
                bg_color=bg_hex,
                text_color=text_hex,
                width=512,
                height=512,
            )
        except Exception as e:
            self.log(f"  Phase1 생성 실패, 스킵: {e}", "ERROR")
            return
        
        # 전처리
        real_cropped = center_crop_and_resize(real_img, size=512)
        phase1_cropped = center_crop_and_resize(phase1_img, size=512)
        
        # 저장
        subset_dir = output_root / subset
        input_path = subset_dir / "input" / f"{pair_id_str}.png"
        target_path = subset_dir / "target" / f"{pair_id_str}.jpg"
        
        cv2.imwrite(str(input_path), phase1_cropped)
        cv2.imwrite(str(target_path), real_cropped)
        
        self.log(f"  저장: {input_path.name}, {target_path.name}")
        
        # 메타데이터 기록
        metadata[pair_id_str] = {
            "sign_type_key": sign_type_key,
            "sign_type": sample.get("sign_type"),
            "installation_type": sample.get("installation_type"),
            "time": time_key,
            "bg_color": bg_hex,
            "text_color": text_hex,
            "real_photo": self._get_relative_path(real_path, self.labels_path.parent),
            "phase1_input": str(input_path.relative_to(output_root)),
            "phase1_target": str(target_path.relative_to(output_root)),
            "subset": subset,
            "status": "ok",  # ok, problem
        }
    
    def refresh_review(self):
        """결과 확인 탭 새로고침"""
        # 기존 위젯 삭제
        for widget in self.review_grid_frame.winfo_children():
            widget.destroy()
        
        if not self.generated_pairs:
            self.review_status_label.config(text="생성된 pair가 없습니다.")
            return
        
        # 필터 적용
        filter_type = self.filter_var.get()
        filtered_pairs = self.generated_pairs.copy()
        if filter_type == "문제":
            filtered_pairs = {k: v for k, v in filtered_pairs.items() if v.get("status") == "problem"}
        elif filter_type == "정상":
            filtered_pairs = {k: v for k, v in filtered_pairs.items() if v.get("status") == "ok"}
        
        if not filtered_pairs:
            self.review_status_label.config(text=f"필터링 결과: 0개 pair")
            return
        
        self.review_status_label.config(text=f"총 {len(filtered_pairs)}개 pair")
        
        # 그리드 생성 (4열)
        cols = 4
        row = 0
        col = 0
        
        for pair_id, meta in sorted(filtered_pairs.items()):
            # 썸네일 프레임
            thumb_frame = ttk.Frame(self.review_grid_frame, relief='ridge', borderwidth=2)
            thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            
            # 상태 표시
            status = meta.get("status", "ok")
            status_color = "#ffcccc" if status == "problem" else "#ccffcc"
            thumb_frame.configure(style="Thumb.TFrame")
            
            # 썸네일 이미지 (나중에 구현)
            ttk.Label(thumb_frame, text=f"{pair_id}", font=('맑은 고딕', 10, 'bold')).pack(pady=5)
            ttk.Label(thumb_frame, text=f"{meta.get('sign_type_key', 'N/A')}", font=('맑은 고딕', 8)).pack()
            ttk.Label(thumb_frame, text=f"bg: {meta.get('bg_color', 'N/A')}", font=('맑은 고딕', 7)).pack()
            
            # 클릭 이벤트
            def on_thumb_click(p_id=pair_id):
                self.current_pair_id = p_id
                self.current_pair_index = list(sorted(filtered_pairs.keys())).index(p_id)
                self.notebook.select(2)  # 수동 보정 탭으로 이동
                self.load_pair_for_fix()
            
            thumb_frame.bind("<Button-1>", lambda e, p_id=pair_id: on_thumb_click(p_id))
            for child in thumb_frame.winfo_children():
                child.bind("<Button-1>", lambda e, p_id=pair_id: on_thumb_click(p_id))
            
            col += 1
            if col >= cols:
                col = 0
                row += 1
        
        # 그리드 열 설정
        for i in range(cols):
            self.review_grid_frame.columnconfigure(i, weight=1)
    
    def _on_canvas_configure(self, event):
        """캔버스 크기 변경 시 그리드 프레임 너비 조정"""
        canvas_width = event.width
        self.review_canvas.itemconfig(self.review_canvas_window, width=canvas_width)
    
    def load_pair_for_fix(self):
        """수동 보정을 위한 pair 로드"""
        if not self.current_pair_id or self.current_pair_id not in self.generated_pairs:
            return
        
        meta = self.generated_pairs[self.current_pair_id]
        output_root = Path(self.output_path_var.get())
        
        # 이미지 로드
        target_path = output_root / meta["phase1_target"]
        input_path = output_root / meta["phase1_input"]
        
        if target_path.exists():
            target_img = Image.open(target_path)
            target_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            target_photo = ImageTk.PhotoImage(target_img)
            self.target_label.configure(image=target_photo, text="")
            self.target_label.image = target_photo
        
        if input_path.exists():
            input_img = Image.open(input_path)
            input_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            input_photo = ImageTk.PhotoImage(input_img)
            self.input_label.configure(image=input_photo, text="")
            self.input_label.image = input_photo
        
        # 색상 설정
        self.bg_color_var.set(meta.get("bg_color", "#6b2d8f"))
        self.text_color_var.set(meta.get("text_color", "#ffffff"))
        
        # 정보 업데이트
        total_pairs = len(self.generated_pairs)
        current_idx = list(sorted(self.generated_pairs.keys())).index(self.current_pair_id) + 1
        self.pair_info_label.config(text=f"Pair {self.current_pair_id} ({current_idx}/{total_pairs})")
    
    def prev_pair(self):
        """이전 pair"""
        if not self.generated_pairs:
            return
        
        sorted_ids = sorted(self.generated_pairs.keys())
        if self.current_pair_id:
            try:
                idx = sorted_ids.index(self.current_pair_id)
                if idx > 0:
                    self.current_pair_id = sorted_ids[idx - 1]
                    self.current_pair_index = idx - 1
            except ValueError:
                self.current_pair_id = sorted_ids[0]
        else:
            self.current_pair_id = sorted_ids[0]
        
        self.load_pair_for_fix()
    
    def next_pair(self):
        """다음 pair"""
        if not self.generated_pairs:
            return
        
        sorted_ids = sorted(self.generated_pairs.keys())
        if self.current_pair_id:
            try:
                idx = sorted_ids.index(self.current_pair_id)
                if idx < len(sorted_ids) - 1:
                    self.current_pair_id = sorted_ids[idx + 1]
                    self.current_pair_index = idx + 1
            except ValueError:
                self.current_pair_id = sorted_ids[0]
        else:
            self.current_pair_id = sorted_ids[0]
        
        self.load_pair_for_fix()
    
    def choose_color(self, color_type: str):
        """색상 선택"""
        current_color = self.bg_color_var.get() if color_type == 'bg' else self.text_color_var.get()
        
        # hex를 RGB로 변환
        if current_color.startswith('#'):
            rgb = tuple(int(current_color[i:i+2], 16) for i in (1, 3, 5))
        else:
            rgb = (107, 45, 143) if color_type == 'bg' else (255, 255, 255)
        
        color = colorchooser.askcolor(color=rgb, title=f"{'배경' if color_type == 'bg' else '텍스트'} 색상 선택")
        if color[1]:  # color[1]은 hex 값
            if color_type == 'bg':
                self.bg_color_var.set(color[1])
            else:
                self.text_color_var.set(color[1])
    
    def extract_from_target(self):
        """Target 이미지에서 색상 추출"""
        if not self.current_pair_id:
            return
        
        meta = self.generated_pairs[self.current_pair_id]
        output_root = Path(self.output_path_var.get())
        target_path = output_root / meta["phase1_target"]
        
        try:
            if self.use_v2_extractor:
                bg_hex, text_hex = extract_colors_v2(target_path)
            else:
                bg_hex, text_hex = extract_colors(target_path)
            
            self.bg_color_var.set(bg_hex)
            self.text_color_var.set(text_hex)
            self.log(f"Target에서 색상 추출: bg={bg_hex}, text={text_hex}")
        except Exception as e:
            messagebox.showerror("오류", f"색상 추출 실패: {e}")
    
    def regenerate_current_pair(self):
        """현재 pair 재생성"""
        if not self.current_pair_id:
            return
        
        meta = self.generated_pairs[self.current_pair_id]
        output_root = Path(self.output_path_var.get())
        sign_type_key = meta["sign_type_key"]
        bg_hex = self.bg_color_var.get()
        text_hex = self.text_color_var.get()
        
        try:
            # Phase1 재생성
            phase1_img = generate_phase1_image(
                text="간판",
                sign_type_key=sign_type_key,
                bg_color=bg_hex,
                text_color=text_hex,
                width=512,
                height=512,
            )
            
            phase1_cropped = center_crop_and_resize(phase1_img, size=512)
            input_path = output_root / meta["phase1_input"]
            cv2.imwrite(str(input_path), phase1_cropped)
            
            # 메타데이터 업데이트
            meta["bg_color"] = bg_hex
            meta["text_color"] = text_hex
            
            # 메타데이터 파일 저장
            meta_path = output_root / "pairs_metadata.json"
            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(self.generated_pairs, f, ensure_ascii=False, indent=2)
            
            # 이미지 다시 로드
            self.load_pair_for_fix()
            self.log(f"Pair {self.current_pair_id} 재생성 완료")
            messagebox.showinfo("완료", "재생성 완료!")
        except Exception as e:
            messagebox.showerror("오류", f"재생성 실패: {e}")
    
    def save_current_pair(self):
        """현재 pair 저장 (색상만 업데이트)"""
        if not self.current_pair_id:
            return
        
        meta = self.generated_pairs[self.current_pair_id]
        meta["bg_color"] = self.bg_color_var.get()
        meta["text_color"] = self.text_color_var.get()
        
        # 메타데이터 파일 저장
        output_root = Path(self.output_path_var.get())
        meta_path = output_root / "pairs_metadata.json"
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(self.generated_pairs, f, ensure_ascii=False, indent=2)
        
        self.log(f"Pair {self.current_pair_id} 색상 저장 완료")
    
    def mark_ok_and_next(self):
        """괜찮음 표시하고 다음으로"""
        if self.current_pair_id:
            self.generated_pairs[self.current_pair_id]["status"] = "ok"
            self.save_current_pair()
        self.next_pair()
    
    def mark_problem(self):
        """문제있음 표시"""
        if self.current_pair_id:
            self.generated_pairs[self.current_pair_id]["status"] = "problem"
            self.save_current_pair()
            messagebox.showinfo("완료", "문제있음으로 표시했습니다.")
    
    def zoom_image(self, img_type: str):
        """이미지 확대 보기"""
        # TODO: 새 창에서 확대 이미지 표시
        messagebox.showinfo("확대", "확대 기능은 구현 예정입니다.")
    
    def update_stats(self):
        """통계 업데이트"""
        if not self.generated_pairs:
            self.stats_label.config(text="통계 데이터가 없습니다.")
            return
        
        total = len(self.generated_pairs)
        ok_count = sum(1 for v in self.generated_pairs.values() if v.get("status") == "ok")
        problem_count = sum(1 for v in self.generated_pairs.values() if v.get("status") == "problem")
        
        stats_text = f"""
총 Pair 수: {total}

상태별:
  ✓ 정상: {ok_count} ({ok_count/total*100:.1f}%)
  ⚠️ 문제: {problem_count} ({problem_count/total*100:.1f}%)

타입별 분포:
"""
        # 타입별 집계
        type_counts = {}
        for meta in self.generated_pairs.values():
            st_key = meta.get("sign_type_key", "unknown")
            type_counts[st_key] = type_counts.get(st_key, 0) + 1
        
        for st_key, count in sorted(type_counts.items()):
            stats_text += f"  {st_key}: {count}\n"
        
        self.stats_label.config(text=stats_text, justify='left')
    
    def run(self):
        """GUI 실행"""
        self.root.mainloop()


def main():
    """메인 함수"""
    app = PairGeneratorGUI()
    app.run()


if __name__ == "__main__":
    main()

