# ✅ 배포/전달 체크리스트

다른 컴퓨터나 팀원에게 프로젝트를 전달할 때 확인해야 할 사항들입니다.

## 📦 전달 전 체크리스트

### 1. 파일 정리
- [ ] `.env` 파일은 **절대 포함하지 않기** (보안)
- [ ] `.env.example` 파일은 포함하기
- [ ] `README.md` 최신 버전 확인
- [ ] `requirements.txt` 최신 버전 확인
- [ ] 불필요한 캐시 파일 제거 (`__pycache__`, `.pyc`)

### 2. 문서 확인
- [ ] `README.md` - 프로젝트 개요 및 사용법
- [ ] `INSTALLATION_GUIDE.md` - 상세 설치 가이드
- [ ] `requirements.txt` - Python 의존성 목록
- [ ] `.env.example` - 환경 변수 샘플

### 3. 제외해야 할 파일/폴더
```
.env                    # 실제 API 키 포함
.venv/                  # 가상환경
__pycache__/            # Python 캐시
*.pyc                   # 컴파일된 Python
.DS_Store               # macOS 시스템 파일
*.log                   # 로그 파일
cache/                  # 캐시 데이터
```

### 4. 포함해야 할 파일
```
app.py                  # 메인 백엔드
ssr_engine.py           # SSR 엔진
case_database.py        # 사례 데이터베이스
requirements.txt        # 의존성 목록
.env.example            # 환경 변수 샘플
README.md               # 프로젝트 설명
INSTALLATION_GUIDE.md   # 설치 가이드
start.sh                # 시작 스크립트 (Unix)
start.bat               # 시작 스크립트 (Windows)
templates/              # HTML 템플릿
static/                 # CSS, JS, 이미지
```

## 📤 전달 방법

### 방법 1: Git 저장소
```bash
# .gitignore 확인
cat .gitignore

# Git 저장소 초기화 (아직 안 했다면)
git init
git add .
git commit -m "Initial commit"

# 원격 저장소에 푸시
git remote add origin <repository-url>
git push -u origin main
```

**전달 방법:**
1. 저장소 URL 공유
2. 받는 사람이 `git clone` 실행

### 방법 2: 압축 파일
```bash
# 프로젝트 루트에서
cd ..
zip -r email-copywriting-chatbot.zip email-copywriting-chatbot \
  -x "*.pyc" \
  -x "*__pycache__*" \
  -x "*.env" \
  -x "*/.venv/*" \
  -x "*/cache/*" \
  -x "*/.DS_Store"
```

**전달 방법:**
1. 생성된 ZIP 파일 전송 (이메일, 클라우드 등)
2. 받는 사람이 압축 해제 후 INSTALLATION_GUIDE.md 참고

## 📋 받는 사람에게 전달할 정보

### 필수 정보
```
1. API 키 발급 방법
   - Gemini: https://makersuite.google.com/app/apikey
   - Perplexity: https://www.perplexity.ai/settings/api

2. Python 버전: 3.10 이상

3. 필수 설치 항목:
   - Python 3.10+
   - pip
   - (선택) ChromeDriver

4. 문서 참고:
   - INSTALLATION_GUIDE.md: 상세 설치 가이드
   - README.md: 기능 및 사용법
```

### 전달 메시지 템플릿
```
안녕하세요,

PortOne 이메일 생성 챗봇 프로젝트를 전달합니다.

📦 설치 방법:
1. INSTALLATION_GUIDE.md 파일을 먼저 읽어주세요
2. Python 3.10 이상 필요
3. API 키 2개 발급 필요 (Gemini, Perplexity)
4. requirements.txt로 의존성 설치

🔑 API 키 발급:
- Gemini: https://makersuite.google.com/app/apikey
- Perplexity: https://www.perplexity.ai/settings/api

❓ 문제 발생 시:
INSTALLATION_GUIDE.md의 "문제 해결" 섹션 참고

감사합니다!
```

## 🔒 보안 체크리스트

### 전달 전 확인
- [ ] `.env` 파일이 제외되었는지 확인
- [ ] 코드에 하드코딩된 API 키가 없는지 확인
- [ ] 민감한 로그 파일이 포함되지 않았는지 확인
- [ ] 고객 데이터나 테스트 CSV가 포함되지 않았는지 확인

### .gitignore 확인
프로젝트에 `.gitignore` 파일이 있는지 확인하고, 다음 내용이 포함되어 있어야 합니다:

```gitignore
# 환경 변수
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# 캐시 및 로그
cache/
*.log
*.cache

# 사용자 데이터
*.csv
!example.csv
uploads/
results/
```

## 🧪 전달 후 테스트

### 받는 사람이 확인할 사항
```bash
# 1. Python 버전 확인
python3 --version

# 2. 의존성 설치 확인
pip list | grep flask
pip list | grep google-generativeai

# 3. 환경 변수 확인
cat .env  # API 키가 설정되어 있는지

# 4. 서버 실행 테스트
./start.sh

# 5. API 연결 테스트
curl http://localhost:5001/api/health
```

## 📊 전달 완료 확인

### 체크리스트
- [ ] 받는 사람이 프로젝트를 받았는지 확인
- [ ] 설치 가이드를 전달했는지 확인
- [ ] API 키 발급 방법을 안내했는지 확인
- [ ] 테스트 실행이 성공했는지 확인
- [ ] 질문이나 문제가 없는지 확인

## 🔄 업데이트 전달

프로젝트 업데이트 시:
```bash
# Git 사용 시
git pull origin main
pip install -r requirements.txt --upgrade

# ZIP 사용 시
# 새 버전 다운로드 후
# .env 파일만 백업
# 새 파일로 덮어쓰기
# .env 파일 복원
```

---

**중요**: 절대로 `.env` 파일이나 실제 API 키를 공개 저장소나 이메일로 전송하지 마세요!
