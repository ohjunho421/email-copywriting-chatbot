"""
CSV 열 이름 동적 매핑 유틸리티

열 이름이 변경되어도 올바르게 데이터를 추출할 수 있도록 
유연한 매핑 시스템을 제공합니다.
"""

# 표준 필드명 → 가능한 열 이름 변형들
COLUMN_ALIASES = {
    # 회사 기본 정보
    'company_name': ['회사명', '회사이름', '업체명', '기업명', 'company_name', 'company'],
    'business_number': ['사업자등록번호', '사업자번호', '등록번호', 'business_number', 'bizno'],
    'customer_type': ['고객유형', '고객타입', '유형', 'customer_type'],
    
    # 담당자 정보
    'contact_name': ['담당자명', '담당자', '대표자명', 'CEO명', '이름', 'contact_name', 'name'],
    'contact_position': ['직책', '직위', '포지션', 'position', 'title'],
    'email_salutation': ['이메일 호칭', '이메일호칭', '호칭', 'salutation'],
    
    # 이메일 관련
    'email': ['대표이메일', '이메일', 'email', '메일', '메일주소', 'email_address'],
    'email_template_type': ['이메일템플릿 타입', '이메일템플릿타입', '템플릿타입', '템플릿 타입', 'template_type'],
    
    # 회사 연락처
    'homepage': ['홈페이지', '홈페이지링크', '대표홈페이지', '웹사이트', 'website', 'homepage', 'url', '사이트'],
    'phone': ['전화번호', '연락처', '대표전화', 'phone', 'tel'],
    
    # 비즈니스 정보
    'news_url': ['관련뉴스', '뉴스', '뉴스URL', 'news', 'news_url'],
    'revenue': ['매출액', '매출', '연매출', 'revenue', 'sales'],
    'sales_point': ['세일즈포인트', '세일즈 포인트', '판매포인트', 'sales_point'],
    'hosting': ['호스팅사', '호스팅', 'hosting', 'hosting_provider'],
    'pg_provider': ['사용PG', 'PG사', 'PG', 'pg_provider', 'payment_gateway'],
    'competitor': ['경쟁사명', '경쟁사', 'competitor'],
    'industry': ['업종', '업계', '산업', 'industry'],
    'company_size': ['규모', '회사규모', '직원수', 'size', 'company_size'],
    
    # 발송 관련
    'sent_status': ['발송여부', '발송', 'sent', 'sent_status'],
    'sent_date': ['발송일', '발송날짜', 'sent_date'],
    'open_count': ['오픈횟수', '열람횟수', 'open_count'],
    'first_open_time': ['최초오픈시각', '최초열람시각', 'first_open_time'],
    'reply_date': ['회신일자', '회신일', 'reply_date'],
    'recent_open_time': ['최근오픈시각', '최근열람시각', 'recent_open_time'],
    'intent_expression': ['의사표현', '의사', 'intent'],
    
    # 2차 발송 관련
    'second_sent_status': ['2차발송여부', '2차 발송여부', 'second_sent'],
    'second_sent_date': ['2차발송일', '2차 발송일', 'second_sent_date'],
    'second_open_count': ['2차 오픈횟수', '2차오픈횟수', 'second_open_count'],
    'second_first_open': ['2차 최초오픈시각', '2차최초오픈시각', 'second_first_open'],
    'second_reply_date': ['2차 회신일자', '2차회신일자', 'second_reply_date'],
    'second_recent_open': ['2차 최근오픈시각', '2차최근오픈시각', 'second_recent_open'],
    
    # 기타
    'previous_contact': ['기존컨택여부', '기존컨택', 'previous_contact'],
    'enrich_done': ['🤖_enrich_완료여부', 'enrich_완료여부', 'enrich_done'],
    'competitor_done': ['🤖_competitor_완료여부', 'competitor_완료여부', 'competitor_done'],
    'last_opportunity': ['마지막 opportunity', '마지막opportunity', 'last_opportunity'],
    'lead_time': ['리드타임', 'lead_time'],
    'fit_score': ['도입적합도', '적합도', 'fit_score'],
    'sales_item': ['sales_item', '세일즈아이템', '판매아이템'],
    'service_type': ['서비스유형', '서비스타입', 'service_type'],
}


def get_column_value(company_data: dict, field_name: str, default: str = '') -> str:
    """
    회사 데이터에서 필드 값을 유연하게 추출합니다.
    
    Args:
        company_data: 회사 데이터 딕셔너리
        field_name: 표준 필드명 (COLUMN_ALIASES의 키)
        default: 값이 없을 때 반환할 기본값
        
    Returns:
        찾은 값 또는 기본값
    """
    # 1. 표준 필드명으로 직접 매핑된 별칭 확인
    if field_name in COLUMN_ALIASES:
        for alias in COLUMN_ALIASES[field_name]:
            if alias in company_data and company_data[alias]:
                return str(company_data[alias]).strip()
    
    # 2. 필드명 자체가 데이터에 있는지 확인 (표준 필드명이 아닌 경우)
    if field_name in company_data and company_data[field_name]:
        return str(company_data[field_name]).strip()
    
    # 3. 대소문자 무시하고 부분 일치 검색
    field_lower = field_name.lower()
    for key in company_data.keys():
        if key.lower() == field_lower or field_lower in key.lower():
            if company_data[key]:
                return str(company_data[key]).strip()
    
    return default


def get_company_name(company_data: dict) -> str:
    """회사명 추출"""
    return get_column_value(company_data, 'company_name', '')


def get_business_number(company_data: dict) -> str:
    """사업자등록번호 추출"""
    return get_column_value(company_data, 'business_number', '')


def get_contact_name(company_data: dict) -> str:
    """담당자명/대표자명 추출"""
    return get_column_value(company_data, 'contact_name', '')


def get_email(company_data: dict) -> str:
    """대표이메일 추출"""
    return get_column_value(company_data, 'email', '')


def get_homepage(company_data: dict) -> str:
    """홈페이지 URL 추출"""
    return get_column_value(company_data, 'homepage', '')


def get_phone(company_data: dict) -> str:
    """전화번호 추출"""
    return get_column_value(company_data, 'phone', '')


def get_news_url(company_data: dict) -> str:
    """관련뉴스 URL 추출"""
    return get_column_value(company_data, 'news_url', '')


def get_sales_point(company_data: dict) -> str:
    """세일즈포인트 추출"""
    return get_column_value(company_data, 'sales_point', '')


def get_revenue(company_data: dict) -> str:
    """매출액 추출"""
    return get_column_value(company_data, 'revenue', '')


def get_hosting(company_data: dict) -> str:
    """호스팅사 추출"""
    return get_column_value(company_data, 'hosting', '')


def get_pg_provider(company_data: dict) -> str:
    """사용 PG 추출"""
    return get_column_value(company_data, 'pg_provider', '')


def get_competitor(company_data: dict) -> str:
    """경쟁사명 추출"""
    return get_column_value(company_data, 'competitor', '')


def get_industry(company_data: dict) -> str:
    """업종 추출"""
    return get_column_value(company_data, 'industry', '')


def get_company_size(company_data: dict) -> str:
    """회사 규모 추출"""
    return get_column_value(company_data, 'company_size', '')


def get_email_salutation(company_data: dict) -> str:
    """이메일 호칭 추출"""
    return get_column_value(company_data, 'email_salutation', '')


def get_sales_item(company_data: dict) -> str:
    """sales_item 추출"""
    return get_column_value(company_data, 'sales_item', '')


def get_service_type(company_data: dict) -> str:
    """서비스유형 추출"""
    return get_column_value(company_data, 'service_type', '')


def get_customer_type(company_data: dict) -> str:
    """고객유형 추출"""
    return get_column_value(company_data, 'customer_type', '')


def get_contact_position(company_data: dict) -> str:
    """직책 추출"""
    return get_column_value(company_data, 'contact_position', '')


def normalize_company_data(company_data: dict) -> dict:
    """
    회사 데이터를 표준 필드명으로 정규화합니다.
    원본 데이터는 유지하면서 표준 필드명으로도 접근 가능하게 합니다.
    
    Args:
        company_data: 원본 회사 데이터
        
    Returns:
        정규화된 회사 데이터 (원본 + 표준 필드명)
    """
    normalized = company_data.copy()
    
    # 표준 필드명으로 매핑
    field_extractors = {
        '_company_name': get_company_name,
        '_business_number': get_business_number,
        '_contact_name': get_contact_name,
        '_email': get_email,
        '_homepage': get_homepage,
        '_phone': get_phone,
        '_news_url': get_news_url,
        '_sales_point': get_sales_point,
        '_revenue': get_revenue,
        '_hosting': get_hosting,
        '_pg_provider': get_pg_provider,
        '_competitor': get_competitor,
        '_industry': get_industry,
        '_company_size': get_company_size,
        '_email_salutation': get_email_salutation,
        '_sales_item': get_sales_item,
        '_service_type': get_service_type,
        '_customer_type': get_customer_type,
        '_contact_position': get_contact_position,
    }
    
    for field_name, extractor in field_extractors.items():
        normalized[field_name] = extractor(company_data)
    
    return normalized


def get_additional_info(company_data: dict) -> dict:
    """
    회사 조사에 필요한 추가 정보를 표준화된 형태로 추출합니다.
    """
    return {
        '사업자번호': get_business_number(company_data),
        '사업자등록번호': get_business_number(company_data),
        '업종': get_industry(company_data),
        '세일즈포인트': get_sales_point(company_data),
        '규모': get_company_size(company_data),
        '대표자명': get_contact_name(company_data),
        'CEO명': get_contact_name(company_data),
        '이메일': get_email(company_data),
        '홈페이지링크': get_homepage(company_data),
        '대표홈페이지': get_homepage(company_data),
        '웹사이트': get_homepage(company_data),
        '매출액': get_revenue(company_data),
        '호스팅사': get_hosting(company_data),
        '사용PG': get_pg_provider(company_data),
        '경쟁사명': get_competitor(company_data),
        'sales_item': get_sales_item(company_data),
        '서비스유형': get_service_type(company_data),
        '고객유형': get_customer_type(company_data),
        '직책': get_contact_position(company_data),
        '이메일호칭': get_email_salutation(company_data),
    }


# 하위 호환성을 위한 레거시 함수들
def safe_get(company_data: dict, *keys, default='') -> str:
    """
    여러 가능한 키 중 하나라도 있으면 값을 반환합니다.
    레거시 코드 호환용.
    
    Args:
        company_data: 회사 데이터
        *keys: 확인할 키들 (우선순위 순)
        default: 기본값
    """
    for key in keys:
        if key in company_data and company_data[key]:
            return str(company_data[key]).strip()
    return default
