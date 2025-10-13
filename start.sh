#!/bin/bash

# PortOne 이메일 생성 챗봇 시작 스크립트 (SSR 버전)
echo "🚀 PortOne 이메일 생성 챗봇 SSR 버전을 시작합니다..."

# 현재 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경 활성화
if [ -d "../.venv" ]; then
    echo "🔧 가상환경을 활성화합니다..."
    source ../.venv/bin/activate
elif [ -d ".venv" ]; then
    echo "🔧 가상환경을 활성화합니다..."
    source .venv/bin/activate
else
    echo "⚠️  가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다..."
fi

# 기존 프로세스 종료
echo "📋 기존 서버 프로세스를 정리합니다..."
pkill -f "python.*app.py" 2>/dev/null
pkill -f "python.*http.server.*8000" 2>/dev/null

# 잠시 대기
sleep 2

# 백엔드 서버 시작 (포트 5001)
echo "🔧 백엔드 서버를 시작합니다 (포트 5001)..."
python3 app.py &
BACKEND_PID=$!

# 백엔드 서버 시작 대기
sleep 3

# 프론트엔드 서버 시작 (포트 8000)
echo "🌐 프론트엔드 서버를 시작합니다 (포트 8000)..."
python3 -m http.server 8000 &
FRONTEND_PID=$!

# 서버 시작 대기
sleep 2

echo ""
echo "✅ 서버가 성공적으로 시작되었습니다!"
echo ""
echo "📱 사용 방법:"
echo "   브라우저에서 http://localhost:8000 접속"
echo ""
echo "🔧 서버 상태:"
echo "   - 백엔드 (API): http://localhost:5001"
echo "   - 프론트엔드 (UI): http://localhost:8000"
echo ""
echo "⚠️  서버를 종료하려면 Ctrl+C를 누르세요"
echo ""

# 브라우저 자동 열기 (macOS)
if command -v open >/dev/null 2>&1; then
    echo "🌐 브라우저를 자동으로 열고 있습니다..."
    sleep 1
    open http://localhost:8000
fi

# 사용자가 Ctrl+C를 누를 때까지 대기
trap 'echo ""; echo "🛑 서버를 종료합니다..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' INT

# 무한 대기
while true; do
    sleep 1
done
