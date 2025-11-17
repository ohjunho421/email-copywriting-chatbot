"""
Upstage Groundedness Check 테스트 스크립트
환각 감지 시스템이 제대로 작동하는지 검증
"""

import os
from dotenv import load_dotenv
from upstage_groundedness import (
    UpstageGroundednessChecker,
    verify_perplexity_research
)

load_dotenv()


def test_basic_groundedness():
    """기본 Groundedness Check 테스트"""
    print("\n" + "="*60)
    print("🧪 테스트 1: 기본 Groundedness Check")
    print("="*60)
    
    checker = UpstageGroundednessChecker()
    
    # 참조 문서 (실제 정보)
    context = """
    포트원(PortOne)은 결제 인프라 통합 솔루션을 제공하는 핀테크 기업입니다.
    2016년 설립되었으며, 대표이사는 박재현입니다.
    국내 25개 이상의 PG사와 제휴하여 단일 API로 통합 결제 서비스를 제공합니다.
    주요 서비스는 One Payment Infra(OPI)와 국내커머스채널 재무자동화 솔루션입니다.
    """
    
    # ✅ 정상 케이스: 참조 문서에 근거한 답변
    grounded_answer = "포트원은 2016년 설립된 핀테크 기업으로, 박재현 대표가 이끌고 있습니다. 25개 이상의 PG사와 제휴하여 통합 결제 서비스를 제공합니다."
    
    # ❌ 환각 케이스: 참조 문서에 없는 정보
    hallucinated_answer = "포트원은 2010년 설립되어 AI 로봇 개발과 블록체인 기술에 집중하는 회사입니다. 글로벌 100개국에 서비스를 제공하고 있습니다."
    
    # ⚠️ 애매한 케이스: 일부만 맞는 정보
    partial_answer = "포트원은 결제 솔루션을 제공하는 회사로, 최근 미국 시장 진출을 위해 500억원 투자를 유치했습니다."
    
    test_cases = [
        ("✅ 정상 케이스", grounded_answer, "grounded"),
        ("❌ 환각 케이스", hallucinated_answer, "notGrounded"),
        ("⚠️ 애매한 케이스", partial_answer, "notSure")
    ]
    
    for label, answer, expected in test_cases:
        print(f"\n{label}:")
        print(f"답변: {answer[:100]}...")
        
        result = checker.check(context, answer)
        
        print(f"검증 결과: {result['groundedness']} (신뢰도: {result['confidence_score']:.2f})")
        print(f"예상 결과: {expected}")
        print(f"통과: {'✅' if result['groundedness'] == expected else '❌'}")


def test_email_verification():
    """이메일 검증 테스트"""
    print("\n" + "="*60)
    print("🧪 테스트 2: 이메일 검증")
    print("="*60)
    
    checker = UpstageGroundednessChecker()
    
    # Perplexity 조사 결과 (실제 정보)
    perplexity_research = """
    토스페이먼츠는 국내 대표 간편결제 서비스입니다.
    2021년 매출 1조원을 돌파했으며, 최근 글로벌 확장을 위해 시리즈 E 투자를 유치했습니다.
    주요 서비스는 토스페이와 POS 시스템입니다.
    """
    
    # ✅ 정상 이메일: Perplexity 조사에 근거
    good_email = """
    제목: 토스페이먼츠님의 글로벌 확장 계획 관련 문의
    
    안녕하세요, 토스페이먼츠 담당자님.
    
    최근 시리즈 E 투자 유치 소식을 봤습니다. 글로벌 확장 준비로 바쁘시겠지만,
    해외 결제 인프라 구축 시 저희 포트원의 글로벌 PG 통합 솔루션이 도움이 될 것 같습니다.
    """
    
    # ❌ 환각 이메일: 없는 정보 포함
    bad_email = """
    제목: 토스페이먼츠님의 블록체인 사업 관련 제안
    
    안녕하세요, 토스페이먼츠 담당자님.
    
    최근 NFT 마켓플레이스 출시 발표를 봤습니다. 블록체인 결제 통합에 어려움을 겪고 계실 것 같아,
    저희 포트원의 암호화폐 결제 솔루션을 제안드립니다.
    """
    
    print("\n✅ 정상 이메일 검증:")
    result_good = checker.verify_email_against_research(
        perplexity_research, 
        "토스페이먼츠님의 글로벌 확장 계획 관련 문의",
        good_email
    )
    print(f"검증 결과: {result_good['groundedness']} (신뢰도: {result_good['confidence_score']:.2f})")
    print(f"재생성 필요: {result_good['needs_regeneration']}")
    
    print("\n❌ 환각 이메일 검증:")
    result_bad = checker.verify_email_against_research(
        perplexity_research,
        "토스페이먼츠님의 블록체인 사업 관련 제안", 
        bad_email
    )
    print(f"검증 결과: {result_bad['groundedness']} (신뢰도: {result_bad['confidence_score']:.2f})")
    print(f"재생성 필요: {result_bad['needs_regeneration']}")


def test_batch_verification():
    """배치 검증 테스트 (4개 이메일 동시 검증)"""
    print("\n" + "="*60)
    print("🧪 테스트 3: 배치 검증 (4개 이메일)")
    print("="*60)
    
    checker = UpstageGroundednessChecker()
    
    perplexity_research = """
    카카오는 국내 1위 모바일 메신저 서비스입니다.
    카카오톡, 카카오페이, 카카오뱅크 등 다양한 서비스를 운영합니다.
    최근 AI 기술 투자를 확대하고 있으며, 글로벌 시장 진출을 추진 중입니다.
    """
    
    emails = {
        "opi_professional": "카카오페이 서비스를 운영하시면서 다양한 PG사 통합 관리에 어려움을 겪고 계실 것 같습니다.",
        "opi_curiosity": "카카오의 AI 기술 투자 확대 소식을 봤습니다. AI 기반 결제 시스템 최적화에 관심 있으신가요?",
        "finance_professional": "카카오뱅크 운영 시 정산 자동화는 어떻게 하고 계신가요?",
        "hallucinated": "최근 카카오의 자율주행 자동차 출시 소식을 봤습니다. 차량 내 결제 시스템 구축에 도움을 드리고 싶습니다."
    }
    
    results = checker.batch_check(perplexity_research, emails)
    
    print("\n📊 검증 결과:")
    for email_type, result in results.items():
        status_icon = "✅" if result['is_verified'] else "❌"
        print(f"{status_icon} {email_type}: {result['groundedness']} (신뢰도: {result['confidence_score']:.2f})")


def test_business_data_verification():
    """사업자 정보 검증 테스트"""
    print("\n" + "="*60)
    print("🧪 테스트 4: 사업자 정보 검증")
    print("="*60)
    
    checker = UpstageGroundednessChecker()
    
    # 홈페이지 HTML (시뮬레이션)
    website_html = """
    <footer>
        <div class="company-info">
            <p>회사명: (주)포트원</p>
            <p>대표자: 박재현</p>
            <p>사업자등록번호: 123-45-67890</p>
            <p>연매출: 500억원 (2023년 기준)</p>
        </div>
    </footer>
    """
    
    # ✅ 정확한 정보
    print("\n✅ 정확한 사업자 정보 검증:")
    result_good = checker.verify_business_data(
        website_html,
        business_number="123-45-67890",
        revenue="500억원",
        ceo_name="박재현"
    )
    print(f"전체 검증 통과: {result_good['all_verified']}")
    print(f"검증 통과: {result_good['verified_count']}/{result_good['total_count']}")
    
    # ❌ 잘못된 정보
    print("\n❌ 잘못된 사업자 정보 검증:")
    result_bad = checker.verify_business_data(
        website_html,
        business_number="999-99-99999",  # 틀린 번호
        revenue="1조원",  # 틀린 매출
        ceo_name="김철수"  # 틀린 대표자
    )
    print(f"전체 검증 통과: {result_bad['all_verified']}")
    print(f"검증 통과: {result_bad['verified_count']}/{result_bad['total_count']}")
    
    for field, result in result_bad['individual_results'].items():
        status = "✅" if result['is_verified'] else "❌"
        print(f"  {status} {field}: {result['groundedness']}")


if __name__ == "__main__":
    print("\n🚀 Upstage Groundedness Check 테스트 시작")
    print("="*60)
    
    # API 키 확인
    api_key = os.getenv('UPSTAGE_API_KEY')
    if not api_key:
        print("❌ 오류: UPSTAGE_API_KEY가 설정되지 않았습니다.")
        print("💡 .env 파일에 다음 라인을 추가하세요:")
        print("   UPSTAGE_API_KEY=your_api_key_here")
        exit(1)
    
    print(f"✅ API 키 확인: {api_key[:10]}***")
    
    try:
        # 모든 테스트 실행
        test_basic_groundedness()
        test_email_verification()
        test_batch_verification()
        test_business_data_verification()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
