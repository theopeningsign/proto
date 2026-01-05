# Google Drive 업로드 환경 설정 및 실행 스크립트
# Windows PowerShell용

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 Google Drive 업로드 환경 설정 및 실행" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 현재 디렉토리 확인
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 1. 필요한 라이브러리 확인 및 설치
Write-Host "[1/3] 필요한 라이브러리 확인 중..." -ForegroundColor Yellow

$requiredPackages = @(
    "google-auth",
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "google-api-python-client"
)

$missingPackages = @()
foreach ($package in $requiredPackages) {
    $installed = pip show $package 2>&1
    if ($LASTEXITCODE -ne 0) {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "  📦 다음 패키지 설치 중: $($missingPackages -join ', ')" -ForegroundColor Yellow
    pip install $missingPackages
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ 패키지 설치 실패" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ 패키지 설치 완료" -ForegroundColor Green
} else {
    Write-Host "  ✅ 모든 패키지가 이미 설치되어 있습니다" -ForegroundColor Green
}
Write-Host ""

# 2. credentials.json 파일 확인
Write-Host "[2/3] credentials.json 파일 확인 중..." -ForegroundColor Yellow
if (-not (Test-Path "credentials.json")) {
    Write-Host "  ⚠️  credentials.json 파일을 찾을 수 없습니다!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  📋 다음 단계를 따라주세요:" -ForegroundColor Yellow
    Write-Host "  1. Google Cloud Console에 접속:" -ForegroundColor White
    Write-Host "     https://console.cloud.google.com/" -ForegroundColor Cyan
    Write-Host "  2. 프로젝트 생성 또는 선택" -ForegroundColor White
    Write-Host "  3. 'API 및 서비스' > '라이브러리'에서 'Google Drive API' 활성화" -ForegroundColor White
    Write-Host "  4. 'API 및 서비스' > '사용자 인증 정보'에서 OAuth 2.0 클라이언트 ID 생성" -ForegroundColor White
    Write-Host "  5. 애플리케이션 유형: '데스크톱 앱' 선택" -ForegroundColor White
    Write-Host "  6. 생성된 credentials를 다운로드하여 이 폴더에 'credentials.json'으로 저장" -ForegroundColor White
    Write-Host ""
    Write-Host "  📖 자세한 내용은 COLAB_SETUP_GUIDE.md를 참고하세요." -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "  credentials.json을 준비하셨나요? (Y/N)"
    if ($continue -ne "Y" -and $continue -ne "y") {
        Write-Host "  ❌ 업로드를 중단합니다." -ForegroundColor Red
        exit 1
    }
    
    if (-not (Test-Path "credentials.json")) {
        Write-Host "  ❌ credentials.json 파일을 여전히 찾을 수 없습니다." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  ✅ credentials.json 파일 확인 완료" -ForegroundColor Green
Write-Host ""

# 3. 업로드 실행
Write-Host "[3/3] Google Drive에 데이터 업로드 중..." -ForegroundColor Yellow
Write-Host ""
python upload_to_drive.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "✅ 모든 작업 완료!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "❌ 업로드 중 오류가 발생했습니다." -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    exit 1
}

