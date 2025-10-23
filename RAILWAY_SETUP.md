# Railway 배포 가이드

## 1. PostgreSQL 데이터베이스 추가

1. Railway 프로젝트 대시보드에서 **"+ New"** 클릭
2. **"Database"** → **"Add PostgreSQL"** 선택
3. 자동으로 `DATABASE_URL` 환경변수가 생성됩니다

## 2. 환경 변수 설정

Railway 프로젝트 → Settings → Variables에서 다음 환경변수 설정:

```
SECRET_KEY=your-secret-key-here
DATABASE_URL=(PostgreSQL에서 자동 생성됨)
PERPLEXITY_API_KEY=your-perplexity-key
GEMINI_API_KEY=your-gemini-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
```

**중요:** `DATABASE_URL`은 PostgreSQL 추가시 자동으로 생성되므로 수동 설정 불필요!

## 3. 배포

Railway는 GitHub 연동시 자동 배포됩니다:

1. Git push하면 자동으로 배포 시작
2. 빌드 로그에서 "✅ 데이터베이스 초기화 완료" 확인
3. 배포 완료 후 도메인 URL로 접속

## 4. 첫 사용 (관리자 계정 생성)

1. 배포된 URL로 접속
2. **회원가입** 페이지에서 `ocean@portone.io`로 가입
3. 자동으로 관리자 권한이 부여됩니다
4. 로그인하면 **관리자 페이지** 링크가 상단에 표시됩니다

## 5. 데이터베이스 확인

Railway PostgreSQL 플러그인에서:
- **Data** 탭: 테이블 및 데이터 확인
- **Query** 탭: SQL 쿼리 실행

테이블 확인:
```sql
SELECT * FROM users;
SELECT * FROM email_generations;
```

## 6. 문제 해결

### 데이터베이스 연결 오류
- Railway에서 PostgreSQL이 추가되었는지 확인
- `DATABASE_URL` 환경변수가 자동 생성되었는지 확인

### 로그 확인
```
Railway Dashboard → Deployments → 최신 배포 → Logs
```

### 데이터베이스 초기화
Railway Shell에서:
```bash
python
>>> from app import app, db
>>> with app.app_context():
...     db.create_all()
```
