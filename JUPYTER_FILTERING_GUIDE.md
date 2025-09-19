# 📊 주피터 노트북 데이터 필터링 가이드

## 🎯 개요
이 가이드는 서울성남 통신판매사업자 데이터를 주피터 노트북으로 효과적으로 필터링하고 분석하는 방법을 설명합니다.

## 📁 파일 구조
```
email-copywriting-chatbot/
├── data_filtering.ipynb              # 기본 데이터 분석 노트북
├── advanced_filtering.ipynb          # 고급 필터링 시스템
├── interactive_filtering_examples.ipynb  # 실제 사용 예제
├── data_integration_utils.py         # 앱 연동 유틸리티
└── requirements.txt                  # 필요한 패키지 목록
```

## 🚀 시작하기

### 1. 환경 설정
```bash
# 필요한 패키지 설치
pip install -r requirements.txt

# 주피터 노트북 실행
jupyter notebook
```

### 2. 데이터 경로 설정
각 노트북에서 다음 경로를 확인하고 수정하세요:
```python
data_path = '/Users/milo/Desktop/ocean/영중소구간필터링/202508최종취합/서울성남_통신판매사업자_완전통합.csv'
```

## 📋 주요 기능

### 🎯 1. 기본 데이터 분석 (`data_filtering.ipynb`)
- 데이터 로드 및 기본 정보 확인
- 결측값 및 중복값 분석
- 데이터 품질 평가

### 🔧 2. 고급 필터링 시스템 (`advanced_filtering.ipynb`)
```python
# 필터 객체 생성
filter_obj = DataFilter(df)

# 체이닝 방식으로 필터링
result = filter_obj.filter_by_region(['성남시']) \
                  .filter_by_business_type(['법인']) \
                  .exclude_invalid_emails() \
                  .get_results()
```

**주요 필터링 메서드:**
- `filter_by_region()`: 지역별 필터링
- `filter_by_business_type()`: 법인구분별 필터링 (개인/법인)
- `filter_by_email_domain()`: 이메일 도메인별 필터링
- `filter_by_website_platform()`: 웹사이트 플랫폼별 필터링
- `exclude_invalid_emails()`: 유효하지 않은 이메일 제외
- `filter_by_registration_date()`: 신고일자별 필터링

### 📊 3. 실제 사용 예제 (`interactive_filtering_examples.ipynb`)

#### 시나리오 1: 이메일 마케팅 타겟 추출
```python
def get_valid_email_targets(df):
    return df[
        (df['전자우편'].notna()) & 
        (df['전자우편'] != '') &
        (~df['전자우편'].str.contains('\\*', na=False)) &
        (df['업소상태'] == '정상영업')
    ]
```

#### 시나리오 2: 플랫폼별 분류
- 네이버 스마트스토어
- 쿠팡 마켓플레이스
- 자체 웹사이트
- 기타 플랫폼

#### 시나리오 3: 법인 vs 개인사업자 분석
- 법인구분별 통계
- 시각화 차트
- 크로스탭 분석

## 🔗 앱 연동 방법

### 1. 데이터 연동 유틸리티 사용
```python
from data_integration_utils import DataIntegrationUtils

# 유틸리티 객체 생성
utils = DataIntegrationUtils()

# 법인만 필터링
corporate_data = utils.filter_by_business_type(['법인'])

# 앱 연동용 JSON 파일 생성
utils.save_for_app_integration(corporate_data, 'corporate_targets.json')
```

### 2. 생성된 파일 활용
- `corporate_targets.json`: 앱에서 직접 로드 가능한 JSON 형식
- `corporate_targets.csv`: 추가 분석용 CSV 형식

## 📈 실제 사용 시나리오

### 🎯 시나리오 A: 법인 고객 타겟팅
```python
# 1. 법인만 필터링
corporate_targets = utils.filter_by_business_type(['법인'])

# 2. 자체 웹사이트를 가진 법인만 추출
website_corporates = utils.filter_by_platform(['자체웹사이트'])

# 3. 결과 저장
utils.save_for_app_integration(website_corporates, 'premium_targets.json')
```

### 🛍️ 시나리오 B: 이커머스 플랫폼 분석
```python
# 네이버 스마트스토어 운영 업체
naver_stores = filter_obj.filter_by_website_platform(['네이버', 'smartstore'])

# 쿠팡 입점 업체
coupang_stores = filter_obj.filter_by_website_platform(['쿠팡'])

# 플랫폼별 비교 분석
platform_comparison = pd.concat([
    naver_stores.assign(플랫폼='네이버'),
    coupang_stores.assign(플랫폼='쿠팡')
])
```

### 📧 시나리오 C: 이메일 마케팅 캠페인 준비
```python
# 1. 유효한 이메일 보유 업체만 추출
email_targets = get_valid_email_targets(df)

# 2. 도메인별 분류 (gmail, naver, 기업 도메인 등)
gmail_users = filter_obj.filter_by_email_domain(['gmail.com'])
naver_users = filter_obj.filter_by_email_domain(['naver.com'])

# 3. 캠페인별 타겟 리스트 생성
utils.save_for_app_integration(gmail_users, 'gmail_campaign.json')
utils.save_for_app_integration(naver_users, 'naver_campaign.json')
```

## 🔍 고급 분석 팁

### 1. 데이터 품질 체크
```python
# 이메일 유효성 검사
valid_emails = df[df['전자우편'].str.contains('@', na=False)]
masked_emails = df[df['전자우편'].str.contains('\\*', na=False)]

print(f"유효한 이메일: {len(valid_emails):,}개")
print(f"마스킹된 이메일: {len(masked_emails):,}개")
```

### 2. 시계열 분석
```python
# 신고일자별 등록 추이
df['신고일자'] = pd.to_datetime(df['신고일자'], format='%Y%m%d')
monthly_registrations = df.groupby(df['신고일자'].dt.to_period('M')).size()
monthly_registrations.plot(kind='line', title='월별 신규 등록 추이')
```

### 3. 지역별 분석
```python
# 지역별 업체 분포
region_stats = df.groupby('지역').agg({
    '상호': 'count',
    '법인구분': lambda x: (x == '법인').sum(),
    '전자우편': lambda x: x.notna().sum()
}).rename(columns={
    '상호': '총업체수',
    '법인구분': '법인수',
    '전자우편': '이메일보유수'
})
```

## ⚠️ 주의사항

1. **개인정보 보호**: 실제 이메일 주소와 전화번호는 마케팅 동의를 받은 경우에만 사용
2. **데이터 최신성**: 정기적으로 최신 데이터로 업데이트 필요
3. **필터링 검증**: 필터링 결과는 항상 샘플링하여 검증
4. **백업**: 원본 데이터는 항상 백업 보관

## 🆘 문제 해결

### 자주 발생하는 오류
1. **한글 인코딩 오류**: `encoding='utf-8-sig'` 사용
2. **메모리 부족**: 큰 데이터셋은 청크 단위로 처리
3. **날짜 형식 오류**: `pd.to_datetime()` 사용 시 format 명시

### 성능 최적화
```python
# 큰 데이터셋 처리 시
chunk_size = 10000
for chunk in pd.read_csv(data_path, chunksize=chunk_size):
    # 청크별 처리
    processed_chunk = process_chunk(chunk)
```

## 📞 지원

추가 질문이나 기능 요청이 있으시면 이슈를 등록해주세요.

---
**마지막 업데이트**: 2024년 9월 19일
