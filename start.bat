@echo off
chcp 65001 >nul
title PortOne 이메일 생성 챗봇

echo 🚀 PortOne 이메일 생성 챗봇을 시작합니다...
echo.

REM 현재 디렉토리로 이동
cd /d "%~dp0"

REM 기존 프로세스 종료
echo 📋 기존 서버 프로세스를 정리합니다...
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul

REM 백엔드 서버 시작 (포트 5001)
echo 🔧 백엔드 서버를 시작합니다 (포트 5001)...
start "Backend Server" python app.py
timeout /t 3 /nobreak >nul

REM 프론트엔드 서버 시작 (포트 8000)
echo 🌐 프론트엔드 서버를 시작합니다 (포트 8000)...
start "Frontend Server" python -m http.server 8000
timeout /t 2 /nobreak >nul

echo.
echo ✅ 서버가 성공적으로 시작되었습니다!
echo.
echo 📱 사용 방법:
echo    브라우저에서 http://localhost:8000 접속
echo.
echo 🔧 서버 상태:
echo    - 백엔드 (API): http://localhost:5001
echo    - 프론트엔드 (UI): http://localhost:8000
echo.
echo 🌐 브라우저를 자동으로 열고 있습니다...
start http://localhost:8000

echo.
echo ⚠️  서버를 종료하려면 이 창을 닫으세요
echo.
pause
