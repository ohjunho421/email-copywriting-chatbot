#!/usr/bin/env python3
"""
Public 서버 실행 스크립트
Apps Script에서 접근 가능하도록 0.0.0.0으로 바인딩
"""

import os
import sys
from flask import Flask
from flask_cors import CORS

# 기존 app.py에서 app 객체 가져오기
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    try:
        # app.py에서 Flask 앱 가져오기
        from app import app
        
        # CORS 설정 (Apps Script에서 접근 가능하도록)
        CORS(app, origins=['*'])
        
        print("🚀 PortOne AI 챗봇 서버 시작 중...")
        print("📡 외부 접근 가능 모드")
        print("🌐 Apps Script 연동 준비 완료")
        
        # 0.0.0.0으로 바인딩하여 외부에서 접근 가능하게 설정
        app.run(
            host='0.0.0.0',  # 모든 인터페이스에서 접근 가능
            port=5001,
            debug=True,
            threaded=True
        )
        
    except ImportError as e:
        print(f"❌ app.py를 가져올 수 없습니다: {e}")
        print("💡 app.py 파일이 같은 디렉토리에 있는지 확인하세요.")
    except Exception as e:
        print(f"❌ 서버 시작 오류: {e}")
