"""
Google Drive 자동 업로드 스크립트

사용법:
    python upload_to_drive.py

기능:
- 최초 1회: OAuth 인증 (웹 브라우저 자동 열림)
- 인증 토큰을 token.json에 저장
- 이후 실행: 저장된 토큰으로 자동 업로드
- 증분 업로드: 이미 있는 파일은 스킵
"""

import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import mimetypes

# Google Drive API 스코프
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# 인증 정보 파일
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

# 업로드 설정
DRIVE_FOLDER_NAME = 'Colab_Signboard_Data'
SOURCE_DIR = Path(__file__).parent / 'phase2_data' / 'paired_data'


def get_drive_service():
    """Google Drive API 서비스 객체 생성"""
    creds = None
    
    # 저장된 토큰이 있으면 로드
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # 토큰이 없거나 유효하지 않으면 인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 토큰 갱신
            creds.refresh(Request())
        else:
            # 새로운 인증 플로우 시작
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"[오류] {CREDENTIALS_FILE} 파일을 찾을 수 없습니다.")
                print(f"[안내] Google Cloud Console에서 credentials.json을 다운로드하세요.")
                print(f"[안내] 자세한 내용은 COLAB_SETUP_GUIDE.md를 참고하세요.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 토큰 저장
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f'[오류] Drive API 오류: {error}')
        return None


def find_or_create_folder(service, folder_name, parent_id=None):
    """폴더 찾기 또는 생성"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    try:
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])
        
        if items:
            return items[0]['id']
        else:
            # 폴더 생성
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = service.files().create(body=file_metadata, fields='id').execute()
            print(f"[폴더 생성] {folder_name}")
            return folder.get('id')
    except HttpError as error:
        print(f'[오류] 폴더 생성/찾기 오류: {error}')
        return None


def get_file_id_in_folder(service, file_name, folder_id):
    """폴더 내 파일 ID 찾기"""
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    try:
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get('files', [])
        return items[0]['id'] if items else None
    except HttpError as error:
        return None


def upload_file(service, file_path, folder_id, parent_folders=None):
    """파일 업로드 (증분 업로드 지원)"""
    if parent_folders is None:
        parent_folders = []
    
    file_name = file_path.name
    file_path_str = str(file_path)
    
    # MIME 타입 확인
    mime_type, _ = mimetypes.guess_type(file_path_str)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    
    # 이미 업로드된 파일인지 확인
    existing_file_id = get_file_id_in_folder(service, file_name, folder_id)
    
    try:
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path_str, mimetype=mime_type, resumable=True)
        
        if existing_file_id:
            # 기존 파일 업데이트
            file = service.files().update(
                fileId=existing_file_id,
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id'), 'updated'
        else:
            # 새 파일 업로드
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id'), 'uploaded'
    except HttpError as error:
        print(f'[오류] 업로드 오류 ({file_name}): {error}')
        return None, 'error'


def upload_directory(service, source_dir, target_folder_id, relative_path=""):
    """디렉토리 재귀적으로 업로드"""
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"[오류] 경로가 존재하지 않습니다: {source_path}")
        return
    
    uploaded_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    # 현재 폴더의 파일들
    files = [f for f in source_path.iterdir() if f.is_file()]
    for file_path in files:
        # .gitkeep 같은 숨김 파일 스킵
        if file_path.name.startswith('.'):
            continue
        
        display_path = f"{relative_path}/{file_path.name}" if relative_path else file_path.name
        status = upload_file(service, file_path, target_folder_id)
        
        if status[1] == 'uploaded':
            uploaded_count += 1
            print(f"  [업로드] {display_path}")
        elif status[1] == 'updated':
            updated_count += 1
            print(f"  [업데이트] {display_path}")
        elif status[1] == 'error':
            error_count += 1
        else:
            skipped_count += 1
    
    # 현재 폴더의 하위 디렉토리들
    dirs = [d for d in source_path.iterdir() if d.is_dir()]
    for dir_path in dirs:
        dir_name = dir_path.name
        # .git 같은 숨김 폴더 스킵
        if dir_name.startswith('.'):
            continue
        
        display_path = f"{relative_path}/{dir_name}" if relative_path else dir_name
        print(f"[폴더 처리] {display_path}/")
        
        # 하위 폴더 생성 또는 찾기
        subfolder_id = find_or_create_folder(service, dir_name, target_folder_id)
        if subfolder_id:
            new_relative_path = f"{relative_path}/{dir_name}" if relative_path else dir_name
            sub_uploaded, sub_updated, sub_skipped, sub_errors = upload_directory(
                service, dir_path, subfolder_id, new_relative_path
            )
            uploaded_count += sub_uploaded
            updated_count += sub_updated
            skipped_count += sub_skipped
            error_count += sub_errors
    
    return uploaded_count, updated_count, skipped_count, error_count


def main():
    """메인 함수"""
    print("=" * 60)
    print("[Google Drive 업로드 시작]")
    print("=" * 60)
    
    # 소스 디렉토리 확인
    if not SOURCE_DIR.exists():
        print(f"[오류] 소스 디렉토리를 찾을 수 없습니다: {SOURCE_DIR}")
        return
    
    print(f"[소스 디렉토리] {SOURCE_DIR}")
    print(f"[목적지] Google Drive / {DRIVE_FOLDER_NAME}")
    print()
    
    # Drive 서비스 생성
    print("[인증] Google Drive 인증 중...")
    service = get_drive_service()
    if not service:
        return
    
    print("[완료] 인증 완료!")
    print()
    
    # 루트 폴더 찾기 또는 생성
    print(f"[폴더 확인] '{DRIVE_FOLDER_NAME}' 폴더 확인 중...")
    root_folder_id = find_or_create_folder(service, DRIVE_FOLDER_NAME)
    if not root_folder_id:
        print("[오류] 루트 폴더를 생성할 수 없습니다.")
        return
    
    print(f"[완료] 폴더 준비 완료 (ID: {root_folder_id})")
    print()
    
    # 업로드 시작
    print("[업로드] 파일 업로드 시작...")
    print("-" * 60)
    
    uploaded, updated, skipped, errors = upload_directory(service, SOURCE_DIR, root_folder_id)
    
    # 결과 출력
    print()
    print("=" * 60)
    print("[완료] 업로드 완료!")
    print("=" * 60)
    print(f"[통계]")
    print(f"  새로 업로드: {uploaded}개")
    print(f"  업데이트: {updated}개")
    print(f"  스킵: {skipped}개")
    if errors > 0:
        print(f"  오류: {errors}개")
    print()
    print(f"[다음 단계]")
    print(f"  1. Google Drive에서 '{DRIVE_FOLDER_NAME}' 폴더 확인")
    print(f"  2. Colab 노트북 (pix2pix_training.ipynb) 열기")
    print(f"  3. 학습 시작!")
    print("=" * 60)


if __name__ == '__main__':
    main()

