"""
CSV 열 이름 동적 매핑 유틸리티

열 이름이 변경되어도 올바르게 데이터를 추출할 수 있도록 
유연한 매핑 시스템을 제공합니다.
"""

import requests
import logging
import re

logger = logging.getLogger(__name__)

# 비정상 대표자명 필터링 패턴
INVALID_CEO_PATTERNS = [
    '이미지', '사진', '로고', 'logo', 'image', 'photo', 'img',
    '대표이미지', '프로필', 'profile', 'icon', '아이콘',
    'banner', '배너', 'thumbnail', '썸네일', 'alt', 'src',
    'http', 'www', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'
]


def is_valid_ceo_name(name: str) -> bool:
    """대표자명이 유효한지 검증"""
    if not name or len(name.strip()) < 2:
        return False
    
    name_lower = name.lower().strip()
    
    # 비정상 패턴 체크
    for pattern in INVALID_CEO_PATTERNS:
        if pattern in name_lower:
            return False
    
    # 숫자만 있거나 특수문자만 있는 경우
    if re.match(r'^[\d\s\-_\.]+$', name):
        return False
    
    # 너무 긴 경우 (일반적으로 이름은 10자 이내)
    if len(name.strip()) > 20:
        return False
    
    return True


def normalize_company_name_for_match(name: str) -> str:
    """회사명 비교를 위한 정규화"""
    if not name:
        return ''
    # 법인 유형 제거, 공백/특수문자 제거, 소문자 변환
    normalized = re.sub(r'\([^)]*\)', '', name)  # 괄호 내용 제거
    normalized = re.sub(r'[주식회사|유한회사|주|유]', '', normalized)
    normalized = re.sub(r'[\s\-_\.\,]', '', normalized)
    return normalized.lower().strip()


def is_company_name_match(csv_name: str, bizno_name: str) -> bool:
    """
    CSV 회사명과 비즈노 회사명이 일치하는지 검증
    
    느슨한 매칭: 핵심 키워드가 포함되면 일치로 판단
    """
    if not csv_name or not bizno_name:
        return False
    
    csv_norm = normalize_company_name_for_match(csv_name)
    bizno_norm = normalize_company_name_for_match(bizno_name)
    
    # 정확히 일치
    if csv_norm == bizno_norm:
        return True
    
    # 한쪽이 다른 쪽을 포함 (부분 일치)
    if csv_norm in bizno_norm or bizno_norm in csv_norm:
        return True
    
    # 3글자 이상 공통 부분이 있으면 일치로 간주
    min_len = min(len(csv_norm), len(bizno_norm))
    if min_len >= 3:
        for i in range(min_len - 2):
            if csv_norm[i:i+3] in bizno_norm:
                return True
    
    return False


def get_ceo_name_from_bizno(business_number: str, expected_company_name: str = '') -> str:
    """
    비즈노 API를 통해 사업자번호로 대표자명 조회 + 회사명 역검증
    
    Args:
        business_number: 사업자등록번호 (10자리 숫자)
        expected_company_name: CSV의 회사명 (역검증용)
    
    Returns:
        대표자명 또는 빈 문자열
    """
    if not business_number:
        return ''
    
    # 사업자번호 정규화 (숫자만 추출)
    clean_bizno = re.sub(r'[^0-9]', '', str(business_number))
    
    if len(clean_bizno) != 10:
        logger.warning(f"사업자번호 형식 오류: {business_number}")
        return ''
    
    try:
        # 비즈노 API 호출
        url = f"https://bizno.net/api/fapi?key=&gb=1&q={clean_bizno}&type=json"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            if items and len(items) > 0:
                ceo_name = items[0].get('repreName', '') or items[0].get('ceoNm', '')
                bizno_company = items[0].get('corpNm', '') or items[0].get('company', '')
                
                # 회사명 역검증
                if expected_company_name and bizno_company:
                    if not is_company_name_match(expected_company_name, bizno_company):
                        logger.warning(f"❌ 비즈노 회사명 불일치: CSV='{expected_company_name}' vs 비즈노='{bizno_company}'")
                        return ''
                    logger.info(f"✅ 회사명 검증 통과: '{expected_company_name}' ≈ '{bizno_company}'")
                
                if ceo_name and is_valid_ceo_name(ceo_name):
                    logger.info(f"💼 비즈노 대표자명 조회 성공: {bizno_company} - {ceo_name}")
                    return ceo_name.strip()
        
        logger.debug(f"비즈노 API에서 대표자명 없음: {clean_bizno}")
        return ''
        
    except requests.Timeout:
        logger.warning(f"비즈노 API 타임아웃: {clean_bizno}")
        return ''
    except Exception as e:
        logger.warning(f"비즈노 API 오류: {str(e)}")
        return ''

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


def is_ceo_name_match(csv_name: str, bizno_name: str) -> bool:
    """CSV 대표자명과 비즈노 대표자명이 일치하는지 검증"""
    if not csv_name or not bizno_name:
        return False
    
    csv_clean = csv_name.strip().replace(' ', '')
    bizno_clean = bizno_name.strip().replace(' ', '')
    
    # 정확히 일치
    if csv_clean == bizno_clean:
        return True
    
    # 한쪽이 다른쪽을 포함 (성만 있거나, 이름 일부만 있는 경우)
    if csv_clean in bizno_clean or bizno_clean in csv_clean:
        return True
    
    # 성(첫 글자)이 같고 길이가 비슷하면 일치로 간주
    if len(csv_clean) >= 2 and len(bizno_clean) >= 2:
        if csv_clean[0] == bizno_clean[0]:  # 성이 같음
            return True
    
    return False


def get_contact_name(company_data: dict) -> str:
    """
    담당자명/대표자명 추출 + 비즈노 역검증
    
    1. CSV에서 대표자명 추출
    2. 유효성 검증 (이미지, 사진 등 비정상 값 필터링)
    3. 사업자번호가 있으면 비즈노에서 대표자명 조회
    4. CSV 대표자명 vs 비즈노 대표자명 역검증
    """
    csv_name = get_column_value(company_data, 'contact_name', '')
    business_number = get_column_value(company_data, 'business_number', '')
    company_name = get_column_value(company_data, 'company_name', '')
    
    # CSV 대표자명 유효성 검증
    csv_valid = is_valid_ceo_name(csv_name)
    
    # 사업자번호가 있으면 비즈노에서 조회 (회사명 역검증 포함)
    bizno_name = ''
    if business_number:
        bizno_name = get_ceo_name_from_bizno(business_number, company_name)
    
    # Case 1: CSV 유효 + 비즈노 있음 → 대표자명 역검증
    if csv_valid and bizno_name:
        if is_ceo_name_match(csv_name, bizno_name):
            logger.info(f"✅ 대표자명 검증 통과: CSV='{csv_name}' ≈ 비즈노='{bizno_name}'")
            return csv_name
        else:
            logger.warning(f"❌ 대표자명 불일치: CSV='{csv_name}' vs 비즈노='{bizno_name}' → 비즈노 값 사용")
            return bizno_name
    
    # Case 2: CSV 유효 + 비즈노 없음 → CSV 사용 (검증 불가)
    if csv_valid and not bizno_name:
        logger.info(f"⚠️ 대표자명 검증 불가 (비즈노 조회 실패): '{csv_name}' 그대로 사용")
        return csv_name
    
    # Case 3: CSV 무효 + 비즈노 있음 → 비즈노 사용
    if not csv_valid and bizno_name:
        logger.info(f"🔄 비정상 대표자명 '{csv_name}' → 비즈노 대표자명 '{bizno_name}' 사용")
        return bizno_name
    
    # Case 4: 둘 다 없음 → 빈 문자열
    if csv_name:
        logger.warning(f"⚠️ 대표자명 조회 실패: CSV='{csv_name}' (비정상), 비즈노도 없음")
    return ''


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
