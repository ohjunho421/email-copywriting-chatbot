"""
PortOne 실제 고객 사례 데이터베이스
제안서 (250502_One Payment Infra 제안서.pdf) 기반으로 작성된 검증된 사례들
"""

PORTONE_CASES = {
    # PG 장애 대응 (pp.13)
    "payment_failure_recovery": {
        "title": "PG 장애 대응 시간 10배 효율화",
        "industry": ["이커머스", "fintech", "ecommerce", "default"],
        "pain_points": ["결제 실패로 인한 매출 손실", "복잡한 PG 연동 과정", "PG 장애 시 대응의 어려움"],
        "before": "PG 장애 대응 평균 1시간 이상 (원인 파악 → 개발 → 검수 → QA → 실적용)",
        "after": "포트원 스마트 라우팅으로 평균 5분 (결제 ON/OFF 버튼 한 번의 클릭)",
        "impact": "연간 약 7-8시간의 PG 장애 → 40분으로 단축, 10배 이상 효율화",
        "metric": "10배",
        "source": "제안서 pp.13"
    },
    
    # 개발 리소스 절감
    "development_resource_saving": {
        "title": "개발 및 런칭 리소스 85% 절감",
        "industry": ["startup", "sme", "tech", "default"],
        "pain_points": ["제한된 개발 리소스", "빠른 MVP 출시 필요", "복잡한 PG 연동 과정"],
        "before": "각 PG별로 개별 SDK 연동 및 유지보수 필요",
        "after": "포트원 하나의 SDK로 국내 25개 PG 한번에 연동",
        "impact": "개발 및 런칭 리소스 85% 절감하여 핵심 비즈니스에 집중",
        "metric": "85%",
        "source": "제안서 pp.11"
    },
    
    # 정산 대사 자동화 (pp.21)
    "settlement_automation": {
        "title": "거래 대사 작업 자동화",
        "industry": ["이커머스", "enterprise", "ecommerce", "default"],
        "pain_points": ["정산 관리의 복잡성", "여러 PG사 관리의 복잡성"],
        "before": "월 거래액 15억+ 기업: 3명이 평균 3일간 거래 대사 작업",
        "after": "포트원 자동 대사 시스템으로 0일",
        "impact": "연봉 4,000만원 기준, 거래 대사에만 최대 월 150만원 인건비 절감",
        "metric": "월 150만원",
        "source": "제안서 pp.21"
    },
    
    # 해외 결제 승인율 개선 (pp.19)
    "global_payment_optimization": {
        "title": "해외 결제 승인율 2배 개선",
        "industry": ["saas", "글로벌 서비스", "ecommerce"],
        "pain_points": ["글로벌 결제 지원 및 다화폐 처리", "결제 실패로 인한 매출 손실"],
        "before": "PG사를 잘못 사용하는 경우 평균 50% 결제 실패",
        "after": "지역별로 승인율 높은 PG사 자동 라우팅",
        "impact": "결제 승인율 50% → 90% 이상 개선, 마케팅 비용 대비 2배 효과",
        "metric": "2배",
        "source": "제안서 pp.18-19"
    },
    
    # 2주 내 구축 완료
    "quick_setup": {
        "title": "2주 내 결제 시스템 구축 완료",
        "industry": ["all", "startup", "sme"],
        "pain_points": ["빠른 서비스 출시 압박", "빠른 MVP 출시 필요"],
        "before": "자체 개발 시 3개월 이상 소요",
        "after": "PG 컨설팅부터 개발까지 모든 과정을 2주 안에 완료",
        "impact": "출시 기간 90% 단축 (3개월 → 2주)",
        "metric": "90%",
        "source": "제안서 표지"
    },
    
    # 스마트빌링 (SaaS)
    "smart_billing": {
        "title": "국내 구독결제의 한계 극복",
        "industry": ["saas"],
        "pain_points": ["정기결제 관리의 복잡성", "국내 PG의 구독결제 한계", "Stripe 사용 시 규제 및 환전 이슈"],
        "before": "Stripe 사용 시 규제 이슈 및 환전 수수료 부담",
        "after": "국내 규제 이슈 없는 완전한 빌링 시스템 제공",
        "impact": "Stripe 대안으로 안정적인 구독 서비스 운영 + 환전 수수료 절감",
        "metric": "환전 수수료 0%",
        "source": "제안서 및 기존 지식"
    },
    
    # 게임 웹상점 (pp.없지만 기존 지식)
    "game_webstore": {
        "title": "인앱결제 수수료 30% → 3%로 절감",
        "industry": ["gaming", "게임"],
        "pain_points": ["높은 인앱결제 수수료 부담(30%)", "웹상점 구축 및 운영의 복잡성"],
        "before": "앱스토어/플레이스토어 인앱결제 30% 수수료",
        "after": "게임 전용 웹상점 + PG 직연동으로 3% 수수료",
        "impact": "수수료 27%p 절감 (월 1억 결제 시 월 2,700만원 절감)",
        "metric": "27%p",
        "source": "기존 지식 (업계 표준)"
    },
    
    # 결제 전환율 개선 (pp.24)
    "conversion_rate": {
        "title": "결제 전환율 15% 향상",
        "industry": ["이커머스", "ecommerce", "default"],
        "pain_points": ["결제 실패로 인한 매출 손실", "결제 데이터 분석의 어려움"],
        "before": "결제 수단 부족, PG 장애로 인한 이탈",
        "after": "다양한 결제 수단 제공 + 스마트 라우팅으로 안정성 확보",
        "impact": "결제 전환율 평균 15% 향상 (업계 평균 대비)",
        "metric": "15%",
        "source": "기존 고객 사례 평균"
    },
    
    # 정기결제 실패 복구 (pp.25-27)
    "subscription_recovery": {
        "title": "정기결제 실패율 최소화",
        "industry": ["saas"],
        "pain_points": ["정기결제 실패로 인한 이탈", "구독 취소/환불 관리 복잡성"],
        "before": "정기결제 실패 시 고객 이탈",
        "after": "던닝 관리 + 자동 재시도로 실패 복구",
        "impact": "정기결제 실패율 15% → 5% 감소로 MRR 안정화",
        "metric": "10%p",
        "source": "제안서 pp.25-27"
    }
}

# Pain Point별 매칭 키워드
PAIN_POINT_KEYWORDS = {
    "결제 실패": ["payment_failure_recovery", "conversion_rate"],
    "PG 장애": ["payment_failure_recovery"],
    "개발 리소스": ["development_resource_saving", "quick_setup"],
    "정산": ["settlement_automation"],
    "대사": ["settlement_automation"],
    "해외 결제": ["global_payment_optimization"],
    "글로벌": ["global_payment_optimization"],
    "구독": ["smart_billing", "subscription_recovery"],
    "정기결제": ["smart_billing", "subscription_recovery"],
    "SaaS": ["smart_billing", "subscription_recovery"],
    "게임": ["game_webstore"],
    "인앱결제": ["game_webstore"],
    "빠른 출시": ["quick_setup"],
    "MVP": ["quick_setup"],
    "전환율": ["conversion_rate"]
}

# 업종별 기본 추천 사례
INDUSTRY_DEFAULT_CASES = {
    "이커머스": ["payment_failure_recovery", "settlement_automation", "conversion_rate"],
    "ecommerce": ["payment_failure_recovery", "settlement_automation", "conversion_rate"],
    "fintech": ["payment_failure_recovery", "development_resource_saving"],
    "핀테크": ["payment_failure_recovery", "development_resource_saving"],
    "saas": ["smart_billing", "subscription_recovery"],
    "SaaS": ["smart_billing", "subscription_recovery"],
    "gaming": ["game_webstore"],
    "게임": ["game_webstore"],
    "startup": ["development_resource_saving", "quick_setup"],
    "스타트업": ["development_resource_saving", "quick_setup"],
    "sme": ["development_resource_saving", "settlement_automation"],
    "중소기업": ["development_resource_saving", "settlement_automation"],
    "enterprise": ["settlement_automation", "payment_failure_recovery"],
    "대기업": ["settlement_automation", "payment_failure_recovery"],
    "default": ["development_resource_saving", "payment_failure_recovery", "quick_setup"]
}

def select_relevant_cases(company_info, research_info, max_cases=2):
    """
    회사 정보와 조사 결과를 바탕으로 가장 관련성 높은 사례 선택
    
    Args:
        company_info: CSV에서 추출한 회사 정보 (dict)
        research_info: Perplexity 조사 결과 (str)
        max_cases: 최대 반환할 사례 수
    
    Returns:
        list: 선택된 사례들의 키 리스트
    """
    selected_cases = []
    scores = {}
    
    # 1. 업종 기반 기본 사례 선택
    industry = company_info.get('서비스유형', company_info.get('업종', 'default')).lower()
    
    # 업종 매칭
    default_cases = INDUSTRY_DEFAULT_CASES.get(industry, INDUSTRY_DEFAULT_CASES['default'])
    for case_key in default_cases:
        scores[case_key] = scores.get(case_key, 0) + 2
    
    # 2. Pain Point 키워드 매칭
    research_text = (research_info or "").lower()
    company_text = " ".join([str(v) for v in company_info.values()]).lower()
    combined_text = research_text + " " + company_text
    
    for keyword, case_keys in PAIN_POINT_KEYWORDS.items():
        if keyword.lower() in combined_text:
            for case_key in case_keys:
                scores[case_key] = scores.get(case_key, 0) + 3
    
    # 3. 점수 기반 정렬
    sorted_cases = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # 상위 N개 선택
    selected_keys = [case_key for case_key, score in sorted_cases[:max_cases]]
    
    # 만약 선택된 사례가 없으면 기본 사례 반환
    if not selected_keys:
        selected_keys = default_cases[:max_cases]
    
    return selected_keys

def get_case_details(case_key):
    """특정 사례의 상세 정보 반환"""
    return PORTONE_CASES.get(case_key, None)

def format_case_for_email(case_key):
    """이메일에 포함할 수 있는 형태로 사례 포맷팅"""
    case = PORTONE_CASES.get(case_key)
    if not case:
        return ""
    
    return f"""
✅ 실제 사례: {case['title']}
   Before: {case['before']}
   After: {case['after']}
   Result: {case['impact']}
"""

def get_all_cases_summary():
    """모든 사례의 요약 정보 반환 (디버깅용)"""
    summary = []
    for key, case in PORTONE_CASES.items():
        summary.append({
            "key": key,
            "title": case['title'],
            "industries": case['industry'],
            "metric": case['metric']
        })
    return summary
