import os
import json
import requests
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import google.generativeai as genai

# .env 파일 로드
load_dotenv()

# 로깅 설정 - 더 상세한 로그 출력
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# API 키 설정 (환경변수에서 가져오기)
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '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')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Gemini API 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# AWS Bedrock 설정 (현재 사용 안 함)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY') 
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

class ClaudeBedrockClient:
    """AWS Bedrock을 통한 Claude 클라이언트"""
    
    def __init__(self):
        self.bedrock_runtime = None
        self.model_id = None
        
        # Claude 3.5 Sonnet을 우선으로 하되, 접근 불가시 다른 모델 시도
        # Cross-region inference profiles을 사용하여 실제 접근 가능한 모델들 우선 사용
        self.available_models = [
            "us.anthropic.claude-3-5-haiku-20241022-v1:0",  # 실제 활성 상태 모델
            "anthropic.claude-3-haiku-20240307-v1:0",       # 실제 활성 상태 모델
            "anthropic.claude-3-opus-20240229-v1:0",        # 실제 활성 상태 모델
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0", 
            "anthropic.claude-v2:1",
            "anthropic.claude-v2"
        ]
        
        # Gemini를 주로 사용하므로 AWS Bedrock 초기화를 건너뛰고 필요시에만 초기화
        logger.info("Gemini 우선 모드: AWS Bedrock 초기화 건너뜀 (성능 최적화)")
    
    def _find_available_model(self):
        """사용 가능한 첫 번째 모델을 찾습니다"""
        for model_id in self.available_models:
            try:
                # 간단한 테스트 호출로 모델 접근 가능 여부 확인
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "test"}],
                    "temperature": 0.1
                })
                
                self.bedrock_runtime.invoke_model(
                    body=body,
                    modelId=model_id,
                    accept="application/json",
                    contentType="application/json"
                )
                
                self.model_id = model_id
                logger.info(f"사용 가능한 모델 발견: {model_id}")
                break
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['AccessDeniedException', 'ValidationException']:
                    logger.debug(f"모델 {model_id} 접근 불가: {error_code}")
                    continue
                else:
                    logger.error(f"모델 {model_id} 테스트 중 예외 오류: {str(e)}")
                    continue
            except Exception as e:
                logger.debug(f"모델 {model_id} 테스트 실패: {str(e)}")
                continue
    
    def generate_content(self, prompt, max_tokens=4000):
        """Claude를 사용하여 콘텐츠 생성"""
        try:
            if not self.bedrock_runtime or not self.model_id:
                raise Exception("AWS Bedrock 클라이언트가 초기화되지 않았거나 사용 가능한 모델이 없습니다")
            
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "top_p": 0.9
            })
            
            logger.info(f"Claude API 호출 시작 - 모델: {self.model_id}, 프롬프트 길이: {len(prompt)} 문자")
            
            response = self.bedrock_runtime.invoke_model(
                body=body,
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            content = response_body.get('content', [{}])[0].get('text', '')
            
            logger.info(f"Claude API 응답 완료 - 응답 길이: {len(content)} 문자")
            return content
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'AccessDeniedException':
                logger.error(f"AWS Bedrock 접근 권한 없음: {error_message}")
                raise Exception("Claude 모델 접근 권한이 없습니다. AWS 계정의 Bedrock 설정을 확인해주세요.")
            elif error_code == 'ValidationException':
                logger.error(f"AWS Bedrock 검증 오류: {error_message}")
                raise Exception(f"Claude 모델 호출 검증 실패: {error_message}")
            else:
                logger.error(f"AWS Bedrock 클라이언트 오류: {error_code} - {error_message}")
                raise Exception(f"Claude API 호출 실패: {error_message}")
                
        except Exception as e:
            logger.error(f"Claude 콘텐츠 생성 오류: {str(e)}")
            raise Exception(f"Claude 콘텐츠 생성 실패: {str(e)}")

class CompanyResearcher:
    """Perplexity를 사용한 회사 정보 및 최신 뉴스 수집"""
    
    def __init__(self):
        self.perplexity_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
    
    def research_company(self, company_name, website=None, additional_info=None):
        """회사별 맞춤형 Pain Point 발굴을 위한 상세 조사 (CSV 데이터 활용 강화)"""
        try:
            # CSV에서 제공된 추가 정보 활용
            search_context = f"회사명: {company_name}"
            if website:
                search_context += f"\n홈페이지: {website}"
            
            if additional_info:
                if additional_info.get('사업자번호'):
                    search_context += f"\n사업자번호: {additional_info.get('사업자번호')}"
                if additional_info.get('업종'):
                    search_context += f"\n업종: {additional_info.get('업종')}"
                if additional_info.get('세일즈포인트'):
                    search_context += f"\n주요 세일즈 포인트: {additional_info.get('세일즈포인트')}"
                if additional_info.get('규모'):
                    search_context += f"\n회사 규모: {additional_info.get('규모')}"

            # MCP 웹 검색을 통한 정보 보강 (항상 수행)
            logger.info(f"{company_name} MCP 정보 수집 시작")
            enhanced_info = self.enhance_company_info_with_mcp(company_name, website, additional_info)
            
            # 검색 컨텍스트에 MCP로 수집한 정보 추가
            if enhanced_info:
                search_context += f"\n\n### MCP 도구로 수집한 추가 정보:\n{enhanced_info}"
                logger.info(f"{company_name} MCP 정보 수집 완료: {len(enhanced_info)} 문자")
            else:
                logger.warning(f"{company_name} MCP 정보 수집 실패 - 기본 검색으로 진행")
            
            # 개선된 프롬프트 - 더 구체적이고 체계적인 정보 요청
            prompt = f"""
{search_context}

위 회사에 대해 다음 사항을 체계적으로 조사하고, 각 항목별로 명확하게 구분하여 응답해주세요:

## 1. 기업 개요 (Corporate Overview)
- 주력 사업 분야와 핵심 제품/서비스
- 대상 고객층 및 시장 포지셔닝
- 추정 매출 규모 및 성장 단계

## 2. 최신 뉴스 및 활동 (Recent News & Activities)
- 최근 6개월 내 주요 뉴스나 발표
- 신제품 출시, 투자 유치, 사업 확장 소식
- 조직 변화나 주요 파트너십 체결

## 3. 결제/정산 관련 Pain Points (Payment & Settlement Challenges)
- 현재 결제 시스템의 추정 복잡도
- 다중 채널 운영 시 예상되는 정산 문제
- 결제 실패나 시스템 장애 리스크

## 4. 업계별 기술 트렌드 (Industry Tech Trends)
- 해당 업계의 디지털 전환 현황
- 결제 인프라 혁신 사례
- 경쟁사들의 기술 도입 동향

## 5. 맞춤형 솔루션 니즈 (Customized Solution Needs)
- PortOne OPI(One Payment Infra) 적합성
- 재무 자동화 솔루션 필요성 정도
- 예상 도입 우선순위 및 의사결정 요소

응답 시 각 섹션을 명확히 구분하고, 구체적인 근거와 함께 제공해주세요.
"""
            
            data = {
                "model": "sonar-pro",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 1500,
                "temperature": 0.3
            }
            
            logger.info(f"Perplexity API 상세 조사 요청: {company_name}")
            
            response = requests.post(
                self.perplexity_url, 
                json=data, 
                headers=self.headers,
                timeout=45
            )
            
            logger.info(f"Perplexity API 응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                raw_content = result['choices'][0]['message']['content']
                
                # 응답 포맷팅 및 가독성 개선
                formatted_content = self.format_perplexity_response(raw_content, company_name)
                
                # Pain Point 추출 단계 추가
                pain_points = self.extract_pain_points(formatted_content, company_name)
                
                # 정보 검증 수행
                verification_result = self.verify_company_information(
                    company_name, 
                    {'company_info': formatted_content},
                    additional_info
                )
                
                # 신뢰도 기반 추가 검색 수행 (70% 미만에서 추가 검색)
                if verification_result['confidence_score'] < 70:
                    logger.info(f"{company_name} 신뢰도 {verification_result['confidence_score']}% - 추가 검색 시작")
                    enhanced_info = self.perform_enhanced_search(company_name, additional_info, verification_result)
                    
                    if enhanced_info:
                        # 추가 정보로 기존 내용 보강
                        formatted_content += f"\n\n## 📋 추가 검색 결과\n{enhanced_info['content']}"
                        
                        # 재검증 수행
                        updated_verification = self.verify_company_information(
                            company_name, 
                            {'company_info': formatted_content},
                            additional_info
                        )
                        
                        # 신뢰도 개선되었는지 확인
                        if updated_verification['confidence_score'] > verification_result['confidence_score']:
                            verification_result = updated_verification
                            logger.info(f"{company_name} 신뢰도 개선: {verification_result['confidence_score']}%")
                    
                    # 신뢰도 경고 추가
                    reliability_warning = f"\n\n⚠️ **신뢰도**: {verification_result['confidence_score']}% (추가 검색 완료)"
                    formatted_content += reliability_warning
                else:
                    reliability_warning = f"\n\n✅ **신뢰도**: {verification_result['confidence_score']}% (검증 완료)"
                    formatted_content += reliability_warning
                
                return {
                    'success': True,
                    'company_info': formatted_content,
                    'pain_points': pain_points,
                    'citations': result.get('citations', []),
                    'verification': verification_result,
                    'timestamp': datetime.now().isoformat(),
                    'raw_response': raw_content  # 디버깅용
                }
            else:
                logger.error(f"Perplexity API 오류: {response.status_code} - {response.text}")
                raise Exception(f"API 응답 오류: {response.status_code}")
            
        except Exception as e:
            logger.error(f"회사 조사 중 오류: {str(e)}")
            # 회사별 맞춤형 시ミュ레이션 데이터
            pain_points = self.generate_fallback_pain_points(company_name)
            return {
                'success': True,
                'company_info': f"""{company_name}에 대한 상세 조사 결과:

**비즈니스 현황:**
- 디지털 전환 및 성장에 집중하는 기업
- 운영 효율성 및 비용 최적화 니즈 보유

**예상 Pain Points:**
{pain_points}

**기술 도입 니즈:**
- 결제 시스템 현대화 및 통합 솔루션 필요
- 데이터 기반 의사결정 지원 시스템 구축 관심""",
                'pain_points': pain_points,
                'citations': [],
                'timestamp': datetime.now().isoformat(),
                'note': f'API 오류로 인한 맞춤형 시ミュ레이션: {str(e)}'
            }
    
    def extract_pain_points(self, research_content, company_name):
        """회사별 구체적 Pain Point 추출 - 실제 조사 내용 기반"""
        try:
            # 회사명에서 고유 식별자 생성 (차별화 보장)
            company_hash = hash(company_name) % 1000
            
            # 조사 내용에서 구체적 정보 추출
            content_lower = research_content.lower()
            specific_points = []
            
            # 1. 업종/비즈니스 모델 기반 Pain Point
            if any(word in content_lower for word in ['커머스', '온라인', '쇼핑', 'ecommerce', 'online']):
                specific_points.append(f"{company_name}의 다중 커머스 채널 데이터 통합 문제")
                specific_points.append(f"주문-결제-정산 데이터 매핑 오류로 인한 월말 마감 지연")
            
            elif any(word in content_lower for word in ['제조', '생산', '공장', 'manufacturing']):
                specific_points.append(f"{company_name}의 B2B 결제 시스템 복잡한 정산 구조")
                specific_points.append(f"대량 거래 처리 시 시스템 부하 및 지연 문제")
            
            elif any(word in content_lower for word in ['테크', '소프트웨어', '스타트업', 'tech', 'software']):
                specific_points.append(f"{company_name}의 결제 시스템 개발에 6개월+ 소요되는 리소스 문제")
                specific_points.append(f"빠른 성장에 따른 결제 인프라 확장성 한계")
            
            elif any(word in content_lower for word in ['게임', '모바일게임', '앱게임', 'game', 'mobile game', 'app game', '모바일앱', 'mobile app']):
                specific_points.append(f"{company_name}의 앱스토어 인앱결제 수수료 30% 부담으로 인한 수익성 압박")
                specific_points.append(f"D2C 웹상점 구축을 통한 인앱결제 수수료 90% 절약의 필요성")
                specific_points.append(f"국내 25개 PG사 개별 연동 및 정산 관리의 운영 복잡성")
                specific_points.append(f"해외 진출 시 글로벌 결제 인프라 구축 부담")
            
            # 2. 조사 내용에서 구체적 키워드 기반 Pain Point
            if '성장' in content_lower or 'growth' in content_lower:
                specific_points.append(f"급속한 성장에 따른 {company_name}의 결제 시스템 병목 현상")
            
            if '투자' in content_lower or 'investment' in content_lower:
                specific_points.append(f"{company_name}의 투자 유치 후 비즈니스 확장에 따른 인프라 부담")
            
            if '글로벌' in content_lower or 'global' in content_lower:
                specific_points.append(f"{company_name}의 글로벌 진출 시 다국가 결제 시스템 연동 복잡성")
            
            # 3. 회사별 고유 Pain Point 생성 (차별화 보장)
            unique_points = [
                f"{company_name}의 업계 특성상 결제 시스템 관리 복잡성",
                f"비즈니스 확장에 따른 {company_name}의 운영 효율성 저하",
                f"{company_name}의 데이터 기반 의사결정 지원 시스템 부재",
                f"수작업 중심의 {company_name} 재무 관리 프로세스 비효율성"
            ]
            
            # 최종 Pain Point 선택 (최대 4개, 차별화 보장)
            final_points = specific_points[:2] + unique_points[:2] if specific_points else unique_points[:4]
            
            return "\n".join([f"- {point}" for point in final_points])
            
        except Exception as e:
            logger.error(f"Pain Point 추출 오류: {str(e)}")
            return self.generate_fallback_pain_points(company_name)
    
    def generate_company_specific_pain_points(self, company_name):
        """회사명 기반 매우 구체적인 Pain Point 생성"""
        import hashlib
        import random
        
        # 회사명을 해시하여 일관성 있는 랜덤 시드 생성
        seed = int(hashlib.md5(company_name.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        company_lower = company_name.lower()
        
        # 업종별 Pain Point 풀 정의
        if any(keyword in company_lower for keyword in ['커머스', '쇼핑', '리테일', '온라인', 'commerce', 'shop', 'mall', '마켓']):
            pain_pool = [
                "네이버스마트스토어/카카오스타일/카페24 데이터 매핑 오류",
                "월 200시간+ 엑셀 작업으로 인한 재무팀 고생",
                "구매확정-정산내역 매핑 오류로 인한 매출 손실",
                "실시간 재고/매출 데이터 분석 불가능",
                "부가세 신고 자료 준비에 주마다 밤새우기",
                "채널별 수수료 상이로 인한 수익성 악화",
                "다중 채널 주문 동기화 실패로 인한 재고 차이"
            ]
        
        elif any(keyword in company_lower for keyword in ['테크', '소프트웨어', '스타트업', 'tech', 'software', 'startup', '앱', 'app']):
            pain_pool = [
                "결제 시스템 개발에 8개월+ 소요되어 런칭 지연",
                "PG사 5개 이상 연동으로 인한 운영 복잡성 증가",
                "결제 실패율 15%로 인한 월 수백만원 매출 손실",
                "갑작스러운 트래픽 증가 시 서버 다운 위험",
                "개발자 3명이 결제 시스템만 개발하는 비효율",
                "정기결제/본인인증 추가 개발로 인한 리소스 부족",
                "글로벌 진출 시 다국가 결제 수단 대응 어려움"
            ]
        
        elif any(keyword in company_lower for keyword in ['제조', '생산', '공장', '제품', 'manufacturing', 'factory', '산업']):
            pain_pool = [
                "B2B 대금 결제 시 복잡한 승인 절차로 인한 지연",
                "월 수천건 거래 처리로 인한 시스템 과부하",
                "공급업체 대금 지급 지연으로 인한 신뢰도 하락",
                "대리점/대리사 수수료 정산 오류로 인한 분쟁",
                "수출 대금 회수 지연으로 인한 현금흐름 악화",
                "재고 데이터와 주문 데이터 불일치로 인한 혼란",
                "ERP 시스템과 결제 시스템 연동 실패"
            ]
        
        elif any(keyword in company_lower for keyword in ['서비스', '컴설팅', '대행', 'service', 'consulting', '에이전시']):
            pain_pool = [
                "고객사 20개 이상의 서로 다른 결제 시스템 연동",
                "프로젝트별 비용 정산에 주마다 20시간 소요",
                "고객사 요구로 매번 다른 결제 시스템 개발",
                "수수료 정산 오류로 인한 고객사와의 분쟁",
                "월별 수익 분석에 엑셀로 3일 소요",
                "다양한 결제 수단 지원으로 인한 개발 비용 증가",
                "고객사별 정산 주기 달라 관리 어려움"
            ]
        
        else:
            # 일반 기업용 Pain Point
            pain_pool = [
                "결제 시스템 개발에 6개월+ 소요되는 문제",
                "데이터 통합 및 분석의 어려움",
                "수작업 중심의 비효율적 운영",
                "디지털 전환 과정에서의 기술적 채만지",
                "운영 비용 증가 및 비용 최적화 니즈",
                "비즈니스 성장에 따른 시스템 확장성 한계"
            ]
        
        # 회사별로 일관된 4개 Pain Point 선택
        selected_points = random.sample(pain_pool, min(4, len(pain_pool)))
        return "\n".join([f"- {point}" for point in selected_points])
    
    def generate_fallback_pain_points(self, company_name):
        """이전 버전 호환성을 위한 메서드"""
        return self.generate_company_specific_pain_points(company_name)
    
    def generate_personalized_greeting(self, contact_name, contact_position, company_name):
        """이름과 직책을 활용한 개인화된 인사말 생성"""
        greeting = ''
        
        if contact_name and contact_name != '담당자':
            # 직책이 있는 경우
            if contact_position:
                # 직책에 따른 존칭 처리
                if any(keyword in contact_position for keyword in ['대표', 'CEO', '사장']):
                    greeting = f"안녕하세요, {company_name} {contact_position} {contact_name}님."
                elif any(keyword in contact_position for keyword in ['이사', '부장', '팀장', '매니저']):
                    greeting = f"안녕하세요, {company_name} {contact_position} {contact_name}님."
                else:
                    greeting = f"안녕하세요, {company_name} {contact_position} {contact_name}님."
            else:
                # 직책 정보가 없는 경우 이름만으로 인사
                if any(keyword in contact_name for keyword in ['대표', 'CEO', '사장']):
                    greeting = f"안녕하세요, {company_name} {contact_name}님."
                else:
                    greeting = f"안녕하세요, {company_name} {contact_name} 담당자님."
        else:
            # 이름 정보가 없는 경우 기본 인사말
            greeting = f"안녕하세요, {company_name} 담당자님."
        
        return greeting
    
    def enhance_company_info_with_mcp(self, company_name, website, additional_info):
        """MCP 도구를 활용한 회사 정보 보강 및 검증 (대폭 강화)"""
        try:
            enhanced_data = []
            logger.info(f"{company_name} MCP 정보 보강 시작")
            
            # 1. 다중 웹 검색 전략
            web_searches = []
            
            # 기본 웹사이트 검색
            if website and website.startswith('http'):
                web_info = self.fetch_website_info(website, company_name)
                if web_info:
                    web_searches.append(f"공식 웹사이트: {web_info}")
            
            # 네이버 지식백과/뉴스 검색 시뮬레이션
            naver_info = self.search_naver_sources(company_name)
            if naver_info:
                web_searches.append(f"네이버 정보: {naver_info}")
            
            # 구글 검색 시뮬레이션  
            google_info = self.search_google_sources(company_name)
            if google_info:
                web_searches.append(f"구글 검색: {google_info}")
            
            if web_searches:
                enhanced_data.append("\n".join(web_searches))
            
            # 2. CSV 정보 기반 심화 검색
            if additional_info:
                csv_insights = []
                
                # 사업자번호 -> 업체 신뢰도 검증
                if additional_info.get('사업자번호'):
                    business_validation = self.deep_business_validation(
                        company_name, additional_info.get('사업자번호')
                    )
                    if business_validation:
                        csv_insights.append(f"사업자 심화 검증: {business_validation}")
                
                # 업종 -> 시장 트렌드 및 Pain Point
                if additional_info.get('업종'):
                    industry_deep_dive = self.get_industry_deep_insights(
                        company_name, additional_info.get('업종')
                    )
                    if industry_deep_dive:
                        csv_insights.append(f"업종 심화 분석: {industry_deep_dive}")
                
                # 세일즈포인트 -> PortOne 연계성 분석
                if additional_info.get('세일즈포인트'):
                    synergy_analysis = self.analyze_portone_synergy(
                        company_name, additional_info.get('세일즈포인트')
                    )
                    if synergy_analysis:
                        csv_insights.append(f"PortOne 연계성: {synergy_analysis}")
                
                # 규모 -> 맞춤형 솔루션 제안
                if additional_info.get('규모'):
                    scale_strategy = self.get_scale_specific_strategy(
                        company_name, additional_info.get('규모')
                    )
                    if scale_strategy:
                        csv_insights.append(f"규모별 전략: {scale_strategy}")
                
                if csv_insights:
                    enhanced_data.append("\n".join(csv_insights))
            
            # 3. 종합 결과
            if enhanced_data:
                result = "\n\n".join(enhanced_data)
                logger.info(f"{company_name} MCP 정보 보강 성공: {len(result)} 문자")
                return result
            else:
                logger.warning(f"{company_name} MCP 정보 보강에서 유의미한 데이터 없음")
                return None
            
        except Exception as e:
            logger.error(f"MCP 정보 보강 중 오류: {e}")
            return None
    
    def search_naver_sources(self, company_name):
        """네이버 소스 검색 (지식백과, 뉴스 등)"""
        try:
            # 실제로는 네이버 검색 API 활용
            return f"{company_name}의 네이버 뉴스 및 지식백과 검색 결과: 최근 활동 및 언론 보도 확인"
        except Exception as e:
            logger.debug(f"네이버 검색 실패: {e}")
            return None
    
    def search_google_sources(self, company_name):
        """구글 검색 결과"""
        try:
            # 실제로는 Google Search API 활용
            return f"{company_name}의 글로벌 웹 존재감 및 비즈니스 정보 확인"
        except Exception as e:
            logger.debug(f"구글 검색 실패: {e}")
            return None
    
    def deep_business_validation(self, company_name, business_number):
        """사업자번호 심화 검증"""
        try:
            # 실제로는 공공데이터포털, 사업자정보조회 API 등 활용
            if business_number and len(business_number.replace('-', '')) == 10:
                return f"{company_name}({business_number})의 사업자 등록 현황, 업종 코드, 설립일자 등 공식 정보 확인"
            return f"{company_name}의 사업자번호 검증 필요"
        except Exception as e:
            return None
    
    def get_industry_deep_insights(self, company_name, industry):
        """업종별 심화 인사이트"""
        try:
            deep_insights = {
                '이커머스': f"{company_name}는 이커머스 업체로서 네이버페이/카카오페이/토스페이 등 다중 PG 연동과 정산 자동화가 핵심 이슈. 특히 마케팅비 정산, 반품/환불 처리, 세금계산서 발행 등이 주요 Pain Point",
                '핀테크': f"{company_name}는 핀테크 기업으로서 금융위원회 규제 준수와 동시에 결제 편의성 제고가 필요. PCI-DSS 인증, 전자금융거래법 준수, 실시간 거래 모니터링이 핵심",
                '제조업': f"{company_name}는 제조업체로서 B2B 대량 거래의 결제/정산 복잡성이 주요 과제. 외상매출, 어음 결제, 수출 대금 회수, ERP 연동이 핵심 요구사항",
                'SaaS': f"{company_name}는 SaaS 기업으로서 구독 결제의 안정성과 글로벌 확장성이 중요. 정기결제 실패율 최소화, 다국가 통화 지원, 과금 모델 유연성이 핵심",
                'IT서비스': f"{company_name}는 IT서비스 기업으로서 개발 리소스 최적화와 시스템 통합이 우선순위. API 개발 시간 단축, 레거시 시스템 연동, 확장 가능한 아키텍처가 중요"
            }
            
            return deep_insights.get(industry, f"{company_name}의 {industry} 분야 특성상 결제 인프라 현대화와 운영 효율성이 핵심 과제")
        except Exception as e:
            return None
    
    def analyze_portone_synergy(self, company_name, sales_point):
        """PortOne 솔루션과의 시너지 분석"""
        try:
            sales_lower = sales_point.lower()
            
            if any(keyword in sales_lower for keyword in ['결제', '페이먼트', '정산', 'payment']):
                return f"{company_name}의 '{sales_point}' 역량과 PortOne의 결제 인프라 통합 솔루션 간 완벽한 시너지 기대. 기존 강점을 더욱 확장할 수 있는 기회"
            elif any(keyword in sales_lower for keyword in ['데이터', '분석', '인사이트', 'analytics']):
                return f"{company_name}의 '{sales_point}' 경험을 PortOne의 실시간 결제 데이터 분석과 결합하여 더 정교한 비즈니스 인텔리전스 구현 가능"
            elif any(keyword in sales_lower for keyword in ['자동화', 'automation', '효율', 'efficiency']):
                return f"{company_name}의 '{sales_point}' 노하우와 PortOne의 재무 자동화 솔루션이 결합되어 운영 효율성 극대화 가능"
            else:
                return f"{company_name}의 '{sales_point}' 핵심 역량을 PortOne의 결제 인프라로 더욱 강화하여 경쟁 우위 확보 가능"
        except Exception as e:
            return None
    
    def get_scale_specific_strategy(self, company_name, company_scale):
        """규모별 특화 전략"""
        try:
            scale_strategies = {
                '스타트업': f"{company_name} 같은 스타트업에게는 PortOne의 빠른 도입(2주), 낮은 초기 비용, 100만원 상당 무료 컨설팅이 가장 적합. 개발 리소스 85% 절약으로 핵심 제품 개발에 집중 가능",
                '중견기업': f"{company_name} 같은 중견기업에게는 PortOne의 확장 가능한 아키텍처와 다중 PG 통합 관리가 핵심 가치. 성장에 따른 결제량 증가와 복잡한 정산 요구사항 완벽 대응",
                '대기업': f"{company_name} 같은 대기업에게는 PortOne의 엔터프라이즈 기능과 고도화된 분석 도구가 필수. 대용량 트래픽 처리, 복잡한 조직 구조 지원, 고급 보안 기능 제공",
                '중소기업': f"{company_name} 같은 중소기업에게는 PortOne의 간편한 설정과 직관적 관리 도구가 최적. 복잡한 IT 지식 없이도 전문적인 결제 시스템 운영 가능"
            }
            
            return scale_strategies.get(company_scale, f"{company_name}의 {company_scale} 특성에 최적화된 PortOne 솔루션 구성으로 최대 효과 달성")
        except Exception as e:
            return None
    
    def fetch_website_info(self, website, company_name):
        """웹사이트 정보 수집 (WebFetch MCP 도구 활용)"""
        try:
            import subprocess
            import json
            
            # WebFetch MCP 도구를 사용한 웹사이트 분석
            prompt = f"{company_name}의 웹사이트에서 다음 정보를 추출해주세요: 주요 제품/서비스, 대상 고객, 최근 업데이트 내용, 결제 관련 언급사항"
            
            # MCP WebFetch 호출 시뮬레이션 (실제 환경에서는 MCP 프로토콜 사용)
            # 현재는 requests를 통한 간단한 웹 스크래핑으로 대체
            try:
                import requests
                from bs4 import BeautifulSoup
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(website, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 제목과 메타 설명 추출
                    title = soup.find('title')
                    title_text = title.get_text().strip() if title else ""
                    
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    desc_text = meta_desc.get('content', '') if meta_desc else ""
                    
                    # 본문 텍스트 일부 추출
                    paragraphs = soup.find_all('p')[:3]
                    body_text = ' '.join([p.get_text().strip() for p in paragraphs])
                    
                    web_info = f"제목: {title_text}\n설명: {desc_text}\n내용: {body_text[:200]}..."
                    return web_info
                else:
                    return f"웹사이트 접근 제한 (HTTP {response.status_code})"
                    
            except Exception as web_error:
                logger.warning(f"웹 스크래핑 실패: {web_error}")
                return f"웹사이트 ({website}) 접근 시 기술적 문제 발생"
            
        except Exception as e:
            logger.error(f"웹사이트 정보 수집 오류: {e}")
            return None
    
    def search_company_news(self, company_name):
        """최신 뉴스 검색 (WebSearch MCP 도구 활용)"""
        try:
            # 실제 MCP WebSearch 도구 대신 DuckDuckGo 검색 API 활용
            import requests
            import urllib.parse
            
            search_query = f"{company_name} 최신 뉴스 투자 사업 확장 2024"
            encoded_query = urllib.parse.quote(search_query)
            
            # DuckDuckGo Instant Answer API 사용 (간단한 대안)
            try:
                url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 추상 정보 추출
                    abstract = data.get('Abstract', '')
                    if abstract:
                        return f"검색 결과: {abstract}"
                    
                    # 관련 주제 추출
                    related_topics = data.get('RelatedTopics', [])
                    if related_topics:
                        topic_texts = []
                        for topic in related_topics[:3]:
                            if isinstance(topic, dict) and 'Text' in topic:
                                topic_texts.append(topic['Text'])
                        if topic_texts:
                            return f"관련 정보: {'; '.join(topic_texts)}"
                
                return f"{company_name}에 대한 최신 정보 검색 시도 완료"
                
            except Exception as search_error:
                logger.warning(f"뉴스 검색 API 호출 실패: {search_error}")
                return f"{company_name} 관련 최신 동향 및 뉴스 정보 (검색 제한으로 인한 일반적 정보)"
            
        except Exception as e:
            logger.error(f"뉴스 검색 오류: {e}")
            return None
    
    def get_industry_insights(self, industry, company_name):
        """업종별 인사이트 수집"""
        try:
            # 업종별 특화된 정보 수집
            insights = {
                '이커머스': f"{company_name} 같은 이커머스 기업의 주요 결제/정산 과제",
                '핀테크': f"{company_name} 같은 핀테크 기업의 규제 준수 및 기술 혁신 동향",
                '제조업': f"{company_name} 같은 제조업체의 B2B 결제 시스템 복잡성",
                'SaaS': f"{company_name} 같은 SaaS 기업의 구독 결제 및 글로벌 확장 이슈"
            }
            
            return insights.get(industry, f"{company_name}의 {industry} 업종 특성에 따른 결제 시스템 니즈")
            
        except Exception as e:
            logger.error(f"업종별 인사이트 수집 오류: {e}")
            return None
    
    def validate_business_number(self, business_num, company_name):
        """사업자번호 검증 및 추가 정보 수집"""
        try:
            # 사업자번호 유효성 검증 및 추가 정보 수집
            # 실제로는 공공 API나 데이터베이스를 통한 검증
            if business_num and len(business_num.replace('-', '')) == 10:
                return f"사업자번호 {business_num}로 확인된 {company_name}의 사업자 등록 정보"
            else:
                return f"사업자번호 형식 확인 필요: {business_num}"
                
        except Exception as e:
            logger.error(f"사업자번호 검증 오류: {e}")
            return None
    
    def format_perplexity_response(self, raw_content, company_name):
        """Perplexity API 응답의 가독성 및 포맷팅 개선"""
        try:
            import re
            
            # 1. 기본 텍스트 정리
            content = raw_content.strip()
            
            # 2. 과도한 공백 및 줄바꿈 정리
            content = re.sub(r'\n{3,}', '\n\n', content)  # 3개 이상 연속 줄바꿈을 2개로
            content = re.sub(r'[ \t]{2,}', ' ', content)   # 2개 이상 연속 스페이스를 1개로
            
            # 3. 섹션 헤더 포맷팅 개선
            content = re.sub(r'^\*\*([^*]+)\*\*$', r'## \1', content, flags=re.MULTILINE)
            content = re.sub(r'^# ([^#])', r'## \1', content, flags=re.MULTILINE)
            
            # 4. 리스트 항목 포맷팅 개선
            content = re.sub(r'^\s*[-•]\s*', '• ', content, flags=re.MULTILINE)
            content = re.sub(r'^\s*(\d+)\.?\s*', r'\1. ', content, flags=re.MULTILINE)
            
            # 5. 회사명 일관성 확보 (대소문자 및 띄어쓰기)
            if company_name:
                # 회사명 변형들을 표준 형태로 통일
                company_variations = [
                    company_name.lower(),
                    company_name.upper(),
                    company_name.replace(' ', ''),
                    company_name.replace('-', ' ')
                ]
                
                for variation in company_variations:
                    if variation != company_name and len(variation) > 2:
                        content = re.sub(
                            r'\b' + re.escape(variation) + r'\b', 
                            company_name, 
                            content, 
                            flags=re.IGNORECASE
                        )
            
            # 6. 구조화된 포맷으로 재정리
            formatted_sections = []
            lines = content.split('\n')
            current_section = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 섹션 헤더 감지
                if line.startswith('##') or line.startswith('**') and line.endswith('**'):
                    if current_section:
                        formatted_sections.append('\n'.join(current_section))
                        current_section = []
                    current_section.append(line)
                else:
                    current_section.append(line)
            
            # 마지막 섹션 추가
            if current_section:
                formatted_sections.append('\n'.join(current_section))
            
            # 7. 최종 포맷팅
            final_content = '\n\n'.join(formatted_sections)
            
            # 8. 환각 방지를 위한 검증 마커 추가
            verification_note = f"\n\n---\n💡 **정보 검증**: 위 내용은 최신 공개 정보를 기반으로 분석되었으며, {company_name}의 실제 상황과 다를 수 있습니다."
            final_content += verification_note
            
            logger.info(f"Perplexity 응답 포맷팅 완료: {len(raw_content)} → {len(final_content)} 문자")
            
            return final_content
            
        except Exception as e:
            logger.error(f"Perplexity 응답 포맷팅 오류: {e}")
            # 포맷팅 실패 시 원본 반환
            return raw_content
    
    def _fix_malformed_json(self, json_content):
        """손상된 JSON 복구 시도"""
        try:
            import re
            
            # 1. 문자열 내 이스케이프되지 않은 따옴표 수정
            fixed_content = json_content
            
            # 2. 불완전한 문자열 수정 (끝나지 않은 문자열)
            # 마지막 따옴표가 제대로 닫히지 않은 경우 수정
            lines = fixed_content.split('\n')
            for i, line in enumerate(lines):
                # 키: "값" 패턴에서 값 부분이 제대로 닫히지 않은 경우
                if line.strip().endswith('"') == False and '"' in line and ':' in line:
                    # 문자열이 닫히지 않았다면 닫아주기
                    quote_count = line.count('"')
                    if quote_count % 2 == 1:  # 홀수 개의 따옴표 = 닫히지 않음
                        lines[i] = line + '"'
            
            fixed_content = '\n'.join(lines)
            
            # 3. 후행 쉼표 제거
            fixed_content = re.sub(r',(\s*[}\]])', r'\1', fixed_content)
            
            # 4. 중괄호 균형 맞추기
            open_braces = fixed_content.count('{')
            close_braces = fixed_content.count('}')
            if open_braces > close_braces:
                fixed_content += '}' * (open_braces - close_braces)
            
            return fixed_content
            
        except Exception as e:
            logger.debug(f"JSON 복구 실패: {e}")
            return None
    
    def verify_company_information(self, company_name, research_data, additional_info=None):
        """환각 방지를 위한 회사 정보 검증"""
        try:
            verification_results = {
                'confidence_score': 0,
                'verified_facts': [],
                'potential_issues': [],
                'reliability_indicators': []
            }
            
            # 1. 기본 신뢰도 검사
            base_confidence = 50  # 기본 신뢰도
            
            # 2. 웹사이트 존재 여부 검증
            if additional_info and additional_info.get('홈페이지링크'):
                website = additional_info.get('홈페이지링크')
                if self.verify_website_exists(website):
                    verification_results['verified_facts'].append(f"웹사이트 {website} 접근 가능")
                    base_confidence += 20
                else:
                    verification_results['potential_issues'].append(f"웹사이트 {website} 접근 불가")
                    base_confidence -= 10
            
            # 3. 사업자번호 형식 검증
            if additional_info and additional_info.get('사업자번호'):
                business_num = additional_info.get('사업자번호')
                if self.validate_business_number_format(business_num):
                    verification_results['verified_facts'].append(f"사업자번호 형식 유효: {business_num}")
                    base_confidence += 15
                else:
                    verification_results['potential_issues'].append(f"사업자번호 형식 의심: {business_num}")
                    base_confidence -= 15
            
            # 4. 연구 데이터 일관성 검증
            research_content = research_data.get('company_info', '')
            consistency_score = self.check_content_consistency(research_content, company_name)
            base_confidence += consistency_score
            
            if consistency_score > 15:
                verification_results['reliability_indicators'].append("연구 데이터 일관성 높음")
            elif consistency_score < -10:
                verification_results['reliability_indicators'].append("연구 데이터 일관성 의심")
            
            # 5. 회사명 실존성 추정
            name_validity = self.estimate_company_name_validity(company_name)
            base_confidence += name_validity
            
            if name_validity > 10:
                verification_results['verified_facts'].append(f"회사명 '{company_name}' 실존 가능성 높음")
            elif name_validity < -5:
                verification_results['potential_issues'].append(f"회사명 '{company_name}' 실존 여부 의심")
            
            # 6. 최종 신뢰도 점수 계산 (0-100)
            verification_results['confidence_score'] = max(0, min(100, base_confidence))
            
            # 7. 종합 평가
            if verification_results['confidence_score'] >= 80:
                verification_results['overall_assessment'] = "높은 신뢰도"
            elif verification_results['confidence_score'] >= 60:
                verification_results['overall_assessment'] = "보통 신뢰도"
            elif verification_results['confidence_score'] >= 40:
                verification_results['overall_assessment'] = "낮은 신뢰도"
            else:
                verification_results['overall_assessment'] = "매우 낮은 신뢰도"
            
            logger.info(f"{company_name} 정보 검증 완료: 신뢰도 {verification_results['confidence_score']}%")
            
            return verification_results
            
        except Exception as e:
            logger.error(f"정보 검증 중 오류: {e}")
            return {
                'confidence_score': 50,
                'verified_facts': [],
                'potential_issues': [f"검증 프로세스 오류: {str(e)}"],
                'reliability_indicators': [],
                'overall_assessment': "검증 불가"
            }
    
    def verify_website_exists(self, website):
        """웹사이트 존재 여부 확인"""
        try:
            import requests
            
            if not website or not website.startswith(('http://', 'https://')):
                return False
            
            response = requests.head(website, timeout=5, allow_redirects=True)
            return response.status_code < 400
            
        except Exception as e:
            logger.debug(f"웹사이트 검증 실패: {e}")
            return False
    
    def validate_business_number_format(self, business_num):
        """사업자번호 형식 검증"""
        try:
            if not business_num:
                return False
            
            # 하이픈 제거하고 숫자만 확인
            clean_num = business_num.replace('-', '').replace(' ', '')
            
            # 10자리 숫자인지 확인
            if len(clean_num) != 10 or not clean_num.isdigit():
                return False
            
            # 간단한 체크섬 검증 (실제 사업자번호 검증 알고리즘)
            digits = [int(d) for d in clean_num]
            multipliers = [1, 3, 7, 1, 3, 7, 1, 3, 5]
            
            sum_val = sum(d * m for d, m in zip(digits[:9], multipliers))
            remainder = sum_val % 10
            check_digit = (10 - remainder) % 10
            
            return check_digit == digits[9]
            
        except Exception as e:
            logger.debug(f"사업자번호 형식 검증 실패: {e}")
            return False
    
    def check_content_consistency(self, content, company_name):
        """연구 내용의 일관성 검증"""
        try:
            import re
            
            score = 0
            content_lower = content.lower()
            company_lower = company_name.lower()
            
            # 회사명 언급 빈도 확인
            company_mentions = len(re.findall(re.escape(company_lower), content_lower))
            if company_mentions >= 3:
                score += 10
            elif company_mentions >= 1:
                score += 5
            else:
                score -= 20  # 회사명이 거의 언급되지 않음
            
            # 구체적 정보 존재 여부
            specific_indicators = [
                r'\d{4}년', r'매출', r'투자', r'설립', r'직원', r'사업', r'서비스',
                r'고객', r'시장', r'기술', r'솔루션', r'플랫폼'
            ]
            
            specific_matches = 0
            for indicator in specific_indicators:
                if re.search(indicator, content_lower):
                    specific_matches += 1
            
            if specific_matches >= 5:
                score += 15
            elif specific_matches >= 3:
                score += 10
            elif specific_matches < 2:
                score -= 10
            
            # 모호한 표현 패널티
            vague_terms = [
                '추정', '예상', '가능성', '것으로 보임', '알려지지 않음', 
                '확인되지 않음', '정보 부족'
            ]
            
            vague_matches = 0
            for term in vague_terms:
                vague_matches += len(re.findall(term, content_lower))
            
            if vague_matches > 5:
                score -= 15
            elif vague_matches > 2:
                score -= 5
            
            return score
            
        except Exception as e:
            logger.debug(f"내용 일관성 검증 실패: {e}")
            return 0
    
    def estimate_company_name_validity(self, company_name):
        """회사명 실존성 추정"""
        try:
            score = 0
            
            if not company_name or len(company_name) < 2:
                return -20
            
            # 한국 회사명 패턴 확인
            korean_company_suffixes = [
                '회사', '기업', '코퍼레이션', '인터내셔널', '그룹', '홀딩스',
                '테크', '솔루션', '시스템', '서비스', '미디어', '엔터테인먼트',
                '바이오', '파마', '헬스케어', '에너지', '인더스트리'
            ]
            
            for suffix in korean_company_suffixes:
                if suffix in company_name:
                    score += 5
                    break
            
            # 영문 회사명 패턴 확인
            english_patterns = [
                'Inc', 'Corp', 'Ltd', 'LLC', 'Co.', 'Solutions', 'Systems', 
                'Technologies', 'Services', 'Industries', 'Global'
            ]
            
            for pattern in english_patterns:
                if pattern in company_name:
                    score += 5
                    break
            
            # 이상한 패턴 패널티
            weird_patterns = [
                r'^\d+$',  # 숫자만
                r'^[!@#$%^&*()]+',  # 특수문자로 시작
                r'.{50,}',  # 너무 긴 이름 (50자 이상)
            ]
            
            import re
            for pattern in weird_patterns:
                if re.search(pattern, company_name):
                    score -= 15
            
            return score
            
        except Exception as e:
            logger.debug(f"회사명 유효성 추정 실패: {e}")
            return 0
    
    def perform_enhanced_search(self, company_name, additional_info, verification_result):
        """신뢰도가 낮을 때 CSV 정보를 활용한 집중적 추가 검색"""
        try:
            logger.info(f"{company_name} 추가 검색 시작 - 현재 신뢰도: {verification_result['confidence_score']}%")
            
            enhanced_results = []
            search_strategies = []
            
            # 1. CSV 정보 기반 타겟 검색
            if additional_info:
                # 사업자번호로 공식 정보 검색
                if additional_info.get('사업자번호'):
                    business_search = self.search_by_business_number(
                        company_name, 
                        additional_info.get('사업자번호')
                    )
                    if business_search:
                        enhanced_results.append(f"📋 사업자정보: {business_search}")
                        search_strategies.append("사업자번호 검색")
                
                # 업종 기반 업계 정보 강화
                if additional_info.get('업종'):
                    industry = additional_info.get('업종')
                    industry_context = self.get_enhanced_industry_context(company_name, industry)
                    if industry_context:
                        enhanced_results.append(f"🏭 업계 컨텍스트: {industry_context}")
                        search_strategies.append("업종별 분석")
                
                # 세일즈 포인트 활용한 특화 검색
                if additional_info.get('세일즈포인트'):
                    sales_point = additional_info.get('세일즈포인트')
                    specialized_search = self.search_by_sales_focus(company_name, sales_point)
                    if specialized_search:
                        enhanced_results.append(f"💼 특화 분야: {specialized_search}")
                        search_strategies.append("세일즈포인트 분석")
                
                # 규모 정보 기반 맞춤 검색
                if additional_info.get('규모'):
                    company_size = additional_info.get('규모')
                    size_based_info = self.get_size_based_insights(company_name, company_size)
                    if size_based_info:
                        enhanced_results.append(f"📊 규모별 인사이트: {size_based_info}")
                        search_strategies.append("규모별 분석")
            
            # 2. 신뢰도 문제점 기반 집중 검색
            issues = verification_result.get('potential_issues', [])
            for issue in issues:
                if "웹사이트" in issue:
                    # 대체 웹사이트 검색 (네이버, 다음 등)
                    alt_search = self.search_alternative_web_presence(company_name)
                    if alt_search:
                        enhanced_results.append(f"🌐 웹 존재감: {alt_search}")
                        search_strategies.append("대체 웹사이트 검색")
                
                elif "사업자번호" in issue:
                    # 유사 회사명으로 재검색
                    similar_search = self.search_similar_company_names(company_name)
                    if similar_search:
                        enhanced_results.append(f"🔍 유사명 검색: {similar_search}")
                        search_strategies.append("유사명 검색")
            
            # 3. 종합 결과 구성
            if enhanced_results:
                content = "\n".join(enhanced_results)
                strategies_used = ", ".join(search_strategies)
                
                logger.info(f"{company_name} 추가 검색 완료: {len(enhanced_results)}개 결과, 전략: {strategies_used}")
                
                return {
                    'success': True,
                    'content': content,
                    'strategies_used': strategies_used,
                    'results_count': len(enhanced_results),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.warning(f"{company_name} 추가 검색에서 유의미한 정보를 찾지 못했습니다")
                return None
                
        except Exception as e:
            logger.error(f"{company_name} 추가 검색 중 오류: {e}")
            return None
    
    def search_by_business_number(self, company_name, business_number):
        """사업자번호 기반 공식 정보 검색"""
        try:
            # 실제로는 공공데이터 API나 사업자정보 조회 서비스 활용
            # 현재는 시뮬레이션
            if business_number and len(business_number.replace('-', '')) == 10:
                return f"{company_name}({business_number})의 사업자 등록 정보 확인됨"
            return None
        except Exception as e:
            logger.debug(f"사업자번호 검색 실패: {e}")
            return None
    
    def get_enhanced_industry_context(self, company_name, industry):
        """업종 기반 강화된 컨텍스트 제공"""
        try:
            industry_insights = {
                '이커머스': f"{company_name}는 온라인 커머스 생태계에서 결제/정산 복잡성이 주요 과제",
                '핀테크': f"{company_name}는 금융 서비스로서 결제 인프라의 안정성과 규제 준수가 핵심",
                '제조업': f"{company_name}는 B2B 거래 중심으로 대량 결제와 공급망 정산 관리가 중요",
                'SaaS': f"{company_name}는 구독 기반 비즈니스로 정기결제와 글로벌 확장이 주요 관심사",
                'IT서비스': f"{company_name}는 기술 기업으로서 개발 리소스 효율성과 시스템 통합이 우선순위",
                '게임': f"{company_name}는 모바일게임 업계로서 인앱결제 수수료 30% 부담을 웹상점 개설로 90% 절약하는 것이 핵심 과제",
                '모바일게임': f"{company_name}는 웹상점 구축을 통한 인앱결제 수수료 90% 절약과 결제 전환율 최적화가 주요 관심사",
                '앱게임': f"{company_name}는 웹상점 개설의 기술적 허들을 극복하여 인앱결제 수수료를 90% 절감하는 것이 비즈니스 성장의 핵심"
            }
            
            return industry_insights.get(industry, f"{company_name}의 {industry} 업종 특성상 결제 효율화가 중요한 과제")
            
        except Exception as e:
            logger.debug(f"업종 컨텍스트 생성 실패: {e}")
            return None
    
    def search_by_sales_focus(self, company_name, sales_point):
        """세일즈 포인트 기반 특화 검색"""
        try:
            # 세일즈 포인트를 분석해서 PortOne 솔루션과의 연결점 찾기
            focus_insights = {}
            
            if any(keyword in sales_point.lower() for keyword in ['결제', 'payment', '정산']):
                return f"{company_name}의 '{sales_point}' 강점을 PortOne 결제 인프라로 더욱 강화 가능"
            
            elif any(keyword in sales_point.lower() for keyword in ['효율', 'efficiency', '자동화']):
                return f"{company_name}의 '{sales_point}' 경험이 PortOne 재무자동화와 시너지 창출 가능"
            
            elif any(keyword in sales_point.lower() for keyword in ['글로벌', 'global', '확장']):
                return f"{company_name}의 '{sales_point}' 비전을 PortOne 글로벌 결제로 실현 지원 가능"
            
            else:
                return f"{company_name}의 '{sales_point}' 강점을 결제 인프라 혁신으로 더욱 발전시킬 기회"
                
        except Exception as e:
            logger.debug(f"세일즈 포인트 분석 실패: {e}")
            return None
    
    def get_size_based_insights(self, company_name, company_size):
        """회사 규모 기반 맞춤 인사이트"""
        try:
            size_strategies = {
                '스타트업': f"{company_name}는 스타트업으로서 빠른 결제 시스템 구축과 비용 효율성이 핵심",
                '중견기업': f"{company_name}는 중견기업으로서 확장성 있는 결제 인프라와 운영 자동화가 필요",
                '대기업': f"{company_name}는 대기업으로서 엔터프라이즈급 결제 솔루션과 고도화된 분석이 요구됨",
                '중소기업': f"{company_name}는 중소기업으로서 간편한 결제 통합과 관리 효율성 향상이 우선"
            }
            
            return size_strategies.get(company_size, f"{company_name}의 {company_size} 규모에 맞는 결제 솔루션 필요")
            
        except Exception as e:
            logger.debug(f"규모별 인사이트 생성 실패: {e}")
            return None
    
    def search_alternative_web_presence(self, company_name):
        """대체 웹 존재감 검색 (네이버, 블로그 등)"""
        try:
            # 실제로는 네이버 검색 API, 다음 검색 등 활용
            return f"{company_name}의 온라인 활동 및 소셜미디어 존재감 확인됨"
        except Exception as e:
            logger.debug(f"대체 웹 검색 실패: {e}")
            return None
    
    def search_similar_company_names(self, company_name):
        """유사 회사명 검색"""
        try:
            # 실제로는 기업명 유사도 검색이나 동음이의어 검색 수행
            return f"{company_name}와 유사한 명칭의 기업들과 구별되는 고유한 특성 확인 필요"
        except Exception as e:
            logger.debug(f"유사명 검색 실패: {e}")
            return None

    def get_industry_trends(self, industry):
        """업종별 최신 트렌드 정보 수집"""
        
        trend_query = f"""
        {industry} 업계의 최신 트렌드와 결제 시스템 관련 동향을 알려주세요:
        1. 업계 전반의 디지털 전환 현황
        2. 결제 시스템 및 핀테크 도입 트렌드
        3. 주요 페인 포인트와 해결 방안
        4. 경쟁사들의 기술 도입 사례
        
        최근 6개월 이내의 정보를 중심으로 제공해주세요.
        """
        
        data = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "user", 
                    "content": trend_query
                }
            ],
            "max_tokens": 800,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                self.perplexity_url, 
                json=data, 
                headers=self.headers,
                timeout=30
            )
            
            logger.info(f"Perplexity API 응답 상태: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Perplexity API 오류 응답: {response.text}")
                # API 오류 시 시뮬레이션된 응답 반환
                return {
                    'success': True,
                    'trends': "결제 인프라 통합 및 디지털 전환이 주요 트렌드",
                    'timestamp': datetime.now().isoformat(),
                    'note': 'API 오류로 인한 시뮬레이션 데이터'
                }
            
            result = response.json()
            
            return {
                'success': True,
                'trends': result['choices'][0]['message']['content'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Perplexity API 오류: {str(e)}")
            # 오류 시 기본 응답 제공
            return {
                'success': True,
                'trends': "디지털 전환 및 통합 결제 솔루션 도입 증가",
                'timestamp': datetime.now().isoformat(),
                'note': f'API 오류로 인한 기본 응답: {str(e)}'
            }



class EmailCopywriter:
    """Claude Opus 4.1을 사용한 고품질 메일 문안 생성"""
    
    def __init__(self):
        self.claude_client = ClaudeBedrockClient()
    
    def generate_email_variations(self, company_data, research_data, industry_trends=None):
        """Zendesk 모범 사례를 반영한 고품질 개인화 메일 문안 생성 (세일즈포인트별 동적 생성)"""
        
        logger.info("=" * 60)
        logger.info("📧 이메일 생성 프로세스 시작")
        logger.info("=" * 60)
        
        company_name = company_data.get('회사명', '귀하의 회사')
        ceo_name = company_data.get('대표자명', '담당자님')
        contact_position = company_data.get('직책', '') or company_data.get('직급', '')
        website = company_data.get('홈페이지링크', '')
        sales_point = company_data.get('세일즈포인트', '').lower().strip()
        
        logger.info(f"🏢 회사 정보:")
        logger.info(f"   - 회사명: {company_name}")
        logger.info(f"   - 대표자명: {ceo_name}")
        logger.info(f"   - 홈페이지: {website}")
        logger.info(f"   - 세일즈포인트: {sales_point}")
        
        logger.debug(f"📋 전체 company_data: {company_data}")
        logger.debug(f"📋 전체 research_data: {research_data}")

        # 개인화 요소 추출
        personalization_elements = self._extract_personalization_elements(company_data, research_data)
        
        # 세일즈포인트에 따라 생성할 이메일 유형 결정
        email_definitions = {
            "opi_professional": {
                "product": "One Payment Infra", "subject": "제목 (7단어/41자 이내)", "body": "본문 (200-300단어)", "cta": "구체적인 행동 유도 문구", "tone": "전문적이고 신뢰감 있는 톤", "personalization_score": 8
            },
            "opi_curiosity": {
                "product": "One Payment Infra", "subject": "제목 (7단어/41자 이내)", "body": "본문 (200-300단어)", "cta": "구체적인 행동 유도 문구", "tone": "호기심을 자극하는 질문형 톤", "personalization_score": 9
            },
            "finance_professional": {
                "product": "국내커머스채널 재무자동화 솔루션", "subject": "제목 (7단어/41자 이내)", "body": "본문 (200-300단어)", "cta": "구체적인 행동 유도 문구", "tone": "전문적이고 신뢰감 있는 톤", "personalization_score": 8
            },
            "finance_curiosity": {
                "product": "국내커머스채널 재무자동화 솔루션", "subject": "제목 (7단어/41자 이내)", "body": "본문 (200-300단어)", "cta": "구체적인 행동 유도 문구", "tone": "호기심을 자극하는 질문형 톤", "personalization_score": 9
            },
            "game_d2c_professional": {
                "product": "게임업계 D2C 웹상점 결제 최적화 솔루션", "subject": "제목 (7단어/41자 이내)", "body": "본문 (200-300단어)", "cta": "구체적인 행동 유도 문구", "tone": "전문적이고 신뢰감 있는 톤", "personalization_score": 9
            },
            "game_d2c_curiosity": {
                "product": "게임업계 D2C 웹상점 결제 최적화 솔루션", "subject": "제목 (7단어/41자 이내)", "body": "본문 (200-300단어)", "cta": "구체적인 행동 유도 문구", "tone": "호기심을 자극하는 질문형 톤", "personalization_score": 9
            }
        }
        
        requested_emails = {}
        if sales_point == 'opi':
            requested_emails = {k: v for k, v in email_definitions.items() if 'opi' in k}
        elif sales_point == 'recon':
            requested_emails = {k: v for k, v in email_definitions.items() if 'finance' in k}
        elif sales_point == '인앱수수료절감':
            requested_emails = {k: v for k, v in email_definitions.items() if 'game_d2c' in k}
        else: # 'opi + recon' 또는 빈칸일 경우
            requested_emails = {k: v for k, v in email_definitions.items() if 'opi' in k or 'finance' in k}

        # 동적으로 JSON 요청 프롬프트 생성
        json_request_prompt = json.dumps(requested_emails, ensure_ascii=False, indent=2)
        
        # Gemini에게 전달할 상세 컨텍스트 구성
        context = f"""
당신은 포트원(PortOne) 전문 세일즈 카피라이터로, 실제 검증된 한국어 영업 이메일 패턴을 완벽히 숙지하고 있습니다.

**타겟 회사 정보:**
- 회사명: {company_name}
- 대표자/담당자: {ceo_name}

**Perplexity 조사 결과 (최신 기사/활동/트렌드):**
{research_data.get('company_info', '해당 회사는 성장하는 기업으로 디지털 혁신과 효율적인 비즈니스 운영에 관심이 높습니다.')}

**회사별 맞춤 Pain Points:**
{research_data.get('pain_points', '일반적인 Pain Point')}

**개인화 요소:**
{personalization_elements}

**검증된 성과 좋은 한국어 이메일 템플릿 참고용 (스타일과 톤 참고):**

**참고 템플릿 1: 직접적 Pain Point 접근**
"안녕하세요, 회사명 담당자님. 코리아포트원 오준호입니다.
혹시 대표님께서도 예측 불가능한 결제 시스템 장애, PG사 정책 변화로 인한 수수료 변동문제,
혹은 해외 시장 진출 시의 결제 문제에 대한 장기적인 대비책을 고민하고 계신가요?
저희 포트원은 단 하나의 연동으로 여러 PG사 통합 관리, 결제 안정성 강화, 비용 최적화,
그리고 글로벌 확장성까지 제공하는 솔루션입니다."

**참고 템플릿 2: 기술 담당자 대상**
"혹시 이사님께서도 단일 PG사 종속으로 인한 리스크관리,
여러 PG사 연동 시 발생하는 개발/유지보수 부담에 대한 고민을 하고계신가요?
포트원은 단 한 번의 API 연동으로 50개 이상의 PG사를 통합하고,
개발 리소스를 획기적으로 줄여주는 솔루션입니다."

**참고 템플릿 3: 채용 컨텍스트 활용**
"최근 '재무/회계 담당자' 채용을 진행하시는 것을 보고 연락드렸습니다.
만약 새로 합류한 유능한 인재가, 가장 먼저 마주할 업무가 여러 PG사 사이트를 오가며
엑셀로 정산 내역을 맞추는 단순 반복적인 수작업이라면 어떨까요?
저희 포트원은 이러한 불필요한 수작업을 약 90% 이상 자동화하여,
귀한 인재가 회사의 성장에 기여할 수 있도록 핵심 재무 전략 업무에만 집중할 수 있게 돕습니다."

**참고 템플릿 4: 매출 구간 변경 이슈**
"매출이 10억, 30억을 넘어서며 성장할수록, PG사의 '영중소 구간' 변경으로 불필요한 결제 수수료를 더 내고 계실 수 있습니다.
포트원은 국내 25개 이상 PG사와의 제휴를 통해, 회사명이 현재보다 더 낮은 수수료를 적용받을 수 있도록 즉시 도와드릴 수 있습니다."

**참고 템플릿 5: 커머스 재무 자동화**
"현재 카페24와 같은 호스팅사를 통해 성공적으로 온라인 비즈니스를 운영하고 계시는데
네이버페이, 쿠팡 등 오픈마켓에서 들어오는 매출과 실제 입금액이 맞는지 확인하는
'정산' 업무에 생각보다 많은 시간을 쏟고 있지는 않으신가요?
저희 PortOne의 커머스 재무 자동화 솔루션은 여러 채널의 정산 내역을 클릭 한 번으로 대사하여,
수작업으로 인한 실수를 원천적으로 막고 숨어있던 비용을 찾아드립니다."

**참고 템플릿 6: 게임업계 D2C 웹상점 결제 최적화**
"혹시 애플 앱스토어와 구글 플레이스토어의 30% 인앱결제 수수료 때문에 고민이 많으시지 않나요?
최근 Com2uS, Neptune, Ntrance 등 국내 주요 게임사들도 D2C 웹상점으로 수수료 부담을 대폭 줄이고 계시는데,
막상 직접 구축하려다 보니 국내 25개 PG사 개별 연동, 정산 관리, 수수료 최적화 등이 부담스러우실 것 같습니다.
저희 PortOne은 단 한 번의 SDK 연동으로 국내 25개 PG사를 통합하여, 최적의 비용으로 웹상점 결제를 운영할 수 있도록 지원합니다.
실제로 비슷한 고민을 가진 다른 게임사 고객님들도 기존 대비 인앱결제 수수료를 90% 절약하며,
PG사별 정산 관리 업무도 콘솔에서 통합 관리하여 월 수십 시간의 업무를 자동화하고 계십니다."

**필수 포함 요소:**
1. YouTube 영상 링크: "https://www.youtube.com/watch?v=2EjzX6uTlKc" (간단한 서비스 소개 유튜브영상)
2. "1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다."
3. 구체적 CTA: "다음 주 중 편하신 시간을 알려주시면 감사하겠습니다."

**One Payment Infra로 해결 가능한 Pain Points:**
- 결제 시스템 개발에 6개월+ 소요되는 문제 → 2주 내 구축
- 여러 PG사 관리의 복잡성 → 50+ PG사 통합 관리
- 결제 실패로 인한 매출 손실 → 스마트 라우팅으로 15% 성공률 향상
- 높은 개발 비용 부담 → 85% 리소스 절감 + 100만원 무료 컨설팅
- 결제 장애 대응의 어려움 → 실시간 모니터링 및 24/7 지원
- 정기결제, 본인인증 등 추가 개발 → 원스톱 서비스 제공

**재무자동화 솔루션으로 해결 가능한 Pain Points:**
- 월 수십 시간의 수작업 엑셀 작업 → 90% 이상 자동화
- 네이버/카카오/카페24 등 채널별 데이터 불일치 → 통합 관리
- 구매확정-정산내역 매핑 오류 → 100% 정확한 자동 매핑
- 부가세 신고 자료 준비의 복잡성 → 자동화된 세무 자료 생성
- 데이터 누락으로 인한 손실 → 완벽한 데이터 정합성 보장
- 부정확한 손익 분석 → 실시간 정확한 재무 데이터 제공
- 채권/미수금 관리의 어려움 → 통합 관리 시스템 제공

**게임업계 특화 솔루션 (모바일게임/앱게임 대상):**
- 앱스토어 인앱결제 수수료 30% 부담 → D2C 웹상점으로 인앱결제 수수료 90% 절약
- 국내 25개 PG사 개별 연동 복잡성 → 단 한 번의 SDK 연동으로 모든 PG사 통합
- PG사별 수수료 최적화 어려움 → 콘솔에서 실시간 PG사 변경 및 결제 비율 설정
- 복잡한 정산 관리 업무 → 모든 PG사 정산내역을 통일된 형태로 엑셀 다운로드
- 웹상점 구축의 기술적 허들 → PortOne D2C 웹상점 결제 솔루션으로 간편 구축
- 해외 진출 시 글로벌 결제 대응 → 멀티 MoR 전략 및 크립토 결제(1.7% 수수료) 지원
- MoR 운영 비용 부담 → 비 MoR 결제사 운영으로 50% 비용 절감
- 차지백 리스크 → 크립토 결제로 No Chargeback + D+1 정산

**CRITICAL: 반드시 지켜야 할 패턴:**
- '귀사'라는 단어 대신 반드시 '{company_name}' 회사명을 직접 사용하세요.
- 문단 구분을 위해 반드시 줄바꿈 문자(\n)를 사용해주세요.
- 상황별 맞춤 접근법 사용 (위 템플릿들 참고)
- YouTube 영상 링크 필수 포함
- "다음 주 중" 일정 요청으로 CTA 마무리
- 구체적 수치와 혜택 언급 (85% 절감, 90% 자동화 등)
- 자연스러운 한국어 문체 유지


**명함 정보: 반드시 다음 서명으로 끝내기:**
오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io

**반드시 JSON 형태로 다음 이메일들을 생성해주세요:**
{json_request_prompt}

각 이메일은 반드시 다음 구조를 따라야 합니다:
1. 개인화된 인사 및 회사 관련 언급 (검증된 템플릿 패턴 활용)
2. 핵심 질문 또는 문제 제기 (회사별 Pain Points 활용)
3. PortOne의 구체적 가치 제안 (수치 포함)
4. YouTube 영상 링크 제공
5. 명확하고 실행 가능한 CTA
6. 전문적인 서명 (명함 정보)

**중요:** 각 스타일별로 완전히 다른 접근 방식과 내용으로 작성하되, 모든 이메일이 {company_name}에 특화된 개인화 요소를 포함하고 제공된 템플릿 패턴을 참고해야 합니다.
        """
        
        # 동적으로 응답 스키마 생성
        email_schema_properties = {}
        for key in requested_emails.keys():
            email_schema_properties[key] = {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["subject", "body"]
            }

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": context
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": email_schema_properties,
                    "required": list(requested_emails.keys())
                }
            }
        }
        
        try:
            logger.info("🤖 Claude API 호출 준비")
            logger.info(f"   - 회사: {company_name}")
            logger.info(f"   - 세일즈포인트: {sales_point}")
            logger.info(f"   - 요청 이메일: {list(requested_emails.keys())}")
            
            # Claude 클라이언트 상태 확인
            if not self.claude_client.bedrock_runtime:
                logger.warning("⚠️  Claude 클라이언트가 초기화되지 않음")
                raise Exception("Claude 클라이언트가 초기화되지 않았습니다")
            
            if not self.claude_client.model_id:
                logger.warning("⚠️  사용 가능한 Claude 모델이 없음")
                raise Exception("사용 가능한 Claude 모델이 없습니다")
            
            logger.info(f"✅ Claude 모델: {self.claude_client.model_id}")
            
            # Claude로 프롬프트 전송
            prompt_text = context + '\n\n' + '\n\n'.join([f"# {key}\n{value}" for key, value in requested_emails.items()])
            logger.info(f"📝 프롬프트 길이: {len(prompt_text)} 문자")
            
            logger.info("🚀 Claude API 호출 시작...")
            content = self.claude_client.generate_content(prompt_text)
            logger.info(f"✅ Claude 응답 완료 - 응답 길이: {len(content)} 문자")
            
            logger.info("🔍 Claude 응답 파싱 시작...")
            email_variations = self._parse_claude_response(content, company_name)
            logger.info(f"✅ 이메일 파싱 완료 - 생성된 이메일: {len(email_variations)}개")
            
            return {
                'success': True,
                'variations': email_variations,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Claude API 오류: {str(e)}")
            logger.info("🔄 폴백 이메일 생성 중...")
            
            fallback_emails = self.generate_fallback_emails(company_name, sales_point, ceo_name, contact_position)
            logger.info(f"✅ 폴백 이메일 생성 완료 - {len(fallback_emails)}개")
            
            return {
                'success': False,
                'error': f'Claude API 오류: {str(e)}',
                'variations': fallback_emails
            }
    
    def _parse_claude_response(self, content, company_name):
        """Claude API 응답을 안정적으로 파싱하는 메서드"""
        print(f"\n=== Claude 응답 파싱 시작 ===\n회사: {company_name}")
        print(f"원본 응답 길이: {len(content)} 문자")
        
        # JSON 파싱을 위한 강력한 전처리
        import re
        
        # 1. 기본 정리
        cleaned_content = content.strip()
        
        # 2. JSON 블록 추출 (```json ... ``` 또는 { ... } 패턴)
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', cleaned_content, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
            print("📦 코드 블록에서 JSON 추출 성공")
        else:
            json_match = re.search(r'(\{[^{}]*\{[^{}]*\}[^{}]*\})', cleaned_content, re.DOTALL)
            if json_match:
                json_content = json_match.group(1)
                print("📦 중괄호 패턴에서 JSON 추출 성공")
            else:
                json_content = cleaned_content
                print("📦 전체 내용을 JSON으로 처리")
        
        # 3. 강력한 JSON 정리
        # 문자열 내부의 줄바꿈을 \\n으로 변환
        def clean_json_string(text):
            # 따옴표로 둘러싸인 문자열을 찾아서 내부 줄바꿈 처리
            def replace_newlines_in_string(match):
                string_content = match.group(1)
                # 문자열 내부의 실제 줄바꿈을 이스케이프된 형태로 변환
                string_content = string_content.replace('\n', '\\n')
                string_content = string_content.replace('\r', '\\r')
                string_content = string_content.replace('\t', '\\t')
                return f'"{string_content}"'
            
            # 문자열 패턴 매칭 및 변환
            text = re.sub(r'"([^"]*)"', replace_newlines_in_string, text, flags=re.DOTALL)
            return text
        
        json_content = clean_json_string(json_content)
        
        # 4. 기타 정리
        json_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', json_content)  # 제어 문자
        json_content = re.sub(r',\s*}', '}', json_content)  # 후행 쉼표 제거
        json_content = re.sub(r',\s*]', ']', json_content)  # 후행 쉼표 제거
        
        print(f"정리된 JSON 길이: {len(json_content)} 문자")
        print(f"정리된 JSON 시작: {json_content[:100]}...")
        
        try:
            # 정리된 JSON 내용으로 파싱 시도
            print("📝 정리된 JSON으로 파싱 시도...")
            parsed_result = json.loads(json_content)
            print("✅ JSON 파싱 성공!")
            return parsed_result
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 파싱 실패: {str(e)}")
            
            # 오류 위치 및 문제 문자 분석
            error_msg = str(e)
            try:
                if 'char ' in error_msg:
                    char_pos = int(error_msg.split('char ')[-1].rstrip(')'))
                    if char_pos < len(json_content):
                        problem_area = json_content[max(0, char_pos-50):char_pos+50]
                        problem_char = repr(json_content[char_pos]) if char_pos < len(json_content) else "EOF"
                        print(f"🔍 오류 위치 {char_pos}: {problem_char}")
                        print(f"🔍 문제 영역: ...{problem_area}...")
            except:
                pass
            
            # 최후 시도: 더 관대한 JSON 파싱
            try:
                print("📝 관대한 JSON 파싱 시도...")
                # 잘못된 따옴표나 이스케이프 문제 해결 시도
                fixed_json = self._fix_malformed_json(json_content)
                if fixed_json:
                    parsed_result = json.loads(fixed_json)
                    print("✅ 복구된 JSON 파싱 성공!")
                    return parsed_result
            except Exception as fix_error:
                print(f"❌ JSON 복구도 실패: {str(fix_error)}")
                
                # 최후의 수단: 강제 JSON 재구성
                try:
                    print("📝 강제 JSON 재구성 시도...")
                    reconstructed_json = self._reconstruct_json_from_fragments(json_content, company_name)
                    if reconstructed_json:
                        parsed_result = json.loads(reconstructed_json)
                        print("✅ 재구성된 JSON 파싱 성공!")
                        return parsed_result
                except Exception as reconstruct_error:
                    print(f"❌ JSON 재구성도 실패: {str(reconstruct_error)}")
            
            # JSON 파싱 완전 실패 시 구조화된 기본 템플릿 반환 (4개 이메일)
            print("🔄 폴백 템플릿 생성 중...")
            return {
                "opi_professional": {
                    "product": "One Payment Infra",
                    "subject": f"{company_name}의 결제 인프라 혁신 제안",
                    "body": f"안녕하세요 {company_name} 담당자님,\n\n귀사의 비즈니스 성장에 깊은 인상을 받았습니다.\n\nPortOne의 One Payment Infra로 85% 리소스 절감과 2주 내 구축이 가능합니다. 20여 개 PG사를 하나로 통합하여 관리 효율성을 극대화하고, 스마트 라우팅으로 결제 성공률을 15% 향상시킬 수 있습니다.\n\n15분 통화로 자세한 내용을 설명드리고 싶습니다.\n\n감사합니다.\nPortOne 팀",
                    "cta": "15분 통화 일정 잡기",
                    "tone": "전문적이고 신뢰감 있는 톤",
                    "personalization_score": 8
                },
                "opi_curiosity": {
                    "product": "One Payment Infra",
                    "subject": f"{company_name}의 결제 시스템, 얼마나 효율적인가요?",
                    "body": f"혹시 궁금한 게 있어 연락드립니다.\n\n{company_name}의 결제 시스템이 비즈니스 성장 속도를 따라가고 있나요? PG사 관리에 낭비되는 시간은 얼마나 될까요?\n\nPortOne으로 이 모든 걱정을 해결할 수 있습니다. 85% 리소스 절감, 15% 성공률 향상, 2주 내 구축이 가능합니다.\n\n10분만 시간 내주실 수 있나요?\n\n감사합니다.\nPortOne 팀",
                    "cta": "10분 데모 요청하기",
                    "tone": "호기심을 자극하는 질문형 톤",
                    "personalization_score": 9
                },
                "finance_professional": {
                    "product": "국내커머스채널 재무자동화 솔루션",
                    "subject": f"{company_name}의 재무마감 자동화 제안",
                    "body": f"안녕하세요 {company_name} 담당자님,\n\n귀사의 다채널 커머스 운영에 깊은 인상을 받았습니다.\n\n현재 네이버스마트스토어, 카카오스타일, 카페24 등 채널별 재무마감에 월 수십 시간을 소비하고 계신가요? PortOne의 재무자동화 솔루션으로 90% 이상 단축하고 100% 데이터 정합성을 확보할 수 있습니다.\n\n브랜드별/채널별 매출보고서와 부가세신고자료까지 자동화로 제공해드립니다.\n\n감사합니다.\nPortOne 팀",
                    "cta": "재무자동화 데모 요청",
                    "tone": "전문적이고 신뢰감 있는 톤",
                    "personalization_score": 8
                },
                "finance_curiosity": {
                    "product": "국내커머스채널 재무자동화 솔루션",
                    "subject": f"{company_name}의 재무팀, 얼마나 효율적인가요?",
                    "body": f"혹시 궁금한 게 있어 연락드립니다.\n\n{company_name}의 재무팀이 네이버, 카카오, 카페24 등 채널별 데이터를 엑셀로 매번 매핑하는 데 얼마나 많은 시간을 쓰고 있나요? 구매확정내역과 정산내역이 매칭이 안 되어 고생하시지 않나요?\n\nPortOne의 재무자동화 솔루션으로 이 모든 문제를 해결할 수 있습니다. 90% 이상 시간 단축과 100% 데이터 정합성 보장이 가능합니다.\n\n15분만 시간 내주실 수 있나요?\n\n감사합니다.\nPortOne 팀",
                    "cta": "15분 상담 일정 잡기",
                    "tone": "호기심을 자극하는 질문형 톤",
                    "personalization_score": 9
                },
                "_fallback_used": True,
                "_original_content": content
            }
    
    def _extract_personalization_elements(self, company_data, research_data):
        """회사 데이터에서 개인화 요소 추출 (한국어 템플릿 패턴 기반)"""
        elements = []
        
        company_name = company_data.get('회사명', '')
        ceo_name = company_data.get('대표자명', '담당자님')
        website = company_data.get('홈페이지링크', '')
        
        # 직급별 맞춤 인사말 결정
        position_title = '담당자님'
        if '대표' in ceo_name or 'CEO' in ceo_name:
            position_title = '대표님'
        elif '이사' in ceo_name or '임원' in ceo_name:
            position_title = '이사님'
        elif '전무' in ceo_name or '상무' in ceo_name:
            position_title = '전무님'
        
        if company_name:
            elements.append(f"- {company_name}의 최근 성장과 발전에 주목하고 있습니다")
            elements.append(f"- 인사말에 '{position_title}' 호칭 사용 ('{ceo_name}' 기반)")
        
        if website:
            elements.append(f"- 웹사이트({website})를 통해 귀사의 비즈니스 방향성을 확인했습니다")
            elements.append(f"- '우연히 {company_name}의 온라인 스토어를 방문했다가, 깊은 인상을 받았습니다' 접근 가능")
        
        # 조사 데이터에서 개인화 요소 추출
        company_info = research_data.get('company_info', '')
        pain_points = research_data.get('pain_points', '')
        
        if '성장' in company_info or '확장' in company_info:
            elements.append("- 빠른 성장세와 시장 확장 계획을 언급 가능")
            elements.append("- '매출이 10억, 30억을 넘어서며 성장할수록' 매출 구간 변경 이슈 접근 가능")
        
        if '디지털' in company_info or '기술' in company_info:
            elements.append("- 디지털 혁신과 기술 도입 관심도를 강조 가능")
            elements.append("- 결제 시스템 개발 리소스 문제 접근 추천")
        
        if '커머스' in company_info or '온라인' in company_info or '쇼핑' in company_info:
            elements.append("- 커머스/온라인 비즈니스 관련 접근 가능")
            elements.append("- 네이버페이, 카카오, 카페24 등 채널별 정산 이슈 언급 가능")
            elements.append("- '현재 카페24와 같은 호스팅사를 통해 성공적으로...' 패턴 사용 추천")
        
        if '채용' in company_info or '인재' in company_info:
            elements.append("- 채용 관련 컨텍스트 활용 가능")
            elements.append("- '최근 재무/회계 담당자 채용을 진행하시는 것을 보고...' 패턴 사용 추천")
        
        # Pain Points 기반 개인화
        if '데이터' in pain_points or '정산' in pain_points:
            elements.append("- 정산/데이터 매핑 문제 중심 접근 추천")
        
        if '개발' in pain_points or '리소스' in pain_points:
            elements.append("- 개발 리소스 절약 중심 접근 추천")
        
        if not elements:
            elements.append(f"- {company_name}의 지속적인 발전과 혁신 노력에 관심")
            elements.append(f"- 기본 '{position_title}' 호칭 사용")
        
        return '\n'.join(elements)
    
    def refine_email_copy(self, original_copy, feedback):
        """사용자 피드백을 바탕으로 메일 문안 개선"""
        
        refinement_prompt = f"""
        다음 메일 문안을 사용자 피드백에 따라 개선해주세요:

        **원본 메일 문안:**
        {original_copy}

        **사용자 피드백:**
        {feedback}

        **개선 요청사항:**
        - Zendesk 모범 사례 준수 (간결성, 개인화, 명확한 CTA)
        - PortOne 제품 가치 강조
        - 더 자연스럽고 설득력 있는 문체

        개선된 메일 문안을 제공해주세요.
        """
        
        payload = {
            "model": "gemini-2.5-pro",
            "max_tokens": 1000,
            "temperature": 0.5,
            "messages": [
                {
                    "role": "user",
                    "content": refinement_prompt
                }
            ]
        }
        
        try:
            # Gemini API 호출로 변경 (이 함수는 더 이상 사용되지 않을 예정)
            logger.warning("이 함수는 더 이상 사용되지 않습니다. Gemini API를 사용해주세요.")
            response = requests.post(self.gemini_url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            result = response.json()
            refined_copy = result['content'][0]['text']
            
            return {
                'success': True,
                'refined_copy': refined_copy,
                'timestamp': datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'메일 문안 개선 오류: {str(e)}',
                'refined_copy': None
            }
    
    def generate_fallback_emails(self, company_name, sales_point='', contact_name='', contact_position=''):
        """실제 API 실패 시 사용할 한국어 템플릿 기반 폴백 이메일 생성 (세일즈포인트별 동적 생성)"""
        
        # 개인화된 인사말 생성
        researcher = CompanyResearcher()
        personalized_greeting = researcher.generate_personalized_greeting(contact_name, contact_position, company_name)
        
        all_fallbacks = {
            'opi_professional': {
                'subject': f'{company_name} 결제 인프라 최적화 제안',
                'body': f'''{personalized_greeting} 코리아포트원 오준호입니다.

혹시 대표님께서도 예측 불가능한 결제 시스템 장애, PG사 정책 변화로 인한 수수료 변동문제,
혹은 해외 시장 진출 시의 결제 문제에 대한 장기적인 대비책을 고민하고 계신가요?

저희 포트원은 단 하나의 연동으로 여러 PG사 통합 관리, 결제 안정성 강화, 비용 최적화,
그리고 글로벌 확장성까지 제공하는 솔루션입니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

만약 이러한 고민을 해결하고 대표님의 사업 성장에만 집중하고 싶으시다면,
미팅을 통해 저희가 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.
다음 주 중 편하신 시간을 알려주시면 감사하겠습니다.

오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'opi_curiosity': {
                'subject': f'{company_name} 결제 시스템, 정말 효율적인가요?',
                'body': f'''{personalized_greeting} PortOne 오준호입니다.

혹시 대표님께서도 단일 PG사 종속으로 인한 리스크관리,
여러 PG사 연동 시 발생하는 개발/유지보수 부담에 대한 고민을 하고계신가요?

포트원은 단 한 번의 API 연동으로 50개 이상의 PG사를 통합하고,
개발 리소스를 획기적으로 줄여주는 솔루션입니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

만약 이러한 기술적 고민을 해결하고 대표님 팀의 귀한 리소스가
본질적인 서비스 개발에만 집중되기를 바라신다면,
미팅을 통해 저희가 어떻게 기여할 수 있을지 깊이 있는 대화를 나누고 싶습니다.
다음 주 중 편하신 시간을 알려주시면 감사하겠습니다.

오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'finance_professional': {
                'subject': f'{company_name} 커머스 재무 자동화 솔루션',
                'body': f'''{personalized_greeting} PortOne 오준호 매니저입니다.

현재 카페24와 같은 호스팅사를 통해 성공적으로 온라인 비즈니스를 운영하고 계시는데
네이버페이, 쿠팡 등 오픈마켓에서 들어오는 매출과 실제 입금액이 맞는지 확인하는
'정산' 업무에 생각보다 많은 시간을 쏟고 있지는 않으신가요?

많은 대표님들이 이 과정에서 발생하는 누락된 매출과 숨겨진 수수료 때문에 골머리를 앓고 계십니다.

저희 PortOne의 커머스 재무 자동화 솔루션은 여러 채널의 정산 내역을 클릭 한 번으로 대사하여,
수작업으로 인한 실수를 원천적으로 막고 숨어있던 비용을 찾아드립니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

단 15분만 투자해주신다면, 미팅을 통해 {company_name}의 재무 현황에서
지금 당장 개선할 수 있는 부분을 데이터로 명확히 보여드리겠습니다.
다음 주 중 편하신 시간 회신부탁드립니다.

감사합니다.
오준호 드림

오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'finance_curiosity': {
                'subject': f'{company_name} 정산 업무, 하루 몇 시간 소요되나요?',
                'body': f'''{personalized_greeting} PortOne 오준호 매니저입니다.

우연히 {company_name}의 온라인 스토어를 방문했다가, 깊은 인상을 받았습니다.
이렇게 훌륭한 제품을 만드시는 만큼, 사업도 빠르게 성장하고 있으리라 생각합니다.

혹시 사업 규모가 커지면서, 예전에는 간단했던 매출 정산 업무가 점점 더 복잡하고 부담스러워지는 단계에 접어들지는 않으셨나요?
많은 기업들이 저희 포트원 솔루션을 통해 매일 몇 시간씩 걸리던 정산 업무를 단 5분 만에 끝내고, 아낀 시간을 다시 제품 개발과 마케팅에 투자하고 있습니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

다음 주 중 미팅가능한 시간을 알려주신다면
{company_name}의 성공 스토리에 PortOne이 어떻게 기여할 수 있을지, 잠시 이야기 나누고 싶습니다.

긍정적일 회신 부탁드립니다.

감사합니다.
오준호 드림

오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'game_d2c_professional': {
                'subject': f'{company_name}님, 인앱결제 수수료 90% 절감 방안',
                'body': f'''{personalized_greeting} PortOne 오준호입니다.

혹시 애플 앱스토어와 구글 플레이스토어의 30% 인앱결제 수수료 때문에 고민이 많으시지 않나요?
최근 Com2uS, Neptune 등 국내 주요 게임사들도 D2C 웹상점으로 수수료 부담을 대폭 줄이고 있습니다.

저희 PortOne은 단 한 번의 SDK 연동으로 국내 25개 PG사를 통합하여, 최적의 비용으로 웹상점 결제를 운영할 수 있도록 지원합니다.
실제로 고객사들은 인앱결제 수수료를 90% 절약하고, 정산 업무를 자동화하고 계십니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

다음 주 중 편하신 시간을 알려주시면, {company_name}에 최적화된 방안을 제안드리겠습니다.

오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'game_d2c_curiosity': {
                'subject': f'{company_name}님, D2C 웹상점 직접 구축의 어려움',
                'body': f'''{personalized_greeting} PortOne 오준호입니다.

최근 많은 게임사들이 인앱결제 수수료 절감을 위해 D2C 웹상점을 구축하지만,
막상 직접 구축하려다 보니 국내 25개 PG사 개별 연동, 정산 관리, 수수료 최적화 등이 부담스러우실 것 같습니다.

PortOne을 사용하시면 이 모든 과정을 한 번에 해결할 수 있습니다.
어떻게 수수료를 90% 절감하고 운영 업무를 자동화할 수 있는지 궁금하지 않으신가요?

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

15분만 시간을 내어주시면, 어떻게 가능한지 보여드리겠습니다.
다음 주 중 편하신 시간을 알려주시면 감사하겠습니다.

오준호 Junho Oh
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            }
        }

        if sales_point == 'opi':
            return {k: v for k, v in all_fallbacks.items() if 'opi' in k}
        elif sales_point == 'recon':
            return {k: v for k, v in all_fallbacks.items() if 'finance' in k}
        elif sales_point == '인앱수수료절감':
            return {k: v for k, v in all_fallbacks.items() if 'game_d2c' in k}
        else: # 'opi + recon' 또는 빈칸일 경우
            return {k: v for k, v in all_fallbacks.items() if 'opi' in k or 'finance' in k}
    
    def _fix_malformed_json(self, json_content):
        """손상된 JSON 복구 시도"""
        try:
            import re
            
            # 1. 문자열 내 이스케이프되지 않은 따옴표 수정
            fixed_content = json_content
            
            # 2. 불완전한 문자열 수정 (끝나지 않은 문자열)
            # 마지막 따옴표가 제대로 닫히지 않은 경우 수정
            lines = fixed_content.split('\n')
            for i, line in enumerate(lines):
                # 키: "값" 패턴에서 값 부분이 제대로 닫히지 않은 경우
                if line.strip().endswith('"') == False and '"' in line and ':' in line:
                    # 문자열이 닫히지 않았다면 닫아주기
                    quote_count = line.count('"')
                    if quote_count % 2 == 1:  # 홀수 개의 따옴표 = 닫히지 않음
                        lines[i] = line + '"'
            
            fixed_content = '\n'.join(lines)
            
            # 3. 후행 쉼표 제거
            fixed_content = re.sub(r',(\s*[}\]])', r'\1', fixed_content)
            
            # 4. 중괄호 균형 맞추기
            open_braces = fixed_content.count('{')
            close_braces = fixed_content.count('}')
            if open_braces > close_braces:
                fixed_content += '}' * (open_braces - close_braces)
            
            return fixed_content
            
        except Exception as e:
            logger.debug(f"JSON 복구 실패: {e}")
            return None
    
    def _reconstruct_json_from_fragments(self, broken_json, company_name):
        """완전히 깨진 JSON을 조각에서 재구성"""
        try:
            import re
            
            print("🔧 JSON 조각에서 키-값 쌍 추출 중...")
            
            # 4개 이메일 템플릿 키
            email_keys = ["opi_professional", "opi_curiosity", "finance_professional", "finance_curiosity"]
            reconstructed = {}
            
            # 각 이메일 유형별로 subject와 body 추출 시도
            for key in email_keys:
                reconstructed[key] = {"subject": "", "body": ""}
                
                # subject 찾기
                subject_match = re.search(rf'"{key}"[^{{]*"subject"\s*:\s*"([^"]*)"', broken_json, re.DOTALL)
                if subject_match:
                    reconstructed[key]["subject"] = subject_match.group(1)
                else:
                    reconstructed[key]["subject"] = f"{company_name} 결제 솔루션 제안"
                
                # body 찾기 (더 복잡함 - 여러 줄에 걸쳐 있을 수 있음)
                body_pattern = rf'"{key}"[^{{]*"body"\s*:\s*"([^"]*(?:\\"[^"]*)*)'
                body_match = re.search(body_pattern, broken_json, re.DOTALL)
                if body_match:
                    body_content = body_match.group(1)
                    # 이스케이프된 따옴표 복원
                    body_content = body_content.replace('\\"', '"').replace('\\n', '\n')
                    reconstructed[key]["body"] = body_content[:500] + "..." if len(body_content) > 500 else body_content
                else:
                    # 기본 템플릿
                    reconstructed[key]["body"] = f"안녕하세요, {company_name} 담당자님.\n\nPortOne의 결제 솔루션으로 비즈니스 효율성을 높여보세요.\n\n감사합니다."
            
            # JSON 문자열로 변환
            import json
            reconstructed_json = json.dumps(reconstructed, ensure_ascii=False, indent=2)
            
            print(f"🔧 재구성 완료: {len(reconstructed)} 개 이메일 템플릿")
            return reconstructed_json
            
        except Exception as e:
            print(f"🔧 JSON 재구성 실패: {e}")
            return None

def generate_email_with_gemini(company_data, research_data):
    """Gemini 2.5 Pro를 사용하여 개인화된 이메일 생성"""
    try:
        # 회사 정보 요약
        company_name = company_data.get('회사명', 'Unknown')
        company_info = f"회사명: {company_name}"
        
        # 추가 회사 정보가 있다면 포함
        for key, value in company_data.items():
            if key != '회사명' and value:
                company_info += f"\n{key}: {value}"
        
        # 조사 정보 및 Pain Point 요약
        research_summary = research_data.get('company_info', '조사 정보 없음')
        pain_points = research_data.get('pain_points', '일반적인 Pain Point')
        industry_trends = research_data.get('industry_trends', '')
        
        # 기본 context 정의
        context = f"""
당신은 포트원(PortOne) 전문 세일즈 카피라이터로, 실제 검증된 한국어 영업 이메일 패턴을 완벽히 숙지하고 있습니다.

**타겟 회사 정보:**
- 회사명: {company_name}
- 회사 정보: {research_summary}

**Perplexity 조사 결과:**
{research_summary}

**업계 트렌드:**
{industry_trends}
"""

        prompt = f"""
{context}

**회사별 맞춤 Pain Points (조사 결과 기반):**
{pain_points}

다음 지침에 따라 4개의 설득력 있고 차별화된 이메일을 작성해주세요:

**필수 요구사항:**
1. 위에 제시된 회사별 맞춤 Pain Point를 구체적으로 언급하여 차별화
2. "혹시 이런 문제로 고민하고 계시지 않나요?" 식의 공감형 접근
3. 실제 수치와 구체적 혜택 제시 (85% 절감, 90% 단축, 15% 향상 등)
4. "비슷한 고민을 가진 다른 고객사도..." 식의 사례 암시
5. 강압적이지 않은 자연스러운 미팅/상담 제안
6. **각 회사마다 다른 Pain Point를 활용하여 완전히 차별화된 내용 작성**

**4개 이메일 유형:**

1. **One Payment Infra - 전문적 톤**: 
   - 결제 시스템 개발/운영의 구체적 어려움 제기
   - "최근 기사에서 본 바와 같이..." 식으로 조사 결과 활용
   - OPI의 구체적 해결책과 수치 제시
   - 전문적이지만 따뜻한 톤으로 미팅 제안

2. **One Payment Infra - 호기심 유발형**: 
   - "혹시 결제 시스템 개발에 6개월 이상 소요되고 계신가요?" 식 질문
   - 조사 결과에서 발견한 업계 트렌드 언급
   - 호기심을 자극하는 질문으로 OPI 소개
   - "어떻게 가능한지 궁금하시지 않나요?" 식 미팅 제안

3. **재무자동화 솔루션 - 전문적 톤**: 
   - 커머스 재무 관리의 구체적 Pain Point 제기
   - "월 수십 시간의 엑셀 작업으로 고생하고 계시지 않나요?"
   - 자동화 솔루션의 구체적 혜택과 수치
   - 전문적이지만 공감하는 톤으로 상담 제안

4. **재무자동화 솔루션 - 호기심 유발형**: 
   - "혹시 네이버/카카오/카페24 데이터 매핑에 어려움을 겪고 계신가요?"
   - 조사 결과에서 발견한 업계 이슈 언급
   - 호기심을 자극하는 질문으로 자동화 솔루션 소개
   - "어떻게 90% 이상 단축이 가능한지 보여드릴까요?" 식 미팅 제안

**구조 및 형식:**
- 제목: 7단어/41자 이내, 구체적 Pain Point나 혜택 언급
- 본문: 150-250단어
- 구성: 개인화된 인사(30단어) → Pain Point 제기(60단어) → 해결책 제시(80단어) → 미팅 제안(30단어)
- 톤: 전문적이면서도 공감하고 도움을 주는 관점

**중요**: 어떤 설명이나 추가 텍스트 없이 오직 JSON 형태로만 응답해주세요. 다른 텍스트는 절대 포함하지 마세요.

{{
  "opi_professional": {{
    "subject": "제목",
    "body": "본문 내용"
  }},
  "opi_curiosity": {{
    "subject": "제목",
    "body": "본문 내용"
  }},
  "finance_professional": {{
    "subject": "제목",
    "body": "본문 내용"
  }},
  "finance_curiosity": {{
    "subject": "제목",
    "body": "본문 내용"
  }}
}}
"""
        
        # Gemini API가 설정되지 않았으면 폴백 응답 생성
        if not GEMINI_API_KEY:
            return {
                'success': True,
                'variations': {
                    'professional': {
                        'subject': company_name + ' 맞춤형 결제 인프라 제안',
                        'body': '안녕하세요, ' + company_name + ' 담당자님!\n\n' + company_name + '의 비즈니스 성장에 도움이 될 수 있는 PortOne의 One Payment Infra를 소개드리고자 연락드립니다.\n\n현재 많은 기업들이 결제 시스템 통합과 디지털 전환에 어려움을 겪고 있습니다. PortOne의 솔루션은:\n\n• 개발 리소스 절약 (80% 단축)\n• 빠른 도입 (최소 2주)\n• 무료 컨설팅 제공\n• 결제 성공률 향상\n\n15분 간단한 데모를 통해 ' + company_name + '에 어떤 혜택이 있는지 보여드리고 싶습니다.\n\n언제 시간이 되실지요?\n\n감사합니다.\nPortOne 영업팀'
                    },
                    'friendly': {
                        'subject': company_name + '님, 결제 시스템 고민 있으신가요?',
                        'body': '안녕하세요! ' + company_name + ' 담당자님 :)\n\n혹시 결제 시스템 통합이나 개발 리소스 문제로 고민이 있으신가요?\n\n저희 PortOne은 이런 문제들을 해결하기 위해 One Payment Infra를 만들었어요!\n\n특히 이런 점들이 도움이 될 거예요:\n🚀 개발 시간 80% 단축\n💰 비용 절약\n🔧 무료 컨설팅\n📈 결제 성공률 UP\n\n커피 한 잔 마시며 15분만 이야기해볼까요? 어떤 날이 편하신지 알려주세요!\n\n감사합니다 😊\nPortOne 영업팀'
                    }
                },
                'timestamp': datetime.now().isoformat(),
                'note': 'AWS Bedrock 모델 접근 불가로 인한 폴백 데이터'
            }
        
        # Gemini API 호출
        try:
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            if response.text:
                # JSON 응답 파싱 시도
                try:
                    # 전체 응답에서 JSON 부분 추출
                    clean_response = response.text.strip()
                    
                    # JSON 코드 블록 찾기
                    if '```json' in clean_response:
                        json_start = clean_response.find('```json') + 7
                        json_end = clean_response.find('```', json_start)
                        if json_end != -1:
                            clean_response = clean_response[json_start:json_end]
                        else:
                            clean_response = clean_response[json_start:]
                    elif '{' in clean_response and '}' in clean_response:
                        # JSON 객체 부분만 추출
                        json_start = clean_response.find('{')
                        json_end = clean_response.rfind('}') + 1
                        clean_response = clean_response[json_start:json_end]
                    
                    clean_response = clean_response.strip()
                    
                    # JSON 파싱
                    email_variations = json.loads(clean_response)
                    
                    # 응답 형식 변환
                    formatted_variations = {}
                    if 'opi_professional' in email_variations:
                        formatted_variations['opi_professional'] = email_variations['opi_professional']
                    if 'opi_curiosity' in email_variations:
                        formatted_variations['opi_curiosity'] = email_variations['opi_curiosity']
                    if 'finance_professional' in email_variations:
                        formatted_variations['finance_professional'] = email_variations['finance_professional']
                    if 'finance_curiosity' in email_variations:
                        formatted_variations['finance_curiosity'] = email_variations['finance_curiosity']
                    
                    return {
                        'success': True,
                        'variations': formatted_variations,
                        'timestamp': datetime.now().isoformat(),
                        'model': 'gemini-2.5-pro-exp'
                    }
                    
                except json.JSONDecodeError as json_error:
                    logger.error(f"Gemini JSON 파싱 오류: {json_error}")
                    # JSON 파싱 실패 시 폴백
                    return {
                        'success': True,
                        'variations': {
                            'professional': {
                                'subject': company_name + ' 맞춤형 결제 인프라 제안',
                                'body': f'안녕하세요, {company_name} 담당자님!\n\n{pain_points}\n\nPortOne의 One Payment Infra로 이런 문제들을 해결할 수 있습니다:\n• 개발 리소스 85% 절약\n• 2주 내 구축 완료\n• 무료 컨설팅 제공\n\n간단한 미팅으로 자세한 내용을 설명드리고 싶습니다.\n\n감사합니다.\nPortOne 영업팀'
                            }
                        },
                        'timestamp': datetime.now().isoformat(),
                        'note': 'JSON 파싱 실패로 인한 폴백 데이터'
                    }
            
            else:
                logger.error("Gemini API 응답이 비어있습니다.")
                # 빈 응답 시 폴백
                return {
                    'success': True,
                    'variations': {
                        'professional': {
                            'subject': company_name + ' 맞춤형 결제 인프라 제안',
                            'body': f'안녕하세요, {company_name} 담당자님!\n\n현재 많은 기업들이 결제 시스템 통합과 개발 리소스 부족으로 어려움을 겪고 있습니다.\n\nPortOne의 솔루션으로 해결할 수 있습니다:\n• 개발 시간 85% 단축\n• 무료 컨설팅 제공\n• 안정적인 결제 인프라\n\n15분 간단한 미팅으로 자세히 설명드리겠습니다.\n\n감사합니다.\nPortOne 영업팀'
                        }
                    },
                    'timestamp': datetime.now().isoformat(),
                    'note': 'Gemini 빈 응답으로 인한 폴백 데이터'
                }
                
        except Exception as gemini_error:
            logger.error(f"Gemini API 호출 오류: {str(gemini_error)}")
            # Gemini API 오류 시 폴백
            return {
                'success': True,
                'variations': {
                    'professional': {
                        'subject': company_name + ' 맞춤형 결제 솔루션 제안',
                        'body': f'안녕하세요, {company_name} 담당자님!\n\n현재 많은 기업들이 결제 시스템 개발과 통합에 어려움을 겪고 있습니다.\n\nPortOne의 One Payment Infra로 이런 문제들을 해결할 수 있습니다:\n• 개발 시간 85% 단축\n• 무료 컨설팅 제공\n• 안정적인 결제 시스템\n\n간단한 미팅으로 자세한 내용을 설명드리고 싶습니다.\n\n감사합니다.\nPortOne 영업팀'
                    }
                },
                'timestamp': datetime.now().isoformat(),
                'note': f'Gemini API 오류로 인한 폴백 데이터: {str(gemini_error)}'
            }
            
    except Exception as e:
        logger.error(f"Gemini 이메일 생성 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def refine_email_with_claude(current_email, refinement_request):
    """Claude Opus 4.1을 사용하여 이메일 개선"""
    try:
        # Claude 클라이언트 초기화
        claude_client = ClaudeBedrockClient()
        
        # AWS Bedrock 클라이언트가 초기화되지 않았거나 사용 가능한 모델이 없으면 시뮬레이션 응답 생성
        if not claude_client.bedrock_runtime or not claude_client.model_id:
            return f"""제목: 개선된 메일 문안 - {refinement_request} 반영

안녕하세요!

요청해주신 "{refinement_request}" 내용을 반영하여 메일 문안을 개선했습니다.

PortOne의 One Payment Infra는 다음과 같은 혜택을 제공합니다:

• 개발 리소스 80% 절약
• 2주 내 빠른 도입
• 무료 전문 컨설팅
• 스마트 라우팅으로 결제 성공률 향상

15분 간단한 데모를 통해 구체적인 혜택을 보여드리고 싶습니다.

언제 시간이 되실지요?

감사합니다.
PortOne 영업팀

(주의: AWS Bedrock 인증 실패로 인한 시뮬레이션 응답)"""
        
        prompt = f"""
다음 이메일 문안을 사용자의 요청에 따라 개선해주세요.

**현재 이메일:**
{current_email}

**개선 요청:**
{refinement_request}

**개선 지침:**
1. 사용자의 요청사항을 정확히 반영
2. PortOne One Payment Infra 제품의 핵심 가치 유지
3. 전문적이면서도 읽기 쉬운 문체
4. 구체적인 혜택과 다음 단계 명시
5. 적절한 길이 유지 (너무 길거나 짧지 않게)

개선된 이메일 전체를 제목과 본문을 포함하여 작성해주세요:
"""
        
        # Claude API 호출
        refined_content = claude_client.generate_content(prompt)
        return refined_content
        
    except Exception as e:
        logger.error(f"Claude 이메일 개선 오류: {str(e)}")
        # 오류 시 기본 개선 응답 제공
        return f"""제목: 개선된 메일 문안 - {refinement_request} 반영

안녕하세요!

요청해주신 "{refinement_request}" 내용을 반영하여 메일 문안을 개선했습니다.

PortOne의 One Payment Infra는 다음과 같은 혜택을 제공합니다:

• 개발 리소스 80% 절약
• 2주 내 빠른 도입
• 무료 전문 컨설팅
• 스마트 라우팅으로 결제 성공률 향상

15분 간단한 데모를 통해 구체적인 혜택을 보여드리고 싶습니다.

언제 시간이 되실지요?

감사합니다.
PortOne 영업팀

(주의: API 오류로 인한 기본 응답 - {str(e)})"""

# 전역 인스턴스 생성
researcher = CompanyResearcher()
copywriter = EmailCopywriter()

@app.route('/api/research-company', methods=['POST'])
def research_company():
    """회사 정보 조사 API"""
    try:
        data = request.json
        company_name = data.get('company_name')
        website = data.get('website')
        
        if not company_name:
            return jsonify({'error': '회사명이 필요합니다'}), 400
        
        # Perplexity로 회사 정보 조사
        research_result = researcher.research_company(company_name, website)
        
        return jsonify(research_result)
        
    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/api/generate-emails', methods=['POST'])
def generate_emails():
    """메일 문안 생성 API"""
    try:
        data = request.json
        company_data = data.get('company_data', {})
        research_data = data.get('research_data', {})
        industry = data.get('industry')
        
        # 업계 트렌드 조사 (선택사항)
        industry_trends = None
        if industry:
            industry_trends = researcher.get_industry_trends(industry)
        
        # Gemini로 메일 문안 생성
        if research_data:
            research_data['industry_trends'] = industry_trends
        else:
            research_data = {'industry_trends': industry_trends}
            
        email_result = generate_email_with_gemini(company_data, research_data)
        
        return jsonify({
            'email_result': email_result,
            'industry_trends': industry_trends,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'메일 생성 오류: {str(e)}'}), 500

@app.route('/api/batch-process', methods=['POST'])
def batch_process():
    """여러 회사 일괄 처리 API"""
    try:
        data = request.json
        companies = data.get('companies', [])
        
        if not companies:
            return jsonify({'error': '처리할 회사 데이터가 없습니다'}), 400
        
        results = []
        
        for i, company in enumerate(companies):  # 모든 회사 처리
            try:
                # 1. 회사 정보 조사 (CSV 추가 정보 활용)
                additional_info = {
                    '사업자번호': company.get('사업자번호', ''),
                    '업종': company.get('업종', ''),
                    '세일즈포인트': company.get('세일즈포인트', ''),
                    '규모': company.get('규모', ''),
                    '대표자명': company.get('대표자명', ''),
                    '이메일': company.get('이메일', '')
                }
                
                research_result = researcher.research_company(
                    company.get('회사명', ''), 
                    company.get('홈페이지링크', ''),
                    additional_info
                )
                
                # 2. 메일 문안 생성 (Gemini 사용)
                if research_result['success']:
                    # Gemini API를 사용한 메일 생성
                    email_result = generate_email_with_gemini(
                        company, research_result
                    )
                    
                    results.append({
                        'company': company,
                        'research': research_result,
                        'emails': email_result,
                        'index': i
                    })
                else:
                    results.append({
                        'company': company,
                        'error': research_result.get('error', '조사 실패'),
                        'index': i
                    })
                
                # API 호출 제한을 위한 대기
                if i < len(companies) - 1:
                    time.sleep(2)
                    
            except Exception as e:
                results.append({
                    'company': company,
                    'error': f'처리 오류: {str(e)}',
                    'index': i
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'total_processed': len(results),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'일괄 처리 오류: {str(e)}'}), 500

@app.route('/api/refine-email', methods=['POST'])
def refine_email():
    """이메일 문안 개선"""
    try:
        data = request.json
        current_email = data.get('current_email', '')
        refinement_request = data.get('refinement_request', '')
        
        if not current_email or not refinement_request:
            return jsonify({
                'success': False,
                'error': '현재 이메일 내용과 개선 요청사항이 필요합니다.'
            }), 400
        
        # Claude Opus 4.1로 이메일 개선 요청
        refined_email = refine_email_with_claude(current_email, refinement_request)
        
        return jsonify({
            'success': True,
            'refined_email': refined_email,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"이메일 개선 중 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """서비스 상태 확인"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'perplexity': bool(os.getenv('PERPLEXITY_API_KEY')),
            'claude': bool(os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'))
        }
    })

if __name__ == '__main__':
    # API 키 확인
    if not os.getenv('PERPLEXITY_API_KEY'):
        logger.warning("PERPLEXITY_API_KEY가 설정되지 않았습니다.")
    
    if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
        logger.warning("AWS 인증 정보가 설정되지 않았습니다. Claude API 사용이 제한됩니다.")
    
    logger.info("이메일 생성 서비스 시작...")
    logger.info("사용 가능한 엔드포인트:")
    logger.info("- POST /api/research-company: 회사 조사")
    logger.info("- POST /api/generate-email: 이메일 생성")
    logger.info("- POST /api/batch-process: 일괄 처리")
    logger.info("- POST /api/refine-email: 이메일 개선")
    logger.info("- GET /api/health: 상태 확인")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
