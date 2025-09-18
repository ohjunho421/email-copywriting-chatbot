# 🚀 PortOne 메일 문안 생성 챗봇

PortOne의 One Payment Infra 제품을 위한 개인화된 영업 메일 템플릿을 생성하는 AI 챗봇입니다.

## 주요 기능

- 📊 **CSV 파일 업로드**: 회사 정보가 담긴 CSV 파일을 업로드하여 일괄 처리
- 🤖 **AI 기반 조사**: Perplexity AI를 통한 실시간 회사 정보 및 최신 뉴스 수집
- ✍️ **개인화된 메일 생성**: Google Gemini 2.5 Pro를 활용한 4가지 스타일의 메일 문안 생성
- 🔄 **개선 요청**: 생성된 메일 문안에 대한 상세한 개선 요청 처리
- 📰 **뉴스 기사 분석 (NEW!)**: 뉴스 기사 링크를 분석하여 페인 포인트 기반 메일 생성
- 🧠 **관련성 검증**: 기사 내용과 PortOne 솔루션의 관련성을 자동 판단
- 💾 **회사 정보 캐시**: 기존 조사 결과를 자동 저장하고 재활용
- 📋 **텍스트 복사**: HTML이 아닌 순수 텍스트 형태로 메일 문안 복사
- 📄 **CSV 다운로드**: 생성된 메일 문안을 원본 CSV에 추가하여 다운로드
- ⚡ **병렬 처리**: 다중 회사 데이터를 효율적으로 병렬 처리

## 🆕 새로운 기능

### 🚀 고급 뉴스 기사 분석 시스템

#### 📊 스마트 스크래핑
- **하이브리드 스크래핑**: BeautifulSoup + Selenium으로 정적/동적 사이트 모두 지원
- **사이트별 최적화**: 조선일보, 중앙일보 등 주요 언론사 특화 선택자
- **자동 폴백**: 기본 스크래핑 실패 시 Selenium으로 자동 전환

#### 🧠 관련성 검증 시스템
- **스코어링 알고리즘**: 0-10점 관련성 점수 자동 계산
- **키워드 분석**: PortOne 관련 키워드 vs 비관련 키워드 가중치 적용
- **억지 연결 방지**: 관련성 낮은 기사는 자연스러운 접근 방식 적용

#### 💾 회사 정보 캐시 시스템
- **24시간 캐시**: 메모리 + 파일 기반 이중 캐시 구조
- **자동 연동**: 기존 회사 조사 결과와 자동 연결
- **개인화 강화**: 회사 업종, 규모, 특성 정보 활용

#### 🎯 Pain Point 중심 메일 생성
- **실제 이슈 도출**: 기사에서 구체적인 업계 어려움 파악
- **자연스러운 연결**: 억지스러운 솔루션 연결 대신 논리적 접근
- **개인화 극대화**: 회사명, 대표자명, 업종별 맞춤 메시지

### 개선된 복사 기능
- HTML 태그가 제거된 순수 텍스트로 복사
- 줄바꿈과 서식이 자연스럽게 보존
- 이메일 클라이언트에서 바로 사용 가능한 형태로 제공

## 기술 스택

- **Backend**: Python Flask, Google Gemini 2.5 Pro API, Perplexity AI API
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5
- **AI/ML**: Google Generative AI, Perplexity Sonar Pro
- **데이터 처리**: Pandas, BeautifulSoup4, Requests
- **웹 스크래핑**: BeautifulSoup4, Selenium, Requests (뉴스 기사 분석용)
- **캐시 시스템**: 메모리 + 파일 기반 회사 정보 캐시

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

### 기본 사용법
1. **브라우저 접속**: http://localhost:8000
2. **CSV 파일 업로드**: 회사명, 홈페이지링크 등 포함
3. **메일 문안 생성**: "메일 문안 생성하기" 버튼 클릭
4. **결과 확인**: 4가지 스타일의 개인화 이메일 확인
5. **활용**: 텍스트 복사, HTML 변환, AI 개선 기능 사용

### 🆕 뉴스 기사 분석 기능 사용법

#### 📰 직접 뉴스 분석 (권장)
1. **뉴스 분석 탭** 클릭
2. **뉴스 URL 입력**: 조선일보, 중앙일보 등 주요 언론사 기사 URL
3. **회사명 입력**: 분석 대상 회사명 (기존 조사 결과 자동 연동)
4. **자동 처리**: 
   - 기사 스크래핑 (BeautifulSoup + Selenium)
   - 관련성 점수 계산 (0-10점)
   - 회사 정보 캐시 조회
   - Perplexity 추가 분석 (선택적)
5. **개인화 메일 생성**: Gemini AI가 모든 정보를 종합하여 생성

#### 🔄 기존 메일 개선 방식
1. **메일 생성 후** 원하는 메일의 "개선 요청" 버튼 클릭
2. **뉴스 URL 포함** 입력 예시:
   ```
   https://www.chosun.com/economy/2024/09/17/fintech-trend
   이 기사를 바탕으로 더 설득력 있는 메일을 작성해주세요
   ```
3. **자동 분석**: 시스템이 URL을 감지하고 기사 내용을 자동 분석
4. **관련성 검증**: 기사와 PortOne 솔루션의 연관성 자동 판단
5. **맞춤 메일 생성**: 관련성에 따라 자연스럽거나 직접적인 접근 방식 선택

### 💡 개선 요청 팁
- **일반 개선**: "제목을 더 임팩트있게 바꿔주세요"
- **톤 변경**: "친근한 톤으로 바꾸고 기술 수치는 줄여주세요"
- **뉴스 기반**: 뉴스 URL + 구체적 요청사항 조합

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

## 🔗 API 엔드포인트

### 기본 기능
- `POST /api/research-company`: 회사 정보 조사
- `POST /api/generate-email`: 이메일 생성
- `POST /api/batch-process`: 일괄 처리
- `POST /api/refine-email`: 이메일 개선

### 🆕 뉴스 분석 기능
- `POST /api/analyze-news`: 뉴스 기사 분석 및 메일 생성
- `POST /api/test-scraping`: 뉴스 스크래핑 테스트
- `GET /api/health`: 서비스 상태 확인

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

### 🔧 추가 의존성 설치 (뉴스 분석용)

```bash
# Selenium 웹드라이버 설치 (동적 사이트 스크래핑용)
pip install selenium

# Chrome 드라이버 설치 (macOS)
brew install chromedriver

# 또는 수동 설치
# https://chromedriver.chromium.org/downloads
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

### 뉴스 스크래핑 실패
```bash
# Chrome 브라우저 설치 확인
google-chrome --version

# ChromeDriver 경로 확인
which chromedriver

# Selenium 재설치
pip uninstall selenium
pip install selenium
```

### API 키 오류
- `.env` 파일에 올바른 API 키가 설정되어 있는지 확인
- API 키에 충분한 크레딧이 있는지 확인
- Gemini API 키: https://makersuite.google.com/app/apikey
- Perplexity API 키: https://www.perplexity.ai/settings/api

### 관련성 점수가 낮게 나오는 경우
- 기사 내용이 PortOne 솔루션과 관련성이 낮을 수 있음
- 시스템이 자동으로 자연스러운 접근 방식으로 전환됨
- 더 관련성 높은 핀테크/결제 관련 기사 사용 권장

## 📞 지원

문제가 발생하면 다음을 확인해주세요:
1. Python 3.7+ 설치 여부
2. 필요한 패키지 설치: `pip install -r requirements.txt`
3. API 키 설정 상태
4. 네트워크 연결 상태
5. Chrome 브라우저 및 ChromeDriver 설치 (뉴스 분석용)

## 📈 성능 최적화

### 뉴스 분석 성능
- **캐시 활용**: 동일 회사 24시간 내 재분석 시 캐시 데이터 사용
- **관련성 검증**: 불필요한 Selenium 실행 방지
- **병렬 처리**: 여러 기사 동시 분석 가능

### 메모리 관리
- **자동 정리**: Selenium 드라이버 자동 종료
- **캐시 제한**: 파일 캐시 24시간 자동 만료
- **로그 관리**: 상세한 디버그 로그로 문제 추적

---

**PortOne Team** | 결제 인프라의 혁신을 이끌어갑니다 🚀

## 🔄 업데이트 로그

### v2.1.0 (2025-09-17) - 뉴스 분석 기능 추가
- ✅ 고급 뉴스 기사 스크래핑 시스템 (BeautifulSoup + Selenium)
- ✅ 관련성 검증 알고리즘 (0-10점 스코어링)
- ✅ 회사 정보 캐시 시스템 (24시간 메모리+파일 캐시)
- ✅ Pain Point 중심 개인화 메일 생성
- ✅ 조선일보, 중앙일보 등 주요 언론사 최적화
- ✅ 억지 연결 방지 및 자연스러운 접근 방식
