# 📰 PortOne 블로그 자동 스크랩핑 및 이메일 통합 가이드

## 🎯 개요

PortOne 블로그의 최신 콘텐츠를 자동으로 스크랩핑하고, 업종별로 매칭하여 이메일 생성 시 활용하는 시스템입니다.

### 주요 기능

1. **자동 블로그 스크랩핑**
   - 하루 2번 (오전 9시, 오후 6시) 자동 업데이트
   - 국내 결제(OPI) 관련 글: 5페이지
   - 매출 마감(Recon) 관련 글: 1페이지

2. **업종별 자동 매칭**
   - 게임, 이커머스, 여행, 교육, 금융, 미디어, SaaS, 물류 등
   - 회사 정보 기반 관련 블로그 자동 조회

3. **이메일 자동 통합**
   - 메일 생성 시 관련 블로그 자동 활용
   - 업종에 맞는 맞춤형 콘텐츠 제공

---

## 🚀 설치 및 설정

### 1. 필수 패키지 설치

```bash
pip install -r requirements.txt
```

새로 추가된 패키지:
- `APScheduler==3.10.4` - 자동 스케줄링

### 2. 데이터베이스 초기화

서버를 처음 시작하면 자동으로 `portone_blog.db` 파일이 생성됩니다.

```bash
python app.py
```

### 3. 초기 블로그 데이터 수집

**방법 1: API 호출 (권장)**

```bash
curl -X POST http://localhost:8000/api/init-blog
```

**방법 2: 테스트 스크립트 실행**

```bash
python test_blog_scraping.py
```

---

## 📊 데이터베이스 구조

### blog_posts 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | 자동 증가 ID |
| title | TEXT | 블로그 글 제목 |
| link | TEXT | 블로그 글 URL (UNIQUE) |
| summary | TEXT | 요약 (앞 200자) |
| content | TEXT | 전체 내용 (최대 5000자) |
| category | TEXT | 카테고리 (OPI, Recon) |
| **keywords** | TEXT | 자동 추출 키워드 (결제, 정산, 자동화 등) |
| **industry_tags** | TEXT | 업종 태그 (게임, 이커머스, 여행 등) |
| created_at | TIMESTAMP | 생성 시간 |
| updated_at | TIMESTAMP | 업데이트 시간 |

---

## 🔄 자동 업데이트 시스템

### 스케줄러 설정

```python
# app.py에 자동 구성됨
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scheduled_blog_update,
    trigger=CronTrigger(hour='9,18', minute='0'),
    id='blog_update_job',
    name='블로그 자동 업데이트'
)
scheduler.start()
```

### 실행 시간
- **오전 9:00** - 첫 번째 업데이트
- **오후 18:00** - 두 번째 업데이트

### 업데이트 조건
- 캐시 나이가 12시간 이상일 때만 스크랩핑
- 최신 상태면 스킵

---

## 🎨 업종별 키워드 매칭

### 자동 인식 업종

| 업종 | 키워드 |
|------|--------|
| 게임 | 게임, game, 모바일게임 |
| 이커머스 | 이커머스, e커머스, 쇼핑몰, commerce |
| 여행 | 여행, travel, 항공 |
| 교육 | 교육, education, 에듀테크 |
| 금융 | 금융, fintech, 핀테크 |
| 미디어 | 미디어, media, 콘텐츠 |
| SaaS | saas, 구독 |
| 물류 | 물류, logistics, 배송 |

### 기능 키워드

- 결제 (payment)
- 매출관리 (reconciliation)
- 자동화 (automation)
- PG (간편결제)
- 글로벌 (global, 해외)
- 정기결제 (subscription)

---

## 💻 API 엔드포인트

### 1. 블로그 초기 데이터 수집

```bash
POST /api/init-blog
```

**응답 예시:**
```json
{
  "success": true,
  "message": "블로그 초기 데이터 수집 완료",
  "posts_count": 45,
  "timestamp": "2025-10-21T14:03:00"
}
```

### 2. 블로그 수동 업데이트

```bash
POST /api/update-blog
```

**응답 예시:**
```json
{
  "success": true,
  "message": "블로그 업데이트 완료",
  "posts_count": 48,
  "timestamp": "2025-10-21T14:05:00"
}
```

### 3. 블로그 캐시 상태 확인

```bash
GET /api/blog-cache-status
```

**응답 예시:**
```json
{
  "success": true,
  "cache_exists": true,
  "posts_count": 45,
  "cache_age_hours": 2.5,
  "last_updated": "2025-10-21T11:30:00",
  "needs_update": false
}
```

---

## 🔧 주요 함수 사용법

### 1. 업종별 블로그 조회

```python
from portone_blog_cache import get_relevant_blog_posts_by_industry

# 회사 정보
company_info = {
    'industry': '게임',
    'category': '모바일게임',
    'description': '모바일 게임 개발 및 퍼블리싱'
}

# 관련 블로그 조회 (최대 3개)
relevant_blogs = get_relevant_blog_posts_by_industry(company_info, max_posts=3)

# 결과
for blog in relevant_blogs:
    print(f"제목: {blog['title']}")
    print(f"업종태그: {blog['industry_tags']}")
    print(f"키워드: {blog['keywords']}")
    print(f"링크: {blog['link']}")
```

### 2. 이메일용 포맷팅

```python
from portone_blog_cache import format_relevant_blog_for_email

# 블로그를 이메일용으로 포맷팅
formatted_text = format_relevant_blog_for_email(
    relevant_blogs,
    company_name='게임회사'
)

# Gemini 프롬프트에 추가
prompt = f"""
{company_info}
{formatted_text}

위 블로그 내용을 참고하여 이메일 작성...
"""
```

### 3. 수동 키워드 추출

```python
from portone_blog_cache import extract_keywords_from_post

post = {
    'title': '게임 업계를 위한 글로벌 결제 솔루션',
    'content': '모바일 게임 회사들이 해외 진출 시...'
}

keywords, industry_tags = extract_keywords_from_post(post)
print(f"키워드: {keywords}")  # 결제,글로벌,PG
print(f"업종: {industry_tags}")  # 게임
```

---

## 📧 이메일 통합 예시

### 자동 통합 (기본 동작)

```python
# app.py의 generate_email_with_gemini_and_cases 함수
# 자동으로 업종별 블로그 조회 및 통합됨

result = generate_email_with_gemini_and_cases(
    company_data={'회사명': '게임회사', '업종': '게임'},
    research_data={'company_info': '...'}
)
```

### 생성된 이메일 예시

```
안녕하세요, 게임회사 대표님.
PortOne 오준호 매니저입니다.

최근 포트원 블로그에서 "게임 업계의 글로벌 결제 트렌드" 글을 보셨나요?
많은 게임사들이 해외 진출 시 결제 시스템 구축에 어려움을 겪고 계십니다.

게임회사도 해외 진출을 준비 중이신 것으로 알고 있는데,
글로벌 PG 연동과 정산 자동화가 필요하지 않으신가요?

[본문 계속...]
```

---

## 🧪 테스트

### 전체 시스템 테스트

```bash
python test_blog_scraping.py
```

**테스트 항목:**
1. ✅ 데이터베이스 초기화
2. ✅ 블로그 스크랩핑 (OPI 5페이지, Recon 1페이지)
3. ✅ 캐시 로드 및 나이 확인
4. ✅ 업종별 블로그 매칭 (게임, 이커머스, 여행)
5. ✅ 키워드 자동 추출

### 예상 출력

```
🚀 포트원 블로그 시스템 통합 테스트 시작
============================================================
1. 데이터베이스 초기화 테스트
✅ 데이터베이스 초기화 성공

2. 블로그 스크랩핑 테스트
📰 [OPI] 스크래핑 시작...
   페이지 1/5 스크래핑...
      ✅ 게임 업계를 위한 결제 솔루션...
✅ 블로그 스크랩핑 성공: 45개 글

3. 블로그 캐시 로드 테스트
✅ 캐시 로드 성공: 45개 글
📅 캐시 나이: 0.05시간

4. 업종별 블로그 매칭 테스트
🔍 테스트: 게임 회사
   ✅ 관련 블로그 3개 발견
      - 게임 업계 결제 시스템 가이드
        업종태그: 게임
   📧 이메일 포맷팅 완료 (523 자)

✅ 모든 테스트 완료!
```

---

## 🔍 문제 해결

### 1. 스크랩핑 실패

**증상:** `스크래핑된 글이 없습니다`

**해결책:**
```python
# 1. 네트워크 확인
curl https://blog.portone.io

# 2. User-Agent 확인 (app.py에서)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

# 3. 타임아웃 조정
response = requests.get(url, headers=headers, timeout=30)
```

### 2. 키워드 매칭 안됨

**증상:** 게임 회사인데 관련 블로그가 안 나옴

**해결책:**
```python
# portone_blog_cache.py의 extract_keywords_from_post 함수에 키워드 추가
if '신규키워드' in text_lower:
    industry_tags.append('업종명')
```

### 3. 스케줄러 미작동

**증상:** 9시, 18시에 자동 업데이트 안됨

**확인:**
```python
# 서버 로그 확인
⏰ 블로그 자동 업데이트 스케줄러 시작됨 (매일 9시, 18시 실행)

# 수동 테스트
from app import scheduled_blog_update
scheduled_blog_update()
```

### 4. 캐시 업데이트 너무 자주

**증상:** 매번 스크랩핑 실행

**해결책:**
```python
# app.py의 scheduled_blog_update 함수에서 조건 확인
if cache_age is None or cache_age >= 12:  # 12시간 이상일 때만
    blog_posts = scrape_portone_blog_initial()
```

---

## 📈 모니터링

### 캐시 상태 확인

```bash
# API로 확인
curl http://localhost:8000/api/blog-cache-status

# 직접 DB 확인
sqlite3 portone_blog.db "SELECT COUNT(*) FROM blog_posts"
sqlite3 portone_blog.db "SELECT title, category, industry_tags FROM blog_posts LIMIT 5"
```

### 로그 모니터링

```bash
# 서버 실행 시 로그 확인
python app.py 2>&1 | grep "블로그"

# 주요 로그 메시지
📰 [회사명]: 관련 블로그 3개 조회됨
📚 업종별 블로그 콘텐츠 사용 완료
⏰ 스케줄 블로그 업데이트 시작
✅ 자동 블로그 업데이트 완료: 45개 글
```

---

## 🎯 활용 팁

### 1. 특정 업종 키워드 강화

업종별 인식률을 높이려면 `portone_blog_cache.py`의 `extract_keywords_from_post` 함수에 키워드를 추가하세요.

### 2. 블로그 수동 업데이트

중요한 블로그 글이 새로 올라왔을 때:
```bash
curl -X POST http://localhost:8000/api/update-blog
```

### 3. 이메일 프롬프트 최적화

관련 블로그가 있을 때 더 강하게 활용하도록 프롬프트를 수정하세요:

```python
context = f"""
{blog_content}

⚠️ 위 블로그 콘텐츠는 {company_name}의 업종에 맞춰 선별된 최신 정보입니다.
이메일 작성 시 반드시 자연스럽게 언급하세요.
"""
```

---

## 📚 참고 자료

### 스크랩핑 대상 URL
- OPI (국내 결제): `https://blog.portone.io/?filter=%EA%B5%AD%EB%82%B4%20%EA%B2%B0%EC%A0%9C`
- Recon (매출 마감): `https://blog.portone.io/?filter=%EB%A7%A4%EC%B6%9C%20%EB%A7%88%EA%B0%90`

### 주요 파일
- `portone_blog_cache.py` - 블로그 DB 관리
- `portone_blog.db` - SQLite 데이터베이스
- `app.py` - 메인 서버 및 스케줄러
- `test_blog_scraping.py` - 테스트 스크립트

---

## ✅ 체크리스트

시스템이 정상 작동하는지 확인:

- [ ] `pip install -r requirements.txt` 완료
- [ ] 서버 시작 시 "⏰ 블로그 자동 업데이트 스케줄러 시작됨" 로그 확인
- [ ] `/api/init-blog` 또는 `test_blog_scraping.py` 실행
- [ ] `/api/blog-cache-status`로 캐시 확인
- [ ] 이메일 생성 시 "📰 관련 블로그 X개 조회됨" 로그 확인
- [ ] 생성된 이메일에 블로그 관련 내용 포함 확인

---

## 🎉 완료!

이제 PortOne 블로그의 최신 콘텐츠가 자동으로 수집되고, 업종에 맞춰 이메일에 자연스럽게 통합됩니다.

**문의사항이나 개선사항이 있으면 언제든지 알려주세요!** 🚀
