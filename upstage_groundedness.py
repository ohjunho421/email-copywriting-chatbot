"""
Upstage Solar Pro Groundedness Check 유틸리티
환각(hallucination) 감소를 위한 생성 콘텐츠 검증 시스템

⚠️ 주의: Upstage Groundedness Check 전용 모델은 Console에서만 사용 가능
이 코드는 Solar Pro (solar-pro) 모델을 활용하여 동일한 기능 구현
"""

import os
import logging
from typing import Dict, Any, Optional, Literal
from dotenv import load_dotenv

# OpenAI SDK 사용 (Upstage는 OpenAI 호환)
try:
    from openai import OpenAI
except ImportError:
    raise ImportError("openai 패키지가 필요합니다.")

load_dotenv()

logger = logging.getLogger(__name__)

# Groundedness 결과 타입
GroundednessResult = Literal['grounded', 'notGrounded', 'notSure']


class UpstageGroundednessChecker:
    """Upstage AI Groundedness Check API 클라이언트 (공식 API 사용)"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Upstage API 키 (None이면 환경변수에서 로드)
        """
        api_key = api_key or os.getenv('UPSTAGE_API_KEY')
        
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY가 설정되지 않았습니다.")
        
        # OpenAI SDK로 Upstage API 클라이언트 생성
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.upstage.ai/v1/solar"
        )
        # Solar Pro 2 모델 사용 (고성능 추론 및 한국어 지원)
        self.model = "solar-pro"
    
    def check(
        self, 
        context: str, 
        answer: str,
        raise_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        생성된 답변이 참조 문서(context)에 근거하고 있는지 검증
        
        Args:
            context: 참조 문서 (Perplexity 조사 결과, 홈페이지 내용 등)
            answer: 검증할 답변 (생성된 이메일, 사업자번호 등)
            raise_on_error: 오류 시 예외 발생 여부
        
        Returns:
            {
                'groundedness': 'grounded' | 'notGrounded' | 'notSure',
                'confidence_score': float (0.0 ~ 1.0),
                'is_verified': bool,
                'error': Optional[str]
            }
        """
        try:
            # Solar Pro 2로 Groundedness 검증 (프롬프트 기반)
            system_prompt = """당신은 정확성 검증 전문가입니다.
주어진 참조 문서(Reference)를 바탕으로 답변(Answer)이 사실에 근거하고 있는지 판단하세요.

판단 기준:
- grounded: 답변의 모든 주요 내용이 참조 문서에 명시되어 있음
- notGrounded: 답변에 참조 문서에 없는 중요한 정보나 사실이 포함됨
- notSure: 애매하거나 추론 가능하지만 직접 명시되지 않은 내용

결과는 반드시 "grounded", "notGrounded", "notSure" 중 하나만 출력하고, 간단한 이유를 한 줄로 추가하세요."""
            
            user_prompt = f"""**참조 문서(Reference):**
{context[:4000]}

**검증할 답변(Answer):**
{answer[:2000]}

위 답변이 참조 문서에 근거하고 있나요?"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0  # 일관된 판단을 위해 temperature=0
            )
            
            # 응답에서 groundedness 결과 추출
            result_text = response.choices[0].message.content.strip().lower()
            
            # 결과 파싱 (Solar Pro 2의 응답 분석)
            if "grounded" in result_text:
                if "not" in result_text.split("grounded")[0][-10:]:
                    # "not grounded" 케이스
                    groundedness = "notGrounded"
                else:
                    groundedness = "grounded"
            elif "근거" in result_text and ("없" in result_text or "불일치" in result_text):
                groundedness = "notGrounded"
            elif "확인" in result_text and ("가능" in result_text or "일치" in result_text):
                groundedness = "grounded"
            else:
                groundedness = "notSure"
            
            # 신뢰도 점수 계산
            confidence_map = {
                'grounded': 1.0,
                'notGrounded': 0.0,
                'notSure': 0.5
            }
            confidence_score = confidence_map.get(groundedness, 0.0)
            
            logger.info(f"✅ Groundedness Check 완료 (Solar Pro): {groundedness} (신뢰도: {confidence_score})")
            logger.debug(f"Solar Pro 2 응답: {result_text[:200]}")
            
            return {
                'groundedness': groundedness,
                'confidence_score': confidence_score,
                'is_verified': groundedness == 'grounded',
                'error': None
            }
        
        except Exception as e:
            error_msg = f"Groundedness Check 오류: {str(e)}"
            logger.error(error_msg)
            
            if raise_on_error:
                raise
            
            return {
                'groundedness': 'notSure',
                'confidence_score': 0.0,
                'is_verified': False,
                'error': error_msg
            }
    
    def batch_check(
        self, 
        context: str, 
        answers: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        여러 답변을 한 번에 검증 (배치 처리)
        
        Args:
            context: 참조 문서
            answers: {answer_type: answer_content} 형태의 딕셔너리
        
        Returns:
            {answer_type: verification_result} 형태의 딕셔너리
        """
        import time
        results = {}
        
        for answer_type, answer_content in answers.items():
            logger.info(f"🔍 {answer_type} 검증 중...")
            result = self.check(context, answer_content)
            results[answer_type] = result
            
            # 환각 감지 시 경고
            if result['groundedness'] == 'notGrounded':
                logger.warning(f"⚠️ {answer_type}에서 환각 감지! 근거 없는 내용 포함")
        
        # 요약 통계
        verified_count = sum(1 for r in results.values() if r['is_verified'])
        hallucinated_count = sum(1 for r in results.values() if r['groundedness'] == 'notGrounded')
        
        logger.info(f"📊 배치 검증 완료: 검증 통과 {verified_count}/{len(results)}, 환각 감지 {hallucinated_count}개")
        
        return results
    
    def verify_email_against_research(
        self,
        perplexity_research: str,
        email_subject: str,
        email_body: str,
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        생성된 이메일이 Perplexity 조사 결과에 근거하는지 검증
        
        Args:
            perplexity_research: Perplexity 조사 결과
            email_subject: 이메일 제목
            email_body: 이메일 본문
            min_confidence: 최소 요구 신뢰도 (0.0 ~ 1.0)
        
        Returns:
            검증 결과 + 재생성 필요 여부
        """
        # 제목과 본문을 합쳐서 검증
        full_email = f"제목: {email_subject}\n\n본문:\n{email_body}"
        
        result = self.check(perplexity_research, full_email)
        
        # 최소 신뢰도 미달 시 재생성 권장
        result['needs_regeneration'] = result['confidence_score'] < min_confidence
        
        if result['needs_regeneration']:
            logger.warning(
                f"⚠️ 이메일 신뢰도 {result['confidence_score']:.2f} < 최소 요구 {min_confidence} "
                f"- 재생성 권장"
            )
        
        return result
    
    def verify_business_data(
        self,
        source_context: str,
        business_number: Optional[str] = None,
        revenue: Optional[str] = None,
        ceo_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        사업자 정보(사업자번호, 매출액, 대표자명 등)가 출처에 근거하는지 검증
        
        Args:
            source_context: 출처 문서 (홈페이지 HTML, Perplexity 조사 등)
            business_number: 검증할 사업자번호
            revenue: 검증할 매출액
            ceo_name: 검증할 대표자명
        
        Returns:
            각 항목별 검증 결과
        """
        results = {}
        
        if business_number:
            answer = f"사업자등록번호: {business_number}"
            results['business_number'] = self.check(source_context, answer)
        
        if revenue:
            answer = f"매출액: {revenue}"
            results['revenue'] = self.check(source_context, answer)
        
        if ceo_name:
            answer = f"대표자명: {ceo_name}"
            results['ceo_name'] = self.check(source_context, answer)
        
        # 전체 검증 통과 여부
        all_verified = all(r['is_verified'] for r in results.values())
        
        return {
            'individual_results': results,
            'all_verified': all_verified,
            'verified_count': sum(1 for r in results.values() if r['is_verified']),
            'total_count': len(results)
        }


def verify_perplexity_research(
    company_name: str,
    perplexity_content: str,
    website_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perplexity 조사 결과가 회사 홈페이지와 일치하는지 역방향 검증
    
    Args:
        company_name: 회사명
        perplexity_content: Perplexity 조사 내용
        website_url: 회사 홈페이지 URL (있으면 HTML 가져와서 검증)
    
    Returns:
        역방향 검증 결과
    """
    if not website_url:
        logger.warning(f"{company_name}: 홈페이지 URL 없음 - 역검증 건너뛰기")
        return {'verified': False, 'reason': 'no_website'}
    
    try:
        # 홈페이지 HTML 가져오기
        response = requests.get(
            website_url,
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"{company_name}: 홈페이지 접근 실패 ({response.status_code})")
            return {'verified': False, 'reason': 'website_unavailable'}
        
        website_html = response.text[:15000]  # 앞 15KB만 사용
        
        # Groundedness Check
        checker = UpstageGroundednessChecker()
        result = checker.check(website_html, perplexity_content)
        
        if result['groundedness'] == 'notGrounded':
            logger.warning(
                f"⚠️ {company_name}: Perplexity 조사 결과가 홈페이지와 불일치! "
                f"조사 내용을 신뢰할 수 없습니다."
            )
        
        return {
            'verified': result['is_verified'],
            'groundedness': result['groundedness'],
            'confidence_score': result['confidence_score'],
            'reason': 'checked'
        }
    
    except Exception as e:
        logger.error(f"{company_name} 역검증 오류: {e}")
        return {'verified': False, 'reason': f'error: {str(e)}'}


# 전역 인스턴스 (싱글톤 패턴)
_groundedness_checker = None

def get_groundedness_checker() -> UpstageGroundednessChecker:
    """전역 Groundedness Checker 인스턴스 반환"""
    global _groundedness_checker
    if _groundedness_checker is None:
        _groundedness_checker = UpstageGroundednessChecker()
    return _groundedness_checker
