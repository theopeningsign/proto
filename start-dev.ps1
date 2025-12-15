# 개발 서버 시작 스크립트

Write-Host "Starting development servers..." -ForegroundColor Green
Write-Host ""

# 백엔드 서버 시작 (새 창)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd signboard-backend; .\venv\Scripts\python.exe main.py" -WindowStyle Normal

# 3초 대기
Start-Sleep -Seconds 3

# 프론트엔드 서버 시작
Write-Host "Starting frontend server..." -ForegroundColor Cyan
Set-Location signboard-frontend
npm start




