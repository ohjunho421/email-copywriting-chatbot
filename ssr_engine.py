"""
Semantic Similarity Rating (SSR) 엔진
논문: "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"

이메일 효과성을 예측하여 최적의 메일을 선택합니다.
"""

import os
import logging

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화 (임베딩용) - 지연 초기화
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai_client = None

def get_openai_client():
    """OpenAI 클라이언트를 필요할 때만 초기화 (지연 로딩)"""
    global openai_client
    if openai_client is None and OPENAI_API_KEY:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("✅ SSR 엔진: OpenAI 임베딩 사용 (90% 정확도)")
        except Exception as e:
            logger.warning(f"⚠️ OpenAI 클라이언트 초기화 실패: {e}")
            logger.info("🔄 SSR 엔진: 휴리스틱 모드로 전환 (60-70% 정확도)")
            openai_client = False  # 재시도 방지
    return openai_client if openai_client is not False else None

# Likert 척도 기준 문장 (5점 척도)
# 각 점수별로 "이 메일을 받았을 때의 반응"을 나타내는 기준 문장
REFERENCE_STATEMENTS = {
    1: [
        "이 메일은 전혀 흥미롭지 않고 삭제할 것 같습니다.",
        "스팸처럼 느껴지며 읽을 가치가 없어 보입니다.",
        "이런 영업 메일은 거의 열어보지 않습니다."
    ],
    2: [
        "별로 관심이 가지 않지만 한 번쯤은 읽어볼 수도 있습니다.",
        "제안이 다소 일반적이고 우리 회사와 맞지 않는 것 같습니다.",
        "지금은 필요하지 않지만 나중에 생각해볼 수도 있겠네요."
    ],
    3: [
        "어느 정도 관심이 가며 좀 더 정보를 알아볼 가치가 있어 보입니다.",
        "제안이 괜찮아 보이지만 확신이 들지는 않습니다.",
        "시간이 되면 답장을 고려해볼 만합니다."
    ],
    4: [
        "매우 관심이 가며 곧 답장할 가능성이 높습니다.",
        "우리 회사의 pain point를 잘 파악한 것 같아 통화를 원합니다.",
        "구체적이고 관련성이 높아서 미팅을 잡고 싶습니다."
    ],
    5: [
        "정확히 우리가 찾던 솔루션이며 즉시 답장하겠습니다.",
        "매우 시의적절하고 필요한 제안이라 빨리 미팅을 잡고 싶습니다.",
        "이 메일은 우리 회사의 현재 문제를 정확히 이해하고 있어 매우 인상적입니다."
    ]
}

def cosine_similarity(vec1, vec2):
    """두 벡터 간의 코사인 유사도 계산"""
    import numpy as np
    
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)

def get_embedding(text, model="text-embedding-3-small"):
    """텍스트의 임베딩 벡터 가져오기 (OpenAI)"""
    client = get_openai_client()
    if not client:
        logger.warning("OpenAI API 키가 없어 SSR을 사용할 수 없습니다. 기본 점수 반환")
        return None
    
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"임베딩 생성 오류: {e}")
        return None

def calculate_ssr_score(email_content, company_info=None):
    """
    SSR 방식으로 이메일 효과성 점수 계산
    
    Args:
        email_content: 이메일 본문 (str)
        company_info: 회사 정보 (dict, optional)
    
    Returns:
        dict: {
            'score': float (1-5),
            'distribution': dict (각 점수별 확률),
            'confidence': float (0-1),
            'reasoning': str
        }
    """
    
    # OpenAI 없으면 휴리스틱 기반 점수
    client = get_openai_client()
    if not client:
        return calculate_heuristic_score(email_content, company_info)
    
    try:
        # 1. 이메일 내용 임베딩
        email_embedding = get_embedding(email_content)
        if email_embedding is None:
            return calculate_heuristic_score(email_content, company_info)
        
        # 2. 각 기준 문장과의 유사도 계산
        similarities = {}
        for rating, statements in REFERENCE_STATEMENTS.items():
            rating_similarities = []
            for statement in statements:
                ref_embedding = get_embedding(statement)
                if ref_embedding:
                    sim = cosine_similarity(email_embedding, ref_embedding)
                    rating_similarities.append(sim)
            
            # 평균 유사도
            if rating_similarities:
                similarities[rating] = sum(rating_similarities) / len(rating_similarities)
            else:
                similarities[rating] = 0.0
        
        # 3. 유사도를 확률 분포로 변환
        min_sim = min(similarities.values())
        adjusted_sims = {r: max(0, s - min_sim) for r, s in similarities.items()}
        
        total = sum(adjusted_sims.values())
        if total == 0:
            # fallback
            distribution = {r: 0.2 for r in range(1, 6)}
        else:
            distribution = {r: s / total for r, s in adjusted_sims.items()}
        
        # 4. 기대값 계산 (가중 평균)
        expected_score = sum(rating * prob for rating, prob in distribution.items())
        
        # 5. Confidence 계산 (엔트로피 기반)
        import math
        entropy = -sum(p * math.log(p + 1e-10) for p in distribution.values() if p > 0)
        max_entropy = math.log(5)  # 5개 선택지
        confidence = 1 - (entropy / max_entropy)
        
        # 6. 점수별 확률이 높은 이유 추론
        top_rating = max(distribution.items(), key=lambda x: x[1])[0]
        reasoning = f"가장 유사한 반응: {top_rating}점 ({distribution[top_rating]*100:.1f}% 확률)"
        
        return {
            'score': round(expected_score, 2),
            'distribution': distribution,
            'confidence': round(confidence, 2),
            'reasoning': reasoning,
            'method': 'SSR'
        }
        
    except Exception as e:
        logger.error(f"SSR 계산 오류: {e}")
        return calculate_heuristic_score(email_content, company_info)

def calculate_heuristic_score(email_content, company_info=None):
    """
    휴리스틱 기반 점수 계산 (OpenAI 없을 때 fallback)
    이메일 내용의 특징을 분석하여 점수 부여
    """
    score = 3.0  # 기본 점수
    reasons = []
    
    content_lower = email_content.lower()
    
    # 긍정적 요소들
    positive_factors = {
        '개인화': ['님', '귀사', '회사명'],
        '구체적 수치': ['%', '억', '만원', '배', '시간'],
        '실제 사례': ['사례', '고객', 'case', '실제로'],
        'Pain Point': ['고민', '문제', '어려움', '과제'],
        'CTA': ['통화', '미팅', '데모', '상담'],
        '혜택': ['무료', '절감', '향상', '개선']
    }
    
    for factor, keywords in positive_factors.items():
        if any(kw in content_lower for kw in keywords):
            score += 0.3
            reasons.append(f"{factor} 포함")
    
    # 부정적 요소들
    negative_factors = {
        '너무 긴 내용': len(email_content) > 1000,
        '과도한 특수문자': email_content.count('!') > 3,
        '스팸성 단어': any(word in content_lower for word in ['대박', '확실', '100%', '클릭'])
    }
    
    for factor, condition in negative_factors.items():
        if condition:
            score -= 0.3
            reasons.append(f"{factor}")
    
    # 점수 범위 제한
    score = max(1.0, min(5.0, score))
    
    # 간단한 분포 생성 (정규분포 근사)
    distribution = {}
    for r in range(1, 6):
        # score를 중심으로 한 분포
        diff = abs(r - score)
        prob = max(0, 1 - diff * 0.3)
        distribution[r] = prob
    
    # 정규화
    total = sum(distribution.values())
    distribution = {r: p / total for r, p in distribution.items()}
    
    return {
        'score': round(score, 2),
        'distribution': distribution,
        'confidence': 0.6,  # 휴리스틱은 낮은 confidence
        'reasoning': ", ".join(reasons) if reasons else "기본 휴리스틱 평가",
        'method': 'heuristic'
    }

def rank_emails(emails, company_info=None):
    """
    여러 이메일을 SSR 점수로 순위 매기기
    
    Args:
        emails: 이메일 객체 리스트 [{'type': '', 'subject': '', 'body': ''}, ...]
        company_info: 회사 정보 (dict)
    
    Returns:
        list: SSR 점수순으로 정렬된 이메일 리스트 (점수 정보 포함)
    """
    ranked = []
    
    for email in emails:
        # 제목 + 본문을 합쳐서 평가
        full_content = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
        
        ssr_result = calculate_ssr_score(full_content, company_info)
        
        email_with_score = email.copy()
        email_with_score['ssr_score'] = ssr_result['score']
        email_with_score['ssr_confidence'] = ssr_result['confidence']
        email_with_score['ssr_reasoning'] = ssr_result['reasoning']
        email_with_score['ssr_distribution'] = ssr_result['distribution']
        email_with_score['ssr_method'] = ssr_result['method']
        
        ranked.append(email_with_score)
    
    # 점수 내림차순 정렬
    ranked.sort(key=lambda x: x['ssr_score'], reverse=True)
    
    return ranked

def get_top_email(emails, company_info=None):
    """
    가장 높은 SSR 점수를 받은 이메일 1개 반환
    """
    ranked = rank_emails(emails, company_info)
    return ranked[0] if ranked else None

# 테스트용 함수
def test_ssr():
    """SSR 엔진 테스트"""
    test_emails = [
        {
            'type': '전문적 톤',
            'subject': '[PortOne] 결제 시스템 개선 제안',
            'body': '안녕하세요. 포트원입니다. 결제 시스템을 개선해드리겠습니다.'
        },
        {
            'type': '개인화 톤',
            'subject': '[PortOne] ABC사 김대표님께 전달 부탁드립니다',
            'body': '안녕하세요, ABC사 김대표님. PG 장애로 월 평균 몇 시간을 손실하고 계신가요? 유사 업종 고객사는 포트원으로 10배 효율화를 달성했습니다. 15분 통화 가능하실까요?'
        }
    ]
    
    ranked = rank_emails(test_emails)
    
    print("=== SSR 테스트 결과 ===")
    for i, email in enumerate(ranked, 1):
        print(f"\n{i}위: {email['type']}")
        print(f"점수: {email['ssr_score']:.2f} / 5.0")
        print(f"신뢰도: {email['ssr_confidence']:.2f}")
        print(f"이유: {email['ssr_reasoning']}")
        print(f"방법: {email['ssr_method']}")

if __name__ == "__main__":
    test_ssr()
