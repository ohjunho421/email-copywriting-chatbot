# 🚀 PortOne 이메일 생성 챗봇

PortOne의 One Payment Infra 제품을 위한 AI 기반 개인화 영업 이메일 생성 시스템입니다.

## ✨ 주요 기능

- 🔍 **다중 검색 엔진**: Google Search, DuckDuckGo, Perplexity를 통한 최신 뉴스 수집
- 🤖 **Google Gemini 2.5 Pro**: 고품질 개인화 이메일 문안 생성
- 📊 **4가지 이메일 템플릿**: OPI, 재무자동화, 게임D2C 각 전문/호기심 톤
- 📋 **병렬 일괄 처리**: CSV 파일로 여러 회사 동시 처리 (최적화된 성능)
- 🎨 **HTML 변환**: 전문적인 이메일 템플릿으로 변환
- ✨ **AI 개선**: 사용자 피드백 기반 문안 개선
- ⚡ **실시간 뉴스**: 최신 회사 동향을 반영한 개인화된 메시지

## 🚀 빠른 시작

### 1. 간단한 실행 (권장)

**macOS/Linux:**
```bash
./start.sh
```

**Windows:**
```cmd
start.bat
```

### 2. 수동 실행

**터미널 1 - 백엔드 서버:**
```bash
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot
python3 app.py
```

**터미널 2 - 프론트엔드 서버:**
```bash
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot
python3 -m http.server 8000
```

## 📱 사용 방법

1. **브라우저 접속**: http://localhost:8000
2. **CSV 파일 업로드**: 회사명, 홈페이지링크 등 포함
3. **메일 문안 생성**: "메일 문안 생성하기" 버튼 클릭
4. **결과 확인**: 3가지 스타일의 개인화 이메일 확인
5. **활용**: 복사, HTML 변환, AI 개선 기능 사용

## 📋 CSV 파일 형식

```csv
회사명,홈페이지링크,업종,규모
한국신용데이터,https://www.kcd.co.kr,핀테크,중견기업
엑시트파트너스,https://www.exitpartners.co.kr,부동산,스타트업
```

## 🔧 서버 정보

- **프론트엔드 (UI)**: http://localhost:8000
- **백엔드 (API)**: http://localhost:5001
- **브라우저 자동 열기**: 스크립트 실행 시 자동

## 🎯 생성되는 이메일 스타일

### 1. 전문적 톤
- 신뢰감 있는 비즈니스 톤
- 구체적인 수치와 혜택 제시
- 15분 통화 일정 제안

### 2. 친근한 톤  
- 접근하기 쉬운 친근한 톤
- 커피챗 형태의 만남 제안
- 무료 컨설팅 혜택 강조

### 3. 호기심 유발형
- 질문을 통한 관심 유도
- 현재 상황에 대한 문제 제기
- 10분 데모 요청

## 🛠 기술 스택

- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5
- **Backend**: Python Flask, Flask-CORS
- **AI Services**: 
  - Google Gemini 2.5 Pro (메인 생성 엔진)
  - Perplexity AI (sonar-pro 모델) - 회사 조사
  - Multi-Search Engines: Google Search API, DuckDuckGo
- **Dependencies**: requests, python-dotenv

## ⚙️ 환경 설정

`.env` 파일에 API 키 설정:
```env
# 필수 API 키
GEMINI_API_KEY=your-gemini-api-key-here
PERPLEXITY_API_KEY=your-perplexity-api-key-here

# 선택사항: 더 정확한 뉴스 검색을 위한 Google Search API
GOOGLE_SEARCH_API_KEY=your-google-search-api-key-here
GOOGLE_CSE_ID=your-custom-search-engine-id-here

# 서버 설정
FLASK_ENV=development
FLASK_DEBUG=True
```

### 🔍 다중 검색 엔진 설정
- **기본**: Perplexity + DuckDuckGo 사용
- **고급**: Google Search API 키 추가 시 더 정확한 실시간 뉴스 수집
- **자동 Fallback**: API 장애 시 자동으로 다른 검색 엔진 활용

## 🔒 보안

- API 키는 `.env` 파일에 안전하게 저장
- 로컬 환경에서만 실행 (개발용)
- 민감한 정보는 로그에 노출되지 않음

## 🚨 문제 해결

### 서버 시작 실패
```bash
# 포트 사용 중인 프로세스 확인
lsof -i :8000
lsof -i :5001

# 프로세스 종료
pkill -f "python.*app.py"
pkill -f "python.*http.server"
```

### API 키 오류
- `.env` 파일에 올바른 API 키가 설정되어 있는지 확인
- API 키에 충분한 크레딧이 있는지 확인

## 📞 지원

문제가 발생하면 다음을 확인해주세요:
1. Python 3.7+ 설치 여부
2. 필요한 패키지 설치: `pip install -r requirements.txt`
3. API 키 설정 상태
4. 네트워크 연결 상태

---

**PortOne Team** | 결제 인프라의 혁신을 이끌어갑니다 🚀
