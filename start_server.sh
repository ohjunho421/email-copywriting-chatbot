#!/bin/bash

# PortOne 이메일 챗봇 서버 시작 스크립트

echo "🚀 PortOne 이메일 챗봇 서버 시작 중..."

# 디렉토리 이동
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot

# 환경변수 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다. .env.example을 참고하여 생성해주세요."
    exit 1
fi

# Python 서버 시작
echo "📡 서버 시작: http://localhost:5001"
echo "🔄 중지하려면 Ctrl+C를 누르세요"
echo ""

python3 app.py
