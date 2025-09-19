# 🚀 PortOne 이메일 챗봇 & Apps Script 통합 가이드

## 📋 개요

이 가이드는 Python 기반 이메일 생성 챗봇과 Google Apps Script 콜드메일 시스템을 통합하는 방법을 설명합니다.

### 🎯 주요 기능
- **F열 기반 분기 처리**: "claude 개인화 메일" vs 기존 템플릿
- **4개 문안 생성**: OPI/재무자동화 × 전문적/호기심 유발형
- **웹 인터페이스**: 문안 선택, 편집, AI 개선 기능
- **통일된 제목**: `[PortOne] 회사명 담당자님께 전달 부탁드립니다`
- **실시간 발송**: 최종 선택된 문안으로 즉시 이메일 발송

## 🛠️ 설치 및 설정

### 1. Python 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 실제 API 키 입력
```

### 2. Google Cloud 설정

#### 2.1 서비스 계정 생성
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 선택 또는 생성
3. "IAM 및 관리자" > "서비스 계정" 이동
4. "서비스 계정 만들기" 클릭
5. 이름: `portone-email-chatbot`
6. 역할: "편집자" 또는 "Google Sheets API" 권한

#### 2.2 API 키 생성
1. 생성된 서비스 계정 클릭
2. "키" 탭 > "키 추가" > "새 키 만들기"
3. JSON 형식 선택
4. 다운로드된 파일을 `credentials.json`으로 저장

#### 2.3 Google Sheets API 활성화
1. "API 및 서비스" > "라이브러리" 이동
2. "Google Sheets API" 검색 후 활성화

### 3. Apps Script 설정

#### 3.1 기존 프로젝트에 코드 추가
1. [Google Apps Script](https://script.google.com/) 접속
2. 기존 콜드메일 프로젝트 열기
3. `apps-script-integration.js` 내용을 새 파일로 추가

#### 3.2 웹 앱 배포
1. "배포" > "새 배포" 클릭
2. 유형: "웹 앱"
3. 실행 대상: "나"
4. 액세스 권한: "모든 사용자"
5. 배포 후 URL 복사

#### 3.3 Python 챗봇 URL 설정
```javascript
// apps-script-integration.js 파일에서 수정
const CHATBOT_API_URL = 'http://your-server:5001/api/apps-script-integration';
```

## 🔄 워크플로우

### 1. 기본 사용 흐름

```mermaid
graph TD
    A[1차메일발송 버튼 클릭] --> B[F열 값 확인]
    B --> C{claude 개인화 메일?}
    C -->|Yes| D[Python 챗봇 API 호출]
    C -->|No| E[기존 템플릿 발송]
    D --> F[4개 문안 생성]
    F --> G[웹 인터페이스 표시]
    G --> H[사용자 문안 선택/편집]
    H --> I[AI 개선 (선택적)]
    I --> J[최종 발송]
    E --> K[발송 완료]
    J --> K
```

### 2. 상세 단계

#### 단계 1: 데이터 준비
- Google Sheets에 회사 정보 입력
- F열(이메일템플릿형식)에 "claude 개인화 메일" 입력
- sales_item 열에 서비스 유형 입력 (선택적)

#### 단계 2: 발송 시작
- Apps Script 메뉴에서 "1차메일 발송 (AI 개인화 포함)" 클릭
- 시스템이 F열 값에 따라 자동 분기 처리

#### 단계 3: 문안 생성 (claude 개인화 메일인 경우)
- Python 챗봇이 Perplexity로 회사 조사
- Gemini API로 4개 맞춤 문안 생성
- 웹 인터페이스 URL 생성

#### 단계 4: 문안 선택 및 편집
- 새 창에서 웹 인터페이스 열림
- 4개 문안 중 원하는 것 선택
- 실시간 편집 및 미리보기
- AI 개선 기능 활용 (선택적)

#### 단계 5: 최종 발송
- "이메일 발송하기" 버튼 클릭
- Apps Script로 콜백하여 실제 발송
- 시트에 발송 상태 자동 업데이트

## 📊 설정 옵션

### 1. 서비스별 문안 생성

| sales_item 값 | 생성되는 문안 |
|---------------|---------------|
| `opi` | OPI 전문적 + OPI 호기심 유발형 |
| `recon`, `finance`, `재무` | 재무자동화 전문적 + 재무자동화 호기심 유발형 |
| 빈 값 또는 기타 | 4개 모든 문안 |

### 2. 이메일 제목 통일

모든 "claude 개인화 메일"은 다음 형식으로 통일:
```
[PortOne] {회사명} {담당자명}께 전달 부탁드립니다
```

### 3. 환경별 설정

#### 개발 환경
```bash
FLASK_ENV=development
FLASK_DEBUG=True
```

#### 운영 환경
```bash
FLASK_ENV=production
FLASK_DEBUG=False
```

## 🧪 테스트 방법

### 1. Python 챗봇 테스트

```bash
# 서버 시작
python app.py

# API 테스트
curl -X POST http://localhost:5001/api/apps-script-integration \
  -H "Content-Type: application/json" \
  -d '{
    "company_data": {
      "회사명": "테스트회사",
      "담당자명": "김대표",
      "대표이메일": "test@example.com"
    }
  }'
```

### 2. 웹 인터페이스 테스트

1. 위 API 호출로 `interface_url` 획득
2. 브라우저에서 해당 URL 접속
3. 4개 문안 선택/편집 기능 테스트
4. AI 개선 기능 테스트

### 3. Apps Script 테스트

1. Google Sheets에 테스트 데이터 입력
2. F열에 "claude 개인화 메일" 입력
3. Apps Script 메뉴에서 발송 함수 실행
4. 웹 인터페이스 정상 작동 확인

## 🚨 문제 해결

### 1. 일반적인 오류

#### Python 챗봇 연결 실패
```javascript
// apps-script-integration.js에서 URL 확인
const CHATBOT_API_URL = 'http://localhost:5001/api/apps-script-integration';
```

#### Google Sheets API 권한 오류
- 서비스 계정에 시트 편집 권한 부여
- API 키 파일 경로 확인

#### 웹 인터페이스 로딩 실패
- 브라우저 팝업 차단 해제
- CORS 설정 확인

### 2. 로그 확인

#### Python 로그
```bash
# 터미널에서 실시간 로그 확인
tail -f app.log
```

#### Apps Script 로그
1. Apps Script 편집기에서 "실행" > "로그 보기"
2. `console.log()` 출력 확인

## 📈 성능 최적화

### 1. 캐싱 전략
- 회사 조사 결과 24시간 캐싱
- 이메일 템플릿 메모리 캐싱

### 2. 배치 처리
- 대량 발송 시 배치 단위로 처리
- Rate limiting 적용

### 3. 모니터링
- 발송 성공률 추적
- API 응답 시간 모니터링

## 🔒 보안 고려사항

### 1. API 키 관리
- 환경변수로 API 키 관리
- 정기적인 키 로테이션

### 2. 데이터 보호
- 개인정보 암호화 저장
- 로그에서 민감 정보 제외

### 3. 접근 제어
- Apps Script 실행 권한 제한
- 웹 인터페이스 세션 관리

## 📞 지원

문제가 발생하거나 추가 기능이 필요한 경우:
1. GitHub Issues 등록
2. 로그 파일 첨부
3. 재현 단계 상세 기술

---

**🎉 축하합니다! 이제 AI 기반 개인화 이메일 시스템이 준비되었습니다.**
