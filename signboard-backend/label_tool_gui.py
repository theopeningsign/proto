"""
간판 사진 라벨링 도구 (GUI 버전)

사용법:
    python label_tool_gui.py --input real_photos/unlabeled/
    python label_tool_gui.py --input real_photos/unlabeled/ --labels labels.json

기능:
    - GUI로 사진을 보여주고 버튼/키보드로 분류
    - 자동으로 해당 폴더로 이동
    - labels.json에 메타데이터 저장
"""

import os
import json
import shutil
import argparse
import sys
import traceback
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np

# OCR 라이브러리 (선택사항)
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# 디버깅을 위한 간단한 로깅 함수
def log_error(error_msg, exc_info=None):
    """에러를 콘솔과 파일에 기록"""
    print(f"[ERROR] {error_msg}", file=sys.stderr)
    if exc_info:
        traceback.print_exception(*exc_info, file=sys.stderr)

# 간판 타입 매핑
SIGN_TYPES = {
    '1': 'channel',
    '2': 'scasi',
    '3': 'flex_basic',  # 기본 플렉스 (LED 없음)
    '4': 'flex_led'     # LED 플렉스 (LED 백라이트)
}

# 설치 방법 매핑
INSTALLATION_TYPES = {
    'w': 'wall',
    'b': 'frame_bar',
    'p': 'frame_plate'
}

# 플렉스는 항상 frame_plate
FLEX_INSTALLATION = 'frame_plate'

# 시간대 매핑
TIME_TYPES = {
    'd': 'day',
    'n': 'night'
}

# 채널 타입 매핑 (전광/후광/전후광)
CHANNEL_TYPES = {
    'f': 'front',  # 전광
    'h': 'back',   # 후광 (h = 후광의 후)
    'b': 'both'    # 전후광 (b = both의 첫글자)
}

# 타입 한글명
SIGN_TYPE_NAMES = {
    'channel': '채널',
    'scasi': '스카시',
    'flex_basic': '플렉스 기본',
    'flex_led': '플렉스 LED'
}

CHANNEL_TYPE_NAMES = {
    'front': '전광',
    'back': '후광',
    'both': '전후광'
}

INSTALLATION_TYPE_NAMES = {
    'wall': '맨벽',
    'frame_bar': '프레임바',
    'frame_plate': '프레임판'
}

TIME_TYPE_NAMES = {
    'day': '주간',
    'night': '야간'
}


class LabelingToolGUI:
    def __init__(self, input_dir, labels_file=None, output_base=None):
        """
        라벨링 도구 GUI 초기화
        
        Args:
            input_dir: 라벨링할 사진이 있는 폴더
            labels_file: labels.json 파일 경로 (없으면 자동 생성)
            output_base: 출력 기본 폴더 (없으면 input_dir의 상위 폴더)
        """
        self.input_dir = Path(input_dir)
        # output_base가 없으면 phase2_data로 설정
        if output_base:
            self.output_base = Path(output_base)
        else:
            # input_dir이 phase2_data 하위에 있으면 phase2_data를 찾음
            script_dir = Path(__file__).parent
            phase2_data = script_dir / "phase2_data"
            # input_dir이 phase2_data 하위에 있는지 확인 (Path 객체로 변환 후 확인)
            try:
                self.input_dir.relative_to(phase2_data)
                self.output_base = phase2_data
            except ValueError:
                # phase2_data 하위가 아니면 input_dir.parent 사용
                self.output_base = self.input_dir.parent
        
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
        
        # 선택 상태
        self.selected_sign_type = None
        self.selected_channel_type = None  # 전광/후광 (채널 선택 시만 사용)
        self.selected_installation_type = None
        self.selected_time_type = None
        self.selected_lights_enabled = None  # 조명 켜짐/꺼짐 (채널 간판만)
        
        # 크롭 관련 상태
        self.current_image = None  # 원본 PIL Image
        self.display_image = None  # 표시용 PIL Image (리사이즈됨)
        self.display_scale = 1.0  # 원본 대비 표시 스케일
        self.crop_start = None  # 크롭 시작 좌표 (canvas 좌표)
        self.crop_end = None  # 크롭 종료 좌표 (canvas 좌표)
        self.crop_rect = None  # Canvas의 사각형 ID
        self.cropped_photo_path = None  # 크롭된 이미지 경로
        self.crop_region = None  # 원본 이미지 기준 크롭 영역 (x, y, width, height)
        self.text_input = ""  # 입력된 텍스트
        
        # cropped_photos 디렉토리
        self.cropped_photos_dir = self.output_base / "cropped_photos"
        self.cropped_photos_dir.mkdir(parents=True, exist_ok=True)
        
        # GUI 초기화
        self.setup_gui()
        
        # 첫 이미지 로드
        if self.image_files:
            self.load_current_image()
        else:
            messagebox.showwarning("경고", f"{self.input_dir}에 이미지 파일이 없습니다.")
            self.root.quit()
    
    def load_labels(self):
        """labels.json 로드 및 구조 마이그레이션"""
        # 기본 구조 정의 (전광/후광/전후광 구분)
        default_structure = {
            # 전광채널
            "channel_front_wall": {"day": [], "night": []},
            "channel_front_frame_bar": {"day": [], "night": []},
            "channel_front_frame_plate": {"day": [], "night": []},
            # 후광채널
            "channel_back_wall": {"day": [], "night": []},
            "channel_back_frame_bar": {"day": [], "night": []},
            "channel_back_frame_plate": {"day": [], "night": []},
            # 전후광채널
            "channel_front_back_wall": {"day": [], "night": []},
            "channel_front_back_frame_bar": {"day": [], "night": []},
            "channel_front_back_frame_plate": {"day": [], "night": []},
            # 스카시
            "scasi_wall": {"day": [], "night": []},
            "scasi_frame_bar": {"day": [], "night": []},
            "scasi_frame_plate": {"day": [], "night": []},
            # 플렉스
            "flex_frame_plate": {"day": [], "night": []}
        }
        
        if self.labels_file.exists():
            with open(self.labels_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            
            # 새 구조로 마이그레이션
            migrated = default_structure.copy()
            
            # 기존 데이터를 새 구조로 복사
            for key in default_structure:
                if key in loaded:
                    migrated[key] = loaded[key]
            
            # 기존 구조(이전 버전)에서 데이터 마이그레이션 (하위 호환성)
            # 기존 "channel_wall" 등을 "channel_front_wall"로 마이그레이션 (기본값: 전광)
            old_to_new = {
                "channel": "channel_front_wall",  # 기본값으로 전광 wall 사용
                "channel_wall": "channel_front_wall",
                "channel_frame_bar": "channel_front_frame_bar",
                "channel_frame_plate": "channel_front_frame_plate",
                "scasi": "scasi_wall",
                "flex": "flex_frame_plate"
            }
            
            for old_key, default_new_key in old_to_new.items():
                if old_key in loaded and old_key not in migrated:
                    # 기존 데이터를 기본 키로 복사
                    if isinstance(loaded[old_key], dict):
                        for time_key in ["day", "night"]:
                            if time_key in loaded[old_key] and isinstance(loaded[old_key][time_key], list):
                                migrated[default_new_key][time_key].extend(loaded[old_key][time_key])
            
            return migrated
        else:
            return default_structure.copy()
    
    def save_labels(self):
        """labels.json 저장"""
        self.labels_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.labels_file, 'w', encoding='utf-8') as f:
            json.dump(self.labels, f, ensure_ascii=False, indent=2)
    
    def get_image_files(self):
        """이미지 파일 목록 가져오기 (중복 제거)"""
        extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
        files_set = set()  # 중복 제거를 위해 set 사용
        
        for ext in extensions:
            found_files = list(self.input_dir.glob(f'*{ext}'))
            # 파일이 실제로 존재하는지 확인하고 추가
            for file_path in found_files:
                if file_path.exists() and file_path.is_file():
                    files_set.add(file_path)
        
        # 정렬된 리스트로 반환
        return sorted(list(files_set))
    
    def setup_gui(self):
        """GUI 설정"""
        self.root = tk.Tk()
        self.root.title("간판 사진 라벨링 도구")
        self.root.geometry("1200x1000")
        self.root.configure(bg='#1e1e1e')
        
        # 키보드 단축키 바인딩 (텍스트 입력란에 포커스가 없을 때만 작동)
        def check_focus_and_call(func, *args):
            """텍스트 입력란에 포커스가 없을 때만 함수 호출"""
            focused_widget = self.root.focus_get()
            # Entry 위젯에 포커스가 있으면 단축키 무시
            if isinstance(focused_widget, tk.Entry):
                return
            return func(*args)
        
        # 키보드 단축키: 건너뛰기, 되돌리기만 유지
        self.root.bind('<Key-s>', lambda e: check_focus_and_call(self.skip_image))
        self.root.bind('<Key-S>', lambda e: check_focus_and_call(self.skip_image))
        self.root.bind('<Key-z>', lambda e: check_focus_and_call(self.undo_last))
        self.root.bind('<Key-Z>', lambda e: check_focus_and_call(self.undo_last))
        # Escape 키로 텍스트 입력란에서 포커스 해제
        self.root.bind('<Escape>', lambda e: self.root.focus_set())
        self.root.focus_set()
        
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 상단: 진행상황 및 통계
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        top_frame.columnconfigure(1, weight=1)
        
        # 진행상황
        progress = (self.current_index / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        self.progress_label = ttk.Label(
            top_frame,
            text=f"진행: {self.current_index + 1}/{self.stats['total']} ({progress:.1f}%)",
            font=('맑은 고딕', 12, 'bold')
        )
        self.progress_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        
        # 통계
        self.stats_label = ttk.Label(
            top_frame,
            text=f"라벨링: {self.stats['labeled']} | 건너뛰기: {self.stats['skipped']}",
            font=('맑은 고딕', 10)
        )
        self.stats_label.grid(row=0, column=1, sticky=tk.E)
        
        # 중앙: 이미지 및 컨트롤
        center_frame = ttk.Frame(main_frame)
        center_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        center_frame.columnconfigure(0, weight=2)
        center_frame.columnconfigure(1, weight=1)
        
        # 왼쪽: 이미지 표시 (Canvas 사용)
        image_frame = ttk.LabelFrame(center_frame, text="이미지 (드래그로 간판 영역 선택)", padding="10")
        image_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)
        
        # Canvas 생성
        canvas_frame = ttk.Frame(image_frame)
        canvas_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(
            canvas_frame,
            bg='#1e1e1e',
            highlightthickness=1,
            highlightbackground='#555555'
        )
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 스크롤바 (필요시)
        scrollbar_v = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar_h = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        # 마우스 이벤트 바인딩
        self.canvas.bind("<Button-1>", self.on_crop_start)
        self.canvas.bind("<B1-Motion>", self.on_crop_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_crop_end)
        
        # 파일 정보
        self.file_info_label = ttk.Label(
            image_frame,
            text="",
            font=('맑은 고딕', 9),
            foreground='gray'
        )
        self.file_info_label.grid(row=1, column=0, pady=(10, 0))
        
        # 크롭 영역 정보
        self.crop_info_label = ttk.Label(
            image_frame,
            text="마우스로 드래그하여 간판 영역을 선택하세요",
            font=('맑은 고딕', 9),
            foreground='#4CAF50'
        )
        self.crop_info_label.grid(row=2, column=0, pady=(5, 0))
        
        # 오른쪽: 컨트롤 패널
        control_frame = ttk.LabelFrame(center_frame, text="분류", padding="10")
        control_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        # 컨트롤 패널 클릭 시 포커스를 root로 이동 (단축키 사용 가능하도록)
        control_frame.bind("<Button-1>", lambda e: self.root.focus_set())
        
        # 간판 타입 선택
        type_label = ttk.Label(control_frame, text="간판 타입:", font=('맑은 고딕', 11, 'bold'))
        type_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        self.sign_type_buttons = {}
        for i, (key, sign_type) in enumerate(SIGN_TYPES.items()):
            btn = tk.Button(
                control_frame,
                text=f"[{key}] {SIGN_TYPE_NAMES[sign_type]}",
                font=('맑은 고딕', 12),
                bg='#2d2d2d',
                fg='white',
                activebackground='#3d3d3d',
                activeforeground='white',
                relief=tk.RAISED,
                bd=2,
                padx=20,
                pady=10,
                command=lambda k=key: self.select_sign_type(k)
            )
            btn.grid(row=1, column=i, padx=5, pady=5, sticky=(tk.W, tk.E))
            self.sign_type_buttons[key] = btn
        
        # 선택된 타입 표시
        self.selected_type_label = ttk.Label(
            control_frame,
            text="",
            font=('맑은 고딕', 10),
            foreground='#4CAF50'
        )
        self.selected_type_label.grid(row=2, column=0, columnspan=3, pady=(5, 10))
        
        # 채널 타입 선택 (전광/후광) - 채널 선택 시에만 표시
        channel_type_label = ttk.Label(control_frame, text="채널 타입:", font=('맑은 고딕', 11, 'bold'))
        channel_type_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        self.channel_type_buttons = {}
        for i, (key, channel_type) in enumerate(CHANNEL_TYPES.items()):
            btn = tk.Button(
                control_frame,
                text=f"[{key.upper()}] {CHANNEL_TYPE_NAMES[channel_type]}",
                font=('맑은 고딕', 12),
                bg='#2d2d2d',
                fg='white',
                activebackground='#3d3d3d',
                activeforeground='white',
                relief=tk.RAISED,
                bd=2,
                padx=20,
                pady=10,
                command=lambda k=key: self.select_channel_type(k),
                state=tk.DISABLED
            )
            btn.grid(row=4, column=i, padx=5, pady=5, sticky=(tk.W, tk.E))
            self.channel_type_buttons[key] = btn
        
        # 선택된 채널 타입 표시
        self.selected_channel_label = ttk.Label(
            control_frame,
            text="",
            font=('맑은 고딕', 10),
            foreground='#FF9800'
        )
        self.selected_channel_label.grid(row=5, column=0, columnspan=3, pady=(5, 20))
        
        # 설치 방법 선택
        install_label = ttk.Label(control_frame, text="설치 방법:", font=('맑은 고딕', 11, 'bold'))
        install_label.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        self.installation_type_buttons = {}
        for i, (key, install_type) in enumerate(INSTALLATION_TYPES.items()):
            btn = tk.Button(
                control_frame,
                text=f"[{key.upper()}] {INSTALLATION_TYPE_NAMES[install_type]}",
                font=('맑은 고딕', 12),
                bg='#2d2d2d',
                fg='white',
                activebackground='#3d3d3d',
                activeforeground='white',
                relief=tk.RAISED,
                bd=2,
                padx=15,
                pady=10,
                command=lambda k=key: self.select_installation_type(k),
                state=tk.DISABLED
            )
            btn.grid(row=7, column=i, padx=5, pady=5, sticky=(tk.W, tk.E))
            self.installation_type_buttons[key] = btn
        
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)
        
        # 설치 방법 선택 표시
        self.selected_install_label = ttk.Label(
            control_frame,
            text="",
            font=('맑은 고딕', 10),
            foreground='#2196F3'
        )
        self.selected_install_label.grid(row=8, column=0, columnspan=3, pady=(5, 20))
        
        # 시간대 선택
        time_label = ttk.Label(control_frame, text="시간대:", font=('맑은 고딕', 11, 'bold'))
        time_label.grid(row=9, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        self.time_type_buttons = {}
        for i, (key, time_type) in enumerate(TIME_TYPES.items()):
            btn = tk.Button(
                control_frame,
                text=f"[{key.upper()}] {TIME_TYPE_NAMES[time_type]}",
                font=('맑은 고딕', 12),
                bg='#2d2d2d',
                fg='white',
                activebackground='#3d3d3d',
                activeforeground='white',
                relief=tk.RAISED,
                bd=2,
                padx=30,
                pady=10,
                command=lambda k=key: self.select_time_type(k),
                state=tk.DISABLED
            )
            btn.grid(row=10, column=i, padx=5, pady=5, sticky=(tk.W, tk.E))
            self.time_type_buttons[key] = btn
        
        # 조명 선택 (채널 간판만)
        lights_label = ttk.Label(control_frame, text="조명:", font=('맑은 고딕', 11, 'bold'))
        lights_label.grid(row=11, column=0, columnspan=3, sticky=tk.W, pady=(20, 10))
        
        self.lights_buttons = {}
        lights_options = {
            'o': True,   # On (켜짐)
            'x': False   # Off (꺼짐)
        }
        lights_names = {
            True: '켜짐',
            False: '꺼짐'
        }
        for i, (key, lights_value) in enumerate(lights_options.items()):
            btn = tk.Button(
                control_frame,
                text=f"[{key.upper()}] {lights_names[lights_value]}",
                font=('맑은 고딕', 12),
                bg='#2d2d2d',
                fg='white',
                activebackground='#3d3d3d',
                activeforeground='white',
                relief=tk.RAISED,
                bd=2,
                padx=30,
                pady=10,
                command=lambda k=key: self.select_lights(k),
                state=tk.DISABLED
            )
            btn.grid(row=12, column=i, padx=5, pady=5, sticky=(tk.W, tk.E))
            self.lights_buttons[key] = btn
        
        # 선택된 조명 상태 표시
        self.selected_lights_label = ttk.Label(
            control_frame,
            text="",
            font=('맑은 고딕', 10),
            foreground='#9C27B0'
        )
        self.selected_lights_label.grid(row=13, column=0, columnspan=3, pady=(5, 20))
        
        # 간판 텍스트 입력 섹션
        text_label = ttk.Label(control_frame, text="간판 텍스트:", font=('맑은 고딕', 11, 'bold'))
        text_label.grid(row=14, column=0, columnspan=3, sticky=tk.W, pady=(20, 5))
        
        text_input_frame = ttk.Frame(control_frame)
        text_input_frame.grid(row=15, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))
        text_input_frame.columnconfigure(0, weight=1)
        
        self.text_entry = ttk.Entry(text_input_frame, font=('맑은 고딕', 11))
        self.text_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.text_entry.bind('<KeyRelease>', self.on_text_changed)
        
        # OCR 버튼 (선택사항)
        self.ocr_button = tk.Button(
            text_input_frame,
            text="OCR",
            font=('맑은 고딕', 9),
            bg='#2196F3',
            fg='white',
            command=self.run_ocr,
            state=tk.DISABLED if not OCR_AVAILABLE else tk.NORMAL
        )
        self.ocr_button.grid(row=0, column=1, padx=5)
        if not OCR_AVAILABLE:
            self.ocr_button.configure(
                text="OCR\n(미설치)",
                bg='#616161',
                state=tk.DISABLED
            )
        
        # 확인 버튼 (타입, 채널타입(채널인 경우), 설치방법, 시간 모두 선택 후)
        self.confirm_button = tk.Button(
            control_frame,
            text="✓ 확인 및 저장",
            font=('맑은 고딕', 12, 'bold'),
            bg='#4CAF50',
            fg='white',
            activebackground='#45a049',
            activeforeground='white',
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=15,
            command=self.confirm_labeling,
            state=tk.DISABLED
        )
        self.confirm_button.grid(row=16, column=0, columnspan=3, pady=(20, 10), sticky=(tk.W, tk.E))
        
        # 기타 버튼
        other_frame = ttk.Frame(control_frame)
        other_frame.grid(row=17, column=0, columnspan=3, pady=(10, 0), sticky=(tk.W, tk.E))
        
        skip_btn = tk.Button(
            other_frame,
            text="[S] 건너뛰기",
            font=('맑은 고딕', 10),
            bg='#ff9800',
            fg='white',
            command=self.skip_image
        )
        skip_btn.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        
        undo_btn = tk.Button(
            other_frame,
            text="[Z] 되돌리기",
            font=('맑은 고딕', 10),
            bg='#f44336',
            fg='white',
            command=self.undo_last
        )
        undo_btn.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        other_frame.columnconfigure(0, weight=1)
        other_frame.columnconfigure(1, weight=1)
        
        # 종료 버튼
        quit_btn = tk.Button(
            control_frame,
            text="[Q] 종료 및 저장",
            font=('맑은 고딕', 10),
            bg='#616161',
            fg='white',
            command=self.quit_app
        )
        quit_btn.grid(row=18, column=0, columnspan=3, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # 하단: 키보드 단축키 안내
        help_frame = ttk.Frame(main_frame)
        help_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        help_text = "키보드 단축키: [S] 건너뛰기 | [Z] 되돌리기 | [ESC] 포커스 해제 | 마우스 드래그로 간판 영역 선택"
        help_label = ttk.Label(
            help_frame,
            text=help_text,
            font=('맑은 고딕', 9),
            foreground='gray'
        )
        help_label.pack()
    
    def load_current_image(self):
        """현재 이미지 로드 및 표시"""
        # 파일 목록 다시 읽기 (파일이 이동되었을 수 있음)
        old_count = len(self.image_files)
        self.image_files = self.get_image_files()
        new_count = len(self.image_files)
        
        # 파일 수가 변경되었으면 인덱스 조정
        if new_count < old_count and self.current_index >= new_count:
            self.current_index = max(0, new_count - 1)
        
        if not self.image_files:
            messagebox.showinfo("완료", "처리할 이미지가 없습니다!")
            self.quit_app()
            return
        
        if self.current_index >= len(self.image_files):
            messagebox.showinfo("완료", "모든 이미지를 처리했습니다!")
            self.quit_app()
            return
        
        image_path = self.image_files[self.current_index]
        
        # 파일이 존재하는지 확인
        if not image_path.exists():
            # 파일 목록에서 제거하고 다음으로
            if image_path in self.image_files:
                self.image_files.remove(image_path)
            messagebox.showwarning("경고", f"파일을 찾을 수 없습니다: {image_path}\n다음 이미지로 넘어갑니다.")
            self.next_image()
            return
        
        try:
            # 원본 이미지 로드
            self.current_image = Image.open(image_path)
            width, height = self.current_image.size
            file_size = os.path.getsize(image_path) / 1024  # KB
            
            # Canvas 크기에 맞게 리사이즈 (표시용)
            canvas_width = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else 800
            canvas_height = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else 600
            
            max_width = min(1200, canvas_width - 20)
            max_height = min(800, canvas_height - 20)
            
            if width > max_width or height > max_height:
                scale = min(max_width / width, max_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                self.display_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.display_scale = scale
            else:
                self.display_image = self.current_image.copy()
                self.display_scale = 1.0
            
            # Canvas에 이미지 표시
            photo = ImageTk.PhotoImage(self.display_image)
            self.canvas.delete("all")  # 기존 이미지 제거
            img_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.canvas.image = photo  # 참조 유지
            # Canvas 크기 업데이트
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox(img_id))
            
            # 크롭 상태 초기화
            self.crop_start = None
            self.crop_end = None
            self.crop_rect = None
            self.cropped_photo_path = None
            self.crop_region = None
            self.text_entry.delete(0, tk.END)
            self.text_input = ""
            
            # 파일 정보 업데이트
            self.file_info_label.configure(
                text=f"파일: {image_path.name} | 크기: {width}x{height}px | 용량: {file_size:.1f} KB"
            )
            self.crop_info_label.configure(
                text="마우스로 드래그하여 간판 영역을 선택하세요"
            )
            
            # 선택 상태 초기화
            self.selected_sign_type = None
            self.selected_channel_type = None
            self.selected_installation_type = None
            self.selected_time_type = None
            self.selected_lights_enabled = None
            self.update_button_states()
            
            # 진행상황 업데이트
            self.update_progress()
            
        except Exception as e:
            messagebox.showerror("오류", f"이미지 로드 실패: {e}\n파일: {image_path}")
            # 파일이 없으면 다음으로, 있으면 재시도
            if not image_path.exists():
                self.next_image()
            else:
                # 파일은 있지만 로드 실패 - 사용자에게 선택권 제공
                retry = messagebox.askyesno("재시도", "이미지 로드에 실패했습니다. 재시도하시겠습니까?")
                if not retry:
                    self.next_image()
    
    def update_button_states(self):
        """버튼 상태 업데이트"""
        # 간판 타입 버튼 색상
        for key, btn in self.sign_type_buttons.items():
            if self.selected_sign_type == key:
                btn.configure(bg='#4CAF50', fg='white')
            else:
                btn.configure(bg='#2d2d2d', fg='white')
        
        # 선택된 타입 표시
        if self.selected_sign_type:
            sign_type = SIGN_TYPES[self.selected_sign_type]
            self.selected_type_label.configure(
                text=f"선택: {SIGN_TYPE_NAMES[sign_type]} 간판"
            )
        else:
            self.selected_type_label.configure(text="")
        
        # 채널 타입 버튼 활성화/비활성화 (채널 선택 시에만)
        is_channel = self.selected_sign_type == '1'
        if is_channel:
            for btn in self.channel_type_buttons.values():
                btn.configure(state=tk.NORMAL)
        else:
            for btn in self.channel_type_buttons.values():
                btn.configure(state=tk.DISABLED)
        
        # 채널 타입 버튼 색상
        for key, btn in self.channel_type_buttons.items():
            if self.selected_channel_type == key:
                btn.configure(bg='#FF9800', fg='white')
            else:
                btn.configure(bg='#2d2d2d', fg='white')
        
        # 선택된 채널 타입 표시
        if self.selected_channel_type:
            channel_type = CHANNEL_TYPES[self.selected_channel_type]
            self.selected_channel_label.configure(
                text=f"채널: {CHANNEL_TYPE_NAMES[channel_type]}"
            )
        else:
            self.selected_channel_label.configure(text="")
        
        # 플렉스인지 확인
        is_flex = self.selected_sign_type == '3'
        
        # 설치 방법 버튼 활성화/비활성화
        # 채널인 경우: 전광/후광 선택 후에만 활성화
        # 스카시/플렉스인 경우: 간판 타입 선택 후 바로 활성화
        if self.selected_sign_type:
            if is_channel:
                # 채널인 경우 전광/후광 선택 필요
                can_select_install = self.selected_channel_type is not None
            else:
                # 스카시/플렉스는 바로 활성화
                can_select_install = True
            if can_select_install:
                for key, btn in self.installation_type_buttons.items():
                    if is_flex:
                        # 플렉스는 frame_plate만 가능
                        if key == 'p':
                            btn.configure(state=tk.NORMAL, bg='#4CAF50', fg='white')
                        else:
                            btn.configure(state=tk.DISABLED, bg='#2d2d2d', fg='white')
                    else:
                        btn.configure(state=tk.NORMAL)
            else:
                for btn in self.installation_type_buttons.values():
                    btn.configure(state=tk.DISABLED)
        else:
            for btn in self.installation_type_buttons.values():
                btn.configure(state=tk.DISABLED)
        
        # 설치 방법 버튼 색상 (플렉스가 아닌 경우)
        if not is_flex:
            for key, btn in self.installation_type_buttons.items():
                if self.selected_installation_type == key:
                    btn.configure(bg='#2196F3', fg='white')
                else:
                    btn.configure(bg='#2d2d2d', fg='white')
        
        # 플렉스 선택 시 자동으로 frame_plate 설정
        if is_flex and not self.selected_installation_type:
            self.selected_installation_type = 'p'
        
        # 선택된 설치 방법 표시
        if self.selected_installation_type:
            install_type = INSTALLATION_TYPES[self.selected_installation_type]
            self.selected_install_label.configure(
                text=f"설치: {INSTALLATION_TYPE_NAMES[install_type]}"
            )
        else:
            self.selected_install_label.configure(text="")
        
        # 시간대 버튼 활성화/비활성화
        # 채널인 경우: 전광/후광도 선택되어야 함
        can_select_time = False
        if self.selected_sign_type and self.selected_installation_type:
            if is_channel:
                can_select_time = self.selected_channel_type is not None
            else:
                can_select_time = True
        
        if can_select_time:
            for btn in self.time_type_buttons.values():
                btn.configure(state=tk.NORMAL)
        else:
            for btn in self.time_type_buttons.values():
                btn.configure(state=tk.DISABLED)
        
        # 시간대 버튼 색상
        for key, btn in self.time_type_buttons.items():
            if self.selected_time_type == key:
                btn.configure(bg='#FF9800', fg='white')
            else:
                btn.configure(bg='#2d2d2d', fg='white')
        
        # 조명 버튼 활성화/비활성화 (채널 간판만)
        if is_channel and self.selected_time_type:
            for btn in self.lights_buttons.values():
                btn.configure(state=tk.NORMAL)
        else:
            for btn in self.lights_buttons.values():
                btn.configure(state=tk.DISABLED)
        
        # 조명 버튼 색상
        for key, btn in self.lights_buttons.items():
            if self.selected_lights_enabled == key:
                btn.configure(bg='#9C27B0', fg='white')
            else:
                btn.configure(bg='#2d2d2d', fg='white')
        
        # 선택된 조명 상태 표시
        if self.selected_lights_enabled:
            lights_value = True if self.selected_lights_enabled == 'o' else False
            lights_text = '켜짐' if lights_value else '꺼짐'
            self.selected_lights_label.configure(text=f"조명: {lights_text}")
        else:
            self.selected_lights_label.configure(text="")
        
        # 확인 버튼 활성화/비활성화
        # 채널인 경우: 전광/후광도 선택되어야 함
        # 조명 선택은 선택사항 (없으면 False로 저장)
        can_confirm = False
        if self.selected_sign_type and self.selected_installation_type and self.selected_time_type:
            if is_channel:
                can_confirm = self.selected_channel_type is not None
            else:
                can_confirm = True
        
        if can_confirm:
            self.confirm_button.configure(state=tk.NORMAL, bg='#4CAF50')
        else:
            self.confirm_button.configure(state=tk.DISABLED, bg='#616161')
    
    def select_sign_type(self, key):
        """간판 타입 선택"""
        self.selected_sign_type = key
        # 채널 타입 초기화 (채널이 아닌 경우 또는 채널 재선택 시)
        if key != '1':
            self.selected_channel_type = None
        # 플렉스가 아닌 경우 설치 방법 초기화
        if key != '3':
            self.selected_installation_type = None
        else:
            # 플렉스는 자동으로 frame_plate
            self.selected_installation_type = 'p'
        self.selected_time_type = None  # 시간대 초기화
        self.update_button_states()
    
    def select_channel_type(self, key):
        """채널 타입 선택 (전광/후광)"""
        if not self.selected_sign_type or self.selected_sign_type != '1':
            return
        self.selected_channel_type = key
        self.selected_installation_type = None  # 설치 방법 초기화
        self.selected_time_type = None  # 시간대 초기화
        self.update_button_states()
    
    def select_installation_type(self, key):
        """설치 방법 선택"""
        if not self.selected_sign_type:
            return
        # 플렉스는 frame_plate만 가능
        if self.selected_sign_type == '3' and key != 'p':
            return
        self.selected_installation_type = key
        self.selected_time_type = None  # 시간대 초기화
        self.update_button_states()
    
    def select_time_type(self, key):
        """시간대 선택"""
        if not self.selected_sign_type or not self.selected_installation_type:
            return
        self.selected_time_type = key
        self.update_button_states()
    
    def select_lights(self, key):
        """조명 선택 (채널 간판만)"""
        if not self.selected_sign_type or self.selected_sign_type != '1':
            return
        if not self.selected_time_type:
            return
        self.selected_lights_enabled = key
        self.update_button_states()
    
    def confirm_labeling(self):
        """라벨링 확인 및 저장"""
        if not self.selected_sign_type or not self.selected_installation_type or not self.selected_time_type:
            return
        
        # 채널인 경우 전광/후광 확인
        if self.selected_sign_type == '1' and not self.selected_channel_type:
            return
        
        # 크롭 영역이 없으면 경고
        if not self.crop_region:
            if not messagebox.askyesno("확인", "크롭 영역이 선택되지 않았습니다. 계속하시겠습니까?"):
                return
        
        sign_type = SIGN_TYPES[self.selected_sign_type]
        installation_type = INSTALLATION_TYPES[self.selected_installation_type]
        time_type = TIME_TYPES[self.selected_time_type]
        
        # 조합 키 생성
        # 채널인 경우: "channel_front_wall", "channel_back_wall", 또는 "channel_front_back_wall"
        # 스카시/플렉스인 경우: "scasi_wall" 또는 "flex_frame_plate"
        if sign_type == 'channel':
            channel_type = CHANNEL_TYPES[self.selected_channel_type]
            # 전후광인 경우 "both"를 "front_back"로 변환
            if channel_type == 'both':
                channel_type = 'front_back'
            sign_type_key = f"{sign_type}_{channel_type}_{installation_type}"
        else:
            sign_type_key = f"{sign_type}_{installation_type}"
        
        image_path = self.image_files[self.current_index]
        
        try:
            # 크롭 실행 (크롭 영역이 있는 경우) - sign_type_key와 time_type 전달
            if self.crop_region:
                self.save_cropped_image(image_path, sign_type_key, time_type)
            
            # 파일 이동 (sign_type_key 사용)
            dest_file = self.move_file(image_path, sign_type_key, time_type)
            
            # 조명 상태 결정 (채널 간판만, 선택 안 하면 False)
            lights_enabled = False
            if sign_type == 'channel' and self.selected_lights_enabled:
                lights_enabled = (self.selected_lights_enabled == 'o')
            
            # labels.json에 추가
            self.add_to_labels(dest_file, sign_type_key, time_type, image_path, lights_enabled)
            
            # labels.json 저장 (매번 저장하여 안전성 확보)
            self.save_labels()
            
            # 되돌리기 히스토리에 추가
            self.undo_history.append({
                'source_file': image_path,
                'dest_file': dest_file,
                'sign_type_key': sign_type_key,
                'time_type': time_type
            })
            
            # 통계 업데이트
            self.stats['labeled'] += 1
            self.update_progress()
            
            # 다음 이미지
            self.next_image()
            
        except Exception as e:
            # 콘솔에 상세 에러 출력
            exc_type, exc_value, exc_traceback = sys.exc_info()
            log_error(f"파일 이동 실패: {e}", (exc_type, exc_value, exc_traceback))
            
            # 사용자에게는 간단한 메시지
            error_detail = traceback.format_exc()
            print(error_detail, file=sys.stderr)  # 콘솔에도 출력
            messagebox.showerror(
                "파일 이동 오류", 
                f"파일 이동에 실패했습니다.\n\n"
                f"오류: {str(e)}\n\n"
                f"상세 내용은 터미널을 확인하세요."
            )
    
    def skip_image(self):
        """이미지 건너뛰기"""
        self.stats['skipped'] += 1
        self.update_progress()
        self.next_image()
    
    def undo_last(self):
        """마지막 분류 되돌리기"""
        if not self.undo_history:
            messagebox.showinfo("알림", "되돌릴 항목이 없습니다.")
            return
        
        last_action = self.undo_history.pop()
        
        try:
            # 파일 되돌리기
            if last_action['dest_file'].exists():
                shutil.move(str(last_action['dest_file']), str(last_action['source_file']))
            
            # labels.json에서 제거
            sign_type_key = last_action['sign_type_key']
            time_type = last_action['time_type']
            labels_list = self.labels[sign_type_key][time_type]
            
            if labels_list:
                labels_list.pop()
            
            # 통계 업데이트
            self.stats['labeled'] -= 1
            self.current_index -= 1
            self.update_progress()
            
            # 현재 이미지 다시 로드
            self.load_current_image()
            
            messagebox.showinfo("완료", f"되돌림 완료: {last_action['source_file'].name}")
            
        except Exception as e:
            messagebox.showerror("오류", f"되돌리기 실패: {e}")
    
    def next_image(self):
        """다음 이미지로"""
        # 파일 목록 다시 읽기 (이동된 파일 제외)
        self.image_files = self.get_image_files()
        
        if not self.image_files:
            messagebox.showinfo("완료", "모든 이미지를 처리했습니다!")
            self.quit_app()
            return
        
        # 인덱스 증가 전에 현재 범위 확인
        # 파일이 이동되어 목록이 줄어들었을 수 있으므로 안전하게 조정
        if self.current_index >= len(self.image_files):
            self.current_index = max(0, len(self.image_files) - 1)
        else:
            self.current_index += 1
        
        # 인덱스가 범위를 벗어났으면 조정
        if self.current_index >= len(self.image_files):
            self.current_index = max(0, len(self.image_files) - 1)
        
        if self.current_index < len(self.image_files):
            self.load_current_image()
        else:
            messagebox.showinfo("완료", "모든 이미지를 처리했습니다!")
            self.quit_app()
    
    def update_progress(self):
        """진행상황 업데이트"""
        remaining = len(self.image_files)
        total_processed = self.stats['labeled'] + self.stats['skipped']
        original_total = self.stats['total']
        
        # 진행률은 원본 총 개수 대비 처리된 개수로 계산 (일관성 유지)
        if original_total > 0:
            progress = (total_processed / original_total * 100)
            self.progress_label.configure(
                text=f"진행: {total_processed}/{original_total} ({progress:.1f}%) | 남은 파일: {remaining}"
            )
        else:
            # original_total이 0인 경우는 초기화 오류이지만, 안전하게 처리
            current_pos = min(self.current_index + 1, remaining) if remaining > 0 else 0
            self.progress_label.configure(
                text=f"진행: {current_pos}/{remaining} | 남은 파일: {remaining}"
            )
        
        self.stats_label.configure(
            text=f"라벨링: {self.stats['labeled']} | 건너뛰기: {self.stats['skipped']}"
        )
    
    def move_file(self, source, sign_type_key, time_type):
        """파일을 해당 폴더로 이동"""
        print(f"[DEBUG] move_file 호출: source={source}, sign_type_key={sign_type_key}, time_type={time_type}", file=sys.stderr)
        
        # 소스 파일 존재 확인
        if not source.exists():
            error_msg = f"소스 파일을 찾을 수 없습니다: {source}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            raise FileNotFoundError(error_msg)
        
        # sign_type_key를 사용하여 폴더 경로 생성 (예: "channel_front_wall")
        dest_dir = self.output_base / "real_photos" / sign_type_key / time_type
        print(f"[DEBUG] 대상 디렉토리: {dest_dir}", file=sys.stderr)
        print(f"[DEBUG] output_base: {self.output_base}", file=sys.stderr)
        
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            print(f"[DEBUG] 디렉토리 생성 성공: {dest_dir}", file=sys.stderr)
        except Exception as e:
            error_msg = f"디렉토리 생성 실패: {dest_dir}\n오류: {e}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            raise OSError(error_msg)
        
        base_name = source.stem
        ext = source.suffix

        # ✅ 수정: 파일명에서 기존 prefix 제거 (중복 방지)
        # 예: "flex_frame_plate_27" → "27"
        if base_name.startswith(sign_type_key + "_"):
            base_name = base_name[len(sign_type_key) + 1:]

        dest_file = dest_dir / f"{sign_type_key}_{base_name}_{time_type}{ext}"
        print(f"[DEBUG] 대상 파일: {dest_file}", file=sys.stderr)
        
        # 중복 파일 처리
        counter = 1
        while dest_file.exists():
            dest_file = dest_dir / f"{sign_type_key}_{base_name}_{time_type}_{counter}{ext}"
            counter += 1
            if counter > 1000:  # 무한 루프 방지
                error_msg = f"중복 파일명 해결 실패: {dest_file.parent}"
                print(f"[ERROR] {error_msg}", file=sys.stderr)
                raise RuntimeError(error_msg)
        
        try:
            print(f"[DEBUG] 파일 이동 시도: {source} -> {dest_file}", file=sys.stderr)
            shutil.move(str(source), str(dest_file))
            print(f"[DEBUG] 파일 이동 성공", file=sys.stderr)
        except Exception as e:
            error_msg = f"파일 이동 실패\n소스: {source}\n대상: {dest_file}\n오류: {type(e).__name__}: {e}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            raise OSError(error_msg)
        
        return dest_file
    
    def add_to_labels(self, image_path, sign_type_key, time_type, original_path, lights_enabled=False):
        """labels.json에 추가"""
        # 키가 없으면 생성 (안전장치)
        if sign_type_key not in self.labels:
            print(f"[WARN] sign_type_key '{sign_type_key}'가 labels에 없어 생성합니다.", file=sys.stderr)
            self.labels[sign_type_key] = {"day": [], "night": []}
        
        if time_type not in self.labels[sign_type_key]:
            print(f"[WARN] time_type '{time_type}'가 labels[{sign_type_key}]에 없어 생성합니다.", file=sys.stderr)
            self.labels[sign_type_key][time_type] = []
        
        file_id = f"{sign_type_key}_{image_path.stem}_{time_type}"
        
        # sign_type과 installation_type 분리
        parts = sign_type_key.split('_')
        sign_type = parts[0]
        installation_type = '_'.join(parts[1:]) if len(parts) > 1 else 'wall'
        
        entry = {
            "id": file_id,
            "real_photo": str(image_path.relative_to(self.output_base)),
            "sign_type": sign_type,
            "installation_type": installation_type,
            "sign_type_key": sign_type_key,
            "time": time_type,
            "date_labeled": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original_filename": original_path.name
        }
        
        # 채널 간판인 경우에만 lights_enabled 추가
        if sign_type == 'channel':
            entry["lights_enabled"] = lights_enabled
        
        # 크롭된 이미지 경로 추가 (있는 경우)
        if self.cropped_photo_path:
            # ✅ 수정: output_base 기준 상대 경로로 저장
            try:
                rel_path = self.cropped_photo_path.relative_to(self.output_base)
                entry["cropped_photo"] = str(rel_path).replace('\\', '/')
            except ValueError:
                # relative_to 실패하면 파일명만 사용
                entry["cropped_photo"] = f"cropped_photos/{self.cropped_photo_path.name}"
                
        # 텍스트 추가 (있는 경우)
        if self.text_input:
            entry["text"] = self.text_input
        
        # 크롭 영역 정보 추가 (있는 경우)
        if self.crop_region:
            entry["crop_region"] = {
                "x": int(self.crop_region[0]),
                "y": int(self.crop_region[1]),
                "width": int(self.crop_region[2]),
                "height": int(self.crop_region[3])
            }
        
        self.labels[sign_type_key][time_type].append(entry)
    
    def on_crop_start(self, event):
        """크롭 시작"""
        # 포커스를 root로 이동 (단축키 사용 가능하도록)
        self.root.focus_set()
        self.crop_start = (event.x, event.y)
        if self.crop_rect:
            self.canvas.delete(self.crop_rect)
        self.crop_rect = None
    
    def on_crop_drag(self, event):
        """크롭 드래그 중"""
        if not self.crop_start:
            return
        
        if self.crop_rect:
            self.canvas.delete(self.crop_rect)
        
        x1, y1 = self.crop_start
        x2, y2 = event.x, event.y
        
        # 사각형 그리기
        self.crop_rect = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='#4CAF50',
            width=2,
            fill='',
            stipple='gray50'
        )
    
    def on_crop_end(self, event):
        """크롭 종료"""
        if not self.crop_start:
            return
        
        self.crop_end = (event.x, event.y)
        
        # 원본 이미지 기준 좌표로 변환
        x1, y1 = self.crop_start
        x2, y2 = self.crop_end
        
        # 좌표 정규화 (시작점이 끝점보다 클 수 있음)
        x_min = min(x1, x2)
        x_max = max(x1, x2)
        y_min = min(y1, y2)
        y_max = max(y1, y2)
        
        # 표시 스케일로 나눠서 원본 좌표로 변환
        orig_x = int(x_min / self.display_scale)
        orig_y = int(y_min / self.display_scale)
        orig_w = int((x_max - x_min) / self.display_scale)
        orig_h = int((y_max - y_min) / self.display_scale)
        
        # 원본 이미지 범위 내로 제한
        orig_width, orig_height = self.current_image.size
        orig_x = max(0, min(orig_x, orig_width - 1))
        orig_y = max(0, min(orig_y, orig_height - 1))
        orig_w = max(1, min(orig_w, orig_width - orig_x))
        orig_h = max(1, min(orig_h, orig_height - orig_y))
        
        self.crop_region = (orig_x, orig_y, orig_w, orig_h)
        
        # 정보 표시
        self.crop_info_label.configure(
            text=f"크롭 영역: ({orig_x}, {orig_y}) 크기: {orig_w}x{orig_h}px"
        )
    
    def save_cropped_image(self, original_path, sign_type_key, time_type):
        """크롭된 이미지를 저장 (강제로 512x512로 리사이즈, 패딩 없음)
        
        Args:
            original_path: 원본 이미지 경로
            sign_type_key: 간판 타입 키 (예: "channel_front_wall")
            time_type: 시간대 ("day" 또는 "night")
        """
        if not self.crop_region or not self.current_image:
            return
        
        x, y, w, h = self.crop_region
        
        # 원본 이미지에서 크롭 (PIL)
        cropped_pil = self.current_image.crop((x, y, x + w, y + h))
        
        # PIL을 numpy 배열로 변환 (RGB)
        cropped_np = np.array(cropped_pil)
        
        # OpenCV 형식으로 변환 (RGB -> BGR)
        cropped_cv = cv2.cvtColor(cropped_np, cv2.COLOR_RGB2BGR)
        
        # 강제로 512x512로 리사이즈 (패딩 없이, INTER_LANCZOS4 사용)
        target_size = 512
        resized = cv2.resize(cropped_cv, (target_size, target_size), interpolation=cv2.INTER_LANCZOS4)
        
        # 저장 경로 생성: {sign_type_key}_{time_type}_{original_stem}_cropped.jpg
        original_stem = original_path.stem
        # 파일명에서 기존 prefix 제거 (중복 방지)
        if original_stem.startswith(sign_type_key + "_"):
            original_stem = original_stem[len(sign_type_key) + 1:]
        if original_stem.endswith(f"_{time_type}"):
            original_stem = original_stem[:-len(f"_{time_type}")]
        
        # 파일명 생성: sign_type_key_time_type_original_stem_cropped.jpg
        cropped_filename = f"{sign_type_key}_{time_type}_{original_stem}_cropped.jpg"
        self.cropped_photo_path = self.cropped_photos_dir / cropped_filename
        
        # 중복 파일 처리
        counter = 1
        while self.cropped_photo_path.exists():
            cropped_filename = f"{sign_type_key}_{time_type}_{original_stem}_cropped_{counter}.jpg"
            self.cropped_photo_path = self.cropped_photos_dir / cropped_filename
            counter += 1
            if counter > 10000:  # 무한 루프 방지
                raise RuntimeError(f"중복 파일명 해결 실패: {self.cropped_photos_dir}")
        
        # OpenCV로 저장 (JPEG, 품질 95)
        cv2.imwrite(str(self.cropped_photo_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    def on_text_changed(self, event):
        """텍스트 입력 변경"""
        self.text_input = self.text_entry.get()
    
    def run_ocr(self):
        """OCR 실행 (크롭된 영역이 있는 경우)"""
        if not OCR_AVAILABLE:
            messagebox.showwarning("OCR 미설치", "pytesseract가 설치되어 있지 않습니다.\n\n설치 방법:\npip install pytesseract\n\n그리고 Tesseract OCR을 설치하세요:\nhttps://github.com/tesseract-ocr/tesseract")
            return
        
        if not self.crop_region or not self.current_image:
            messagebox.showwarning("경고", "먼저 간판 영역을 선택하세요.")
            return
        
        try:
            x, y, w, h = self.crop_region
            cropped_img = self.current_image.crop((x, y, x + w, y + h))
            
            # OCR 실행 (한글 + 영어)
            text = pytesseract.image_to_string(cropped_img, lang='kor+eng')
            text = text.strip()
            
            if text:
                self.text_entry.delete(0, tk.END)
                self.text_entry.insert(0, text)
                self.text_input = text
                self.crop_info_label.configure(
                    text=f"OCR 결과: {text[:30]}{'...' if len(text) > 30 else ''}"
                )
            else:
                messagebox.showinfo("OCR 결과", "텍스트를 인식하지 못했습니다.")
        except Exception as e:
            messagebox.showerror("OCR 오류", f"OCR 실행 중 오류가 발생했습니다:\n{e}")
    
    def quit_app(self):
        """종료 및 저장"""
        self.save_labels()
        
        # 최종 통계 표시
        stats_msg = f"""라벨링 완료!

총 파일: {self.stats['total']}
라벨링 완료: {self.stats['labeled']}
건너뛰기: {self.stats['skipped']}

labels.json 저장: {self.labels_file}
"""
        messagebox.showinfo("완료", stats_msg)
        self.root.quit()
    
    def run(self):
        """GUI 실행"""
        self.root.mainloop()


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='간판 사진 라벨링 도구 (GUI)')
    parser.add_argument(
        '--input',
        type=str,
        required=False,
        help='라벨링할 사진이 있는 폴더 (없으면 GUI에서 선택)'
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
    
    # input이 없으면 GUI에서 폴더 선택
    if not args.input:
        # 임시 루트로 폴더 선택 다이얼로그 띄우기
        root = tk.Tk()
        root.withdraw()  # 메인 창 숨기기
        
        # 기본 경로 설정 (phase2_data/real_photos/unlabeled/)
        default_path = Path(__file__).parent / "phase2_data" / "real_photos" / "unlabeled"
        if not default_path.exists():
            default_path = Path(__file__).parent
        
        input_dir = filedialog.askdirectory(
            title="라벨링할 사진이 있는 폴더를 선택하세요",
            initialdir=str(default_path)
        )
        
        root.destroy()
        
        if not input_dir:
            print("폴더가 선택되지 않았습니다.")
            return
        
        args.input = input_dir
    
    # 도구 실행
    tool = LabelingToolGUI(
        input_dir=args.input,
        labels_file=args.labels,
        output_base=args.output
    )
    tool.run()


if __name__ == "__main__":
    main()
