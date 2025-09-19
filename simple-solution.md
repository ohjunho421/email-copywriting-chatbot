# 🚀 Apps Script 연동 해결 방법

## 문제
Apps Script는 Google 클라우드에서 실행되므로 `localhost:5001`에 접근할 수 없습니다.

## 해결 방법

### 방법 1: 공개 터널 사용 (추천)
1. **ngrok 설치 및 실행**
   ```bash
   # ngrok 다운로드 (https://ngrok.com/download)
   # 또는 직접 다운로드 후 압축 해제
   
   # 터미널에서 실행
   ./ngrok http 5001
   ```

2. **생성된 공개 URL 사용**
   - ngrok이 제공하는 `https://xxxxx.ngrok.io` URL 복사
   - Apps Script 코드에서 `localhost:5001` 대신 사용

### 방법 2: 클라우드 배포 (권장)
1. **Heroku, Railway, 또는 Vercel에 배포**
2. **공개 URL 사용**

### 방법 3: 임시 해결책 - 직접 이메일 발송
Apps Script에서 Python 서버 없이 직접 이메일 발송하도록 수정

## 즉시 사용 가능한 해결책

현재 상황에서 가장 빠른 해결책은 **Apps Script에서 직접 Claude API를 호출**하는 것입니다.
