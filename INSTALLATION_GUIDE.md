# 🚀 설치 가이드 (다른 컴퓨터에서 실행하기)

이 문서는 PortOne 이메일 생성 챗봇을 처음 설치하는 분들을 위한 가이드입니다.

## 📋 사전 요구사항

- **Python 3.10 이상**
- **인터넷 연결**
- **API 키**:
  - Gemini API 키 (필수)
  - Perplexity API 키 (필수)

## 📦 1. 프로젝트 받기

### 방법 A: Git으로 받기
```bash
git clone <repository-url>
cd email-copywriting-chatbot
```

### 방법 B: 압축 파일로 받기
1. 프로젝트 압축 파일 다운로드
2. 압축 해제
3. 터미널에서 해당 폴더로 이동
```bash
cd email-copywriting-chatbot
```

## 🐍 2. Python 환경 설정

### Python 설치 확인
```bash
python3 --version
```

**최소 버전: Python 3.10**

설치되어 있지 않다면:
- **macOS**: `brew install python@3.10`
- **Windows**: https://www.python.org/downloads/
- **Linux**: `sudo apt-get install python3.10`

### 가상환경 생성 (권장)
```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
# macOS/Linux:
source .venv/bin/activate

# Windows (Command Prompt):
.venv\Scripts\activate.bat

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

가상환경이 활성화되면 프롬프트에 `(.venv)`가 표시됩니다.

## 📚 3. 라이브러리 설치

```bash
pip install -r requirements.txt
```

**설치되는 주요 라이브러리:**
- Flask (웹 프레임워크)
- google-generativeai (Gemini API)
- requests (HTTP 요청)
- beautifulsoup4 (웹 스크래핑)
- selenium (동적 웹 스크래핑)

## 🔑 4. API 키 설정

### 4-1. .env 파일 생성
```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env
```

### 4-2. API 키 발급

#### Gemini API 키 (필수)
1. https://makersuite.google.com/app/apikey 접속
2. Google 계정으로 로그인
3. "Create API Key" 클릭
4. API 키 복사

#### Perplexity API 키 (필수)
1. https://www.perplexity.ai/settings/api 접속
2. 계정 생성/로그인
3. API 키 생성
4. API 키 복사

### 4-3. .env 파일 편집
텍스트 에디터로 `.env` 파일을 열고 API 키 입력:

```env
GEMINI_API_KEY=실제-gemini-api-키
PERPLEXITY_API_KEY=실제-perplexity-api-키
FLASK_ENV=development
FLASK_DEBUG=True
```

⚠️ **주의**: API 키는 절대 공개 저장소에 올리지 마세요!

## 🌐 5. ChromeDriver 설치 (선택사항)

뉴스 기사 스크래핑 기능을 사용하려면 ChromeDriver가 필요합니다.

### macOS
```bash
brew install chromedriver
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install chromium-chromedriver
```

### Windows
1. Chrome 브라우저 설치
2. https://chromedriver.chromium.org/downloads 에서 Chrome 버전에 맞는 드라이버 다운로드
3. 다운로드한 `chromedriver.exe`를 PATH에 추가

**ChromeDriver 설치 확인:**
```bash
chromedriver --version
```

## ▶️ 6. 실행

### 방법 1: 자동 실행 스크립트 (권장)

**macOS/Linux:**
```bash
# 실행 권한 부여 (최초 1회만)
chmod +x start.sh

# 서버 실행
./start.sh
```

**Windows:**
```cmd
start.bat
```

### 방법 2: 수동 실행

**터미널 1 - 백엔드:**
```bash
python3 app.py
```

**터미널 2 - 프론트엔드:**
```bash
python3 -m http.server 8000
```

## 🌐 7. 접속

브라우저에서 http://localhost:8000 접속

성공하면 이메일 생성 챗봇 UI가 표시됩니다! 🎉

## 🧪 8. 테스트

### 간단한 테스트
1. CSV 파일 준비 (회사명, 홈페이지링크 포함)
2. 파일 업로드
3. "메일 문안 생성하기" 클릭
4. 생성된 이메일 확인

### API 연결 테스트
```bash
# 백엔드 서버가 실행 중인 상태에서
curl http://localhost:5001/api/health
```

정상 응답:
```json
{
  "status": "healthy",
  "timestamp": "..."
}
```

## 🚨 문제 해결

### 문제 1: 포트가 이미 사용 중
```bash
# 사용 중인 프로세스 확인
lsof -i :5001
lsof -i :8000

# 프로세스 종료
kill -9 <PID>
```

### 문제 2: API 키 오류
- `.env` 파일이 프로젝트 루트에 있는지 확인
- API 키에 따옴표가 없는지 확인
- API 키가 유효한지 확인 (웹사이트에서 재발급)

### 문제 3: Python 패키지 설치 오류
```bash
# pip 업그레이드
pip install --upgrade pip

# 재설치
pip install -r requirements.txt --force-reinstall
```

### 문제 4: ChromeDriver 오류
```bash
# macOS에서 보안 오류 발생 시
xattr -d com.apple.quarantine /usr/local/bin/chromedriver
```

### 문제 5: 가상환경 활성화 오류 (Windows PowerShell)
```powershell
# PowerShell 실행 정책 변경 (관리자 권한)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📞 추가 도움

문제가 계속되면 다음을 확인하세요:
1. Python 버전이 3.10 이상인지
2. 모든 의존성이 설치되었는지
3. API 키가 올바르게 설정되었는지
4. 방화벽이 5001, 8000 포트를 차단하지 않는지

## 🔄 업데이트

프로젝트를 최신 버전으로 업데이트하려면:

```bash
# Git 사용 시
git pull origin main

# 의존성 업데이트
pip install -r requirements.txt --upgrade
```

---

설치 완료! 이제 PortOne 이메일 생성 챗봇을 사용할 수 있습니다. 🚀
