@echo off
echo Starting development servers...
echo.

REM 백엔드 서버 시작 (백그라운드)
start "Backend Server" cmd /k "cd signboard-backend && venv\Scripts\python.exe main.py"

REM 3초 대기
timeout /t 3 /nobreak >nul

REM 프론트엔드 서버 시작
echo Starting frontend server...
cd signboard-frontend
call npm start


