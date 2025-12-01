"""
비즈니스 모델 자동 분석 모듈
홈페이지와 기사를 통해 회사의 BM을 파악하고 맞춤형 솔루션을 매핑
"""

import re
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class BusinessModelAnalyzer:
    """회사의 비즈니스 모델을 분석하고 PortOne 솔루션을 매핑"""
    
    def __init__(self):
        # BM 감지 키워드 패턴
        self.bm_patterns = {
            'subscription': {
                'keywords': [
                    '구독', '월간', '연간', '정기결제', '회원권', '프리미엄', '플랜', 
                    '가격 플랜', '요금제', '자동 갱신', '자동결제', '구독 해지',
                    '무료 체험', '무료 트라이얼', '멤버십', 'subscription', 'monthly',
                    'yearly', 'premium', 'plan', 'pricing', 'trial', 'membership',
                    'SaaS', '정기배송', '구독박스', 'OTT', '스트리밍'
                ],
                'weight': 2  # 구독은 높은 가중치
            },
            'mobile_app': {
                'keywords': [
                    '앱 다운로드', 'iOS', 'Android', '앱스토어', '구글플레이',
                    '다운로드 받기', '모바일 앱', '앱 전용', '푸시 알림',
                    'App Store', 'Google Play', '앱 설치', '인앱결제',
                    '인앱 구매', 'in-app purchase', '앱 리뷰', '앱 평점',
                    '모바일 게임', '게임 아이템', '모바일 서비스'
                ],
                'weight': 2
            },
            'ecommerce': {
                'keywords': [
                    '쇼핑', '장바구니', '상품', '배송', '주문', '구매하기',
                    '할인', '쿠폰', '프로모션', '세일', '특가', '무료배송',
                    '반품', '교환', '환불', '배송 추적', '상품 리뷰',
                    '카테고리', '온라인 쇼핑', '이커머스', 'e-commerce',
                    '쇼핑몰', '온라인몰', '스토어'
                ],
                'weight': 1
            },
            'platform': {
                'keywords': [
                    '플랫폼', '마켓플레이스', '판매자', '입점', '중개',
                    '파트너', '정산', '수수료', '거래', '매칭',
                    'marketplace', 'platform', '양면 플랫폼', '중개 서비스',
                    '공급자', '수요자', '커미션', '중개수수료'
                ],
                'weight': 2
            },
            'overseas': {
                'keywords': [
                    '해외', '글로벌', '수출', '해외진출', '글로벌 서비스',
                    '다국어', '해외 결제', '국제', 'global', 'overseas',
                    '현지화', '해외 배송', '크로스보더', 'cross-border',
                    '글로벌 확장', '해외 시장'
                ],
                'weight': 1.5
            },
            'b2b': {
                'keywords': [
                    'B2B', '기업 고객', '법인', '도매', '납품', '거래처',
                    '기업 서비스', '엔터프라이즈', 'enterprise', '대량 구매',
                    '견적', '계약', '법인 회원', 'corporate'
                ],
                'weight': 1.5
            },
            'content': {
                'keywords': [
                    '콘텐츠', '디지털 콘텐츠', '전자책', 'e-book', '강의',
                    '온라인 강의', '교육', '튜토리얼', '코스', 'course',
                    '동영상', 'VOD', '스트리밍', '음원', '미디어'
                ],
                'weight': 1.5
            }
        }
        
        # PortOne 솔루션 매핑
        self.solution_mapping = {
            'subscription': {
                'primary': '스마트 빌링키',
                'description': 'PG 종속에서 탈피하고 항상 가장 낮은 수수료로 정기결제를 처리합니다.',
                'pain_points': [
                    '여러 PG사의 빌링키를 통합 관리하기 어려움',
                    '구독자 이탈 시 빌링키 재등록 필요',
                    'PG사 변경 시 전체 구독자 재등록 필요',
                    '정기결제 실패율 관리 어려움'
                ],
                'benefits': [
                    'PG사 변경해도 빌링키 유지 (고객 재등록 불필요)',
                    '여러 PG사 중 가장 낮은 수수료로 자동 결제',
                    '결제 실패 시 자동으로 다른 PG사로 재시도',
                    '구독 관리 효율성 90% 향상'
                ],
                'keywords': ['빌링키', '정기결제', '구독', '자동결제', 'PG 종속']
            },
            'mobile_app': {
                'primary': '웹상점 개설',
                'description': '인앱결제 수수료(30%)를 회피하고 웹결제(2-3%)로 전환하여 수수료를 대폭 절감합니다.',
                'pain_points': [
                    '앱스토어/구글플레이 인앱결제 수수료 30% 부담',
                    '플랫폼 정책 변경에 따른 리스크',
                    '결제 수단 제한 (앱스토어 정책)',
                    '매출 증가 시 수수료 부담 급증'
                ],
                'benefits': [
                    '인앱결제 수수료 30% → 웹결제 2-3%로 절감',
                    '월 1억 매출 기준 연간 3억원 이상 절감',
                    '다양한 결제 수단 제공 가능',
                    '플랫폼 정책 독립성 확보'
                ],
                'keywords': ['인앱결제', '수수료 절감', '웹상점', '앱스토어', '구글플레이']
            },
            'ecommerce': {
                'primary': 'Prism (채널 통합 정산)',
                'description': '네이버, 쿠팡, 11번가 등 여러 채널의 정산을 자동으로 통합하고 대사합니다.',
                'pain_points': [
                    '여러 오픈마켓 정산 내역 수작업 확인',
                    '채널별 수수료 구조가 달라 비교 어려움',
                    '누락된 매출이나 숨겨진 수수료 발견 어려움',
                    '월말 정산에 며칠씩 소요'
                ],
                'benefits': [
                    '여러 채널 정산을 클릭 한 번으로 통합',
                    '채널별 수수료 비교 및 최적화',
                    '누락 매출 자동 감지',
                    '정산 업무 시간 90% 단축'
                ],
                'keywords': ['채널 통합', '정산 자동화', '오픈마켓', '수수료 비교']
            },
            'platform': {
                'primary': 'PS (파트너 정산 자동화)',
                'description': '플랫폼의 판매자/파트너 정산을 자동화하고 전자금융법 리스크를 해소합니다.',
                'pain_points': [
                    '수백~수천 명의 판매자 정산 수작업 처리',
                    '정산 오류로 인한 파트너 불만',
                    '전자금융법 위반 리스크 (지급대행업 무등록)',
                    '정산 데이터 엑셀 관리의 한계'
                ],
                'benefits': [
                    '파트너 정산 100% 자동화',
                    '세금계산서 자동 발행',
                    '전자금융법 리스크 완전 해소',
                    '정산 업무 시간 95% 단축'
                ],
                'keywords': ['파트너 정산', '지급대행', '전자금융법', '세금계산서']
            },
            'overseas': {
                'primary': 'OPI (글로벌 결제 통합)',
                'description': '100개 이상의 해외 간편결제를 단일 API로 연동하고 환율 손실을 최소화합니다.',
                'pain_points': [
                    '국가별 결제 수단 개별 연동 부담',
                    '환율 변동에 따른 수수료 손실',
                    '해외 PG사 계약 및 관리 복잡도',
                    '현지 결제 수단 미지원으로 전환율 하락'
                ],
                'benefits': [
                    '100+ 해외 간편결제 단일 API 연동',
                    '환율 최적화로 수수료 15-20% 절감',
                    '국가별 결제 수단 자동 최적화',
                    '글로벌 매출 30% 이상 증가 사례'
                ],
                'keywords': ['해외 결제', '글로벌', '간편결제', '환율', '현지화']
            },
            'high_volume': {
                'primary': '스마트 라우팅',
                'description': 'AI 기반으로 최적의 PG사를 자동 선택하여 수수료 절감과 안정성을 동시에 확보합니다.',
                'pain_points': [
                    '단일 PG사 장애 시 전체 매출 중단',
                    'PG사별 수수료 차이로 인한 손실',
                    '거래량 증가 시 승인률 하락',
                    '수동 PG사 변경의 번거로움'
                ],
                'benefits': [
                    'PG 수수료 15-30% 자동 절감',
                    '결제 안정성 15% 향상',
                    'AI 기반 실시간 최적 라우팅',
                    '연 수억원 수수료 절감 효과'
                ],
                'keywords': ['스마트 라우팅', 'PG 수수료', '안정성', '자동화']
            }
        }
    
    def analyze_business_model(self, homepage_content: str, research_data: Dict) -> Dict:
        """
        홈페이지와 조사 데이터를 분석하여 비즈니스 모델 파악
        
        Args:
            homepage_content: 홈페이지 HTML/텍스트 내용
            research_data: Perplexity 조사 결과
            
        Returns:
            Dict: {
                'primary_model': str,  # 주요 BM
                'secondary_models': List[str],  # 부가 BM
                'confidence': float,  # 신뢰도 (0-100)
                'detected_keywords': Dict,  # 감지된 키워드들
                'recommended_solutions': List[Dict]  # 추천 솔루션
            }
        """
        logger.info("🔍 비즈니스 모델 분석 시작")
        
        # 분석할 텍스트 통합
        combined_text = self._combine_text(homepage_content, research_data)
        
        # BM별 점수 계산
        bm_scores = self._calculate_bm_scores(combined_text)
        
        # 주요 BM 결정 (점수 기준)
        sorted_bms = sorted(bm_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        
        primary_model = sorted_bms[0][0] if sorted_bms else 'ecommerce'
        primary_score = sorted_bms[0][1]['score'] if sorted_bms else 0
        
        # 부가 BM (점수가 일정 수준 이상인 것들)
        secondary_models = [
            bm for bm, data in sorted_bms[1:4] 
            if data['score'] >= primary_score * 0.5  # 주요 BM의 50% 이상
        ]
        
        # 신뢰도 계산
        confidence = min(100, primary_score * 10)  # 10점 만점을 100점 만점으로 환산
        
        # 솔루션 추천
        recommended_solutions = self._recommend_solutions(
            primary_model, 
            secondary_models, 
            bm_scores
        )
        
        result = {
            'primary_model': primary_model,
            'primary_model_kr': self._translate_bm(primary_model),
            'secondary_models': secondary_models,
            'confidence': round(confidence, 1),
            'detected_keywords': {
                bm: data['keywords'] for bm, data in bm_scores.items()
            },
            'recommended_solutions': recommended_solutions,
            'bm_scores': {bm: data['score'] for bm, data in bm_scores.items()}
        }
        
        logger.info(f"✅ BM 분석 완료: {result['primary_model_kr']} (신뢰도: {confidence:.1f}%)")
        logger.info(f"   부가 BM: {[self._translate_bm(bm) for bm in secondary_models]}")
        
        return result
    
    def _combine_text(self, homepage_content: str, research_data: Dict) -> str:
        """분석할 텍스트 통합"""
        text_parts = []
        
        if homepage_content:
            text_parts.append(homepage_content)
        
        if research_data:
            if isinstance(research_data, dict):
                if 'company_info' in research_data:
                    text_parts.append(str(research_data['company_info']))
                if 'news' in research_data:
                    text_parts.append(str(research_data['news']))
            else:
                text_parts.append(str(research_data))
        
        return ' '.join(text_parts)
    
    def _calculate_bm_scores(self, text: str) -> Dict:
        """BM별 점수 계산"""
        text_lower = text.lower()
        bm_scores = {}
        
        for bm_type, config in self.bm_patterns.items():
            detected_keywords = []
            score = 0
            
            for keyword in config['keywords']:
                keyword_lower = keyword.lower()
                # 키워드 출현 횟수 카운트
                count = text_lower.count(keyword_lower)
                if count > 0:
                    detected_keywords.append(keyword)
                    # 가중치 적용 (중복 출현 시 추가 점수)
                    score += min(count, 3) * config['weight']  # 최대 3회까지만 카운트
            
            bm_scores[bm_type] = {
                'score': score,
                'keywords': detected_keywords,
                'keyword_count': len(detected_keywords)
            }
        
        return bm_scores
    
    def _recommend_solutions(self, primary_model: str, secondary_models: List[str], 
                            bm_scores: Dict) -> List[Dict]:
        """BM 기반 솔루션 추천"""
        solutions = []
        
        # 주요 BM에 대한 솔루션
        if primary_model in self.solution_mapping:
            solution = self.solution_mapping[primary_model].copy()
            solution['priority'] = 1
            solution['model_type'] = primary_model
            solutions.append(solution)
        
        # 부가 BM에 대한 솔루션
        for idx, model in enumerate(secondary_models[:2], start=2):  # 최대 2개
            if model in self.solution_mapping:
                solution = self.solution_mapping[model].copy()
                solution['priority'] = idx
                solution['model_type'] = model
                solutions.append(solution)
        
        # 거래량이 높을 것으로 추정되면 스마트 라우팅 추가
        if bm_scores.get('ecommerce', {}).get('score', 0) > 5 or \
           bm_scores.get('platform', {}).get('score', 0) > 5:
            if 'high_volume' not in [s['model_type'] for s in solutions]:
                solution = self.solution_mapping['high_volume'].copy()
                solution['priority'] = len(solutions) + 1
                solution['model_type'] = 'high_volume'
                solutions.append(solution)
        
        return solutions
    
    def _translate_bm(self, bm_type: str) -> str:
        """BM 타입 한글 번역"""
        translations = {
            'subscription': '구독/정기결제',
            'mobile_app': '모바일 앱',
            'ecommerce': '이커머스/쇼핑몰',
            'platform': '플랫폼/마켓플레이스',
            'overseas': '해외 진출',
            'b2b': 'B2B 거래',
            'content': '디지털 콘텐츠',
            'high_volume': '고거래량 커머스'
        }
        return translations.get(bm_type, bm_type)
    
    def generate_customized_pitch(self, bm_analysis: Dict, company_name: str) -> str:
        """BM 분석 결과 기반 맞춤형 세일즈 포인트 생성"""
        if not bm_analysis['recommended_solutions']:
            return ""
        
        primary_solution = bm_analysis['recommended_solutions'][0]
        
        pitch_parts = []
        
        # 1. BM 기반 Pain Point 제시
        if primary_solution['pain_points']:
            pain_point = primary_solution['pain_points'][0]  # 가장 중요한 것
            pitch_parts.append(f"혹시 {pain_point} 문제로 고민하고 계시지 않나요?")
        
        # 2. 솔루션 제안
        pitch_parts.append(
            f"\n\n포트원의 **{primary_solution['primary']}**는 {primary_solution['description']}"
        )
        
        # 3. 핵심 혜택
        if primary_solution['benefits']:
            top_benefit = primary_solution['benefits'][0]
            pitch_parts.append(f"\n\n특히 {top_benefit}의 효과가 입증되어 있습니다.")
        
        # 4. 복수 솔루션인 경우 추가 언급
        if len(bm_analysis['recommended_solutions']) > 1:
            second_solution = bm_analysis['recommended_solutions'][1]
            pitch_parts.append(
                f"\n\n또한 {second_solution['primary']}를 통해 "
                f"{second_solution['benefits'][0] if second_solution['benefits'] else second_solution['description']}"
            )
        
        return ''.join(pitch_parts)
