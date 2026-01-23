# CSV 열 이름 동적 매핑 시스템 업그레이드

## 📋 변경 개요

CSV 열 이름이 변경되어도 올바르게 메일이 생성될 수 있도록 동적 열 매핑 시스템을 구현했습니다.

## 🆕 새로운 열 구조 지원

기존 열 구조와 새로운 열 구조 모두 지원합니다:

| 표준 필드 | 기존 열 이름 | 새로운 열 이름 |
|----------|-------------|---------------|
| company_name | 회사명 | 회사명 |
| business_number | 사업자번호 | 사업자등록번호 |
| contact_name | 대표자명, CEO명 | 담당자명 |
| contact_position | 직책, 직급 | 직책 |
| email | 이메일 | 대표이메일 |
| homepage | 홈페이지링크, 대표홈페이지 | 홈페이지 |
| phone | - | 전화번호 |
| news_url | 관련뉴스 | 관련뉴스 |
| revenue | - | 매출액 |
| sales_point | 세일즈포인트 | 세일즈포인트 |
| hosting | - | 호스팅사 |
| pg_provider | - | 사용PG |
| competitor | 경쟁사 | 경쟁사명 |
| email_salutation | - | 이메일 호칭 |
| sales_item | sales_item | sales_item |
| service_type | - | 서비스유형 |
| customer_type | - | 고객유형 |

## 📁 수정된 파일

### 1. `column_mapper.py` (신규 생성)
- **COLUMN_ALIASES**: 표준 필드명 → 가능한 열 이름 변형들 매핑
- **get_column_value()**: 유연한 열 값 추출 함수
- **개별 추출 함수들**: `get_company_name()`, `get_email()`, `get_homepage()` 등
- **get_additional_info()**: 회사 조사에 필요한 추가 정보 표준화

### 2. `app.py` (수정)
- column_mapper 모듈 import 추가
- `process_single_company()`: 동적 열 매핑 적용
- `batch_process()`: 동적 열 매핑 적용
- `generate_email_with_gemini()`: 동적 열 매핑 적용
- `_extract_personalization_elements()`: 동적 열 매핑 적용
- `generate_email_with_user_template()`: 동적 열 매핑 적용
- `generate_email_with_user_request()`: 동적 열 매핑 적용
- `refine_email_with_user_request()`: 동적 열 매핑 적용
- `refine_email()` 엔드포인트: 동적 열 매핑 적용

## 🔧 사용 방법

### 기존 방식 (하드코딩)
```python
company_name = company_data.get('회사명', '')
email = company_data.get('대표이메일', '')
```

### 새로운 방식 (동적 매핑)
```python
from column_mapper import get_company_name, get_email

company_name = get_company_name(company_data)
email = get_email(company_data)
```

## ✅ 지원되는 열 이름 변형들

각 필드는 여러 가지 열 이름을 인식합니다:

- **회사명**: 회사명, 회사이름, 업체명, 기업명, company_name, company
- **사업자번호**: 사업자등록번호, 사업자번호, 등록번호, business_number, bizno
- **담당자명**: 담당자명, 담당자, 대표자명, CEO명, 이름, contact_name, name
- **이메일**: 대표이메일, 이메일, email, 메일, 메일주소, email_address
- **홈페이지**: 홈페이지, 홈페이지링크, 대표홈페이지, 웹사이트, website, homepage, url, 사이트
- **전화번호**: 전화번호, 연락처, 대표전화, phone, tel
- **호스팅사**: 호스팅사, 호스팅, hosting, hosting_provider

## 🎯 장점

1. **열 이름 변경에 강건함**: CSV 열 이름이 바뀌어도 코드 수정 불필요
2. **하위 호환성**: 기존 CSV 파일도 그대로 사용 가능
3. **확장성**: 새로운 열 이름 변형은 `COLUMN_ALIASES`에 추가만 하면 됨
4. **유지보수성**: 한 곳에서 매핑 관리

## 📅 업데이트 날짜
2026-01-23
