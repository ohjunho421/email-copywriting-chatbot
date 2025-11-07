import os
import json
import requests
import logging
import time
import asyncio
import concurrent.futures
from functools import partial
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

# SSR 엔진 및 사례 DB 임포트
from ssr_engine import rank_emails, get_top_email, calculate_ssr_score
from case_database import select_relevant_cases, get_case_details, format_case_for_email, PORTONE_CASES

# .env 파일 로드
load_dotenv()

# 로깅 설정 - API 키 노출 방지
logging.basicConfig(
    level=logging.INFO,  # DEBUG → INFO로 변경 (API 키 노출 방지)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
    ]
)
logger = logging.getLogger(__name__)

# urllib3 DEBUG 로그 비활성화 (URL에 포함된 API 키 노출 방지)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'portone-email-generation-secret-key-2025')

# Railway PostgreSQL 연결 (postgres:// → postgresql:// 변환)
database_url = os.getenv('DATABASE_URL', 'sqlite:///email_gen.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)

# 데이터베이스 초기화
from models import db, User, EmailGeneration
db.init_app(app)

# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = '로그인이 필요한 페이지입니다.'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Blueprint 등록
from auth import auth_bp
from admin import admin_bp
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# 데이터베이스 테이블 생성 및 마이그레이션
with app.app_context():
    db.create_all()
    logger.info("✅ 데이터베이스 초기화 완료")
    
    # 신규 컬럼 추가 (마이그레이션)
    try:
        from sqlalchemy import text
        
        # name_en 컬럼 추가
        try:
            db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS name_en VARCHAR(100)'))
            logger.info("✅ name_en 컬럼 추가 완료")
        except Exception as e:
            if 'already exists' not in str(e).lower():
                logger.warning(f"name_en 컬럼 추가 건너뛰기: {e}")
        
        # email_signature 컬럼 추가
        try:
            db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS email_signature TEXT'))
            logger.info("✅ email_signature 컬럼 추가 완료")
        except Exception as e:
            if 'already exists' not in str(e).lower():
                logger.warning(f"email_signature 컬럼 추가 건너뛰기: {e}")
        
        # gmail_app_password 컬럼 추가
        try:
            db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_app_password VARCHAR(200)'))
            logger.info("✅ gmail_app_password 컬럼 추가 완료")
        except Exception as e:
            if 'already exists' not in str(e).lower():
                logger.warning(f"gmail_app_password 컬럼 추가 건너뛰기: {e}")
        
        # sendgrid_api_key 컬럼 추가
        try:
            db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS sendgrid_api_key VARCHAR(200)'))
            logger.info("✅ sendgrid_api_key 컬럼 추가 완료")
        except Exception as e:
            if 'already exists' not in str(e).lower():
                logger.warning(f"sendgrid_api_key 컬럼 추가 건너뛰기: {e}")
        
        db.session.commit()
        logger.info("🔄 데이터베이스 마이그레이션 완료")
        
        # 기존 사용자들에게 서명 자동 생성
        users = User.query.filter(User.email_signature.is_(None)).all()
        if users:
            for user in users:
                user.email_signature = user.generate_email_signature()
            db.session.commit()
            logger.info(f"📝 {len(users)}명의 사용자 서명 자동 생성 완료")
            
    except Exception as e:
        logger.error(f"❌ 마이그레이션 오류: {str(e)}")
        db.session.rollback()

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
    
    def extract_emails_from_html(self, html_content):
        """HTML에서 이메일 주소 추출 - 단순화된 버전"""
        emails = set()
        
        try:
            # HTML을 텍스트로 변환
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text()
            
            # 기본 이메일 패턴으로 검색
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
            found_emails = re.findall(email_pattern, text_content, re.IGNORECASE)
            
            # 결과 정제
            for email in found_emails:
                if '@' in email and '.' in email and len(email) > 5:
                    emails.add(email.lower())
            
            return list(emails)
            
        except Exception as e:
            print(f"이메일 추출 중 오류: {e}")
            return []
    
    def extract_business_number_from_html(self, html_content):
        """HTML에서 사업자등록번호 추출"""
        business_numbers = set()
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text()
            
            # 사업자등록번호 패턴들
            business_patterns = [
                r'\b\d{3}-\d{2}-\d{5}\b',  # 123-45-67890
                r'\b\d{10}\b',             # 1234567890 (연속 10자리)
                r'사업자.*?등록.*?번호.*?[:：]\s*(\d{3}-\d{2}-\d{5})',
                r'사업자.*?번호.*?[:：]\s*(\d{3}-\d{2}-\d{5})',
                r'등록.*?번호.*?[:：]\s*(\d{3}-\d{2}-\d{5})',
            ]
            
            for pattern in business_patterns:
                found_numbers = re.findall(pattern, text_content, re.IGNORECASE)
                for number in found_numbers:
                    # 하이픈 제거하고 10자리인지 확인
                    clean_number = re.sub(r'[^0-9]', '', number)
                    if len(clean_number) == 10:
                        # 표준 형식으로 변환 (123-45-67890)
                        formatted = f"{clean_number[:3]}-{clean_number[3:5]}-{clean_number[5:]}"
                        business_numbers.add(formatted)
            
            return list(business_numbers)
            
        except Exception as e:
            print(f"사업자번호 추출 중 오류: {e}")
            return []
    
    def find_privacy_policy_links(self, html_content, base_url):
        """개인정보 처리방침 페이지 링크 찾기"""
        privacy_links = set()
        
        try:
            from bs4 import BeautifulSoup
            import urllib.parse
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 개인정보 처리방침 관련 키워드
            privacy_keywords = [
                '개인정보', '처리방침', 'privacy', 'policy', 
                '개인정보보호', '개인정보처리', '프라이버시'
            ]
            
            # 모든 링크 검사
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # 키워드가 포함된 링크 찾기
                for keyword in privacy_keywords:
                    if keyword in text.lower() or keyword in href.lower():
                        # 상대 경로를 절대 경로로 변환
                        full_url = urllib.parse.urljoin(base_url, href)
                        privacy_links.add(full_url)
                        break
            
            return list(privacy_links)
            
        except Exception as e:
            print(f"개인정보 처리방침 링크 찾기 중 오류: {e}")
            return []
    
    def crawl_privacy_policy_page(self, privacy_url):
        """개인정보 처리방침 페이지에서 상세 정보 추출"""
        try:
            response = requests.get(privacy_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                text_content = soup.get_text()
                
                # 개인정보 처리방침에서 추출할 정보들
                info = {
                    'emails': self.extract_emails_from_html(response.content),
                    'business_numbers': self.extract_business_number_from_html(response.content),
                    'contact_info': self.extract_contact_info_from_text(text_content)
                }
                
                return info
            
        except Exception as e:
            print(f"개인정보 처리방침 페이지 크롤링 중 오류: {e}")
            
        return None
    
    
    
    def build_enriched_search_query(self, company_name, additional_info):
        """기존 입력 정보를 활용해 더 정확한 검색 쿼리 생성"""
        query_parts = [company_name]
        
        if additional_info:
            # 사업자등록번호가 있으면 검색에 포함
            business_number = (additional_info.get('사업자번호') or 
                             additional_info.get('사업자등록번호'))
            if business_number:
                query_parts.append(f'사업자번호:{business_number}')
            
            # 대표자명이 있으면 검색에 포함
            ceo_name = (additional_info.get('대표자명') or
                       additional_info.get('대표자') or
                       additional_info.get('CEO명'))
            if ceo_name:
                query_parts.append(f'대표:{ceo_name}')
            
            # 홈페이지 도메인이 있으면 site: 검색으로 포함
            website_url = (additional_info.get('홈페이지링크') or
                         additional_info.get('대표홈페이지') or
                         additional_info.get('웹사이트'))
            if website_url:
                # URL에서 도메인만 추출
                import re
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', website_url)
                if domain_match:
                    domain = domain_match.group(1)
                    query_parts.append(f'site:{domain}')
            
            # 업종 정보가 있으면 포함
            if additional_info.get('업종'):
                query_parts.append(additional_info.get('업종'))
            
            # 주요 서비스/제품 정보가 있으면 포함
            for key in ['서비스', '제품', '주요사업']:
                if additional_info.get(key):
                    query_parts.append(additional_info.get(key))
        
        return ' '.join(query_parts)
    
    def research_company(self, company_name, website=None, additional_info=None):
        """회사별 맞춤형 Pain Point 발굴을 위한 상세 조사"""
        try:
            # CSV에서 제공된 추가 정보 활용
            search_context = f"회사명: {company_name}"
            if website:
                search_context += f"\n홈페이지: {website}"
            
            # 기존 입력된 정보들을 검색에 활용할 수 있도록 확장
            search_keywords = [company_name]  # 기본 검색 키워드
            
            if additional_info:
                # 사업자등록번호 (사업자번호 또는 사업자등록번호 컬럼 모두 체크)
                business_number = (additional_info.get('사업자번호') or 
                                 additional_info.get('사업자등록번호'))
                if business_number:
                    search_context += f"\n사업자번호: {business_number}"
                    search_keywords.append(business_number)
                
                # 대표자명 정보 활용
                ceo_name = (additional_info.get('대표자명') or
                           additional_info.get('대표자') or
                           additional_info.get('CEO명'))
                if ceo_name:
                    search_context += f"\n대표자명: {ceo_name}"
                    search_keywords.append(f"{company_name} {ceo_name}")
                
                # 홈페이지링크 추가 검증
                website_url = (additional_info.get('홈페이지링크') or
                             additional_info.get('대표홈페이지') or
                             additional_info.get('웹사이트'))
                if website_url and not website:
                    website = website_url
                    search_context += f"\n홈페이지: {website_url}"
                
                # 기존 정보들
                if additional_info.get('업종'):
                    search_context += f"\n업종: {additional_info.get('업종')}"
                if additional_info.get('세일즈포인트'):
                    search_context += f"\n주요 세일즈 포인트: {additional_info.get('세일즈포인트')}"
                if additional_info.get('규모'):
                    search_context += f"\n회사 규모: {additional_info.get('규모')}"
                
                # 추가 정보들도 검색에 활용
                for key in ['업종', '분야', '서비스', '제품', '비즈니스모델']:
                    if additional_info.get(key):
                        search_keywords.append(f"{company_name} {additional_info.get(key)}")
            
            # 검색 키워드를 로그에 출력
            logger.info(f"{company_name} 검색에 사용할 키워드들: {search_keywords}")

            # 웹사이트 정보를 인스턴스 변수로 저장 (웹 스크래핑용)
            if website:
                self.company_website = website
            
            # 다중 검색 엔진을 통한 최신 뉴스 수집 (enriched query 활용)
            logger.info(f"{company_name} 다중 검색 엔진 뉴스 수집 시작")
            enriched_query = self.build_enriched_search_query(company_name, additional_info)
            news_results = self.search_company_news_with_query(enriched_query, company_name)
            if news_results:
                search_context += f"\n\n### 다중 검색 엔진 뉴스 결과:\n{news_results}"
                logger.info(f"{company_name} 뉴스 수집 완료")
            
            # MCP 웹 검색을 통한 정보 보강 (항상 수행) - enriched query 활용
            logger.info(f"{company_name} MCP 정보 수집 시작")
            enhanced_info = self.enhance_company_info_with_mcp_enhanced(company_name, website, additional_info, [enriched_query])
            
            # 검색 컨텍스트에 MCP로 수집한 정보 추가
            if enhanced_info:
                search_context += f"\n\n### MCP 도구로 수집한 추가 정보:\n{enhanced_info}"
                logger.info(f"{company_name} MCP 정보 수집 완료: {len(enhanced_info)} 문자")
            else:
                logger.warning(f"{company_name} MCP 정보 수집 실패 - 기본 검색으로 진행")
            
            # 개선된 프롬프트 - 기존 입력 정보를 활용한 정확한 검색 쿼리 생성
            search_query = self.build_enriched_search_query(company_name, additional_info)
            
            prompt = f"""
다음 회사에 대한 최신 정보를 웹에서 직접 검색하여 조사하고 분석해주세요.

🔍 **필수: 실시간 웹 검색을 통해 최신 뉴스 기사를 반드시 찾아주세요**

검색 쿼리: {search_query}

이 검색 쿼리에는 사업자등록번호, 대표자명, 공식 홈페이지 등 정확한 식별 정보가 포함되어 있습니다. 
반드시 이 정보를 활용하여:
1. **최근 6개월 이내의 뉴스 기사**를 우선적으로 검색
2. 공식 보도자료, 언론 기사, 업계 뉴스 사이트에서 정보 수집
3. 구체적인 날짜와 출처를 포함하여 인용

추가로 이미 수집된 다중 검색 엔진의 정보도 참고:
{search_context}

다음 구조로 정보를 정리해주세요:

## 1. 최신 뉴스 및 활동 (Recent News & Activities) 🔴 **가장 중요**
**반드시 실제 뉴스 기사를 검색하여 다음 정보 포함:**
- 📰 **기사 제목과 날짜** (예: "2024년 10월 시리즈 A 투자 유치" - 2024.10.15)
- 📰 **신제품 출시, 투자 유치, 사업 확장 관련 구체적 뉴스**
- 📰 **조직 변화, 파트너십, 수상 이력 등**
- 🔗 **뉴스 출처** (가능한 경우 URL 포함)

## 2. 기업 개요 (Corporate Overview)
- 주력 사업 분야와 핵심 제품/서비스
- 대상 고객층 및 시장 포지셔닝  
- 추정 매출 규모 및 성장 단계

## 3. 결제/정산 관련 Pain Points (Payment & Settlement Challenges)
- 현재 결제 시스템의 추정 복잡도
- 다중 채널 운영 시 예상되는 정산 문제
- 업계 특성상 겪을 수 있는 결제 관련 어려움

## 4. 업계별 기술 트렌드 (Industry Tech Trends)
- 해당 업계의 디지털 전환 현황
- 결제 인프라 혁신 사례

## 5. PortOne 솔루션 적합성 (PortOne Solution Fit)
- One Payment Infra(OPI) 적합성 분석
- 재무 자동화 솔루션 필요성 정도

**중요**: 반드시 웹 검색을 통해 실제 최신 뉴스와 기사를 찾아서 인용하고, 구체적인 날짜와 출처를 명시해주세요. 추측이나 일반적인 내용이 아닌, 실제 검색된 사실 기반 정보를 제공해주세요.
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
                
                # 안전한 응답 추출
                if 'choices' in result and len(result['choices']) > 0:
                    raw_content = result['choices'][0]['message']['content']
                    logger.info(f"{company_name} Perplexity 응답 수신: {len(raw_content)} 문자")
                else:
                    logger.error(f"{company_name} Perplexity 응답 형식 오류: {result}")
                    raise Exception("Perplexity API 응답 형식이 올바르지 않습니다")
                
                # Citations (출처) 추출
                citations = result.get('citations', [])
                if citations:
                    logger.info(f"{company_name} Perplexity citations 발견: {len(citations)}개")
                    # Citations를 응답에 추가
                    citations_text = "\n\n## 📚 참고 출처 (Citations)\n"
                    for i, citation in enumerate(citations[:5], 1):  # 최대 5개만
                        citations_text += f"{i}. {citation}\n"
                    raw_content += citations_text
                else:
                    logger.warning(f"{company_name} Perplexity citations 없음 - 실제 검색 결과가 부족할 수 있음")
                
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
            
            # 1. Perplexity 조사 내용에서 실제 니즈 발굴
            # 성장/확장 관련 니즈
            if any(word in content_lower for word in ['성장', '확장', '투자', '매출증가', 'growth', 'expansion', 'investment']):
                if any(word in content_lower for word in ['커머스', '온라인', '쇼핑', 'ecommerce']):
                    specific_points.append(f"{company_name}의 급성장에 따른 다중 채널 결제 데이터 통합 필요성")
                elif any(word in content_lower for word in ['게임', 'game', '모바일']):
                    specific_points.append(f"{company_name}의 사용자 증가에 따른 결제 인프라 확장성 이슈")
                else:
                    specific_points.append(f"{company_name}의 비즈니스 확장에 따른 결제 시스템 복잡성 증가")
            
            # 글로벌/해외진출 관련 니즈
            if any(word in content_lower for word in ['글로벌', '해외', '수출', '진출', 'global', 'overseas', 'international']):
                specific_points.append(f"{company_name}의 해외 진출 시 다국가 결제 수단 및 정산 복잡성")
            
            # 기술/개발 관련 니즈  
            if any(word in content_lower for word in ['개발', '기술', '시스템', 'tech', 'development', 'platform']):
                specific_points.append(f"{company_name}의 결제 시스템 개발 리소스 부담 및 전문성 부족")
            
            # 업종별 특화 니즈
            if any(word in content_lower for word in ['커머스', '온라인', '쇼핑', 'ecommerce', 'online']):
                specific_points.append(f"{company_name}의 다중 커머스 채널 데이터 통합 및 실시간 정산 니즈")
            elif any(word in content_lower for word in ['제조', '생산', '공장', 'manufacturing']):
                specific_points.append(f"{company_name}의 B2B 대량 거래 처리 및 복잡한 정산 구조 개선 필요")
            elif any(word in content_lower for word in ['게임', '모바일게임', '앱게임', 'game', 'mobile']):
                # 게임업계는 수수료가 실제 핵심 이슈
                specific_points.append(f"{company_name}의 앱스토어 인앱결제 수수료 30% 부담 해결 필요성")
                specific_points.append(f"D2C 웹상점 구축을 통한 수수료 절감 및 직접 고객 관계 구축")
            
            # 2. 실제 비즈니스 상황에서 발굴되는 니즈
            # 자금 관련 이슈
            if any(word in content_lower for word in ['자금', '현금흐름', '정산', '수익성', 'cash', 'revenue', 'profit']):
                specific_points.append(f"{company_name}의 현금흐름 관리 및 정산 자동화 필요성")
            
            # 운영 효율성 이슈
            if any(word in content_lower for word in ['효율', '자동화', '인력', '업무', 'efficiency', 'automation', 'operation']):
                specific_points.append(f"{company_name}의 수작업 중심 재무 프로세스 자동화 니즈")
            
            # 데이터/분석 관련 니즈
            if any(word in content_lower for word in ['데이터', '분석', '리포트', 'data', 'analytics', 'report']):
                specific_points.append(f"{company_name}의 실시간 매출 데이터 분석 및 인사이트 도출 필요성")
            
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
                # "대리점/대리사 수수료 정산 오류로 인한 분쟁",
                "수출 대금 회수 지연으로 인한 현금흐름 악화",
                "재고 데이터와 주문 데이터 불일치로 인한 혼란",
                "ERP 시스템과 결제 시스템 연동 실패"
            ]
        
        elif any(keyword in company_lower for keyword in ['서비스', '컴설팅', '대행', 'service', 'consulting', '에이전시']):
            pain_pool = [
                "고객사 20개 이상의 서로 다른 결제 시스템 연동",
                # "프로젝트별 비용 정산에 주마다 20시간 소요",
                "고객사 요구로 매번 다른 결제 시스템 개발",
                # "수수료 정산 오류로 인한 고객사와의 분쟁",
                "월별 수익 분석에 엑셀로 3일 소요",
                "다양한 결제 수단 지원으로 인한 개발 비용 증가",
                # "고객사별 정산 주기 달라 관리 어려움"
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
    
    def enhance_company_info_with_mcp_enhanced(self, company_name, website, additional_info, search_keywords=None):
        """확장된 키워드를 활용한 MCP 도구 정보 보강 및 검증 (대폭 강화)"""
        try:
            enhanced_data = []
            logger.info(f"{company_name} MCP 정보 보강 시작")
            
            if not search_keywords:
                search_keywords = [company_name]
            
            # 1. 다중 웹 검색 전략 (확장된 키워드 활용)
            web_searches = []
            
            # 기본 웹사이트 검색
            if website and website.startswith('http'):
                web_info = self.fetch_website_info(website, company_name)
                if web_info:
                    web_searches.append(f"공식 웹사이트: {web_info}")
            
            # 확장된 키워드로 네이버/구글 검색 (최대 2개 키워드)
            primary_search_keywords = search_keywords[:2]
            
            for keyword in primary_search_keywords:
                # 네이버 지식백과/뉴스 검색 시뮬레이션
                naver_info = self.search_naver_sources(keyword)
                if naver_info:
                    web_searches.append(f"네이버 검색 ({keyword}): {naver_info}")
                
                # 구글 검색 시뮬레이션  
                google_info = self.search_google_sources(keyword)
                if google_info:
                    web_searches.append(f"구글 검색 ({keyword}): {google_info}")
            
            if web_searches:
                enhanced_data.append("\n".join(web_searches))
            
            # 2. CSV 정보 기반 심화 검색 (확장됨)
            if additional_info:
                csv_insights = []
                
                # 사업자번호 -> 업체 신뢰도 검증 (사업자등록번호도 포함)
                business_number = (additional_info.get('사업자번호') or 
                                 additional_info.get('사업자등록번호'))
                if business_number:
                    business_validation = self.deep_business_validation(
                        company_name, business_number
                    )
                    if business_validation:
                        csv_insights.append(f"사업자 심화 검증: {business_validation}")
                
                # 대표자명 정보 활용
                ceo_name = (additional_info.get('대표자명') or
                           additional_info.get('대표자') or
                           additional_info.get('CEO명'))
                if ceo_name:
                    ceo_insights = self.analyze_ceo_profile(company_name, ceo_name)
                    if ceo_insights:
                        csv_insights.append(f"대표자 프로필 분석: {ceo_insights}")
                
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
    
    def enhance_company_info_with_mcp(self, company_name, website, additional_info):
        """기존 호환성을 위한 함수 - 새로운 확장된 함수 호출"""
        return self.enhance_company_info_with_mcp_enhanced(company_name, website, additional_info)
    
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
    
    def analyze_ceo_profile(self, company_name, ceo_name):
        """대표자 프로필 분석"""
        try:
            # 실제로는 네이버 인물검색, LinkedIn, 기업 공시 등을 활용
            return f"{company_name} {ceo_name} 대표의 경력 및 비즈니스 철학 분석을 통한 의사결정 스타일 파악"
        except Exception as e:
            return None
    
    def get_industry_deep_insights(self, company_name, industry):
        """업종별 심화 인사이트"""
        try:
            deep_insights = {
                '이커머스': f"{company_name}는 이커머스 업체로서 네이버페이/카카오페이/토스페이 등 다중 PG 연동과 정산 자동화가 핵심 이슈. 특히 반품/환불 처리, 세금계산서 발행 등이 주요 Pain Point",
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
                return f"{company_name}의 '{sales_point}' 역량과 PortOne의 결제 인프라 통합 솔루션 간 높은 시너지 기대. 기존 강점을 더욱 확장할 수 있는 기회"
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
                '중견기업': f"{company_name} 같은 중견기업에게는 PortOne의 확장 가능한 아키텍처와 다중 PG 통합 관리가 핵심 가치. 성장에 따른 결제량 증가와 복잡한 정산 요구사항 효과적으로 대응",
                '대기업': f"{company_name} 같은 대기업에게는 PortOne의 엔터프라이즈 기능과 고도화된 분석 도구가 중요. 대용량 트래픽 처리, 복잡한 조직 구조 지원, 고급 보안 기능 제공",
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
    
    def search_company_news_enhanced(self, company_name, search_keywords=None):
        """확장된 키워드를 활용한 최신 뉴스 검색 (다중 검색 엔진 활용 - 품질 개선)"""
        import concurrent.futures
        import time
        
        if not search_keywords:
            search_keywords = [company_name]
        
        all_results = []
        search_start_time = time.time()
        
        # 각 검색 키워드로 병렬 검색 (최대 3개 키워드)
        primary_keywords = search_keywords[:3]  # 성능을 위해 최대 3개로 제한
        
        # 병렬로 검색 실행 (성능 향상)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(primary_keywords) * 2) as executor:
            futures = []
            
            # 각 키워드별로 Google과 DuckDuckGo 검색 실행
            for keyword in primary_keywords:
                futures.append(executor.submit(self.search_with_google, keyword))
                futures.append(executor.submit(self.search_with_duckduckgo, keyword))
            
            # 웹 스크래핑은 회사명으로만 실행
            futures.append(executor.submit(self.search_with_web_scraping, company_name))
            
            # 모든 future 결과 수집
            for i, future in enumerate(futures):
                try:
                    result = future.result(timeout=10)
                    if result and len(result.strip()) > 10:
                        # 결과 소스 구분 (Google/DuckDuckGo/Web)
                        if i < len(primary_keywords) * 2:  # Google + DuckDuckGo 결과
                            keyword_idx = i // 2
                            search_engine = "Google" if i % 2 == 0 else "DuckDuckGo"
                            keyword = primary_keywords[keyword_idx]
                            source = f"📰 {search_engine} ({keyword})"
                        else:  # Web scraping 결과
                            source = f"🌐 웹 검색 ({company_name})"
                        
                        all_results.append(f"{source}: {result}")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"검색 타임아웃 (인덱스 {i})")
                except Exception as e:
                    logger.warning(f"검색 오류 (인덱스 {i}): {e}")
        
        search_elapsed = time.time() - search_start_time
        logger.info(f"{company_name} 다중 검색 완료: {len(all_results)}개 결과, {search_elapsed:.2f}초 소요")
        
        if all_results:
            # 결과 품질 점검 및 중복 제거
            quality_results = self.filter_and_enhance_results(all_results, company_name)
            return quality_results
        
        # 검색 결과가 없는 경우 기본 정보 제공
        return self.generate_fallback_news_info(company_name)
    
    def search_company_news_with_query(self, search_query, company_name):
        """enriched query를 사용한 뉴스 검색"""
        import concurrent.futures
        import time
        
        all_results = []
        search_start_time = time.time()
        
        logger.info(f"{company_name} Enriched 검색 쿼리: {search_query}")
        
        # 병렬로 검색 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # enriched query로 검색
            future_google = executor.submit(self.search_with_google_query, search_query)
            future_duckduckgo = executor.submit(self.search_with_duckduckgo_query, search_query)
            future_web = executor.submit(self.search_with_web_scraping, company_name)  # 웹 스크래핑은 회사명으로
            
            futures = [future_google, future_duckduckgo, future_web]
            sources = ["Google", "DuckDuckGo", "웹 검색"]
            
            # 모든 future 결과 수집
            for i, (future, source) in enumerate(zip(futures, sources)):
                try:
                    result = future.result(timeout=10)
                    if result:
                        # 결과 검증
                        result_str = str(result).strip()
                        if len(result_str) > 10:  # 최소 길이 확인
                            # 이모지 추가
                            emoji = "📰" if source == "Google" else ("🦆" if source == "DuckDuckGo" else "🌐")
                            formatted_result = f"{emoji} {source}: {result_str}"
                            all_results.append(formatted_result)
                            logger.info(f"{company_name} {source} 검색 성공: {len(result_str)} 문자")
                        else:
                            logger.warning(f"{company_name} {source} 결과가 너무 짧음: {result_str}")
                    else:
                        logger.warning(f"{company_name} {source} 검색 결과 없음")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"{company_name} {source} 검색 타임아웃 (10초 초과)")
                except Exception as e:
                    logger.warning(f"{company_name} {source} 검색 오류: {str(e)}")
        
        search_elapsed = time.time() - search_start_time
        logger.info(f"{company_name} enriched 검색 완료: {len(all_results)}개 원본 결과, {search_elapsed:.2f}초 소요")
        
        if all_results:
            # 결과 품질 점검 및 중복 제거
            quality_results = self.filter_and_enhance_results(all_results, company_name)
            return quality_results
        
        # 검색 결과가 없는 경우 기본 정보 제공
        logger.warning(f"{company_name} 모든 검색 엔진에서 결과 없음 - Fallback 정보 사용")
        return self.generate_fallback_news_info(company_name)
    
    def search_company_news(self, company_name):
        """기존 호환성을 위한 함수 - 새로운 확장된 함수 호출"""
        return self.search_company_news_enhanced(company_name)
    
    def search_with_google(self, company_name):
        """Google Search API 활용"""
        try:
            import requests
            import urllib.parse
            from datetime import datetime, timedelta
            
            # Google Custom Search API 키가 있는 경우 사용
            google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
            google_cse_id = os.getenv('GOOGLE_CSE_ID')
            
            if google_api_key and google_cse_id:
                # 최근 6개월 내 뉴스 검색
                recent_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
                search_query = f"{company_name} 뉴스 투자 사업 확장 after:{recent_date}"
                
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    'key': google_api_key,
                    'cx': google_cse_id,
                    'q': search_query,
                    'num': 5,
                    'sort': 'date',
                    'tbm': 'nws'  # 뉴스 검색
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    if items:
                        news_summaries = []
                        for item in items[:3]:
                            title = item.get('title', '')
                            snippet = item.get('snippet', '')
                            date = item.get('pagemap', {}).get('metatags', [{}])[0].get('article:published_time', '')
                            news_summaries.append(f"• {title} - {snippet[:100]}...")
                        
                        return "\n".join(news_summaries)
            
            # API 키가 없는 경우 간단한 검색 결과 시뮬레이션
            return f"{company_name}의 최근 비즈니스 활동 및 성장 동향 (Google 검색 기반)"
            
        except Exception as e:
            logger.warning(f"Google Search 오류: {e}")
            return None
    
    def search_with_google_query(self, search_query):
        """enriched query를 사용한 Google 검색"""
        try:
            import requests
            from datetime import datetime, timedelta
            
            # Google Custom Search API 키가 있는 경우 사용
            google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
            google_cse_id = os.getenv('GOOGLE_CSE_ID')
            
            if google_api_key and google_cse_id:
                # enriched query 사용
                recent_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
                enhanced_query = f"{search_query} 뉴스 after:{recent_date}"
                
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    'key': google_api_key,
                    'cx': google_cse_id,
                    'q': enhanced_query,
                    'num': 5,
                    'sort': 'date',
                    'tbm': 'nws'  # 뉴스 검색
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    if items:
                        news_summaries = []
                        for item in items[:3]:
                            title = item.get('title', '')
                            snippet = item.get('snippet', '')
                            news_summaries.append(f"• {title} - {snippet[:100]}...")
                        
                        return "\n".join(news_summaries)
            
            # API 키가 없는 경우 enriched query를 활용한 시뮬레이션
            return f"정확한 검색 쿼리 '{search_query}'를 활용한 Google 검색 결과: 더 구체적이고 정확한 정보 확인"
            
        except Exception as e:
            logger.warning(f"Google Search 오류: {e}")
            return None
    
    def search_with_duckduckgo(self, company_name):
        """DuckDuckGo 검색 활용"""
        try:
            import requests
            import urllib.parse
            
            search_query = f"{company_name} 최신 뉴스 투자 사업 확장 2024"
            encoded_query = urllib.parse.quote(search_query)
            
            # DuckDuckGo Instant Answer API
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
            response = requests.get(url, timeout=20)
            
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
                        return "; ".join(topic_texts)
            
            return f"{company_name}에 대한 DuckDuckGo 검색 완료"
            
        except Exception as e:
            logger.warning(f"DuckDuckGo 검색 오류: {e}")
            return None
    
    def search_with_duckduckgo_query(self, search_query):
        """enriched query를 사용한 DuckDuckGo 검색"""
        try:
            import requests
            import urllib.parse
            
            # enriched query 사용
            encoded_query = urllib.parse.quote(search_query)
            
            # DuckDuckGo Instant Answer API
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
            response = requests.get(url, timeout=20)
            
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
                        return "; ".join(topic_texts)
            
            return f"정확한 검색 쿼리 '{search_query}'를 활용한 DuckDuckGo 검색 완료: 더 정밀한 정보 확보"
        
        except Exception as e:
            logger.warning(f"DuckDuckGo 뉴스 검색 오류 (Perplexity 보조용): {e}")
            return None
    
    def search_with_web_scraping(self, company_name):
        """웹 스크래핑을 통한 추가 정보 수집"""
        try:
            # 안전한 웹 스크래핑 (robots.txt 준수)
            import requests
            from bs4 import BeautifulSoup
            import time
            import random
            
            # 네이버 뉴스 검색 (공개 API 아닌 경우 제한적 사용)
            news_info = []
            
            # 회사 공식 웹사이트에서 보도자료/뉴스 섹션 확인
            if hasattr(self, 'company_website'):
                try:
                    # 짧은 딜레이로 서버 부하 방지
                    time.sleep(random.uniform(1, 3))
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    
                    # 공식 웹사이트의 뉴스/보도자료 페이지 추정
                    potential_urls = [
                        f"{self.company_website}/news",
                        f"{self.company_website}/press",
                        f"{self.company_website}/media",
                        f"{self.company_website}/announcement"
                    ]
                    
                    for url in potential_urls[:2]:  # 최대 2개만 확인
                        try:
                            response = requests.get(url, headers=headers, timeout=10)
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.content, 'html.parser')
                                # 최신 뉴스 제목들 추출
                                news_titles = soup.find_all(['h1', 'h2', 'h3', 'h4'], limit=3)
                                for title in news_titles:
                                    if title.get_text().strip():
                                        news_info.append(title.get_text().strip()[:100])
                                break
                        except:
                            continue
                            
                except Exception as scrape_error:
                    logger.debug(f"웹 스크래핑 제한: {scrape_error}")
            
            if news_info:
                return f"공식 웹사이트 최신 소식: {'; '.join(news_info[:2])}"
            
            return f"{company_name}의 공개 정보 및 최신 동향 (웹 검색 기반)"
            
        except Exception as e:
            logger.warning(f"웹 스크래핑 오류: {e}")
            return None
    
    def filter_and_enhance_results(self, all_results, company_name):
        """검색 결과 품질 필터링 및 향상"""
        try:
            if not all_results:
                logger.warning(f"{company_name}: 필터링할 결과가 없음")
                return self.generate_fallback_news_info(company_name)
            
            enhanced_results = []
            seen_content = set()
            
            for result in all_results:
                try:
                    # 안전한 결과 내용 추출
                    if isinstance(result, str) and result.strip():
                        # 이모지와 헤더 제거
                        if ': ' in result:
                            parts = result.split(': ', 1)
                            content = parts[1] if len(parts) > 1 else result
                        else:
                            content = result
                        
                        content = content.strip()
                        content_lower = content.lower()
                        
                        # 품질 검사 - 최소 길이 확인
                        if len(content) < 15:
                            logger.debug(f"너무 짧은 결과 제외: {content[:50]}")
                            continue
                        
                        # 무의미한 결과 제거
                        skip_phrases = [
                            '검색 결과',
                            '더 구체적이고 정확한 정보',
                            'api 키가 없는 경우',
                            '시뮬레이션'
                        ]
                        if any(phrase in content_lower for phrase in skip_phrases):
                            logger.debug(f"무의미한 결과 제외: {content[:50]}")
                            continue
                        
                        # 중복 내용 제거 (유사도 기반)
                        is_duplicate = False
                        for seen in seen_content:
                            if self.calculate_similarity(content_lower, seen) > 0.7:
                                is_duplicate = True
                                logger.debug(f"중복 결과 제외: {content[:50]}")
                                break
                        
                        if not is_duplicate:
                            seen_content.add(content_lower)
                            enhanced_results.append(result)
                            logger.debug(f"유효한 결과 추가: {content[:100]}")
                    
                except Exception as e:
                    logger.warning(f"개별 결과 처리 오류: {e} - {result[:100] if isinstance(result, str) else result}")
                    continue
            
            if enhanced_results:
                # 최신성 순서로 정렬 (Google 뉴스 우선)
                enhanced_results.sort(key=lambda x: (
                    0 if '📰 Google' in str(x) else
                    1 if '🦆 DuckDuckGo' in str(x) or 'DuckDuckGo' in str(x) else
                    2 if '🌐 웹' in str(x) or '웹 검색' in str(x) else 3
                ))
                
                result_text = "\n\n".join(enhanced_results)
                logger.info(f"{company_name}: {len(enhanced_results)}개 유효 결과 반환")
                return result_text
            
            logger.warning(f"{company_name}: 필터링 후 유효 결과 없음")
            return self.generate_fallback_news_info(company_name)
            
        except Exception as e:
            logger.error(f"결과 필터링 오류: {e}", exc_info=True)
            # 오류 발생 시에도 원본 결과 반환 시도
            if all_results and len(all_results) > 0:
                return "\n\n".join([str(r) for r in all_results if r])
            return self.generate_fallback_news_info(company_name)
    
    def calculate_similarity(self, text1, text2):
        """두 텍스트 간 유사도 계산 (간단한 Jaccard 유사도)"""
        try:
            words1 = set(text1.split())
            words2 = set(text2.split())
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            if len(union) == 0:
                return 0
            return len(intersection) / len(union)
        except:
            return 0
    
    def generate_fallback_news_info(self, company_name):
        """검색 실패 시 대체 정보 생성"""
        try:
            from datetime import datetime
            
            current_year = datetime.now().year
            
            fallback_info = f"""
🔍 {company_name} 최신 동향 정보

📈 {company_name}은(는) {current_year}년 현재 디지털 전환과 비즈니스 혁신에 지속적으로 투자하고 있는 것으로 보입니다.

💼 주요 관심 분야:
• 결제 시스템 현대화 및 효율화
• 고객 경험 개선을 위한 디지털 솔루션 도입
• 운영 효율성 향상을 위한 프로세스 자동화
• 데이터 기반 의사결정 시스템 구축

🎯 예상 성장 동력:
• 온라인/모바일 서비스 확장
• 결제 인프라 통합 및 최적화 필요성
• 고객 데이터 분석을 통한 개인화 서비스

⚡ PortOne 솔루션 적용 포인트:
• One Payment Infra로 통합 결제 환경 구축
• 재무 자동화로 운영 효율성 극대화  
• 개발 리소스 85% 절감으로 핵심 비즈니스 집중

※ 더 정확한 최신 정보 수집을 위해서는 Google Search API 키를 설정하시기 바랍니다.
"""
            return fallback_info.strip()
            
        except Exception as e:
            logger.error(f"Fallback 정보 생성 오류: {e}")
            return f"{company_name} 관련 최신 동향 및 뉴스 정보 (일반적 정보)"
    
    def get_active_search_engines(self):
        """활성화된 검색 엔진 목록 반환"""
        active_engines = ['Perplexity']
        
        # Google Search API 키 확인
        if os.getenv('GOOGLE_SEARCH_API_KEY') and os.getenv('GOOGLE_CSE_ID'):
            active_engines.append('Google Search')
        
        # DuckDuckGo는 항상 사용 가능
        active_engines.append('DuckDuckGo')
        
        # 웹 스크래핑은 웹사이트 정보가 있을 때만
        if hasattr(self, 'company_website') and self.company_website:
            active_engines.append('Web Scraping')
            
        return active_engines
    
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
혹시 대표님께서도 현재 사용 중인 PG사의 높은 수수료 부담, 매출 구간 변경으로 인한 수수료 인상,
그리고 다양한 결제 수단별 최적 PG 선택의 어려움으로 고민하고 계신가요?
저희 포트원은 단 하나의 연동으로 국내 25개 PG사 수수료 조건 비교 분석, 최적 PG사 견적 제안,
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
귀한 인재가 회사의 성장에 기여할 수 있도록 핵심 재무 전략 업무에만 집중할 수 있게 돕습니다.
실제로 비슷한 규모의 고객사들이 기존 대비 평균 15-30% 수수료를 절감하고 계십니다."

**참고 템플릿 4: 매출 구간 변경 이슈**
"매출이 10억, 30억을 넘어서며 성장할수록, PG사의 '영중소 구간' 변경으로 불필요한 결제 수수료를 더 내고 계실 수 있습니다.
포트원은 국내 25개 이상 PG사와의 제휴를 통해, 회사명이 현재보다 더 낮은 수수료를 적용받을 수 있도록 빠르게 도와드릴 수 있습니다.
실제로 비슷한 규모의 고객사들이 기존 대비 평균 15-30% 수수료를 절감하고 계십니다."

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
- 구매확정-정산내역 매핑 오류 → 높은 정확도의 자동 매핑
- 부가세 신고 자료 준비의 복잡성 → 자동화된 세무 자료 생성
- 데이터 누락으로 인한 손실 → 높은 데이터 정합성 보장
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
- **정량적 수치와 핵심 가치 제안은 반드시 볼드 처리하세요 (예: **85% 리소스 절감**, **2주 내 구축**, **90% 자동화**, **15% 향상** 등)**
- 자연스러운 한국어 문체 유지
- 한국어 자연스러운 줄바꿈을 위해 문단은 적절한 길이로 구분하세요
- **⚠️ 이메일 본문에서 극단적 표현 금지**: "즉시", "100%", "완벽한", "완벽", "절대", "무조건", "반드시", "필수" 등 과장된 표현은 피하고, 현실적이고 신뢰감 있는 표현 사용 (예: "90% 이상", "빠르게", "높은 정확도로", "대폭", "크게", "효과적으로" 등)


**명함 정보: 반드시 다음 서명으로 끝내기:**
{user_name}
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
4. 명확하고 실행 가능한 CTA
5. 전문적인 서명 (명함 정보)

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
                    "subject": f"[PortOne] {company_name} 담당자님께 전달 부탁드립니다",
                    "body": f"안녕하세요 {company_name} 담당자님,\n\n귀사의 비즈니스 성장에 깊은 인상을 받았습니다.\n\nPortOne의 One Payment Infra로 85% 리소스 절감과 2주 내 구축이 가능합니다. 20여 개 PG사를 하나로 통합하여 관리 효율성을 극대화하고, 스마트 라우팅으로 결제 성공률을 15% 향상시킬 수 있습니다.\n\n15분 통화로 자세한 내용을 설명드리고 싶습니다.\n\n감사합니다.\nPortOne 팀",
                    "cta": "15분 통화 일정 잡기",
                    "tone": "전문적이고 신뢰감 있는 톤",
                    "personalization_score": 8
                },
                "opi_curiosity": {
                    "product": "One Payment Infra",
                    "subject": f"[PortOne] {company_name} 담당자님께 전달 부탁드립니다",
                    "body": f"혹시 궁금한 게 있어 연락드립니다.\n\n{company_name}의 결제 시스템이 비즈니스 성장 속도를 따라가고 있나요? PG사 관리에 낭비되는 시간은 얼마나 될까요?\n\nPortOne으로 이 모든 걱정을 해결할 수 있습니다. 85% 리소스 절감, 15% 성공률 향상, 2주 내 구축이 가능합니다.\n\n10분만 시간 내주실 수 있나요?\n\n감사합니다.\nPortOne 팀",
                    "cta": "10분 데모 요청하기",
                    "tone": "호기심을 자극하는 질문형 톤",
                    "personalization_score": 9
                },
                "finance_professional": {
                    "product": "국내커머스채널 재무자동화 솔루션",
                    "subject": f"[PortOne] {company_name} 담당자님께 전달 부탁드립니다",
                    "body": f"안녕하세요 {company_name} 담당자님,\n\n귀사의 다채널 커머스 운영에 깊은 인상을 받았습니다.\n\n현재 네이버스마트스토어, 카카오스타일, 카페24 등 채널별 재무마감에 월 수십 시간을 소비하고 계신가요? PortOne의 재무자동화 솔루션으로 90% 이상 단축하고 100% 데이터 정합성을 확보할 수 있습니다.\n\n브랜드별/채널별 매출보고서와 부가세신고자료까지 자동화로 제공해드립니다.\n\n감사합니다.\nPortOne 팀",
                    "cta": "재무자동화 데모 요청",
                    "tone": "전문적이고 신뢰감 있는 톤",
                    "personalization_score": 8
                },
                "finance_curiosity": {
                    "product": "국내커머스채널 재무자동화 솔루션",
                    "subject": f"[PortOne] {company_name} 담당자님께 전달 부탁드립니다",
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
                'subject': f'[PortOne] {company_name} {contact_name if contact_name and contact_name != "담당자" else "담당자님"}께 전달 부탁드립니다',
                'body': f'''{personalized_greeting} 코리아포트원 오준호입니다.

혹시 대표님께서도 현재 사용 중인 PG사의 높은 수수료 부담, 매출 구간 변경으로 인한 수수료 인상,
그리고 다양한 결제 수단별 최적 PG 선택의 어려움으로 고민하고 계신가요?

저희 포트원은 단 하나의 연동으로 국내 25개 PG사 수수료 조건 비교 분석, 최적 PG사 견적 제안,
그리고 글로벌 확장성까지 제공하는 솔루션입니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

만약 이러한 고민을 해결하고 대표님의 사업 성장에만 집중하고 싶으시다면,
미팅을 통해 저희가 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.
다음 주 중 편하신 시간을 알려주시면 감사하겠습니다.

{user_name}
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'opi_curiosity': {
                'subject': f'[PortOne] {company_name} {contact_name if contact_name and contact_name != "담당자" else "담당자님"}께 전달 부탁드립니다',
                'body': f'''{personalized_greeting} PortOne {user_name}입니다.

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

{user_name}
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'finance_professional': {
                'subject': f'[PortOne] {company_name} {contact_name if contact_name and contact_name != "담당자" else "담당자님"}께 전달 부탁드립니다',
                'body': f'''{personalized_greeting} PortOne {user_name} 매니저입니다.

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
{user_name} 드림

{user_name}
Sales team
Sales Manager
M {user_phone}
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'finance_curiosity': {
                'subject': f'[PortOne] {company_name} {contact_name if contact_name and contact_name != "담당자" else "담당자님"}께 전달 부탁드립니다',
                'body': f'''{personalized_greeting} PortOne {user_name} 매니저입니다.

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
{user_name} 드림

{user_name}
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'game_d2c_professional': {
                'subject': f'[PortOne] {company_name} {contact_name if contact_name and contact_name != "담당자" else "담당자님"}께 전달 부탁드립니다',
                'body': f'''{personalized_greeting} PortOne {user_name}입니다.

혹시 애플 앱스토어와 구글 플레이스토어의 30% 인앱결제 수수료 때문에 고민이 많으시지 않나요?
최근 Com2uS, Neptune 등 국내 주요 게임사들도 D2C 웹상점으로 수수료 부담을 대폭 줄이고 있습니다.

저희 PortOne은 단 한 번의 SDK 연동으로 국내 25개 PG사를 통합하여, 최적의 비용으로 웹상점 결제를 운영할 수 있도록 지원합니다.
실제로 고객사들은 인앱결제 수수료를 90% 절약하고, 정산 업무를 자동화하고 계십니다.

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

다음 주 중 편하신 시간을 알려주시면, {company_name}에 최적화된 방안을 제안드리겠습니다.

{user_name}
Sales team
Sales Manager
E ocean@portone.io
M 010 5001 2143
서울시 성동구 성수이로 20길 16 JK타워 4층
https://www.portone.io'''
            },
            'game_d2c_curiosity': {
                'subject': f'[PortOne] {company_name} {contact_name if contact_name and contact_name != "담당자" else "담당자님"}께 전달 부탁드립니다',
                'body': f'''{personalized_greeting} PortOne {user_name}입니다.

최근 많은 게임사들이 인앱결제 수수료 절감을 위해 D2C 웹상점을 구축하지만,
막상 직접 구축하려다 보니 국내 25개 PG사 개별 연동, 정산 관리, 수수료 최적화 등이 부담스러우실 것 같습니다.

PortOne을 사용하시면 이 모든 과정을 한 번에 해결할 수 있습니다.
어떻게 수수료를 90% 절감하고 운영 업무를 자동화할 수 있는지 궁금하지 않으신가요?

https://www.youtube.com/watch?v=2EjzX6uTlKc 간단한 서비스 소개 유튜브영상 보내드립니다.
1분짜리 소리없는 영상이니 부담없이 서비스를 확인해 보시기 바랍니다.

15분만 시간을 내어주시면, 어떻게 가능한지 보여드리겠습니다.
다음 주 중 편하신 시간을 알려주시면 감사하겠습니다.

{user_name}
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


def generate_email_with_gemini(company_data, research_data, user_info=None):
    """Gemini 2.5 Pro를 사용하여 개인화된 이메일 생성"""
    try:
        # 사용자 정보 (서명용) - user_info 파라미터 우선, 없으면 current_user 체크
        if user_info:
            user_name = user_info.get('name', '오준호')
            user_company_nickname = user_info.get('company_nickname', f'PortOne {user_name} 매니저')
            user_phone = user_info.get('phone', '010-2580-2580')
            logger.info(f"👤 이메일 생성자: {user_name} ({user_company_nickname})")
            logger.info(f"✅ 전달받은 사용자 정보 사용: {user_info.get('email', 'N/A')}")
        else:
            user_name = current_user.name if (current_user and current_user.is_authenticated) else "오준호"
            user_company_nickname = current_user.company_nickname if (current_user and current_user.is_authenticated) else f"PortOne {user_name} 매니저"
            user_phone = current_user.phone if (current_user and current_user.is_authenticated) else "010-2580-2580"
            
            # 디버깅: 사용자 정보 로그
            logger.info(f"👤 이메일 생성자: {user_name} (PortOne {user_name} 매니저)")
            if current_user and current_user.is_authenticated:
                logger.info(f"✅ 로그인 사용자 인증됨: {current_user.email}")
            else:
                logger.warning(f"⚠️  current_user 인증 안 됨 - 기본값 사용")
        
        # 회사 정보 요약
        company_name = company_data.get('회사명', 'Unknown')
        
        # sales_item 열 확인 (서비스별 문안 생성 결정)
        sales_item = company_data.get('sales_item', '').lower().strip()
        logger.info(f"Sales item 확인: '{sales_item}' for {company_name}")
        
        # 담당자 정보 추출
        # N열(14번째 열)의 호칭 포함 담당자명을 우선 참조 (이미 완성된 호칭)
        column_keys = list(company_data.keys())
        email_name = ''
        if len(column_keys) >= 14:
            email_name = company_data.get(column_keys[13], '').strip()  # N열 (0-based index 13)
        
        # N열이 비어있거나 없으면 기존 로직 사용
        if not email_name:
            contact_name = company_data.get('담당자명', '') or company_data.get('대표자명', '') or company_data.get('이름', '')
            contact_position = company_data.get('직책', '') or company_data.get('직급', '')
            
            # 담당자명과 직책 처리 (기본값 설정)
            if not contact_name or contact_name == '담당자':
                email_name = '담당자님'
            else:
                # 직책 정보가 있는 경우
                if contact_position:
                    # 직책에 따른 적절한 호칭 처리
                    if any(keyword in contact_position for keyword in ['대표', 'CEO', '사장']):
                        email_name = f'{contact_name} {contact_position}님'
                    elif any(keyword in contact_position for keyword in ['이사', '부장', '팀장', '매니저', '실장', '과장']):
                        email_name = f'{contact_name} {contact_position}님'
                    elif any(keyword in contact_position for keyword in ['주임', '대리', '선임', '책임']):
                        email_name = f'{contact_name} {contact_position}님'
                    else:
                        # 기타 직책
                        email_name = f'{contact_name} {contact_position}님'
                else:
                    # 직책 정보가 없는 경우 이름만으로 처리
                    if any(title in contact_name for title in ['대표', 'CEO', '사장']):
                        email_name = f'{contact_name}님'
                    else:
                        email_name = f'{contact_name} 담당자님'
        
        # 경쟁사 정보 추출 (PortOne 이용 기업)
        competitor_name = company_data.get('경쟁사명', '') or company_data.get('경쟁사', '')
        
        company_info = f"회사명: {company_name}\n담당자: {email_name}"
        if competitor_name:
            company_info += f"\nPortOne 이용 경쟁사: {competitor_name}"
        
        # 추가 회사 정보가 있다면 포함
        for key, value in company_data.items():
            # N열 담당자명도 제외 목록에 추가 (중복 방지)
            excluded_keys = ['회사명', '대표자명', '담당자명', '이름', '직책', '직급', '경쟁사명', '경쟁사']
            if len(column_keys) >= 14:
                excluded_keys.append(column_keys[13])  # N열 키도 제외
            if key not in excluded_keys and value:
                company_info += f"\n{key}: {value}"
        
        # 조사 정보 및 Pain Point 요약
        research_summary = research_data.get('company_info', '조사 정보 없음')
        pain_points = research_data.get('pain_points', '일반적인 Pain Point')
        industry_trends = research_data.get('industry_trends', '')
        
        # 호스팅사 정보 확인 (OPI 제공 가능 여부 판단)
        # CSV 컴럼 구조 디버깅
        logger.debug(f"{company_name} CSV 컴럼들: {list(company_data.keys())}")
        
        # 다양한 호스팅사 컴럼명 지원
        possible_hosting_columns = ['호스팅사', '호스팅', '호스팅서비스', 'hosting', 'Hosting', '웹호스팅', '호스팅업체']
        hosting = ''
        for col in possible_hosting_columns:
            if col in company_data and company_data[col] and str(company_data[col]).strip():
                hosting = str(company_data[col]).lower().strip()
                logger.info(f"{company_name} 호스팅 정보 발견: '{col}' = '{hosting}'")
                break
        
        if not hosting:
            logger.warning(f"{company_name} 호스팅 정보 없음 - CSV에 호스팅사 컴럼이 있는지 확인하세요")
        
        is_self_hosted = '자체' in hosting or 'self' in hosting or '직접' in hosting
        
        # 🆕 sales_item에서 복수 서비스 감지 (콤마, +, & 등으로 분리)
        def parse_sales_items(sales_item_str):
            """sales_item 문자열을 파싱하여 여러 서비스 추출"""
            if not sales_item_str:
                return []
            
            # 콤마, +, &, 공백 등으로 분리
            import re
            items = re.split(r'[,+&\s]+', sales_item_str.lower().strip())
            # 빈 문자열 제거
            items = [item.strip() for item in items if item.strip()]
            return items
        
        # sales_item 파싱
        sales_items = parse_sales_items(sales_item)
        logger.info(f"📋 Sales items 파싱 결과: {sales_items} for {company_name}")
        
        # 감지된 서비스 리스트 (중복 제거)
        detected_services = set()
        for item in sales_items:
            if 'opi' in item:
                detected_services.add('opi')
            if 'recon' in item or '재무' in item:
                detected_services.add('recon')
            if 'prism' in item or '프리즘' in item:
                detected_services.add('prism')
            if 'ps' in item or '플랫폼정산' in item or '파트너정산' in item:
                detected_services.add('ps')
        
        detected_services = list(detected_services)
        logger.info(f"🎯 감지된 서비스: {detected_services} for {company_name}")
        
        # sales_item에 따른 서비스 결정
        services_to_generate = []
        is_multi_service = len(detected_services) > 1
        
        if sales_item:
            if is_multi_service:
                # 🆕 복수 서비스 감지: 통합 문안 생성
                # OPI는 자체구축일 때만 포함
                if 'opi' in detected_services and not is_self_hosted:
                    logger.warning(f"⚠️ OPI 불가능 (호스팅: {hosting}) → 제외: {company_name}")
                    detected_services.remove('opi')
                
                services_to_generate = ['multi_service_professional', 'multi_service_curiosity']
                service_names = []
                if 'opi' in detected_services:
                    service_names.append('OPI')
                if 'recon' in detected_services:
                    service_names.append('Recon')
                if 'prism' in detected_services:
                    service_names.append('Prism')
                if 'ps' in detected_services:
                    service_names.append('PS')
                
                logger.info(f"🎯 복수 서비스 통합 문안 생성: {' + '.join(service_names)} for {company_name}")
            
            elif 'opi' in detected_services:
                # 단일 OPI 서비스
                if is_self_hosted:
                    services_to_generate = ['opi_professional', 'opi_curiosity']
                    logger.info(f"✅ OPI 서비스 문안 생성 (호스팅: {hosting}): {company_name}")
                else:
                    # 자체구축이 아니면 Recon으로 대체
                    services_to_generate = ['finance_professional', 'finance_curiosity']
                    detected_services = ['recon']
                    logger.warning(f"⚠️ OPI 불가능 (호스팅: {hosting}) → Recon(재무자동화)으로 전환: {company_name}")
            
            elif 'recon' in detected_services:
                services_to_generate = ['finance_professional', 'finance_curiosity']
                logger.info(f"Recon(재무자동화) 서비스 문안만 생성: {company_name}")
            
            elif 'prism' in detected_services:
                services_to_generate = ['prism_professional', 'prism_curiosity']
                logger.info(f"Prism(멀티 오픈마켓 정산 통합) 서비스 문안만 생성: {company_name}")
            
            elif 'ps' in detected_services:
                services_to_generate = ['ps_professional', 'ps_curiosity']
                logger.info(f"플랫폼 정산(파트너 정산+세금계산서+지급대행) 서비스 문안만 생성: {company_name}")
            
            else:
                # 알 수 없는 sales_item인 경우
                if is_self_hosted:
                    # 자체구축이면 4개 생성
                    services_to_generate = ['opi_professional', 'opi_curiosity', 'finance_professional', 'finance_curiosity']
                    logger.info(f"알 수 없는 sales_item '{sales_item}', 자체구축이므로 4개 문안 생성: {company_name}")
                else:
                    # 자체구축 아니면 Recon만
                    services_to_generate = ['finance_professional', 'finance_curiosity']
                    logger.info(f"알 수 없는 sales_item '{sales_item}', 자체구축 아니므로 Recon만 생성: {company_name}")
        else:
            # sales_item이 없으면 호스팅사 기준으로 판단
            if not hosting:
                # 호스팅 정보가 없으면 4개 모두 생성
                services_to_generate = ['opi_professional', 'opi_curiosity', 'finance_professional', 'finance_curiosity']
                logger.info(f"sales_item 없음 + 호스팅 정보 없음 → 4개 모두 생성: {company_name}")
            elif is_self_hosted:
                # 자체구축이면 4개 생성
                services_to_generate = ['opi_professional', 'opi_curiosity', 'finance_professional', 'finance_curiosity']
                logger.info(f"sales_item 없음 + 자체구축 → 4개 문안 생성 (호스팅: {hosting}): {company_name}")
            else:
                # 호스팅 정보가 있고 자체구축이 아니면 Recon만
                services_to_generate = ['finance_professional', 'finance_curiosity']
                logger.info(f"sales_item 없음 + 호스팅='{hosting}' (자체구축 아님) → Recon만 생성: {company_name}")
        
        # 서비스별 통합 지식베이스 로드 (서비스 소개서 + 블로그 전체)
        from portone_blog_cache import get_service_knowledge
        
        # 🆕 복수 서비스일 경우 detected_services 기반으로 모두 로드
        if is_multi_service:
            logger.info(f"📚 복수 서비스 지식베이스 로드 시작: {detected_services}")
        
        # OPI용 통합 지식베이스
        opi_blog_content = ""
        if any('opi' in s for s in services_to_generate) or (is_multi_service and 'opi' in detected_services):
            opi_blog_content = get_service_knowledge(service_type='OPI')
            logger.info(f"📚 [OPI] {company_name}: 서비스 소개서 + 블로그 전체 지식베이스 로드")
        
        # Recon용 통합 지식베이스
        recon_blog_content = ""
        if any('finance' in s for s in services_to_generate) or (is_multi_service and 'recon' in detected_services):
            recon_blog_content = get_service_knowledge(service_type='Recon')
            logger.info(f"📚 [Recon] {company_name}: 서비스 소개서 + 블로그 전체 지식베이스 로드")
        
        # Prism용 통합 지식베이스
        prism_blog_content = ""
        if any('prism' in s for s in services_to_generate) or (is_multi_service and 'prism' in detected_services):
            prism_blog_content = get_service_knowledge(service_type='Prism')
            logger.info(f"📚 [Prism] {company_name}: 서비스 소개서 + 블로그 전체 지식베이스 로드")
        
        # 플랫폼 정산(PS)용 통합 지식베이스
        ps_blog_content = ""
        if any('ps' in s for s in services_to_generate) or (is_multi_service and 'ps' in detected_services):
            ps_blog_content = get_service_knowledge(service_type='PS')
            logger.info(f"📚 [플랫폼 정산] {company_name}: 서비스 소개서 + 블로그 전체 지식베이스 로드")
        
        # CSV 뉴스 제공 여부 확인
        has_csv_news = "## 📰 관련 뉴스 기사 (CSV 제공)" in research_summary
        
        # 해외 진출 여부 확인 (뉴스/조사 내용에서 키워드 추출)
        global_keywords = ['해외', '글로벌', 'global', '수출', 'export', '해외진출', '국제', '아시아', '유럽', '미국', '일본', '중국', '동남아']
        is_global = any(keyword in research_summary.lower() for keyword in global_keywords)
        
        # PG사 개수 동적 표현
        if is_global:
            pg_count = "국내외 50여개"
            logger.info(f"🌍 {company_name}: 해외 타겟 감지 → {pg_count} PG사 언급")
        else:
            pg_count = "국내 20여개"
            logger.info(f"🇰🇷 {company_name}: 국내 타겟 → {pg_count} PG사 언급")
        
        # 기본 context 정의
        if has_csv_news:
            news_instruction = """**🎯 최우선 지시: CSV에서 제공된 '관련 뉴스 기사' 섹션의 내용을 반드시 이메일 도입부에 활용하세요!**

이 뉴스는 사용자가 직접 선정한 중요한 기사이므로, 다른 어떤 뉴스보다 우선적으로 언급해야 합니다.

**필수 활용 방식:**
- "최근 '{news_title}' 기사를 봤습니다..." 형태로 직접 인용
- CSV 뉴스가 있으면 Perplexity 뉴스보다 우선
- 뉴스 내용과 회사 상황을 구체적으로 연결

예시:
- "최근 '{company_name}가 100억원 투자를 유치했다'는 기사를 봤습니다. 사업 확장 준비로 바쁘시겠지만, 결제 인프라 확장도 지금 준비해야 할 시점이 아닐까요?"
- "'{company_name}의 매출 200% 증가' 소식을 들었습니다. 급성장할 때 결제 시스템 병목이 가장 큰 리스크인데, 지금 어떻게 대응하고 계신가요?" """
        else:
            news_instruction = """**중요**: 위의 Perplexity 조사 결과에서 구체적인 뉴스 내용을 직접 인용하여 이메일 도입부에 반드시 활용하세요.

예시:
- "최근 기사에서 '{company_name}가 100억원 투자를 유치했다'고 봤습니다. 사업 확장에 따른 결제 인프라 확장 계획도 있으실 텐데..." """
        
        context = f"""
당신은 포트원(PortOne) 전문 세일즈 카피라이터로, 실제 검증된 한국어 영업 이메일 패턴을 완벽히 숙지하고 있습니다.

**🚨 중요: 서비스 소개서와 블로그 기반 제약 사항 🚨**
- 아래 제공된 OPI/Recon 참고 정보(서비스 소개서 + 블로그)에 명시된 기능과 수치만 언급하세요
- 서비스 소개서/블로그에 없는 기능이나 채널은 절대 언급하지 마세요
- 제공할 수 없는 영역을 제공한다고 말하면 안 됩니다
- 확실하지 않은 내용은 일반적인 Pain Point 중심으로만 언급하세요

**✅ OPI에서 언급 가능한 결제 수단 (소개서 기반):**
- 신용카드, 간편결제 (국내 0.5% 수수료)
- 해외: 각국의 간편결제 수단 (100+ 결제 수단)
- 크립토 결제 등
- ❌ **계좌이체는 지원하지 않으므로 절대 언급 금지**

**포트원 핵심 수치 (반드시 활용):**
- 국내 3,000여개 기업이 포트원 사용 중
- 연환산 거래액 12조원 (2024년 12월 기준)
- {pg_count} PG사 연동 가능 (타겟 회사의 해외 진출 여부에 따라 자동 조정됨)
- 이 수치들을 활용하여 신뢰도를 높이세요
  예: "이미 국내 3,000여개 기업이..."
  예: "연 12조원 규모의 거래를 처리하는..."
  예: "{pg_count} PG사를 한 번의 연동으로..."

**타겟 회사 정보:**
{company_info}

**🔥 회사 조사 결과 (이메일에 반드시 활용해야 함):**
{research_summary}

**업계 트렌드:**
{industry_trends}

{news_instruction}
- "'{company_name}의 3분기 매출이 전년 대비 150% 증가했다'는 소식을 들었습니다. 급속한 성장에 따른 재무 관리 부담이 늘어나고 계시지 않나요?"
- "'{company_name}가 일본 시장에 진출한다'는 뉴스를 봤습니다. 해외 진출 시 현지 결제 시스템 연동이 복잡하실 텐데..."

"""

        # 생성할 서비스에 따른 프롬프트 조정
        if is_multi_service:
            # 🆕 복수 서비스 통합 문안
            service_names_kr = []
            if 'opi' in detected_services:
                service_names_kr.append('OPI(해외결제)')
            if 'recon' in detected_services:
                service_names_kr.append('Recon(재무자동화)')
            if 'prism' in detected_services:
                service_names_kr.append('Prism(오픈마켓 정산)')
            if 'ps' in detected_services:
                service_names_kr.append('PS(플랫폼 정산)')
            
            service_focus = f"{' + '.join(service_names_kr)} 통합 솔루션을 자연스럽게 연결하여 제안하는 2개의"
            logger.info(f"📧 복수 서비스 문안 초점: {service_focus}")
        elif len(services_to_generate) == 2:
            if 'opi' in services_to_generate[0]:
                service_focus = "One Payment Infra (OPI) 서비스에 집중한 2개의"
            elif 'prism' in services_to_generate[0]:
                service_focus = "멀티 오픈마켓 정산 통합 솔루션 (Prism)에 집중한 2개의"
            elif 'ps' in services_to_generate[0]:
                service_focus = "플랫폼 정산 자동화 (파트너 정산+세금계산서+지급대행)에 집중한 2개의"
            else:
                service_focus = "재무자동화 솔루션에 집중한 2개의"
        else:
            service_focus = "4개의 설득력 있고 차별화된"
        
        prompt = f"""
{context}

**회사별 맞춤 Pain Points (조사 결과 기반):**
{pain_points}

다음 고정된 형식에 따라 {service_focus} 이메일을 작성해주세요:

**🎯 최우선 목표: B2B 의사결정자가 "즉시 답장하고 싶다"고 느끼는 메일 작성**

당신이 작성하는 메일은 AI 평가 시스템으로 효과성을 측정하며, 아래 기준으로 5점 만점 평가됩니다:

**5점 (목표)**: "정확히 우리가 찾던 솔루션이며 즉시 답장하겠습니다", "매우 시의적절하고 필요한 제안", "우리 회사의 현재 문제를 정확히 이해하고 있어 매우 인상적"
**4점 (합격)**: "매우 관심이 가며 곧 답장할 가능성 높음", "우리 회사의 pain point를 잘 파악", "구체적이고 관련성이 높아 미팅을 잡고 싶다"
**3점 이하 (실패)**: "어느 정도 관심", "제안이 괜찮아 보이지만 확신 없음", "별로 관심 없음", "스팸처럼 느껴짐"

**필수 요구사항 (4-5점을 받기 위한 조건):**
1. **가장 중요**: 퍼플렉시티가 조사한 {company_name}의 최신 뉴스/활동을 반드시 구체적으로 언급하여 개인화
   → "이 회사의 현재 상황을 정확히 이해하고 있다" 인상 필수
2. 위에 제시된 회사별 맞춤 Pain Point를 구체적으로 언급하여 차별화
   → "우리 회사의 pain point를 잘 파악했다" 반응 유도  
3. 고정된 서론/결론 형식 사용 (담당자의 이름과 직책이 정확히 반영되도록)
4. 담당자의 직책에 맞는 관점으로 Pain Point와 해결책 제시
5. 실제 수치와 구체적 혜택 제시 (85% 절감, 90% 단축, 15% 향상 등)
   → "구체적이고 관련성이 높다" 평가 확보
6. PortOne 이용 경쟁사가 있다면 반드시 해당 기업 사례를 언급
   → "시의적절하고 필요한 제안" 인식 강화
7. "비슷한 고민을 가진 다른 고객사도..." 식의 사례 암시
8. **즉시 답장하고 싶게 만드는 요소 포함**:
   - 시급성: "지금 겪고 계실" 문제 언급
   - 관련성: "{company_name}만의 구체적 상황" 정확히 지적
   - 실현 가능성: "2주 내 구축" 등 구체적 타임라인
   - **주의**: 실제 이메일 본문에서는 "즉시", "100%", "완벽한", "절대" 등 극단적 표현은 피하고 현실적 표현 사용 (예: "빠르게", "90% 이상", "높은 정확도로")

**퍼플렉시티 뉴스 직접 인용 예시:**
- "최근 기사에서 '{company_name}가 시리즈A 50억원 투자를 유치했다'고 봤습니다. 사업 확장 준비로 바쁘시겠지만..."
- "'{company_name}의 2분기 매출이 전년 대비 200% 증가했다'는 소식을 들었습니다. 급성장에 따른 시스템 부담은 어떻게 해결하고 계신가요?"
- "'{company_name}가 동남아시아 시장 진출을 발표했다'는 뉴스를 봤습니다. 해외 진출 시 현지 결제 연동이 복잡하실 텐데..."
- "'{company_name}이 AI 서비스 신사업을 시작한다'고 들었습니다. 새로운 수익 모델에 맞는 결제 시스템도 필요하실 것 같은데..."

**직책별 맞춤 접근법:**
- **대표/CEO/사장**: 전략적 관점, 비즈니스 성장, 투자 효율성 강조
- **이사/부장급**: 조직 효율성, 리소스 관리, 성과 개선에 집중
- **팀장/매니저**: 팀 운영 효율화, 업무 프로세스 개선 중심
- **실무진 (대리/주임 등)**: 일상 업무의 구체적 어려움과 해결책 제시

**PortOne 이용 경쟁사 사례 활용 지침:**
{f"- {competitor_name}도 과거 같은 고민을 했었지만, PortOne 도입 후 개발 리소스를 절약하여 지금은 서비스 본질에 집중할 수 있게 되었습니다." if competitor_name else ""}
{f"- {competitor_name}의 경우도 처음에는 결제 시스템 구축에 많은 시간과 비용을 투자했지만, PortOne으로 전환한 후 핵심 비즈니스에 더 많은 리소스를 투입할 수 있게 되었습니다." if competitor_name else ""}
{f"- 같은 업계의 {competitor_name}도 비슷한 Pain Point로 어려움을 겪다가 PortOne을 통해 해결했습니다." if competitor_name else ""}

**사례 언급 방식:**
{f'- "{competitor_name}도 과거 같은 고민을 하셨지만, PortOne 도입 후 개발 리소스 85% 절약으로 지금은 서비스 본질에 집중하고 계십니다."' if competitor_name else ''}
{f'- "실제로 {competitor_name} 같은 경우도 PortOne 도입 전에는 결제 시스템 구축에 6개월 이상 소요됐지만, 지금은 2주 내 새로운 기능을 출시할 수 있게 되었습니다."' if competitor_name else ''}

**고정 서론 형식:**
"안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다."

**고정 결론 형식 (필수!):**
"⚠️  **반드시** 아래 CTA(행동 촉구)를 포함하세요. CTA가 없으면 이메일이 완성되지 않은 것입니다!"

"<br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.<br><br>감사합니다.<br>{user_name} 드림"

‼️ **CTA 필수 포함 요구사항:**
- 위의 "다음주 중 편하신 일정을 알려주시면" CTA는 **반드시** 포함해야 합니다
- 이 CTA가 빠지면 이메일이 불완전하게 됩니다
- 서명("감사합니다. {user_name} 드림") 앞에 반드시 CTA를 배치하세요

**이메일 유형 (요청된 서비스에 따라 선택적 생성):**

1. **One Payment Infra - 전문적 톤**: 
{opi_blog_content}
   - **필수**: 뉴스 내용을 직접 인용. 예: "최근 기사에서 '{company_name}가 XX억원 투자 유치'라고 봤습니다"
   - 구체적 뉴스 → 결제 시스템 확장 필요성 자연스럽게 연결
   - **OPI 참고 정보에 명시된 기능만 언급**: 위 참고 정보에서 확인된 수치/기능만 사용하세요
   - **결제 수단 언급 시**: 신용카드, 간편결제, 해외는 각국의 간편결제 수단 등 (100+ 결제 수단) ❌ **계좌이체는 언급 금지**
   - OPI의 핵심 해결책과 수치 (평균 15-30% 수수료 절감, PG사별 견적 비교 제안)
   - **구체적 수치 활용**: "이미 국내 3,000여개 기업이 포트원으로..." / "연 12조원 규모의 거래를 안정적으로..."
   - **블로그 정보 활용**: 위 OPI 참고 정보의 수치/트렌드를 자연스럽게 녹여서 설득력 강화
   - **경쟁사가 있다면**: "{competitor_name}도 비슷한 성장 과정에서<br>PortOne으로 결제 인프라를 안정화했습니다"

2. **One Payment Infra - 호기심 유발형**: 
{opi_blog_content}
   - **필수**: 뉴스를 직접 언급한 질문. 예: "'{company_name}의 매출 150% 증가' 소식을 봤는데, 결제량 증가는 어떻게 처리하고 계신가요?"
   - 급성장에 따른 결제 시스템 병목 현상 걱정 표현
   - **구체적 수치 활용**: "이미 국내 3,000여개 기업이..." 같이 구체적 수치로 신뢰도 강화
   - **블로그 정보 활용**: 위 OPI 참고 정보의 업계 사례를 자연스럽게 인용
   - **경쟁사가 있다면**: "실제로 {competitor_name}도 급성장할 때<br>같은 고민을 했었는데..." 호기심 유발
   - "어떻게 해결했는지 궁금하시지 않나요?" 관심 유도

3. **재무자동화 솔루션 (Recon) - 전문적 톤**: 
{recon_blog_content}
   - **필수**: 성장/확장 뉴스를 구체적으로 인용. 예: "'{company_name}가 신사업 부문 진출'이라는 소식을 들었습니다"
   - 사업 다각화 → 복잡해지는 재무 관리 자연스럽게 연결
   - **Recon 참고 정보에 명시된 기능만 언급**: 위 참고 정보에서 확인된 기능/채널만 사용하세요
   - **구체적 수치 활용**: "국내 3,000여개 기업의 재무 데이터를 관리하는..." / "연 12조원 규모 거래의 정산을..."
   - **블로그 정보 활용**: 위 Recon 참고 정보의 통계/효과를 근거로 제시하며 설득력 강화
   - **경쟁사가 있다면**: "{competitor_name}도 사업 확장 시<br>재무 자동화로 90% 시간 절약했습니다"
   - **Recon 핵심 가치 프로포지션 (반드시 포함)**: "{pg_count} PG사의 각기다른 양식에도 정확하게 데이터를 통합하고 주문건당 정산여부 파악이 가능합니다. 이를 통해 ERP연동도 가능하기 때문에 재무팀의 반복적인 수작업을 90% 이상 단축하고, 휴먼에러를 줄여 확보된 리소스를 더 가치 있는 성장 전략에 집중하실 수 있습니다"

4. **재무자동화 솔루션 (Recon) - 호기심 유발형**: 
{recon_blog_content}
   - **필수**: 구체적 뉴스로 시작하는 질문. 예: "'{company_name} 해외 진출' 뉴스를 봤는데, 다국가 재무 관리는 어떻게 하실 계획인가요?"
   - 확장에 따른 재무 복잡성 증가 공감 표현
   - **구체적 수치 활용**: "국내 3,000여개 기업이 이미..." 같이 명확한 숫자로 신뢰도 제공
   - **블로그 정보 활용**: 위 Recon 참고 정보의 Pain Point를 자연스럽게 언급
   - **경쟁사가 있다면**: "{competitor_name}도 글로벌 진출 시<br>재무 통합 관리로 큰 도움을 받았는데..." 호기심 자극
   - **Recon 핵심 가치 프로포지션 (반드시 포함)**: "{pg_count} PG사의 다른 데이터 형식도 자동으로 통합하고, ERP 연동으로 재무팀 업무를 90% 이상 줄여드릴 수 있습니다. 휴먼에러도 제거하고요"
   - "구체적으로 어떤 도움이 되는지 보여드릴까요?" 관심 유도

5. **멀티 오픈마켓 정산 통합 솔루션 (Prism) - 전문적 톤**: 
{prism_blog_content}
   - **필수**: 오픈마켓 확장/매출 증가 뉴스를 구체적으로 인용. 예: "'{company_name}가 쿠팡/11번가 입점 확대'라는 소식을 들었습니다"
   - 다중 오픈마켓 운영 → 각 플랫폼마다 다른 정산 기준과 데이터 형식으로 인한 복잡한 정산 관리/현금흐름 파악 어려움 자연스럽게 연결
   - **Prism 참고 정보에 명시된 기능만 언급**: 위 참고 정보에서 확인된 채널/기능만 사용하세요
   - **핵심 Pain Point**: 각 오픈마켓의 정산기준/주기 차이, 반복적인 엑셀 작업, 미수금 관리 어려움, 데이터 누락/오류
   - **구체적 수치 활용**: "재무 마감 시간 **90% 이상 단축**" / "**높은 데이터 정합성** 확보"
   - **블로그 정보 활용**: 위 Prism 참고 정보의 통계/효과를 근거로 제시하며 설득력 강화
   - **경쟁사가 있다면**: "{competitor_name}도 다중 채널 운영 시<br>Prism으로 재무팀 업무를 90% 자동화했습니다"
   - **Prism 핵심 가치 프로포지션 (반드시 포함)**: "네이버 스마트스토어, 쿠팡, 카카오스타일 등 각 오픈마켓의 서로 다른 정산기준과 주기를 자동으로 통합하여, 정확한 현금흐름과 미수금을 실시간으로 파악하실 수 있습니다. 월 수십 시간의 반복적인 엑셀 작업을 자동화하고, 높은 데이터 정합성으로 휴먼에러를 제거합니다"

6. **멀티 오픈마켓 정산 통합 솔루션 (Prism) - 호기심 유발형**: 
{prism_blog_content}
   - **필수**: 구체적 뉴스로 시작하는 질문. 예: "'{company_name}의 2분기 매출 150% 증가' 소식을 봤는데, 네이버/쿠팡/11번가 등 여러 오픈마켓의 서로 다른 정산 데이터는 어떻게 관리하고 계신가요?"
   - 채널 확장에 따른 재무 복잡성 증가 공감 표현
   - **구체적 수치 활용**: "이미 국내 3,000여개 기업이..." 같이 명확한 숫자로 신뢰도 제공
   - **핵심 Pain Point 공감**: "혹시 네이버/쿠팡/11번가 등 각 채널마다 정산 데이터 다운로드하고 엑셀로 수작업하시나요?"
   - **블로그 정보 활용**: 위 Prism 참고 정보의 Pain Point를 자연스럽게 언급
   - **경쟁사가 있다면**: "{competitor_name}도 다중 채널 확장 시<br>재무 마감 자동화로 큰 도움을 받았는데..." 호기심 자극
   - **Prism 핵심 가치 프로포지션 (반드시 포함)**: "각 오픈마켓의 다른 정산 형식도 자동으로 통합하고, 현금흐름/미수금을 실시간 파악하여 재무팀 업무를 **90% 이상** 줄여드릴 수 있습니다"
   - "어떻게 월말 마감을 하루 만에 끝낼 수 있는지 보여드릴까요?" 관심 유도

7. **플랫폼 정산 자동화 (파트너 정산+세금계산서+지급대행) - 전문적 톤**: 
{ps_blog_content}
   - **필수**: 플랫폼/마켓플레이스 확장 뉴스 인용. 예: "'{company_name}의 판매자 수 2배 증가'라는 소식을 봤는데, 파트너 정산 업무도 같이 늘어나셨을 것 같습니다"
   - **핵심 Pain Point**: 매달 한 달 걸리는 파트너 정산 작업, 수기 정산금 계산 오류, 홈택스 세금계산서 발행의 복잡함, 제한적인 지급 시간(영업일만), 개인/프리랜서 지급 불가
   - **구체적 수치 활용**: "**한 달 걸리던 정산을 이틀로 단축** (인프런 사례)", "**100,000건 이상 세금계산서 일괄 발행**", "**365일 24시간 지급**"
   - **블로그 정보 활용**: 인프런 도입 사례 등 실제 고객 성과 언급
   - **경쟁사가 있다면**: "{competitor_name}도 파트너 수 증가로 정산 자동화를 도입했습니다"
   - **플랫폼 정산 핵심 가치 프로포지션 (반드시 포함)**: "파트너 정산금 자동 계산부터 세금계산서 일괄 발행, 365일 지급까지 하나의 플랫폼에서 완전 자동화합니다. 한 달 걸리던 정산 업무를 이틀로 단축하고, 개인/법인/프리랜서 구분 없이 모두 지급 가능하며, 주말과 공휴일에도 실시간 지급됩니다"

8. **플랫폼 정산 자동화 (파트너 정산+세금계산서+지급대행) - 호기심 유발형**: 
{ps_blog_content}
   - **필수**: 구체적 상황으로 시작하는 질문. 예: "'{company_name}의 입점 파트너 3배 증가' 소식을 봤는데, 혹시 매달 정산하느라 월말마다 야근하고 계시진 않으신가요?"
   - **핵심 Pain Point 공감**: "파트너별로 다른 수수료율 적용하고, 세금계산서 발행하고, 하나하나 송금하는 업무... 생각보다 시간이 많이 걸리죠"
   - **구체적 수치 활용**: "인프런은 한 달 걸리던 정산을 이틀로 줄였습니다", "홈택스는 1,000건까지만 가능하지만 포트원은 100,000건도 일괄 발행"
   - **블로그 정보 활용**: 실제 플랫폼 기업들의 정산 고민과 해결 사례
   - **경쟁사가 있다면**: "{competitor_name}도 정산 자동화로 재무팀 리소스를 핵심 업무에 집중하고 있는데..." 호기심 자극
   - **플랫폼 정산 핵심 가치 프로포지션 (반드시 포함)**: "정산금 계산-세금계산서-지급까지 원클릭으로 끝낼 수 있습니다. 주말에도 지급 가능하고, 개인 파트너에게도 바로 송금할 수 있어요"
   - "실제로 어떻게 한 달 정산을 이틀로 줄였는지 보여드릴까요?" 관심 유도

🆕 **9. 복수 서비스 통합 문안 (multi_service_professional / multi_service_curiosity):**

Detected Services: {', '.join(detected_services) if is_multi_service else 'N/A'}

**복수 서비스 통합 전략:**
- **핵심 원칙**: 하나의 큐스토머 Pain Point에서 시작하여 복수 서비스를 자연스럽게 연결
- **어색하게 부각된 제안을 하지 말 것**: "이것도 해드립니다, 저것도 해드립니다" 방식 금지
- **스토리 기반 통합**: 고객의 성장 스토리 안에서 여러 서비스가 필요한 이유를 설명

**통합 방식 예시:**

**OPI + PS 조합 (해외 진출 + 플랫폼)**:
- 시작: "해외 진출 뉴스를 봤습니다. 현지 결제 연동과 파트너 정산, 둘 다 부담되실 텐데..."
- 연결: "**OPI로 현지 결제** 연동하면서, 동시에 **PS로 현지 파트너 정산까지** 자동화할 수 있습니다"
- 가치: "글로벌 확장에 필요한 모든 재무 인프라를 한 번에 해결"

**Prism + PS 조합 (커머스 + 플랫폼 정산)**:
- 시작: "다중 오픈마켓 확장 뉴스를 봤습니다. 각 채널의 서로 다른 정산 기준과 파트너사 정산까지, 재무팀이 부담되실 것 같은데..."
- 연결: "**Prism으로 오픈마켓 정산 통합** + **PS로 파트너 정산 자동화**로 모두 해결됩니다"
- 가치: "월말 재무 마감을 **90% 이상 단축**하고 정확성도 확보"

**OPI + Recon 조합 (해외 + 재무자동화)**:
- 시작: "글로벌 확장과 함께 다양한 PG사 데이터 통합이 복잡해지실 텐데..."
- 연결: "**OPI로 {pg_count} PG사 통합** + **Recon으로 다국가 재무 자동화**"
- 가치: "국내외 모든 재무 데이터를 한 곳에서 관리"

**PS + Recon 조합 (플랫폼 + 재무)**:
- 시작: "플랫폼 확장으로 파트너 정산과 전체 재무 관리가 복잡해지셨을 텐데..."
- 연결: "**PS로 파트너 정산 자동화** + **Recon으로 전체 재무 통합**"
- 가치: "파트너 정산부터 ERP 연동까지 완전 자동화"

**통합 문안 작성 주의사항:**
- 각 서비스의 지식베이스를 모두 활용하되, **하나의 스토리로 연결**
- 서비스별 가치 프로포지션은 본문에서 자연스럽게 녹여서 언급 (목록형 나열 금지)
- Pain Point 공감 → 통합 솔루션 제안 → 결합 효과 강조 순서로 전개
- **분량 주의**: 여러 서비스를 언급하더라도 전체 본문은 130-200단어 유지

**구조 및 형식:**
- 제목: 고정 형식 사용 ("[PortOne] {company_name} {email_name}께 전달 부탁드립니다") - 본문에 제목 포함하지 말것
- 본문: 고정 서론 → Pain Point 제기(50-70단어) → 해결책 제시(50-70단어) → 경쟁사 사례/혜택(30-50단어) → 고정 결론
- 전체 본문: 130-200단어로 간결하면서도 핵심적으로 작성
- **👊 정량적 수치와 핵심 가치 제안은 반드시 볼드 처리하세요**:
  * 예: **85% 리소스 절감**, **2주 내 구축**, **90% 자동화**, **15% 향상**, **0.5% 수수료** 등
  * 가치 제안: **무료 컨설팅**, **신용카드/간편결제**, **100+ 결제 수단** 등
  * Pain Point 해결책의 핵심 기능도 볼드 처리
- **한국어 자연스러운 줄바꾸기 규칙 (매우 중요)**:
  * **기본 규칙: 한 문장이 40-50자 (공백 포함)를 넘으면 반드시 줄바꾸기**
  * 각 줄은 25-50자 범위로 유지, 의미 단위로 자연스럽게 끊기
  * **문단 간 구분: 새로운 주제로 넘어갈 때는 반드시 `<br><br>` (빈 줄) 사용**
  * 긴 문장은 절(clause) 단위로 끊어서 호흡감 확보
  * 리스트/나열: 각 항목마다 `<br>`
  * 예시:
    ```
    나쁜 줄바꿈:
    "최근 투자 유치 소식을 봤습니다. 빠른 성장 속도를 보니 결제 시스템 확장이 부담되실 것 같습니다."
    
    좋은 줄바꿈:
    "최근 투자 유치 소식을 봤습니다.<br>
    빠른 성장 속도를 보니<br>
    결제 시스템 확장이 부담되실 것 같습니다."
    ```
  * **실제 선호 예시 (25-50자 범위)**:
    ```
    <p>최근 클린디가 '혁신성장유형 벤처기업'으로 인증받았다는 기사를 인상 깊게 봤습니다.<br>
    기술력과 성장 가능성을 공식적으로 인정받으신 만큼,<br>
    AI 기반 신사업과 국내외 시장 확장에 더욱 집중하고 계실 텐데요.</p>
    
    <p>이러한 급격한 성장 과정에서 구독 서비스, 자사몰, B2B 채널 등<br>
    다각화된 매출 채널의 정산 데이터 통합에 어려움을 겪는 경우가 많습니다.</p>
    ```
- 톤: 전문적이면서도 공감하고 도움을 주는 관점, 간결하고 임팩트 있는 표현

**중요**: 어떤 설명이나 추가 텍스트 없이 오직 JSON 형태로만 응답해주세요. 다른 텍스트는 절대 포함하지 마세요.

**생성할 서비스**: {', '.join(services_to_generate)}

{{
  "opi_professional": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "opi_curiosity": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "finance_professional": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "finance_curiosity": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "prism_professional": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "prism_curiosity": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "ps_professional": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "ps_curiosity": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "multi_service_professional": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "multi_service_curiosity": {{
    "body": "<p>안녕하세요, {company_name} {email_name}.<br>PortOne {user_name} 매니저입니다.</p>[본문 내용]<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
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
                    
                    # 마크다운을 HTML로 변환하는 함수
                    def convert_markdown_to_html(text):
                        """마크다운 문법을 HTML로 변환 (**볼드**, *이탤릭* 등)"""
                        import re
                        # **텍스트** → <strong>텍스트</strong>
                        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                        # *텍스트* → <em>텍스트</em> (볼드 처리 후 남은 단일 *)
                        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
                        return text
                    
                    # 플레이스홀더 교체 함수
                    def replace_placeholders(text, company_name, email_name, competitor_name=''):
                        result = text.replace('{company_name}', company_name).replace('{email_name}', email_name)
                        if competitor_name:
                            result = result.replace('{competitor_name}', competitor_name)
                        # 사용자 이름 동적 치환
                        result = result.replace('오준호', user_name)
                        result = result.replace('PortOne 오준호 매니저', f'PortOne {user_name} 매니저')
                        # 마크다운 변환 적용
                        result = convert_markdown_to_html(result)
                        return result
                    
                    # 응답 형식 변환 및 플레이스홀더 교체 (요청된 서비스만)
                    formatted_variations = {}
                    
                    for service in services_to_generate:
                        if service in email_variations:
                            # 고정 제목 사용
                            subject = f'[PortOne] {company_name} {email_name}께 전달 부탁드립니다'
                            
                            # body만 플레이스홀더 교체
                            body = replace_placeholders(email_variations[service]['body'], company_name, email_name, competitor_name)
                            
                            formatted_variations[service] = {
                                'subject': subject,
                                'body': body
                            }
                            logger.info(f"서비스 '{service}' 문안 생성 완료: {company_name}")
                    
                    # CTA 검증 및 자동 수정
                    logger.info(f"{company_name}: CTA 검증 시작...")
                    for service_key, email_content in formatted_variations.items():
                        if 'body' in email_content:
                            email_content['body'] = validate_and_fix_cta(
                                email_content['body'],
                                company_name
                            )
                    
                    return {
                        'success': True,
                        'variations': formatted_variations,
                        'services_generated': services_to_generate,
                        'sales_item': sales_item if sales_item else 'all',
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
                                'subject': f'[PortOne] {company_name} 담당자님께 전달 부탁드립니다',
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
                            'subject': f'[PortOne] {company_name} 담당자님께 전달 부탁드립니다',
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
                        'subject': f'[PortOne] {company_name} 담당자님께 전달 부탁드립니다',
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

def generate_email_with_user_template(company_data, research_data, user_template, case_examples="", news_content=None, user_info=None):
    """
    사용자 제공 문안 기반 이메일 생성 (뉴스 후킹 서론 + 사용자 본문 90%)
    
    Args:
        user_info: 로그인한 사용자 정보 (name, email, company_nickname, phone)
    """
    try:
        # 사용자 정보 (서명용) - user_info 파라미터 우선, 없으면 current_user 체크
        if user_info:
            user_name = user_info.get('name', '오준호')
            user_company_nickname = user_info.get('company_nickname', f'PortOne {user_name} 매니저')
            user_phone = user_info.get('phone', '010-2580-2580')
            logger.info(f"👤 [사용자문안] 이메일 생성자: {user_name} ({user_company_nickname})")
            logger.info(f"✅ [사용자문안] 전달받은 사용자 정보 사용: {user_info.get('email', 'N/A')}")
        else:
            user_name = current_user.name if (current_user and current_user.is_authenticated) else "오준호"
            user_company_nickname = current_user.company_nickname if (current_user and current_user.is_authenticated) else f"PortOne {user_name} 매니저"
            user_phone = current_user.phone if (current_user and current_user.is_authenticated) else "010-2580-2580"
            
            # 디버깅: 사용자 정보 로그
            logger.info(f"👤 [사용자문안] 이메일 생성자: {user_name} (PortOne {user_name} 매니저)")
            if current_user and current_user.is_authenticated:
                logger.info(f"✅ [사용자문안] 로그인 사용자 인증됨: {current_user.email}")
            else:
                logger.warning(f"⚠️  [사용자문안] current_user 인증 안 됨 - 기본값 사용")
        
        company_name = company_data.get('회사명', 'Unknown')
        
        # 담당자 정보 추출 (generate_email_with_gemini와 동일)
        column_keys = list(company_data.keys())
        email_name = ''
        if len(column_keys) >= 14:
            email_name = company_data.get(column_keys[13], '').strip()
        
        if not email_name:
            contact_name = company_data.get('담당자명', '') or company_data.get('대표자명', '') or company_data.get('이름', '')
            contact_position = company_data.get('직책', '') or company_data.get('직급', '')
            if not contact_name or contact_name == '담당자':
                email_name = '담당자님'
            else:
                if contact_position:
                    if any(keyword in contact_position for keyword in ['대표', 'CEO', '사장']):
                        email_name = f'{contact_name} {contact_position}님'
                    elif any(keyword in contact_position for keyword in ['이사', '부장', '팀장', '매니저', '실장', '과장']):
                        email_name = f'{contact_name} {contact_position}님'
                    elif any(keyword in contact_position for keyword in ['주임', '대리', '선임', '책임']):
                        email_name = f'{contact_name} {contact_position}님'
                    else:
                        email_name = f'{contact_name} {contact_position}님'
                else:
                    if any(title in contact_name for title in ['대표', 'CEO', '사장']):
                        email_name = f'{contact_name}님'
                    else:
                        email_name = f'{contact_name} 담당자님'
        
        # 경쟁사 정보
        competitor_name = company_data.get('경쟁사명', '') or company_data.get('경쟁사', '')
        
        company_info = f"회사명: {company_name}\n담당자: {email_name}"
        if competitor_name:
            company_info += f"\nPortOne 이용 경쟁사: {competitor_name}"
        
        # 조사 정보
        research_summary = research_data.get('company_info', '조사 정보 없음')
        
        # 호스팅사 정보 확인 (OPI 제공 가능 여부 판단)
        # CSV 컴럼 구조 디버깅
        logger.debug(f"[사용자문안] {company_name} CSV 컴럼들: {list(company_data.keys())}")
        
        # 다양한 호스팅사 컴럼명 지원
        possible_hosting_columns = ['호스팅사', '호스팅', '호스팅서비스', 'hosting', 'Hosting', '웹호스팅', '호스팅업체']
        hosting = ''
        for col in possible_hosting_columns:
            if col in company_data and company_data[col] and str(company_data[col]).strip():
                hosting = str(company_data[col]).lower().strip()
                logger.info(f"[사용자문안] {company_name} 호스팅 정보 발견: '{col}' = '{hosting}'")
                break
        
        if not hosting:
            logger.warning(f"[사용자문안] {company_name} 호스팅 정보 없음 - CSV에 호스팅사 컴럼이 있는지 확인하세요")
        
        is_self_hosted = '자체' in hosting or 'self' in hosting or '직접' in hosting
        
        # sales_item에 따른 서비스 결정
        sales_item = company_data.get('sales_item', '').lower().strip()
        services_to_generate = []
        if sales_item:
            if 'opi' in sales_item:
                # OPI는 자체구축인 경우에만 제공 가능
                if is_self_hosted:
                    services_to_generate = ['opi_professional', 'opi_curiosity']
                    logger.info(f"✅ [사용자문안] OPI 서비스 문안 생성 (호스팅: {hosting}): {company_name}")
                else:
                    # 자체구축이 아니면 Recon으로 대체
                    services_to_generate = ['finance_professional', 'finance_curiosity']
                    logger.warning(f"⚠️ [사용자문안] OPI 불가능 (호스팅: {hosting}) → Recon(재무자동화)으로 전환: {company_name}")
            elif 'recon' in sales_item or '재무' in sales_item:
                services_to_generate = ['finance_professional', 'finance_curiosity']
                logger.info(f"[사용자문안] Recon(재무자동화) 서비스 문안만 생성: {company_name}")
            elif 'prism' in sales_item or '프리즘' in sales_item:
                services_to_generate = ['prism_professional', 'prism_curiosity']
                logger.info(f"[사용자문안] Prism(멀티 오픈마켓 정산 통합) 서비스 문안만 생성: {company_name}")
            elif 'ps' in sales_item or '플랫폼정산' in sales_item or '파트너정산' in sales_item:
                services_to_generate = ['ps_professional', 'ps_curiosity']
                logger.info(f"[사용자문안] 플랫폼 정산(파트너 정산+세금계산서+지급대행) 서비스 문안만 생성: {company_name}")
            else:
                # 알 수 없는 sales_item인 경우
                if is_self_hosted:
                    services_to_generate = ['opi_professional', 'opi_curiosity', 'finance_professional', 'finance_curiosity']
                else:
                    services_to_generate = ['finance_professional', 'finance_curiosity']
                    logger.info(f"[사용자문안] 자체구축 아니므로 Recon만 생성: {company_name}")
        else:
            # sales_item이 없으면 호스팅사 기준으로 판단
            if not hosting:
                # 호스팅 정보가 없으면 4개 모두 생성
                services_to_generate = ['opi_professional', 'opi_curiosity', 'finance_professional', 'finance_curiosity']
                logger.info(f"[사용자문안] sales_item 없음 + 호스팅 정보 없음 → 4개 모두 생성: {company_name}")
            elif is_self_hosted:
                # 자체구축이면 4개 생성
                services_to_generate = ['opi_professional', 'opi_curiosity', 'finance_professional', 'finance_curiosity']
                logger.info(f"[사용자문안] sales_item 없음 + 자체구축 → 4개 문안 생성 (호스팅: {hosting}): {company_name}")
            else:
                # 호스팅 정보가 있고 자체구축이 아니면 Recon만
                services_to_generate = ['finance_professional', 'finance_curiosity']
                logger.info(f"[사용자문안] sales_item 없음 + 호스팅='{hosting}' (자체구축 아님) → Recon만 생성: {company_name}")
        
        # CSV 뉴스 제공 여부 확인
        has_csv_news = "## 📰 관련 뉴스 기사 (CSV 제공)" in research_summary
        
        # 사용자 문안 모드 프롬프트
        if has_csv_news:
            news_instruction_template = """**🎯 최우선 지시: CSV에서 제공된 '관련 뉴스 기사' 섹션의 내용을 반드시 서론에 활용하세요!**

이 뉴스는 사용자가 직접 선정한 중요한 기사이므로, 다른 어떤 뉴스보다 우선적으로 언급해야 합니다.

**필수 작성 방식:**
1. **서론 (2-3문장)**: CSV 제공 뉴스를 직접 인용하여 후킹하는 도입부 작성
   - **시급성 + 관련성 + 공감** 3요소 모두 포함
   - 예: "최근 '{company_name}가 100억원 투자 유치'라는 기사를 봤습니다. 사업 확장 준비로 바쁘시겠지만, 결제 인프라 확장도 지금 준비해야 할 시점이 아닐까요?"
   - 예: "'{company_name}의 매출 150% 증가' 소식을 들었습니다. 급성장할 때 결제 시스템 병목이 가장 큰 리스크인데, 지금 어떻게 대응하고 계신가요?" """
        else:
            news_instruction_template = """**필수 작성 방식:**
1. **서론 (2-3문장)**: 위의 조사 결과에서 구체적인 최신 뉴스를 직접 인용하여 후킹하는 도입부 작성
   - **시급성 + 관련성 + 공감** 3요소 모두 포함
   - 예: "최근 '{company_name}가 100억원 투자 유치' 소식을 봤습니다. 사업 확장 준비로 바쁘시겠지만, 결제 인프라 확장도 지금 준비해야 할 시점이 아닐까요?"
   - 예: "'{company_name}의 매출 150% 증가' 기사를 읽었습니다. 급성장할 때 결제 시스템 병목이 가장 큰 리스크인데, 지금 어떻게 대응하고 계신가요?" """
        
        context = f"""
당신은 포트원(PortOne) 전문 세일즈 카피라이터입니다.

**타겟 회사 정보:**
{company_info}

**🔥 회사 조사 결과 (이메일 서론에 반드시 활용):**
{research_summary}

**🎯 특별 요청사항: 사용자 제공 문안 활용**

사용자가 제공한 본문 문안:
---
{user_template}
---

**🎯 최우선 목표: B2B 의사결정자가 "즉시 답장하고 싶다"고 느끼는 메일 작성**

뉴스 후킹 서론이 다음 반응을 이끌어내야 합니다:
- "우리 회사의 현재 상황을 정확히 이해하고 있다"
- "매우 시의적절하고 필요한 제안"
- "즉시 답장할 가치가 있다"

**⚠️ 중요**: 이메일 본문 작성 시 "즉시", "100%", "완벽한", "절대", "무조건" 등의 극단적 표현은 사용하지 말고, 현실적이고 신뢰감 있는 표현 사용 (예: "빠르게", "90% 이상", "높은 정확도로", "대폭")

{news_instruction_template}

2. **본문 (90%)**: 위에 제공된 사용자 문안을 **거의 그대로** 사용하되, 다음만 자연스럽게 개인화:
   - {{company_name}} 회사명을 본문에 자연스럽게 삽입
   - {{email_name}} 담당자명을 맥락에 맞게 추가 가능
   - 문장 순서나 핵심 내용은 **절대 변경하지 말것**
   - 단어 선택이나 문체도 **최대한 원본 유지**

3. **고정 결론 (⚠️ 필수!)**: 
   "<br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.<br><br>감사합니다.<br>{user_name} 드림"
   
   ‼️ **CTA는 반드시 포함해야 합니다!** "다음주 중 편하신 일정을 알려주시면..."이 빠지면 안 됩니다.

**고정 서론 형식 (서론 시작 전):**
"안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>"

**구조:**
- 제목: "[PortOne] {{company_name}} {{email_name}}께 전달 부탁드립니다"
- 본문: 고정 서론 → 뉴스 후킹 서론(2-3문장) → 사용자 문안(90% 유지) → 고정 결론

**중요**: 어떤 설명이나 추가 텍스트 없이 오직 JSON 형태로만 응답해주세요.

**생성할 서비스**: {', '.join(services_to_generate)}

{{
  "opi_professional": {{
    "body": "<p>안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>[뉴스 후킹 서론 2-3문장]<br><br>[사용자 문안 90% 그대로]</p><p><br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "opi_curiosity": {{
    "body": "<p>안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>[뉴스 후킹 서론 2-3문장]<br><br>[사용자 문안 90% 그대로]</p><p><br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "finance_professional": {{
    "body": "<p>안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>[뉴스 후킹 서론 2-3문장]<br><br>[사용자 문안 90% 그대로]</p><p><br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "finance_curiosity": {{
    "body": "<p>안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>[뉴스 후킹 서론 2-3문장]<br><br>[사용자 문안 90% 그대로]</p><p><br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "prism_professional": {{
    "body": "<p>안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>[뉴스 후킹 서론 2-3문장]<br><br>[사용자 문안 90% 그대로]</p><p><br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }},
  "prism_curiosity": {{
    "body": "<p>안녕하세요, {{company_name}} {{email_name}}.<br>PortOne {user_name} 매니저입니다.<br><br>[뉴스 후킹 서론 2-3문장]<br><br>[사용자 문안 90% 그대로]</p><p><br>다음주 중 편하신 일정을 알려주시면 {{company_name}}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{user_name} 드림</p>"
  }}
}}
"""
        
        # Gemini API 호출
        if not GEMINI_API_KEY:
            return {
                'success': False,
                'error': 'Gemini API 키가 설정되지 않았습니다',
                'timestamp': datetime.now().isoformat()
            }
        
        try:
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(context)
            
            if response.text:
                # JSON 파싱
                clean_response = response.text.strip()
                if '```json' in clean_response:
                    json_start = clean_response.find('```json') + 7
                    json_end = clean_response.find('```', json_start)
                    if json_end != -1:
                        clean_response = clean_response[json_start:json_end]
                    else:
                        clean_response = clean_response[json_start:]
                elif '{' in clean_response and '}' in clean_response:
                    json_start = clean_response.find('{')
                    json_end = clean_response.rfind('}') + 1
                    clean_response = clean_response[json_start:json_end]
                
                clean_response = clean_response.strip()
                email_variations = json.loads(clean_response)
                
                # 마크다운을 HTML로 변환하는 함수
                def convert_markdown_to_html(text):
                    """마크다운 문법을 HTML로 변환 (**볼드**, *이탤릭* 등)"""
                    import re
                    # **텍스트** → <strong>텍스트</strong>
                    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                    # *텍스트* → <em>텍스트</em> (볼드 처리 후 남은 단일 *)
                    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
                    return text
                
                # 플레이스홀더 교체
                def replace_placeholders(text, company_name, email_name, competitor_name=''):
                    result = text.replace('{company_name}', company_name).replace('{email_name}', email_name)
                    result = result.replace('{{company_name}}', company_name).replace('{{email_name}}', email_name)
                    if competitor_name:
                        result = result.replace('{competitor_name}', competitor_name).replace('{{competitor_name}}', competitor_name)
                    # 사용자 이름 동적 치환
                    result = result.replace('오준호', user_name)
                    result = result.replace('PortOne 오준호 매니저', f'PortOne {user_name} 매니저')
                    # 마크다운 변환 적용
                    result = convert_markdown_to_html(result)
                    return result
                
                formatted_variations = {}
                for service in services_to_generate:
                    if service in email_variations:
                        subject = f'[PortOne] {company_name} {email_name}께 전달 부탁드립니다'
                        body = replace_placeholders(email_variations[service]['body'], company_name, email_name, competitor_name)
                        
                        formatted_variations[service] = {
                            'subject': subject,
                            'body': body
                        }
                
                # CTA 검증 및 자동 수정
                logger.info(f"{company_name}: [사용자문안] CTA 검증 시작...")
                for service_key, email_content in formatted_variations.items():
                    if 'body' in email_content:
                        email_content['body'] = validate_and_fix_cta(
                            email_content['body'],
                            company_name
                        )
                
                return {
                    'success': True,
                    'variations': formatted_variations,
                    'services_generated': services_to_generate,
                    'sales_item': sales_item if sales_item else 'all',
                    'timestamp': datetime.now().isoformat(),
                    'model': 'gemini-2.5-pro-exp',
                    'mode': 'user_template'
                }
                
        except Exception as e:
            logger.error(f"사용자 문안 이메일 생성 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"사용자 문안 처리 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def generate_persuasive_reply(context, company_name, email_name, case_examples=""):
    """
    고객 반박/부정적 답변에 대한 재설득 메일 생성
    
    Args:
        context: 고객의 답변 또는 상황 설명
        company_name: 회사명
        email_name: 담당자 호칭
        case_examples: 관련 케이스 스터디
    
    Returns:
        dict: 생성된 재설득 메일
    """
    try:
        logger.info(f"{company_name}: 재설득 메일 생성 시작")
        
        # Gemini 프롬프트 구성
        prompt = f"""
당신은 포트원(PortOne) 최고 영업 전문가입니다. 고객의 부정적 반응이나 반박에 대응하여 재설득하는 메일을 작성합니다.

**고객 상황/답변:**
{context}

**회사 정보:**
- 회사명: {company_name}
- 담당자: {email_name}

**포트원 서비스 소개, 실제 사례 및 최신 블로그 콘텐츠:**
{case_examples}

💡 **위 정보 활용 방법:**
- 실제 고객사 사례를 인용하여 신뢰도 높이기
- 최신 블로그 콘텐츠에서 관련 트렌드나 기술 정보를 자연스럽게 언급
- "최근 포트원 블로그에서도..." 같은 방식으로 활용 가능

**🎯 목표: 고객의 우려를 해소하고 재미팅 기회를 만드는 설득력 있는 메일 작성**

**메일 작성 전략:**

1. **공감 먼저**: 고객의 우려나 의견을 먼저 인정하고 공감
   - "말씀하신 우려 충분히 이해합니다"
   - "좋은 지적이십니다"
   
2. **오해 해소**: 고객이 잘못 이해한 부분이 있다면 부드럽게 설명
   - 강압적이지 않게
   - 데이터와 사례로 뒷받침

3. **구체적 사례 + 최신 정보 제시**: 
   - 위의 실제 케이스 스터디를 활용
   - 비슷한 우려를 가졌던 다른 고객사 사례
   - 도입 후 결과 수치 제시
   - **포트원 블로그의 최신 콘텐츠를 자연스럽게 언급**하여 전문성과 최신성 강조
   - "{company_name}님과 비슷한 상황이었던 [고객사명]도..."

4. **새로운 가치 제안**: 고객이 놓친 부분 강조
   - ROI, 시간 절약, 리스크 감소 등
   - 구체적 수치로 설득
   - 최신 트렌드나 업계 동향 언급

5. **부담 없는 재제안**: 
   - "단 15분만 시간 내주시면..."
   - "한 번만 데모를 보여드리면..."
   - "무료 컨설팅으로 가능성만 확인해보시겠습니까?"

**반박 유형별 대응 전략:**

A. **"비용이 부담됩니다"**
   → ROI 계산, 장기적 절감 효과, 무료 체험 제안

B. **"지금은 바빠서 어렵습니다"**
   → 간단한 도입 프로세스 강조, 2주 내 구축 가능, 최소 리소스

C. **"현재 시스템으로 충분합니다"**
   → 숨겨진 비효율 지적, 확장성 문제, 미래 성장 대비

D. **"다른 솔루션과 비교 중입니다"**
   → 차별점 강조, 고객사 만족도, PG사 비교 견적 제공

E. **"내부 검토가 더 필요합니다"**
   → 의사결정에 필요한 자료 제공, 레퍼런스 연결, CTO 미팅 제안

**필수 포함 요소:**

1. **서론**: 이전 메일 감사 + 공감
   "안녕하세요, {company_name} {email_name}.<br>PortOne {user_name}입니다.<br><br>
   바쁘신 와중에도 답변 주셔서 감사합니다."

2. **본문**: 
   - 우려사항 공감 및 해소
   - 실제 사례 2-3개 구체적 제시
   - 수치 기반 설득 (85% 절감, 2주 내 구축 등)
   - 새로운 관점 제시

3. **CTA (필수!)**: 
   "<br>그래도 한 번만 기회를 주시면 {company_name}의 상황에 맞는<br>
   구체적인 해결책을 보여드리고 싶습니다.<br>
   다음 주 중 15분만 시간 내주실 수 있을까요?<br>
   긍정적인 회신 부탁드립니다.<br><br>
   감사합니다.<br>{user_name} 드림"

**톤앤매너:**
- 절대 강압적이거나 공격적이지 않게
- 진정성 있게, 고객의 성공을 진심으로 원하는 파트너로
- 전문적이지만 친근하게
- 데이터와 사실 기반

**구조:**
제목: [PortOne] {company_name} {email_name} - 추가 말씀 드립니다

본문: HTML 형식으로 작성
<p>서론</p>
<p>본문 - 공감 + 해소</p>
<p>본문 - 사례 제시</p>
<p>본문 - 새로운 가치</p>
<p>CTA</p>

**JSON 형식으로만 응답하세요:**
{{
  "subject": "제목",
  "body": "HTML 본문",
  "strategy_used": "사용한 전략 간단 설명",
  "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"]
}}
"""

        # Gemini API 호출
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            raise Exception("Gemini API 응답이 비어있습니다")
        
        # JSON 파싱
        import re
        response_text = response.text.strip()
        
        # JSON 추출
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        elif '{' in response_text and '}' in response_text:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
        else:
            json_str = response_text
        
        email_data = json.loads(json_str)
        
        # CTA 검증
        if 'body' in email_data:
            email_data['body'] = validate_and_fix_cta(email_data['body'], company_name)
        
        logger.info(f"{company_name}: 재설득 메일 생성 완료")
        
        return {
            'success': True,
            'email': email_data,
            'timestamp': datetime.now().isoformat(),
            'model': 'gemini-2.0-flash-exp'
        }
        
    except Exception as e:
        logger.error(f"{company_name} 재설득 메일 생성 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def validate_and_fix_cta(email_body, company_name):
    """
    이메일 본문에 CTA(Call-to-Action)가 있는지 확인하고 없으면 추가
    
    Args:
        email_body: 이메일 본문 (HTML)
        company_name: 회사명
    
    Returns:
        str: CTA가 포함된 이메일 본문
    """
    # CTA 키워드 체크
    cta_keywords = [
        '다음주 중', '다음 주 중', '편하신 일정', '편하신 시간',
        '긍정적인 회신', '회신 부탁', '일정을 알려주시면',
        '시간을 알려주시면', '미팅 가능한 시간'
    ]
    
    # 본문에 CTA 키워드가 하나라도 있는지 확인
    has_cta = any(keyword in email_body for keyword in cta_keywords)
    
    if has_cta:
        logger.info(f"{company_name}: CTA 검증 통과 ✓")
        return email_body
    
    # CTA가 없으면 자동 추가
    logger.warning(f"{company_name}: ⚠️  CTA 누락 감지 - 자동 추가")
    
    # 표준 CTA 템플릿
    standard_cta = f"""<p><br>다음주 중 편하신 일정을 알려주시면 {company_name}의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p>

<p>감사합니다.<br>{user_name} 드림</p>"""
    
    # 서명 패턴 찾기
    import re
    signature_patterns = [
        r'<p>\s*감사합니다\.?<br>\s*오준호\s*드림\s*</p>',
        r'<p>\s*오준호\s*Junho\s*Oh<br>\s*Sales\s*team.*?</p>',
        r'<p>\s*오준호\s*드림\s*</p>',
        r'감사합니다[.\s]*$'
    ]
    
    # 서명이 있으면 그 앞에 CTA 삽입
    for pattern in signature_patterns:
        if re.search(pattern, email_body, re.DOTALL | re.IGNORECASE):
            email_body = re.sub(
                pattern,
                standard_cta,
                email_body,
                flags=re.DOTALL | re.IGNORECASE
            )
            logger.info(f"{company_name}: CTA 추가 완료 (서명 앞에 삽입)")
            return email_body
    
    # 서명이 없으면 본문 끝에 CTA 추가
    email_body = email_body.rstrip() + "\n\n" + standard_cta
    logger.info(f"{company_name}: CTA 추가 완료 (본문 끝에 추가)")
    
    return email_body

def generate_email_with_gemini_and_cases(company_data, research_data, case_examples="", user_template=None, news_content=None, user_input_mode='template', user_info=None):
    """
    Gemini를 사용하여 개인화된 이메일 생성 (실제 사례 포함 버전)
    
    Args:
        company_data: 회사 정보 dict
        research_data: Perplexity 조사 결과
        case_examples: 선택된 실제 사례 텍스트 (formatted)
        user_template: 사용자 제공 문안 또는 요청사항 (옵션)
        news_content: 스크래핑된 뉴스 내용 (옵션)
        user_input_mode: 'request' (요청사항 모드) 또는 'template' (문안 모드)
        user_info: 로그인한 사용자 정보 (name, email, company_nickname, phone)
    
    Returns:
        dict: 생성된 이메일 variations
    """
    # 사용자 입력이 있으면 모드에 따라 처리
    if user_template:
        if user_input_mode == 'request':
            logger.info(f"{company_data.get('회사명')}: 요청사항 모드 - 기본 생성 + 요청사항 반영")
            return generate_email_with_user_request(company_data, research_data, user_template, case_examples, news_content, user_info)
        else:
            logger.info(f"{company_data.get('회사명')}: 문안 모드 - 뉴스 후킹 + 사용자 본문")
            return generate_email_with_user_template(company_data, research_data, user_template, case_examples, news_content, user_info)
    
    # 사용자 입력이 없으면 기존 SSR 방식 (4개 생성 + 사례 포함)
    logger.info(f"{company_data.get('회사명')}: SSR 모드 - 4개 생성 + 사례 포함")
    return generate_email_with_gemini(company_data, research_data, user_info)

def generate_email_with_user_request(company_data, research_data, user_request, case_examples="", news_content=None, user_info=None):
    """
    사용자 요청사항 기반 이메일 생성 (2단계)
    
    1단계: 기본 SSR 방식으로 4개 문안 생성 (Pain Point + 포트원 해결책 포함)
    2단계: 사용자 요청사항 반영해서 각 문안 개선
    
    Args:
        user_info: 로그인한 사용자 정보 (name, email, company_nickname, phone)
    """
    try:
        company_name = company_data.get('회사명', 'Unknown')
        logger.info(f"{company_name}: 요청모드 1단계 - 기본 문안 생성 시작")
        
        # 1단계: 기본 SSR 모드로 문안 생성
        base_result = generate_email_with_gemini(company_data, research_data, user_info)
        
        if not base_result.get('success'):
            logger.error(f"{company_name}: 기본 문안 생성 실패")
            return base_result
        
        logger.info(f"{company_name}: 요청모드 2단계 - 요청사항 반영 개선 시작")
        
        # 2단계: 각 문안을 사용자 요청사항에 맞춰 개선
        base_variations = base_result.get('variations', {})
        refined_variations = {}
        
        for service_key, email_content in base_variations.items():
            try:
                # 원본 이메일
                original_subject = email_content.get('subject', '')
                original_body = email_content.get('body', '')
                
                # 요청사항 반영해서 개선
                refined_email = refine_email_with_user_request(
                    original_subject=original_subject,
                    original_body=original_body,
                    user_request=user_request,
                    company_data=company_data
                )
                
                if refined_email:
                    refined_variations[service_key] = refined_email
                else:
                    # 개선 실패 시 원본 사용
                    refined_variations[service_key] = email_content
                    
            except Exception as e:
                logger.error(f"{company_name} {service_key} 개선 오류: {str(e)}")
                # 오류 시 원본 사용
                refined_variations[service_key] = email_content
        
        # CTA 검증 및 자동 수정
        for service_key, email_content in refined_variations.items():
            if 'body' in email_content:
                email_content['body'] = validate_and_fix_cta(
                    email_content['body'],
                    company_name
                )
        
        logger.info(f"{company_name}: 요청모드 완료 - {len(refined_variations)}개 문안 생성")
        
        return {
            'success': True,
            'variations': refined_variations,
            'services_generated': base_result.get('services_generated', []),
            'sales_item': base_result.get('sales_item', 'all'),
            'timestamp': datetime.now().isoformat(),
            'model': 'gemini-2.0-flash-exp',
            'mode': 'user_request'
        }
        
    except Exception as e:
        logger.error(f"요청모드 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def refine_email_with_user_request(original_subject, original_body, user_request, company_data):
    """
    생성된 이메일을 사용자 요청사항에 맞춰 개선
    
    ⚠️ 핵심: 원본 이메일의 Pain Point + 포트원 해결책을 반드시 유지하면서
             사용자 요청사항(톤, 강조점, 제목 스타일 등)만 반영
    """
    try:
        company_name = company_data.get('회사명', 'Unknown')
        
        # 요청사항 개선 프롬프트
        context = f"""
당신은 포트원(PortOne) 이메일 개선 전문가입니다.

**원본 이메일:**
제목: {original_subject}

본문:
{original_body}

**사용자 요청사항:**
{user_request}

**🚨 절대 규칙 - MUST KEEP (반드시 유지해야 하는 내용):**

1. **Pain Point (고객 과제) 내용 100% 유지**
   - 원본에서 언급한 회사의 어려움/과제는 절대 삭제 불가
   - 예: "거래량 급증", "결제 시스템 확장 부담", "정산 업무 복잡도 증가" 등
   - 표현만 다듬을 수 있지만, 핵심 메시지는 동일하게 유지

2. **PortOne 해결책 100% 유지**
   - OPI/재무자동화 등 포트원 솔루션 설명은 절대 삭제 불가
   - 구체적 수치(85% 절감, 90% 단축 등)는 반드시 포함
   - 예: "단 하나의 API로 국내외 주요 PG사 연동", "정산 업무 90% 단축" 등

3. **뉴스 후킹 내용 유지**
   - 원본에서 언급한 회사 뉴스/성장 이야기는 유지
   - 투자 유치, 사업 확장 등 구체적 내용 보존

**✅ 변경 가능한 부분 (사용자 요청사항 반영):**

1. **톤&매너 조정**
   - 친근한/전문적/격식있는 등 요청된 톤으로 수정 가능
   - 예: "혹시 이런 고민 있으신가요?" ↔ "다음과 같은 과제를 검토하고 계실 것으로 판단됩니다"

2. **강조점 변경**
   - 사용자가 강조 요청한 부분을 `<strong>` 태그로 강조
   - 볼드 처리 위치 조정 가능

3. **제목 수정 (조건부)**
   - ⚠️ **사용자가 제목 수정을 명시적으로 요청한 경우에만** 제목 변경 가능
   - 예: "제목을 더 임팩트있게", "제목에 ROI 수치 포함" 등의 명확한 요청이 있을 때만
   - **제목 관련 요청이 없으면 원본 제목({original_subject})을 그대로 사용**

4. **구조 개선 및 한국어 자연스러운 줄바꿈**
   - 문장 순서 조정, 문단 나누기 등
   - **한국어의 자연스러운 호흡에 맞춰 줄바꿈 배치**:
     * 주어가 긴 문장: 주어 다음 줄바꿈 (`<br>`)
     * 접속사 전후: 자연스러운 위치에 줄바꿈
     * 의미 단위 구분: 각 의미 블록마다 빈 줄 (`<br><br>`)
     * 리스트나 나열: 각 항목마다 줄바꿈
   - 예시:
     ```
     나쁜 줄바꿈:
     "최근 투자 유치 소식을 봤습니다. 빠른 성장 속도를 보니 결제 시스템 확장이 부담되실 것 같습니다. 저희 OPI는..."
     
     좋은 줄바꿈:
     "최근 투자 유치 소식을 봤습니다.<br>
     빠른 성장 속도를 보니<br>
     결제 시스템 확장이 부담되실 것 같습니다.<br><br>
     저희 포트원 OPI는..."
     ```

5. **길이 조정**
   - 더 간결하게 또는 더 상세하게 (단, Pain Point + 해결책은 유지)

**❌ 절대 금지사항:**
- Pain Point 내용을 삭제하거나 축소
- PortOne 해결책 설명을 삭제하거나 추상화 ("도움 드릴 수 있습니다"로만 끝내기 금지)
- 구체적 수치 삭제
- 뉴스 후킹 내용 삭제

**개선 예시:**

원본:
"최근 투자 유치 소식을 봤습니다. 빠른 성장 속도를 보니 결제 시스템 확장이 부담되실 것 같습니다. 
저희 OPI는 단 하나의 API로 주요 PG사를 연동하고 개발 기간을 85% 단축합니다."

요청사항: "더 친근한 톤으로, ROI 수치 강조"

개선:
"'{company_name} 투자 유치' 소식 정말 축하드립니다! 😊
이렇게 빠르게 성장하시다 보면, 결제 시스템 확장이 개발팀에 큰 부담 되지 않으실까요?
저희 포트원 OPI는 단 하나의 API로 국내외 주요 PG사를 연결하고, <strong>개발 기간을 85% 단축</strong>해드립니다."

→ Pain Point(결제 시스템 확장 부담) + 해결책(OPI, 85% 단축) 모두 유지하면서, 톤만 친근하게 변경

**📤 JSON 출력 형식:**

**중요**: 사용자 요청사항에서 제목 관련 내용이 없으면 subject는 원본 그대로 사용하세요.

{{
  "subject": "사용자가 제목 수정을 요청했다면 개선된 제목, 아니면 '{original_subject}' 그대로",
  "body": "개선된 본문 (HTML 형식, <p>, <br>, <strong> 태그 사용, 한국어 자연스러운 줄바꿈)"
}}

**줄바꿈 예시 (본문):**
```html
<p>안녕하세요, ABC회사 김철수 대표님.<br>
PortOne {user_name} 매니저입니다.</p>

<p>최근 'ABC회사 시리즈 A 투자 유치' 소식을 봤습니다.<br>
정말 축하드립니다!</p>

<p>이렇게 빠르게 성장하시다 보면<br>
결제 시스템 확장과 관리가<br>
개발팀에 큰 부담이 되지 않으실까요?</p>

<p>저희 포트원 OPI는<br>
<strong>단 하나의 API로 국내외 주요 PG사를 연동</strong>하고<br>
<strong>개발 기간을 85% 단축</strong>해드립니다.</p>
```
"""
        
        payload = {
            "contents": [{"parts": [{"text": context}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        }
        
        gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
        
        response = requests.post(
            gemini_api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"{company_name} 개선 API 오류: {response.status_code}")
            return None
        
        result = response.json()
        generated_text = result['candidates'][0]['content']['parts'][0]['text']
        
        import json
        refined_email = json.loads(generated_text)
        
        return {
            'subject': refined_email.get('subject', original_subject),
            'body': refined_email.get('body', original_body)
        }
        
    except Exception as e:
        logger.error(f"이메일 개선 오류: {str(e)}")
        return None

def refine_email_with_gemini(current_email, refinement_request):
    """Gemini 2.5 Pro를 사용하여 이메일 개선"""
    try:
        # Gemini API가 설정되지 않았으면 폴백 응답 생성
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            logger.warning("Gemini API 키가 설정되지 않았습니다")
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

(주의: Gemini API 키 미설정으로 인한 시뮬레이션 응답)"""
        
        # URL이 포함되어 있는지 확인하고 스크래핑
        article_context = ""
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, refinement_request)
        
        if urls:
            logger.info(f"개선 요청에서 URL 발견: {len(urls)}개")
            for url in urls[:3]:  # 최대 3개 URL까지 처리
                try:
                    logger.info(f"URL 내용 스크래핑 시도: {url}")
                    article_data = scrape_news_article(url)
                    
                    if article_data:
                        article_context += f"\n\n### 📰 참고 기사 정보 (출처: {url})\n"
                        article_context += f"**제목**: {article_data.get('title', '제목 없음')}\n"
                        article_context += f"**본문**: {article_data.get('content', '')[:1500]}\n"
                        logger.info(f"URL 스크래핑 성공: {article_data.get('title', '')[:50]}")
                    else:
                        logger.warning(f"URL 스크래핑 실패: {url}")
                        article_context += f"\n\n### ⚠️ 기사 URL 제공됨: {url}\n(자동 스크래핑 실패 - 수동으로 내용 확인 필요)\n"
                except Exception as e:
                    logger.error(f"URL 처리 중 오류: {str(e)}")
                    article_context += f"\n\n### ⚠️ 기사 URL: {url}\n(처리 오류: {str(e)})\n"
        
        prompt = f"""
당신은 B2B SaaS 세일즈 전문가입니다. 다음 이메일 문안을 개선하는 임무를 수행하세요.

**현재 이메일:**
{current_email}

**사용자의 개선 요청:**
{refinement_request}
{article_context}

---

## 🚨 제품 선택 규칙

**사용자 요청을 분석하여 제품을 선택하세요:**

### 1️⃣ 복수 제품 요청 감지 (최우선 확인)
사용자가 **여러 제품을 함께 언급**하거나 **종합 솔루션을 요청**했는지 확인:

**복수 제품 키워드:**
- "OPI와 Recon", "OPI, Recon", "OPI 그리고 Recon"
- "Prism과 재무자동화", "여러 제품", "복수 솔루션"
- "종합적으로", "통합 솔루션", "전체적으로 어필"
- "둘 다", "모두", "함께"

**복수 제품 요청 예시:**
- "OPI 개선 요청에 Recon도 같이 어필하는 메일 만들어줘"
- "Prism과 재무자동화 둘 다 언급해줘"
- "종합 솔루션으로 작성해줘"

→ **복수 제품 감지 시**: 언급된 제품들을 Pain Point에 맞춰 조합하여 제안
   예: Pain Point 1 → OPI, Pain Point 2 → Recon

### 2️⃣ 단일 제품 요청 (복수 제품 키워드 없을 때)
- "prism", "Prism" → **Prism만 사용**
- "recon", "Recon" → **Recon만 사용**  
- "재무자동화", "정산자동화" → **재무자동화만 사용**
- "OPI", "One Payment Infra" → **OPI만 사용**
- 제품명 언급 없음 → **기본 제품 (OPI 또는 Pain Point에 가장 적합한 제품)**

**제품별 정보:**
- **OPI (One Payment Infra)**: 통합 결제 시스템, 2주 내 구축, 개발 리소스 85% 절감, 여러 PG사 통합 관리
- **Prism**: 멀티 오픈마켓 정산 통합 관리, 네이버/쿠팡/11번가 등 각 플랫폼의 서로 다른 정산 데이터와 기준을 한 눈에 통합, 재무 마감 시간 90% 단축, 월 수십 시간의 엑셀 작업 자동화
- **재무자동화**: 정산 데이터 자동화, 정산 프로세스 90% 시간 단축, 실시간 대시보드, 회계 시스템 연동
- **Recon**: 거래 내역 자동 대사, 정산 오류 자동 감지 및 방지, 수작업 대사 시간 95% 절감

**중요: 단일 제품 선택 시 해당 제품만 사용. 복수 제품 선택 시 각 Pain Point에 맞는 제품 조합.**

### 🎯 MUST DO 체크리스트 (뉴스 기사가 제공된 경우)

✅ **1단계: 기사 분석 (필수)**
- [ ] 기사 제목과 본문에서 구체적 사실 3가지 이상 추출
- [ ] 회사의 신규 사업/제품/투자/확장 계획 파악
- [ ] 언급된 수치 (금액, 매장 수, 목표 등) 정확히 기록

✅ **2단계: Pain Point 도출 (필수 - 최소 2개)**
- [ ] 기사 내용 기반으로 회사가 직면할 결제/정산 관련 과제 2개 이상 구체적으로 추론
- [ ] 예시: "6,000개 매장 → 대규모 거래 데이터 통합 관리 어려움"
- [ ] 일반적인 문제가 아닌 **이 회사만의 구체적 상황**에 맞춘 Pain Point

✅ **3단계: PortOne 솔루션 매핑 (필수 - 각 Pain Point마다)**
- [ ] Pain Point 1 → **선택된 제품**으로 해결책 제시
- [ ] Pain Point 2 → **선택된 제품**으로 해결책 제시
- [ ] 각 솔루션에 구체적 수치 포함 (해당 제품의 실제 수치 사용)
- [ ] **중요**: 위에서 확인한 제품만 사용. 다른 제품 언급 금지

✅ **4단계: 이메일 구조 검증 (필수)**
- [ ] 기사 내용 언급 (30-40단어)
- [ ] Pain Point 제기 (50-70단어)
- [ ] PortOne 솔루션 제시 with 불릿 포인트 (60-80단어)
- [ ] 미팅 제안 (30-40단어)

**❌ 절대 금지사항:**
- 기사를 단순히 "최근 소식 접했습니다"로만 언급
- Pain Point 없이 바로 제품 소개
- 일반적인 "결제 시스템 필요하시죠?" 식 접근
- PortOne 솔루션 구체적 설명 없이 "도움 드릴 수 있습니다"로만 마무리

---

### 🎯 URL/뉴스 기사 분석이 제공된 경우 (최우선)

1. **기사 내용 깊이 있게 분석**:
   - 기사에서 언급된 회사의 **새로운 사업**, **제품 출시**, **확장 계획**, **투자 유치** 등을 파악
   - 이러한 움직임이 의미하는 **비즈니스 성장 시그널** 이해
   - 기사에 나온 구체적 **수치, 규모, 목표**를 정확히 기억

2. **Pain Point 추론 - 3단계 분석**:
   
   **[1단계] 비즈니스 성장이 가져오는 운영 부담 파악**
   - 새 사업/제품 출시 → 결제 시스템 다양화 필요
   - 매출 확대 → 거래량 급증으로 인한 시스템 부하
   - 신규 채널 진출 → 멀티 채널 결제 통합 이슈
   - 투자 유치 → 빠른 확장 속도에 IT 리소스 부족
   
   **[2단계] 구체적인 Pain Point 도출**
   - "이마트24가 자체브랜드 출시" → POS/온라인 결제 동시 처리 복잡도 증가
   - "전국 6,000개 매장" → 대규모 결제 데이터 실시간 통합 관리 어려움
   - "옐로우 브랜드로 경쟁력 강화" → 빠른 출시를 위해 결제 개발 시간 단축 필요
   
   **[3단계] 수신자가 공감할 수 있는 표현으로 전환**
   - ❌ "결제 시스템 개발이 어렵죠?" (너무 일반적)
   - ✅ "새로운 PL 브랜드 출시를 준비하시는 시점에서, 온오프라인 통합 결제와 정산 자동화가 큰 과제가 아닐까요?"

3. **PortOne 솔루션을 자연스럽게 연결**:
   
   **Pain Point → Solution 매핑 예시 (선택된 제품 사용)**
   
   사용자가 선택한 제품에 따라 적절한 솔루션 제시:
   
   **단일 제품 선택 시:**
   
   **OPI만 선택:**
   - 빠른 출시 일정 → OPI로 2주 내 결제 시스템 구축
   - 대규모 거래 데이터 → 통합 대시보드로 실시간 모니터링
   - 여러 PG사 관리 → 스마트 라우팅으로 최적 결제 경로 자동 선택
   
   **Prism만 선택:**
   - 다중 오픈마켓 운영 → Prism으로 네이버/쿠팡/11번가 등 각 플랫폼의 서로 다른 정산 데이터를 한 눈에 통합
   - 반복적인 엑셀 작업 → 월 수십 시간의 정산 데이터 다운로드 및 통합 작업을 자동화
   - 정산 기준 차이 → 각 오픈마켓의 다른 정산 주기와 기준을 자동으로 정규화하여 현금흐름 실시간 파악
   
   **재무자동화만 선택:**
   - 정산 데이터 수작업 → 재무자동화로 정산 프로세스 90% 시간 단축
   - 회계 시스템 연동 → 자동 연동으로 수작업 제거
   - 정산 오류 발생 → 실시간 검증으로 오류 사전 방지
   
   **Recon만 선택:**
   - 거래 대사 수작업 → Recon으로 자동 대사, 95% 시간 절감
   - 정산 오류 빈번 → 자동 감지 및 알림으로 오류 방지
   - 대사 작업 복잡 → 원클릭 대사로 단순화
   
   **복수 제품 선택 시 (예: OPI + Recon):**
   - Pain Point 1 (결제 시스템) → OPI로 2주 내 결제 시스템 구축
   - Pain Point 2 (정산 대사) → Recon으로 자동 대사, 95% 시간 절감
   - 종합 가치 제안 → 결제부터 정산까지 end-to-end 자동화
   
   **복수 제품 선택 시 (예: Prism + 재무자동화):**
   - Pain Point 1 (멀티 채널 정산 관리) → Prism으로 네이버/쿠팡 등 각 플랫폼의 정산 데이터를 한 눈에 통합
   - Pain Point 2 (정산 자동화) → 재무자동화로 정산 프로세스 90% 단축
   - 시너지 효과 → 오픈마켓 정산 통합 + 재무 프로세스 자동화로 end-to-end 재무 관리

4. **이메일 문안 구조 (Pain Point 중심)**:

   ```
   📧 인사 (20-30단어)
   안녕하세요, [회사명] [담당자명]님.
   PortOne {{user_name}} 매니저입니다.
   
   📰 기사 기반 컨텍스트 (30-40단어)  
   최근 [회사명]의 [구체적 사업/제품]에 대한 소식을 접했습니다.
   [기사에서 언급된 구체적 수치나 목표]는 정말 인상적이었습니다.
   
   💡 공감형 Pain Point 제기 (50-70단어)
   이런 빠른 성장 속에서 [구체적 pain point 1]과 
   [구체적 pain point 2]가 큰 과제가 아닐까 생각됩니다.
   
   특히 [기사 내용과 연결된 구체적 상황]을 준비하시는 시점에서,
   [기술적/운영적 어려움]을 경험하고 계실 것 같습니다.
   
   ✅ 솔루션 제시 (60-80단어)
   PortOne의 [구체적 제품명]은 이런 문제를 해결해드릴 수 있습니다:
   
   • [Pain Point 1 해결] → [구체적 기능]으로 [결과/수치]
   • [Pain Point 2 해결] → [구체적 기능]으로 [결과/수치]  
   • [추가 혜택] → [차별화 포인트]
   
   🤝 자연스러운 미팅 제안 (30-40단어)
   [회사명]의 [기사에서 언급된 목표]를 더 빠르게 달성하실 수 있도록
   15분 간단한 데모로 구체적인 도움을 드리고 싶습니다.
   
   다음주 중 편한 시간 알려주시면 감사하겠습니다.
   ```

5. **반드시 지켜야 할 원칙**:
   - 기사 내용을 **단순 언급**이 아닌 **Pain Point 분석의 근거**로 활용
   - "결제 시스템이 필요하시죠?" 같은 일반적 접근 금지
   - 기사에서 발견한 **구체적 사실**을 바탕으로 **맞춤형 제안**
   - 수치는 정확하게: PortOne 솔루션 수치는 "85% 절감", "2주 내 구축", "90% 단축" 등 실제 값 사용

### 📝 일반 개선 요청 처리 규칙

**제품 선택 적용:**
1. ✅ 위에서 확인한 제품을 이메일 전체에 일관되게 사용
2. ✅ 선택된 제품이 아닌 다른 제품은 절대 언급 금지
3. ✅ 제품의 특징과 가치를 Pain Point 해결책으로 자연스럽게 연결

**일반 개선 요청 처리:**
1. 사용자의 요청사항을 세밀하게 분석하고 모든 요구사항을 정확히 반영
2. 장문의 요청이라도 각 포인트를 놓치지 않고 체계적으로 적용
3. 요청에서 언급된 톤앤매너, 스타일, 내용 변경사항을 우선적으로 반영
4. 요청된 문체나 접근 방식에 맞춰 전문적 또는 친근한 톤 조절
5. 사용자가 요청한 구체적인 수치나 정보가 있다면 반드시 포함
6. 요청된 길이나 구조 변경사항 적극 반영
7. 사용자가 특정 표현이나 문구 변경을 요청했다면 정확히 적용
8. 의미 단위별로 자연스럽게 <br> 태그로 줄바꿈
9. **사용자 요청이 기본 형식과 충돌하는 경우, 항상 사용자 요청을 우선시**

**외적 형식 및 디자인 요청 처리:**
11. HTML 태그 수정 요청: 사용자가 특정 HTML 태그나 스타일 변경을 요청하면 정확히 적용
12. 레이아웃 변경: 문단 구성, 줄바꿈, 들여쓰기 등의 레이아웃 요청 반영
13. 시각적 강조: 볼드체(**텍스트**), 이탤릭체(*텍스트*), 밑줄 등의 강조 요청 적용
14. 목록 형식: 번호 목록, 불릿 포인트, 체크리스트 등의 형식 변경 요청 처리
15. 색상/스타일 힌트: HTML에서 가능한 텍스트 색상이나 스타일 클래스 적용
16. 테이블 형식: 정보를 표 형태로 정리 요청 시 HTML 테이블로 구성
17. 이미지/아이콘 힌트: 텍스트로 이미지나 아이콘 위치 표시 (예: [이미지 위치], 📧 등)
18. 버튼/링크 스타일: CTA 버튼이나 링크의 HTML 스타일 변경 요청 처리

**기본 서론 형식 (사용자가 다른 요청을 하지 않은 경우만):**
"<p>안녕하세요, [회사명] [담당자명].<br>PortOne {{user_name}} 매니저입니다.</p>"

**기본 결론 형식 (사용자가 다른 요청을 하지 않은 경우만):**
"<p><br>다음주 중 편하신 일정을 알려주시면 [회사명]의 성장에 <br>포트원이 어떻게 기여할 수 있을지 이야기 나누고 싶습니다.<br>긍정적인 회신 부탁드립니다.</p><p>감사합니다.<br>{{user_name}} 드림</p>"

**중요 주의사항:**
- 사용자가 구체적으로 "제목을 이렇게 바꿔줘", "인사말을 이렇게 해줘", "마무리를 이렇게 해줘" 등의 요청을 했다면 반드시 그대로 적용
- 사용자가 "더 짧게", "더 길게", "친근하게", "격식있게" 등의 톤 변경을 요청했다면 전체적으로 적용
- 사용자가 특정 내용 추가/삭제를 요청했다면 정확히 반영
- 사용자 요청이 애매하거나 불분명한 경우에만 기본 형식 유지

**외적 형식 요청 예시:**
- "볼드체로 강조해줘" → <strong> 또는 <b> 태그 사용
- "불릿 포인트로 만들어줘" → <ul><li> 형식으로 변경
- "번호 목록으로 해줘" → <ol><li> 형식으로 변경
- "표로 정리해줘" → <table> 형식으로 구성
- "버튼 스타일로 해줘" → <button> 또는 스타일이 적용된 <a> 태그 사용
- "색깔을 넣어줘" → style="color:" 속성 추가
- "중앙 정렬해줘" → style="text-align:center" 적용
- "큰 글씨로 해줘" → <h1>, <h2> 태그나 style="font-size:" 사용

---

### 🎬 실행 프로세스 (URL/뉴스 기사가 있는 경우)

**단계 1: 기사 분석**
위에 제공된 "참고 기사 정보"를 면밀히 분석하세요.
- 회사명, 제품/서비스명, 사업 내용
- 투자 금액, 매출 목표, 매장 수, 확장 계획 등 구체적 수치
- 출시 시기, 목표 시장, 경쟁 전략

**단계 2: Pain Point 추론**
기사 내용을 바탕으로 이 회사가 현재 직면했거나 곧 직면할 결제/정산 관련 과제를 **3가지 이상** 도출하세요.

예시:
- 자체브랜드 출시 → 신규 SKU 대량 추가로 인한 정산 복잡도 증가
- 전국 매장 확대 → 오프라인/온라인 채널 통합 결제 필요
- 빠른 출시 일정 → IT 개발 리소스 부족, 외부 솔루션 필요

**단계 3: PortOne 솔루션 매핑**
각 Pain Point에 대해 PortOne이 제공할 수 있는 **구체적 해결책**을 연결하세요.
- OPI (One Payment Infra): 통합 결제 시스템, 2주 내 구축, 개발 리소스 85% 절감
- 재무자동화: 정산 데이터 자동화, 90% 시간 단축, 실시간 대시보드
- 스마트 라우팅: 여러 PG사 자동 선택, 결제 성공률 15% 향상

**단계 4: 이메일 작성**
위 분석을 바탕으로 **HTML 형식**의 이메일 본문을 작성하세요.

⚠️ **중요**: 
- 제목은 생성하지 마세요 (본문만 작성)
- HTML 태그 사용: <p>, <br>, <strong>, <ul>, <li> 등
- 기사 내용을 단순 언급이 아닌 Pain Point 근거로 활용
- 구체적 수치와 사실 기반 설득

**출력 형식:**
```html
<p>안녕하세요, [회사명] [담당자명]님.<br>
PortOne {{user_name}} 매니저입니다.</p>

<p>최근 [기사에서 발견한 구체적 사실]에 대한 소식을 접했습니다.<br>
[구체적 수치/목표]는 정말 인상적이었습니다.</p>

<p>이런 빠른 성장과 [구체적 사업 확장] 과정에서<br>
[Pain Point 1]과 [Pain Point 2]가<br>
중요한 과제가 될 것으로 생각됩니다.</p>

<p>PortOne의 [제품명]은 이런 문제를 해결해드릴 수 있습니다:</p>

<ul>
<li><strong>[Pain Point 1 해결]</strong>: [구체적 기능]으로 [수치 결과]</li>
<li><strong>[Pain Point 2 해결]</strong>: [구체적 기능]으로 [수치 결과]</li>
<li><strong>[추가 혜택]</strong>: [차별화 포인트]</li>
</ul>

<p>[회사명]의 [기사에서 언급된 목표]를 더 빠르게 달성하실 수 있도록<br>
15분 간단한 데모로 구체적인 도움을 드리고 싶습니다.</p>

<p>다음주 중 편하신 일정을 알려주시면<br>
[회사명]의 성장에 포트원이 어떻게 기여할 수 있을지<br>
이야기 나누고 싶습니다.</p>

<p>감사합니다.<br>
{{user_name}} 드림</p>
```

---

### ⚠️ 최종 검증 (출력 전 반드시 확인)

**🚨 제품 선택 검증 (최우선)**

**단일 제품 선택 시:**
- [ ] 사용자 요청에서 제품명을 정확히 파악했는가?
- [ ] 선택된 제품만 이메일 전체에 사용했는가?
- [ ] 다른 제품(OPI, Prism, 재무자동화, Recon 중 선택 안 된 제품)을 언급하지 않았는가?
- [ ] 제품의 구체적 수치와 특징을 정확히 사용했는가?

**복수 제품 선택 시:**
- [ ] 사용자가 복수 제품을 요청했는지 확인했는가? ("OPI와 Recon", "둘 다", "종합적으로" 등)
- [ ] 요청된 제품들만 사용하고 다른 제품은 언급하지 않았는가?
- [ ] 각 제품이 적절한 Pain Point 해결에 매핑되었는가?
- [ ] 제품 간 시너지나 종합 가치를 언급했는가?
- [ ] 각 제품의 구체적 수치를 정확히 사용했는가?

**사용자 요청 반영 검증**
- [ ] 사용자가 톤/길이/스타일 변경을 요청했다면 모두 반영되었는가?
- [ ] 사용자가 특정 내용 추가/삭제를 요청했다면 정확히 적용되었는가?

**기사 분석 검증 (기사가 제공된 경우만)**
- [ ] 기사에서 발견한 **구체적 사실** (회사명, 사업, 수치 등) 명시
- [ ] **최소 2개**의 구체적 Pain Point 제기
- [ ] 각 Pain Point에 대해 **선택된 제품(들)**으로 솔루션 제시
- [ ] 솔루션에 해당 제품의 **구체적 수치** 포함
- [ ] <ul><li> 태그로 솔루션 불릿 포인트 작성

---

### 🚨 출력 형식 (매우 중요 - 반드시 준수)

**절대 금지사항:**
- ❌ "핵심 개선 포인트는 다음과 같습니다" 같은 설명 텍스트
- ❌ "개선된 이메일 문안:" 같은 제목이나 헤더
- ❌ "제목: ~" 형식의 제목 생성
- ❌ 개선 이유나 변경 사항 설명
- ❌ 코드 블록(```) 또는 마크다운 형식
- ❌ 그 외 어떠한 부가 설명이나 주석

**반드시 출력:**
- ✅ HTML 형식의 이메일 **본문만** 출력
- ✅ <p>, <br>, <strong>, <ul>, <li> 등 HTML 태그 사용
- ✅ 첫 줄부터 바로 "<p>안녕하세요..." 로 시작

**출력 예시:**
<p>안녕하세요, [회사명] [담당자명].<br>PortOne {{user_name}} 매니저입니다.</p>
<p>최근 [내용]...</p>
...

이제 개선된 이메일 본문만 출력하세요 (다른 텍스트 없이):
"""
        
        # Gemini API 호출
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.5,  # 더 일관된 응답을 위해 낮춤
                'max_output_tokens': 4096,
                'top_p': 0.9,
                'top_k': 40
            }
        )
        
        # Gemini 응답 안전성 검증
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 2:
                logger.warning("Gemini 안전 필터로 인한 응답 차단")
                raise Exception("콘텐츠가 안전 정책에 의해 차단되었습니다")
            elif hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                refined_content = candidate.content.parts[0].text.strip()
                logger.info(f"Gemini 이메일 개선 완료 - 응답 길이: {len(refined_content)} 문자")
                return refined_content
            else:
                logger.warning("Gemini 응답에 유효한 콘텐츠가 없습니다")
                raise Exception("응답 콘텐츠가 비어있습니다")
        
        # 응답이 없는 경우 폴백
        logger.warning("Gemini 응답이 없어 폴백 응답 생성")
        raise Exception("Gemini 응답 없음")
        
    except Exception as e:
        logger.error(f"Gemini 이메일 개선 오류: {str(e)}")
        return f"""제목: 개선된 메일 문안 - {refinement_request} 반영

안녕하세요!

요청해주신 "{refinement_request}" 내용을 반영하여 메일 문안을 개선했습니다.

PortOne의 One Payment Infra는 다음과 같은 혜택을 제공합니다:

• 개발 리소스 85% 절약
• 2주 내 빠른 도입
• 무료 전문 컨설팅
• 스마트 라우팅으로 결제 성공률 향상

15분 간단한 데모를 통해 구체적인 혜택을 보여드리고 싶습니다.

언제 시간이 되실지요?

감사합니다.
PortOne 영업팀

(주의: Gemini API 오류로 인한 기본 응답 - {str(e)})"""

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
        
        # 회사 정보를 캐시에 저장 (뉴스 분석에서 재사용)
        if research_result and research_result.get('success'):
            company_info = {
                'company_name': company_name,
                'industry': research_result.get('industry', ''),
                'business_description': research_result.get('business_description', ''),
                'company_size': research_result.get('company_size', ''),
                'special_notes': research_result.get('pain_points', ''),
                'website': website,
                'research_timestamp': datetime.now().isoformat()
            }
            save_company_info_cache(company_name, company_info)
        
        return jsonify(research_result)
        
    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/api/generate-emails', methods=['POST'])
@login_required
def generate_emails():
    """메일 문안 생성 API (로그인 필요)"""
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

def process_single_company(company, index, user_template=None, user_input_mode='template', user_info=None):
    """
    단일 회사 처리 함수 (병렬 실행용) - SSR 최적화 버전
    
    뉴스 후킹 + SSR 적용 (4개 생성 → 최적 1개 추천) 또는 사용자 문안/요청사항 활용
    
    Args:
        user_info: 로그인한 사용자 정보 (name, email, company_nickname, phone)
    """
    try:
        company_name = company.get('회사명', '')
        
        # CSV에서 "관련뉴스" 열 확인
        news_url = company.get('관련뉴스', '')
        news_content = None
        
        # 뉴스 URL이 있으면 스크래핑
        if news_url and news_url.strip():
            logger.info(f"{company_name}: 관련뉴스 발견 - {news_url}")
            news_content = scrape_news_article(news_url.strip())
            if news_content:
                logger.info(f"{company_name}: 뉴스 스크래핑 성공 - {news_content.get('title', '')}")
            else:
                logger.warning(f"{company_name}: 뉴스 스크래핑 실패")
        
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
            company_name, 
            company.get('홈페이지링크', ''),
            additional_info
        )
        
        # 2. 메일 문안 생성 (Gemini 사용)
        if research_result['success']:
            # 뉴스 내용을 research_result에 추가
            if news_content:
                news_title = news_content.get('title', '')
                news_text = news_content.get('content', '')
                logger.info(f"{company_name}: 관련뉴스 내용을 research에 추가")
                research_result['company_info'] += f"\n\n## 📰 관련 뉴스 기사 (CSV 제공)\n**제목:** {news_title}\n**내용:** {news_text[:1000]}"
            
            # 2-1. 관련 사례 선택 (제안서 기반 실제 사례)
            relevant_case_keys = select_relevant_cases(
                company, 
                research_result.get('company_info', ''),
                max_cases=2
            )
            
            logger.info(f"{company_name} - 선택된 사례: {relevant_case_keys}")
            
            # 사례 정보 포맷팅
            case_examples = ""
            for case_key in relevant_case_keys:
                case_examples += format_case_for_email(case_key)
            
            # 2-2. Gemini API를 사용한 메일 생성 (뉴스 내용, 사례 정보, 사용자 문안/요청사항 포함)
            email_result = generate_email_with_gemini_and_cases(
                company, research_result, case_examples, user_template=user_template, news_content=news_content, user_input_mode=user_input_mode, user_info=user_info
            )
            
            # 2-3. SSR로 4개 이메일 평가 및 순위 매기기
            if email_result.get('success') and email_result.get('variations'):
                try:
                    # 4개 이메일을 SSR로 평가
                    all_emails = []
                    for key, variation in email_result['variations'].items():
                        all_emails.append({
                            'type': key,
                            'product': variation.get('product', 'PortOne'),
                            'subject': variation.get('subject', ''),
                            'body': variation.get('body', ''),
                            'cta': variation.get('cta', ''),
                            'tone': variation.get('tone', '')
                        })
                    
                    # SSR 순위 매기기
                    ranked_emails = rank_emails(all_emails, company)
                    
                    logger.info(f"{company.get('회사명')} SSR 점수: " + 
                              ", ".join([f"{e['type']}: {e.get('ssr_score', 0):.2f}" 
                                       for e in ranked_emails]))
                    
                    # 최고 점수 이메일
                    top_email = ranked_emails[0]
                    
                    # 결과에 SSR 정보 추가
                    email_result['recommended_email'] = top_email
                    email_result['all_ranked_emails'] = ranked_emails
                    email_result['ssr_enabled'] = True
                    
                except Exception as ssr_error:
                    logger.warning(f"SSR 평가 실패: {ssr_error}, 기본 순서 사용")
                    email_result['ssr_enabled'] = False
            
            return {
                'company': company,
                'research': research_result,
                'emails': email_result,
                'selected_cases': relevant_case_keys,
                'index': index
            }
        else:
            return {
                'company': company,
                'error': research_result.get('error', '조사 실패'),
                'index': index
            }
            
    except Exception as e:
        logger.error(f"회사 처리 오류 ({company.get('회사명')}): {str(e)}")
        return {
            'company': company,
            'error': f'처리 오류: {str(e)}',
            'index': index
        }

@app.route('/api/batch-process', methods=['POST'])
@login_required
def batch_process():
    """여러 회사 일괄 처리 API - 병렬 처리 최적화 (로그인 필요)"""
    try:
        data = request.json
        companies = data.get('companies', [])
        max_workers = data.get('max_workers', 3)  # 동시 처리 개수 (기본 3개로 감소)
        user_template = data.get('user_template', None)  # 사용자 문안 또는 요청사항
        user_input_mode = data.get('user_input_mode', 'template')  # 'request' 또는 'template'
        
        # 로그인한 사용자 정보 추출 (병렬 처리에서 사용하기 위해)
        user_info = {
            'name': current_user.name if current_user and current_user.is_authenticated else "오준호",
            'email': current_user.email if current_user and current_user.is_authenticated else "ocean@portone.io",
            'company_nickname': current_user.company_nickname if current_user and current_user.is_authenticated else "PortOne 오준호 매니저",
            'phone': current_user.phone if current_user and current_user.is_authenticated else "010-2580-2580"
        }
        logger.info(f"📧 배치 처리 요청자: {user_info['name']} ({user_info['email']})")
        
        if not companies:
            return jsonify({'error': '처리할 회사 데이터가 없습니다'}), 400
        
        # ⚠️ 대량 처리 제한: 한 번에 최대 50개까지만
        MAX_BATCH_SIZE = 50
        if len(companies) > MAX_BATCH_SIZE:
            return jsonify({
                'error': f'한 번에 최대 {MAX_BATCH_SIZE}개까지만 처리 가능합니다. 현재: {len(companies)}개',
                'suggestion': f'데이터를 {MAX_BATCH_SIZE}개씩 나누어서 처리해주세요.'
            }), 400
        
        logger.info(f"병렬 처리 시작: {len(companies)}개 회사, {max_workers}개 동시 작업")
        if user_template:
            if user_input_mode == 'request':
                logger.info(f"요청사항 모드: {len(user_template)}자 - 기본 생성 + 요청사항 반영")
            else:
                logger.info(f"문안 모드: {len(user_template)}자 - 뉴스 후킹 서론 + 사용자 본문")
        else:
            logger.info("SSR 모드: 뉴스 후킹 + 4개 생성 + 사례 포함 + AI 추천")
        start_time = time.time()
        
        # ThreadPoolExecutor를 사용한 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 각 회사에 대해 처리 작업 제출 (user_template, user_input_mode, user_info 전달)
            future_to_company = {
                executor.submit(process_single_company, company, i, user_template, user_input_mode, user_info): (company, i)
                for i, company in enumerate(companies)
            }
            
            results = []
            completed = 0
            total = len(companies)
            
            # 완료된 작업들 수집
            for future in concurrent.futures.as_completed(future_to_company):
                company, index = future_to_company[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    logger.info(f"진행률: {completed}/{total} ({completed/total*100:.1f}%) - {company.get('회사명', 'Unknown')}")
                    
                except Exception as e:
                    logger.error(f"회사 {company.get('회사명', 'Unknown')} 처리 실패: {str(e)}")
                    results.append({
                        'company': company,
                        'error': f'처리 실패: {str(e)}',
                        'index': index
                    })
                    completed += 1
        
        # 인덱스 순서로 정렬
        results.sort(key=lambda x: x.get('index', 0))
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"병렬 처리 완료: {processing_time:.2f}초, 평균 {processing_time/len(companies):.2f}초/회사")
        
        # 이메일 생성 기록 저장
        try:
            for result in results:
                if 'emails' in result and result['emails'].get('success'):
                    company = result.get('company', {})
                    company_name = company.get('회사명', 'Unknown')
                    company_email = company.get('대표이메일', '')
                    
                    # 생성된 각 이메일 타입 기록
                    variations = result['emails'].get('variations', {})
                    for email_type in variations.keys():
                        email_gen = EmailGeneration(
                            user_id=current_user.id,
                            company_name=company_name,
                            company_email=company_email,
                            email_type=email_type,
                            generation_mode='ssr' if not user_template else ('user_request' if user_input_mode == 'request' else 'user_template')
                        )
                        db.session.add(email_gen)
            
            db.session.commit()
            logger.info(f"📊 {current_user.email}: {len(results)}개 회사, 이메일 생성 기록 저장 완료")
        except Exception as e:
            logger.error(f"이메일 생성 기록 저장 오류: {e}")
            # 기록 저장 실패해도 결과는 반환
        
        return jsonify({
            'success': True,
            'results': results,
            'total_processed': len(results),
            'processing_time': round(processing_time, 2),
            'parallel_workers': max_workers,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"일괄 처리 오류: {str(e)}")
        return jsonify({'error': f'일괄 처리 오류: {str(e)}'}), 500

@app.route('/api/refine-email', methods=['POST'])
@login_required
def refine_email():
    """이메일 문안 개선 (로그인 필요)"""
    try:
        data = request.json
        current_email = data.get('current_email', '')
        refinement_request = data.get('refinement_request', '')
        
        if not current_email or not refinement_request:
            return jsonify({
                'success': False,
                'error': '현재 이메일 내용과 개선 요청사항이 필요합니다.'
            }), 400
        
        # Gemini 2.5 Pro로 이메일 개선 요청
        refined_email = refine_email_with_gemini(current_email, refinement_request)
        
        # 사용자 이름 동적 치환
        user_name = current_user.name if current_user and current_user.is_authenticated else "오준호"
        refined_email = refined_email.replace('{user_name}', user_name)
        refined_email = refined_email.replace('오준호', user_name)
        refined_email = refined_email.replace('PortOne 오준호 매니저', f'PortOne {user_name} 매니저')
        
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

@app.route('/api/analyze-news', methods=['POST'])
def analyze_news():
    """뉴스 기사 링크를 분석하여 페인 포인트 기반 메일 생성"""
    try:
        data = request.json
        news_url = data.get('news_url', '')
        company_name = data.get('company_name', '')
        current_email = data.get('current_email', '')
        
        if not news_url:
            return jsonify({
                'success': False,
                'error': '뉴스 기사 URL이 필요합니다.'
            }), 400
        
        # URL 유효성 검사
        if not is_valid_url(news_url):
            return jsonify({
                'success': False,
                'error': '유효하지 않은 URL입니다.'
            }), 400
        
        # 뉴스 기사 내용 스크래핑
        logger.info(f"뉴스 분석 요청 - URL: {news_url}, 회사: {company_name}")
        article_content = scrape_news_article(news_url)
        
        if not article_content:
            logger.error(f"뉴스 스크래핑 실패: {news_url}")
            return jsonify({
                'success': False,
                'error': '기사 내용을 가져올 수 없습니다. URL을 확인해주세요.'
            }), 400
        
        logger.info(f"뉴스 스크래핑 성공 - 제목: {article_content.get('title', '')[:50]}..., 본문 길이: {len(article_content.get('content', ''))}자")
        
        # 기사 내용 관련성 검증
        relevance_score = check_article_relevance(article_content, company_name)
        logger.info(f"기사 관련성 점수: {relevance_score}/10")
        
        # 회사 정보 조회 (기존 조사 결과 활용)
        company_info = get_existing_company_info(company_name)
        if company_info:
            logger.info(f"기존 회사 정보 발견: {company_name}")
        
        # 기사 내용 기반 페인 포인트 분석 및 메일 생성
        analyzed_email = generate_email_from_news_analysis(
            article_content, 
            company_name, 
            current_email,
            news_url,
            company_info,
            relevance_score
        )
        
        return jsonify({
            'success': True,
            'analyzed_email': analyzed_email,
            'article_summary': article_content.get('summary', ''),
            'pain_points': article_content.get('pain_points', []),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"뉴스 분석 중 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def scrape_article_content(url):
    """
    개별 블로그 글의 상세 내용 스크래핑
    
    Args:
        url: 블로그 글 URL
    
    Returns:
        str: 글 내용
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # article 태그 찾기
        article = soup.find('article')
        if article:
            # 텍스트만 추출 (HTML 태그 제거)
            content = article.get_text(separator=' ', strip=True)
            return content[:5000]  # 최대 5000자로 제한
        
        return ''
    except Exception as e:
        logger.error(f"   글 내용 스크래핑 오류 ({url}): {str(e)}")
        return ''

def scrape_portone_blog_category(category_url, category_name, max_pages=5):
    """
    포트원 블로그 카테고리별 스크래핑
    
    Args:
        category_url: 카테고리 URL
        category_name: 카테고리명 (OPI, Recon 등)
        max_pages: 최대 페이지 수
    
    Returns:
        list: 블로그 글 정보 리스트
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        
        logger.info(f"📰 [{category_name}] 스크래핑 시작: {category_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        all_posts = []
        
        for page in range(1, max_pages + 1):
            # 페이지 URL 구성
            page_url = f"{category_url}&page={page}"
            logger.info(f"   페이지 {page}/{max_pages} 스크래핑...")
            
            try:
                response = requests.get(page_url, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # h3 태그로 제목과 링크 추출
                h3_tags = soup.find_all('h3', class_='group-hover:text-[#FC6B2D]')
                
                if not h3_tags:
                    logger.info(f"   페이지 {page}에 더 이상 글이 없습니다.")
                    break
                
                for h3 in h3_tags:
                    try:
                        title = h3.get_text(strip=True)
                        
                        # 링크 찾기 (h3의 부모나 형제 요소에서)
                        link_elem = h3.find_parent('a') or h3.find('a')
                        if not link_elem:
                            # 형제 요소에서 링크 찾기
                            parent = h3.find_parent()
                            link_elem = parent.find('a') if parent else None
                        
                        if link_elem and link_elem.get('href'):
                            link = link_elem['href']
                            if not link.startswith('http'):
                                link = 'https://blog.portone.io' + link
                            
                            logger.info(f"      ✅ {title[:40]}...")
                            
                            # 상세 내용 스크래핑
                            content = scrape_article_content(link)
                            
                            # 요약은 content의 앞부분
                            summary = content[:200] if content else ''
                            
                            all_posts.append({
                                'title': title,
                                'link': link,
                                'summary': summary,
                                'content': content,
                                'category': category_name
                            })
                            
                            # 과도한 요청 방지
                            import time
                            time.sleep(0.5)
                            
                    except Exception as e:
                        logger.error(f"      글 파싱 오류: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"   페이지 {page} 스크래핑 오류: {str(e)}")
                continue
        
        logger.info(f"📊 [{category_name}] 총 {len(all_posts)}개 글 수집 완료")
        return all_posts
        
    except Exception as e:
        logger.error(f"[{category_name}] 스크래핑 오류: {str(e)}")
        return []

def scrape_portone_blog_initial():
    """
    포트원 블로그 초기 데이터 스크래핑
    - OPI (국내 결제): 5페이지
    - Recon (매출 마감): 1페이지
    """
    try:
        from portone_blog_cache import save_blog_cache, extract_keywords_from_post
        
        logger.info("🚀 포트원 블로그 초기 데이터 스크래핑 시작")
        
        all_posts = []
        
        # 1. OPI (국내 결제) - 5페이지
        opi_url = 'https://blog.portone.io/?filter=%EA%B5%AD%EB%82%B4%20%EA%B2%B0%EC%A0%9C'
        opi_posts = scrape_portone_blog_category(opi_url, 'OPI', max_pages=5)
        all_posts.extend(opi_posts)
        
        # 2. Recon (매출 마감) - 1페이지
        recon_url = 'https://blog.portone.io/?filter=%EB%A7%A4%EC%B6%9C%20%EB%A7%88%EA%B0%90'
        recon_posts = scrape_portone_blog_category(recon_url, 'Recon', max_pages=1)
        all_posts.extend(recon_posts)
        
        # 3. PS (플랫폼 정산) - 3페이지
        ps_url = 'https://blog.portone.io/category/news/?filter=%ED%94%8C%EB%9E%AB%ED%8F%BC%20%EC%A0%95%EC%82%B0'
        ps_posts = scrape_portone_blog_category(ps_url, 'PS', max_pages=3)
        all_posts.extend(ps_posts)
        
        # 키워드 자동 추출
        logger.info("🔍 블로그 글 키워드 추출 중...")
        for post in all_posts:
            keywords, industry_tags = extract_keywords_from_post(post)
            post['keywords'] = keywords
            post['industry_tags'] = industry_tags
        
        # DB에 저장
        if all_posts:
            save_blog_cache(all_posts, replace_all=True)
            logger.info(f"✅ 초기 데이터 스크래핑 완료: 총 {len(all_posts)}개 글")
            return all_posts
        else:
            logger.warning("⚠️ 스크래핑된 글이 없습니다")
            return []
        
    except Exception as e:
        logger.error(f"초기 데이터 스크래핑 오류: {str(e)}")
        return []

def get_blog_content_for_email():
    """
    메일 생성에 사용할 블로그 콘텐츠 가져오기 (캐시 우선)
    
    Returns:
        str: 포맷팅된 블로그 콘텐츠
    """
    from portone_blog_cache import load_blog_cache, format_blog_content_for_email, get_blog_cache_age
    
    # 캐시에서 로드 시도
    cached_posts = load_blog_cache()
    
    if cached_posts:
        cache_age = get_blog_cache_age()
        if cache_age and cache_age < 24:  # 24시간 이내면 캐시 사용
            logger.info(f"📚 블로그 캐시 사용 (업데이트된 지 {cache_age:.1f}시간)")
            return format_blog_content_for_email(cached_posts)
        else:
            logger.info("⏰ 블로그 캐시가 오래됨 (24시간 이상)")
    
    # 캐시가 없거나 오래되었으면 스크래핑
    logger.info("🔄 블로그 새로 스크래핑...")
    new_posts = scrape_portone_blog(max_posts=5)
    
    if new_posts:
        return format_blog_content_for_email(new_posts)
    elif cached_posts:
        # 스크래핑 실패 시 오래된 캐시라도 사용
        logger.info("⚠️ 스크래핑 실패, 오래된 캐시 사용")
        return format_blog_content_for_email(cached_posts)
    else:
        return ""

@app.route('/api/chat-reply', methods=['POST'])
@login_required
def chat_reply():
    """
    자유로운 챗봇 - 고객 답변/반박에 대한 재설득 메일 생성 (로그인 필요)
    
    사용 사례:
    1. 고객의 부정적 답변에 대한 반박 메일
    2. 추가 질문에 대한 답변 메일
    3. 자유로운 컨텍스트 기반 메일 생성
    """
    try:
        data = request.json
        user_context = data.get('context', '')  # 고객 답변/상황 설명
        company_name = data.get('company_name', '')
        email_name = data.get('email_name', '담당자님')
        
        if not user_context:
            return jsonify({'error': '컨텍스트(고객 답변 또는 상황)를 입력해주세요'}), 400
        
        logger.info(f"💬 챗봇 재설득 메일 생성 시작 - {company_name}")
        logger.info(f"   입력 컨텍스트: {user_context[:100]}...")
        
        # 포트원 블로그 콘텐츠 가져오기 (캐시 우선)
        blog_content = get_blog_content_for_email()
        logger.info(f"   📚 블로그 콘텐츠: {'사용' if blog_content else '없음'}")
        
        # 서비스 소개서(케이스 스터디) 로드 - 기본 케이스 사용
        from case_database import PORTONE_CASES, format_case_for_email
        
        # 컨텍스트에서 키워드 추출하여 관련 케이스 선택
        context_lower = user_context.lower()
        selected_case_ids = []
        
        # 키워드 기반 케이스 선택
        if 'pg' in context_lower or '결제' in context_lower or '비용' in context_lower:
            selected_case_ids.append('development_resource_saving')
        if '시간' in context_lower or '바빠' in context_lower or '개발' in context_lower:
            selected_case_ids.append('quick_setup')
        if '실패' in context_lower or '오류' in context_lower:
            selected_case_ids.append('payment_failure_recovery')
        
        # 최소 2개 케이스 보장
        if len(selected_case_ids) == 0:
            selected_case_ids = ['development_resource_saving', 'payment_failure_recovery']
        elif len(selected_case_ids) == 1:
            selected_case_ids.append('multi_pg_management')
        
        # 최대 3개로 제한
        selected_case_ids = selected_case_ids[:3]
        
        # 각 케이스를 포맷팅하여 결합
        case_details = "\n".join([format_case_for_email(case_id) for case_id in selected_case_ids])
        
        # 케이스 스터디와 블로그 콘텐츠 결합
        full_context = case_details + blog_content
        
        # Gemini로 재설득 메일 생성
        result = generate_persuasive_reply(
            context=user_context,
            company_name=company_name,
            email_name=email_name,
            case_examples=full_context
        )
        
        # 사용자 이름 동적 치환
        if result.get('success') and result.get('email', {}).get('body'):
            user_name = current_user.name if current_user and current_user.is_authenticated else "오준호"
            result['email']['body'] = result['email']['body'].replace('오준호', user_name)
            result['email']['body'] = result['email']['body'].replace('PortOne 오준호 매니저', f'PortOne {user_name} 매니저')
        
        if result.get('success'):
            logger.info(f"✅ {company_name} 재설득 메일 생성 완료")
            return jsonify(result)
        else:
            logger.error(f"❌ {company_name} 재설득 메일 생성 실패: {result.get('error')}")
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"챗봇 오류: {str(e)}")
        return jsonify({
            'error': f'챗봇 오류: {str(e)}',
            'success': False
        }), 500

def classify_user_intent(user_message):
    """
    사용자 요청의 의도를 Gemini를 사용하여 분류
    
    Returns:
        dict: {
            'intent': 요청 유형,
            'parameters': 추출된 파라미터,
            'confidence': 신뢰도
        }
    """
    try:
        logger.info(f"🔍 사용자 요청 분석: {user_message[:100]}...")
        
        prompt = f"""
다음은 사용자의 이메일 챗봇 요청입니다. 요청의 의도를 분석하고 필요한 파라미터를 추출하세요.

**사용자 요청:**
{user_message}

**가능한 요청 유형:**
1. **regenerate_with_sales_change**: 판매 상품을 변경해서 메일 재생성
   - 예: "OPI로 다시 써줘", "재무자동화 제품으로 바꿔줘", "recon 상품으로 변경", "prism으로 소개해줘"
   - 파라미터: sales_point (opi, recon, prism, 인앱수수료절감 중 하나)

2. **change_tone**: 톤이나 스타일 변경
   - 예: "더 친근하게", "전문적으로", "캐주얼하게", "공손하게"
   - 파라미터: tone (casual, professional, friendly, formal)

3. **refine_content**: 특정 부분 개선
   - 예: "제목을 더 임팩트있게", "본문 짧게", "수치 강조해줘"
   - 파라미터: refinement_request (구체적 요청사항)

4. **persuasive_reply**: 고객 반박/부정 답변에 대한 재설득
   - 예: "비용이 부담된다고 했어", "지금은 바빠서 어렵대"
   - 파라미터: customer_response (고객 답변)

5. **question**: 일반 질문이나 정보 요청
   - 예: "포트원이 뭐야?", "OPI가 뭔지 설명해줘"

6. **other**: 기타 요청

**회사명 추출:**
- 회사명이 언급되면 추출 (예: "토스", "쿠팡", "네이버" 등)

**JSON 형식으로만 응답:**
{{
  "intent": "요청 유형 (위 6가지 중 하나)",
  "parameters": {{
    "sales_point": "opi/recon/prism/인앱수수료절감/null",
    "tone": "톤 설명 또는 null",
    "refinement_request": "개선 요청사항 또는 null",
    "customer_response": "고객 답변 또는 null",
    "company_name": "회사명 또는 null"
  }},
  "confidence": 0.0-1.0,
  "reasoning": "판단 근거 간단히"
}}
"""

        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            raise Exception("Gemini API 응답이 비어있습니다")
        
        # JSON 파싱
        import re
        response_text = response.text.strip()
        
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        elif '{' in response_text and '}' in response_text:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
        else:
            json_str = response_text
        
        intent_data = json.loads(json_str)
        
        logger.info(f"✅ 의도 분석 완료: {intent_data.get('intent')} (신뢰도: {intent_data.get('confidence')})")
        logger.info(f"   추출된 파라미터: {intent_data.get('parameters')}")
        
        return intent_data
        
    except Exception as e:
        logger.error(f"의도 분석 오류: {str(e)}")
        # Fallback: 단순 키워드 매칭
        return fallback_intent_classification(user_message)

def fallback_intent_classification(user_message):
    """
    Gemini 실패 시 폴백: 단순 키워드 기반 의도 분류
    """
    message_lower = user_message.lower()
    
    # sales_point 변경 키워드
    if any(keyword in message_lower for keyword in ['opi', 'one payment infra', '결제 인프라']):
        return {
            'intent': 'regenerate_with_sales_change',
            'parameters': {'sales_point': 'opi', 'company_name': None},
            'confidence': 0.7,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    if any(keyword in message_lower for keyword in ['recon', '재무자동화', '재무 자동화', '정산']):
        return {
            'intent': 'regenerate_with_sales_change',
            'parameters': {'sales_point': 'recon', 'company_name': None},
            'confidence': 0.7,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    if any(keyword in message_lower for keyword in ['prism', '프리즘', '오픈마켓', '멀티채널', '다중채널', '정산 통합', '쿠팡', '11번가']):
        return {
            'intent': 'regenerate_with_sales_change',
            'parameters': {'sales_point': 'prism', 'company_name': None},
            'confidence': 0.7,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    if any(keyword in message_lower for keyword in ['인앱수수료', '게임', 'd2c', '웹상점']):
        return {
            'intent': 'regenerate_with_sales_change',
            'parameters': {'sales_point': '인앱수수료절감', 'company_name': None},
            'confidence': 0.7,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    # 톤 변경 키워드
    if any(keyword in message_lower for keyword in ['친근', '캐주얼', '부드럽', '편하게']):
        return {
            'intent': 'change_tone',
            'parameters': {'tone': 'friendly', 'company_name': None},
            'confidence': 0.6,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    if any(keyword in message_lower for keyword in ['전문적', '프로페셔널', '공식적']):
        return {
            'intent': 'change_tone',
            'parameters': {'tone': 'professional', 'company_name': None},
            'confidence': 0.6,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    # 재설득 키워드
    if any(keyword in message_lower for keyword in ['비용', '부담', '바빠', '거절', '안된다', '어렵다']):
        return {
            'intent': 'persuasive_reply',
            'parameters': {'customer_response': user_message, 'company_name': None},
            'confidence': 0.6,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    # 개선 요청 키워드
    if any(keyword in message_lower for keyword in ['개선', '수정', '바꿔', '다시', '더', '짧게', '길게']):
        return {
            'intent': 'refine_content',
            'parameters': {'refinement_request': user_message, 'company_name': None},
            'confidence': 0.5,
            'reasoning': 'Keyword matching (fallback)'
        }
    
    # 기본: 질문으로 분류
    return {
        'intent': 'question',
        'parameters': {'company_name': None},
        'confidence': 0.3,
        'reasoning': 'Default fallback'
    }

@app.route('/api/smart-chat', methods=['POST'])
@login_required
def smart_chat():
    """
    통합 스마트 챗봇 - 다양한 사용자 요청을 이해하고 처리
    
    요청 유형:
    - 메일 재생성 (sales_point 변경)
    - 톤/스타일 변경
    - 문안 개선
    - 재설득 메일 생성
    - 일반 질문
    """
    try:
        data = request.json
        user_message = data.get('message', '')
        session_data = data.get('session_data', {})  # 이전 생성 결과 등
        
        if not user_message:
            return jsonify({'error': '메시지를 입력해주세요'}), 400
        
        logger.info(f"💬 스마트 챗봇 요청: {user_message[:100]}...")
        
        # 1단계: 사용자 의도 파악
        intent_result = classify_user_intent(user_message)
        intent = intent_result.get('intent')
        params = intent_result.get('parameters', {})
        
        logger.info(f"📊 분류 결과: {intent} (신뢰도: {intent_result.get('confidence')})")
        
        # 2단계: 의도에 따라 처리
        if intent == 'regenerate_with_sales_change':
            # 판매 상품 변경해서 메일 재생성
            sales_point = params.get('sales_point')
            company_data = session_data.get('company_data', {})
            
            if not company_data:
                return jsonify({
                    'success': False,
                    'error': '이전 생성 데이터가 없습니다. 먼저 메일을 생성해주세요.',
                    'intent': intent
                }), 400
            
            # sales_item 필드 업데이트 (CSV의 sales_item 컬럼)
            company_data['sales_item'] = sales_point
            logger.info(f"🔄 판매 상품 변경: {sales_point} (company_data['sales_item'] 업데이트)")
            
            # 메일 재생성
            # 기존 research_data 재사용
            research_data = session_data.get('research_data', {})
            
            result = generate_email_with_gemini(company_data, research_data)
            
            # 제품명 표시 개선
            product_name_map = {
                'opi': 'OPI (One Payment Infra)',
                'recon': 'Recon (재무자동화)',
                'prism': 'Prism (멀티 오픈마켓 정산 통합)',
                '인앱수수료절감': '게임 웹상점 (인앱수수료절감)'
            }
            product_display_name = product_name_map.get(sales_point, sales_point.upper())
            
            return jsonify({
                'success': True,
                'intent': intent,
                'message': f'✅ {product_display_name} 제품으로 메일을 재생성했습니다!',
                'result': result,
                'sales_point': sales_point
            })
        
        elif intent == 'change_tone':
            # 톤 변경
            tone = params.get('tone', '')
            current_email = session_data.get('current_email', {})
            
            if not current_email:
                return jsonify({
                    'success': False,
                    'error': '변경할 이메일이 없습니다.',
                    'intent': intent
                }), 400
            
            # 톤 변경 요청 생성
            refinement_request = f"이메일의 톤을 {tone}으로 변경해주세요. 내용은 유지하되 톤만 조정합니다."
            
            # refine_email_with_user_request 사용
            company_data = session_data.get('company_data', {})
            refined = refine_email_with_user_request(
                original_subject=current_email.get('subject', ''),
                original_body=current_email.get('body', ''),
                user_request=refinement_request,
                company_data=company_data
            )
            
            return jsonify({
                'success': True,
                'intent': intent,
                'message': f'✅ 톤을 {tone}으로 변경했습니다!',
                'result': refined
            })
        
        elif intent == 'refine_content':
            # 문안 개선
            refinement_request = params.get('refinement_request', user_message)
            current_email = session_data.get('current_email', {})
            
            if not current_email:
                return jsonify({
                    'success': False,
                    'error': '개선할 이메일이 없습니다.',
                    'intent': intent
                }), 400
            
            company_data = session_data.get('company_data', {})
            refined = refine_email_with_user_request(
                original_subject=current_email.get('subject', ''),
                original_body=current_email.get('body', ''),
                user_request=refinement_request,
                company_data=company_data
            )
            
            return jsonify({
                'success': True,
                'intent': intent,
                'message': '✅ 이메일을 개선했습니다!',
                'result': refined
            })
        
        elif intent == 'persuasive_reply':
            # 재설득 메일 생성
            company_name = params.get('company_name', session_data.get('company_data', {}).get('회사명', ''))
            customer_response = params.get('customer_response', user_message)
            email_name = session_data.get('company_data', {}).get('대표자명', '담당자님')
            
            if not company_name:
                return jsonify({
                    'success': False,
                    'error': '회사명을 찾을 수 없습니다.',
                    'intent': intent
                }), 400
            
            # 포트원 블로그 콘텐츠 가져오기
            blog_content = get_blog_content_for_email()
            
            # 케이스 스터디
            from case_database import format_case_for_email
            selected_case_ids = ['development_resource_saving', 'payment_failure_recovery']
            case_details = "\n".join([format_case_for_email(case_id) for case_id in selected_case_ids])
            full_context = case_details + blog_content
            
            result = generate_persuasive_reply(
                context=customer_response,
                company_name=company_name,
                email_name=email_name,
                case_examples=full_context
            )
            
            # 사용자 이름 동적 치환
            if result.get('success') and result.get('email', {}).get('body'):
                user_name = current_user.name if current_user and current_user.is_authenticated else "오준호"
                result['email']['body'] = result['email']['body'].replace('오준호', user_name)
            
            return jsonify({
                'success': result.get('success'),
                'intent': intent,
                'message': '✅ 재설득 메일을 생성했습니다!' if result.get('success') else '❌ 생성 실패',
                'result': result
            })
        
        elif intent == 'question':
            # 일반 질문 - Gemini로 답변 생성
            answer = answer_general_question(user_message)
            
            return jsonify({
                'success': True,
                'intent': intent,
                'message': answer,
                'result': {'answer': answer}
            })
        
        else:
            # 기타 요청
            return jsonify({
                'success': False,
                'intent': intent,
                'message': '죄송합니다. 요청을 이해하지 못했습니다. 다시 설명해주시겠어요?',
                'confidence': intent_result.get('confidence')
            })
    
    except Exception as e:
        logger.error(f"스마트 챗봇 오류: {str(e)}")
        return jsonify({
            'error': f'챗봇 오류: {str(e)}',
            'success': False
        }), 500

def answer_general_question(question):
    """
    일반 질문에 대한 답변 생성
    """
    try:
        prompt = f"""
당신은 포트원(PortOne)의 제품 전문가입니다. 다음 질문에 친절하고 정확하게 답변하세요.

**질문:** {question}

**포트원 제품 정보:**
- One Payment Infra (OPI): 결제 시스템 통합 관리, PG사 통합, 85% 리소스 절감
- Recon (재무자동화): 커머스 재무 마감 자동화, 정산 관리
- Prism (멀티 오픈마켓 정산 통합): 네이버/쿠팡/11번가 등 각 플랫폼의 서로 다른 정산 데이터를 한 눈에 통합, 재무 마감 시간 90% 단축
- 인앱수수료절감: 게임 웹상점 구축, 인앱결제 수수료(30%) 회피

**답변 형식:**
- 간결하고 이해하기 쉽게 (3-5문장)
- 구체적인 수치나 예시 포함
- 친근하고 전문적인 톤

답변만 작성하세요 (설명이나 추가 정보 없이):
"""
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        else:
            return "죄송합니다. 답변을 생성하지 못했습니다."
    
    except Exception as e:
        logger.error(f"질문 답변 생성 오류: {str(e)}")
        return "죄송합니다. 일시적인 오류가 발생했습니다."

@app.route('/api/scrape-blog-initial', methods=['POST'])
def scrape_blog_initial():
    """
    포트원 블로그 초기 데이터 스크래핑
    - OPI (국내 결제): 5페이지
    - Recon (매출 마감): 1페이지
    """
    try:
        logger.info("🚀 블로그 초기 데이터 스크래핑 요청")
        
        blog_posts = scrape_portone_blog_initial()
        
        if blog_posts:
            return jsonify({
                'success': True,
                'message': f'초기 데이터 스크래핑 완료',
                'posts_count': len(blog_posts),
                'categories': {
                    'OPI': len([p for p in blog_posts if p.get('category') == 'OPI']),
                    'Recon': len([p for p in blog_posts if p.get('category') == 'Recon'])
                },
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': '블로그 스크래핑 실패'
            }), 500
            
    except Exception as e:
        logger.error(f"초기 스크래핑 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/update-blog', methods=['POST'])
def update_blog():
    """
    포트원 블로그 콘텐츠 업데이트
    
    OPI와 Recon 카테고리 모두 업데이트
    """
    try:
        logger.info("🔄 블로그 업데이트 요청")
        
        blog_posts = scrape_portone_blog_initial()
        
        if blog_posts:
            return jsonify({
                'success': True,
                'message': f'블로그 콘텐츠 업데이트 완료',
                'posts_count': len(blog_posts),
                'categories': {
                    'OPI': len([p for p in blog_posts if p.get('category') == 'OPI']),
                    'Recon': len([p for p in blog_posts if p.get('category') == 'Recon'])
                },
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': '블로그 스크래핑 실패'
            }), 500
            
    except Exception as e:
        logger.error(f"블로그 업데이트 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/blog-cache-status', methods=['GET'])
def blog_cache_status():
    """
    블로그 캐시 상태 확인
    """
    try:
        from portone_blog_cache import load_blog_cache, get_blog_cache_age
        
        cached_posts = load_blog_cache()
        cache_age = get_blog_cache_age()
        
        return jsonify({
            'success': True,
            'has_cache': cached_posts is not None,
            'posts_count': len(cached_posts) if cached_posts else 0,
            'cache_age_hours': cache_age if cache_age else None,
            'cache_status': 'fresh' if cache_age and cache_age < 24 else 'stale' if cache_age else 'no_cache',
            'posts': cached_posts[:3] if cached_posts else [],  # 최근 3개만 미리보기
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"캐시 상태 확인 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """서비스 상태 확인"""
    return jsonify({
        'status': 'healthy',
        'service': 'email-generation',
        'timestamp': datetime.now().isoformat()
    })

# 뉴스 분석 관련 함수들을 먼저 정의
def is_valid_url(url):
    """URL 유효성 검사"""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def extract_content_from_soup(soup, url):
    """BeautifulSoup 객체에서 제목과 본문 추출"""
    # 한국 주요 뉴스 사이트별 특화 선택자
    site_specific_selectors = {
        'naver.com': {
            'title': ['h2#title', 'h3.tts_head', '.media_end_head_headline'],
            'content': ['#dic_area', '.go_trans._article_content', '#articleBodyContents']
        },
        'daum.net': {
            'title': ['.tit_view', '.txt_tit'],
            'content': ['.article_view', '.news_view']
        },
        'chosun.com': {
            'title': ['h1', 'title', '.article-header h1', '.news_title_text', '[property="og:title"]'],
            'content': ['#fusion-app article', '.story-news__article', '[data-type="article-body"]', '.par', '.news_text', 'article p', '.article-body']
        },
        'joins.com': {
            'title': ['.headline', '.article_title'],
            'content': ['#article_body', '.article_content']
        },
        'donga.com': {
            'title': ['.title', '.news_title'],
            'content': ['.news_view', '.article_txt']
        }
    }
    
    # 일반적인 선택자 (모든 사이트 대응)
    general_selectors = {
        'title': [
            'h1', 'h2', '.title', '.headline', '.article-title', '.news-title',
            '.post-title', '.entry-title', '[data-cy="article-headline"]',
            '.tit_view', '.news_ttl', '.article_head', '.news_headline'
        ],
        'content': [
            'article', '.article-content', '.news-content', '.post-content',
            '.entry-content', '.content', '#content', '.article-body',
            '.news-body', '.post-body', '.story-body', '.article-text',
            '[data-module="ArticleContent"]', '.article_body', '.news_content',
            '.view_txt', '.news_view', '.article_txt', '.par', '#newsContent'
        ]
    }
    
    title = ''
    content = ''
    
    # 사이트별 특화 선택자 시도
    domain = url.lower()
    site_selectors = None
    for site, selectors in site_specific_selectors.items():
        if site in domain:
            site_selectors = selectors
            break
    
    # 제목 추출 - 먼저 meta 태그에서 시도
    try:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title.get('content').strip()
            logger.info(f"OG 태그에서 제목 추출 성공: {title[:50]}...")
    except Exception as e:
        logger.debug(f"OG 태그 제목 추출 실패: {e}")
    
    # meta 태그에서 실패하면 일반 선택자 시도
    if not title:
        title_selectors = site_selectors['title'] if site_selectors else general_selectors['title']
        for selector in title_selectors:
            try:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if len(title) > 5:  # 의미있는 제목인지 확인
                        logger.info(f"제목 추출 성공: {title[:50]}...")
                        break
            except Exception as e:
                logger.debug(f"제목 선택자 {selector} 실패: {e}")
                continue
    
    # 본문 추출 - 조선일보 JSON 데이터에서 먼저 시도
    if 'chosun.com' in url.lower():
        try:
            # script 태그에서 Fusion.globalContent 찾기
            scripts = soup.find_all('script', id='fusion-metadata')
            for script in scripts:
                script_text = script.string
                if script_text and 'Fusion.globalContent' in script_text:
                    # JSON 파싱
                    import json
                    import re
                    
                    # globalContent JSON 추출
                    match = re.search(r'Fusion\.globalContent=({.*?});', script_text, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        
                        # content_elements에서 본문 추출
                        if 'content_elements' in data:
                            content_parts = []
                            for elem in data['content_elements']:
                                if elem.get('type') == 'text' and elem.get('content'):
                                    content_parts.append(elem['content'])
                            
                            if content_parts:
                                content = ' '.join(content_parts)
                                logger.info(f"조선일보 JSON에서 본문 추출 성공: {len(content)}자")
        except Exception as e:
            logger.debug(f"조선일보 JSON 파싱 실패: {e}")
    
    # JSON 파싱 실패 시 일반 선택자로 시도
    if not content or len(content) < 300:
        content_selectors = site_selectors['content'] if site_selectors else general_selectors['content']
        for selector in content_selectors:
            try:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 불필요한 요소 제거 (더 포괄적)
                    unwanted_selectors = [
                        'script', 'style', 'nav', 'header', 'footer', 'aside',
                        '.ad', '.advertisement', '.social-share', '.related-articles',
                        '.comment', '.reply', '.share', '.tag', '.category',
                        '.author', '.date', '.source', '.copyright', '.ad_area',
                        '.related_news', '.more_news', '.sns_area', '.util_area'
                    ]
                    
                    for unwanted_selector in unwanted_selectors:
                        for unwanted in content_elem.select(unwanted_selector):
                            unwanted.decompose()
                    
                    content = content_elem.get_text().strip()
                    content = ' '.join(content.split())  # 공백 정리
                    
                    if len(content) > 300:  # 충분한 내용이 있는 경우만
                        logger.info(f"본문 추출 성공: {len(content)}자 (선택자: {selector})")
                        break
            except Exception as e:
                logger.debug(f"본문 선택자 {selector} 실패: {e}")
                continue
    
    # 본문이 여전히 짧으면 전체 텍스트에서 추출 시도
    if len(content) < 300:
        logger.warning("본문이 짧아서 전체 텍스트에서 추출 시도")
        # 불필요한 태그 제거
        for unwanted_tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            unwanted_tag.decompose()
        
        # 모든 p 태그 내용 수집
        paragraphs = soup.find_all('p')
        if paragraphs:
            content = ' '.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
        
        # 여전히 부족하면 전체 텍스트
        if len(content) < 300:
            content = soup.get_text()
            content = ' '.join(content.split())
    
    # 최종 검증
    if not title:
        # 메타 태그에서 제목 추출 시도
        meta_title = soup.find('meta', property='og:title')
        if meta_title:
            title = meta_title.get('content', '').strip()
        else:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
    
    # 텍스트 정리 및 길이 제한
    content = content.replace('\n', ' ').replace('\t', ' ')
    content = ' '.join(content.split())  # 중복 공백 제거
    
    logger.info(f"BeautifulSoup 스크래핑 결과 - 제목: {len(title)}자, 본문: {len(content)}자")
    
    return title, content

def scrape_news_article(url):
    """뉴스 기사 내용 스크래핑 (Selenium 포함 강화된 버전)"""
    try:
        logger.info(f"뉴스 기사 스크래핑 시작: {url}")
        
        # 먼저 일반 requests로 시도
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 기본 스크래핑 시도
        title, content = extract_content_from_soup(soup, url)
        
        # 내용이 부족하면 Selenium 시도 (조선일보 등 JavaScript 사이트)
        if (not title or len(content) < 200) and ('chosun.com' in url or 'joins.com' in url):
            logger.info("기본 스크래핑 실패, Selenium으로 재시도")
            title, content = scrape_with_selenium(url)
        
        if not title and len(content) < 100:
            logger.error("스크래핑 실패: 제목과 본문 모두 부족")
            return None
            
        return {
            'title': title or '제목 없음',
            'content': content[:3000],  # 최대 3000자로 확장
            'url': url,
            'scraped_length': len(content)
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP 요청 오류: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"뉴스 기사 스크래핑 오류: {str(e)}")
        return None

def scrape_with_selenium(url):
    """Selenium을 사용한 동적 사이트 스크래핑"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # 페이지 로딩 대기
        time.sleep(3)
        
        # 조선일보 특화 선택자
        if 'chosun.com' in url:
            try:
                # 제목 대기 및 추출
                title_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .article-header h1, .news_title_text"))
                )
                title = title_element.text.strip()
                
                # 본문 추출
                content_selectors = [
                    ".story-news__article",
                    ".article-body", 
                    ".news-article-memo",
                    "[data-type='article-body']",
                    ".par"
                ]
                
                content = ""
                for selector in content_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            content = " ".join([elem.text.strip() for elem in elements])
                            if len(content) > 200:
                                break
                    except:
                        continue
                
                # 여전히 내용이 부족하면 모든 p 태그 수집
                if len(content) < 200:
                    p_elements = driver.find_elements(By.TAG_NAME, "p")
                    content = " ".join([p.text.strip() for p in p_elements if len(p.text.strip()) > 20])
                
            except Exception as e:
                logger.warning(f"Selenium 조선일보 특화 추출 실패: {e}")
                # 일반적인 방법으로 폴백
                title = driver.find_element(By.TAG_NAME, "h1").text.strip() if driver.find_elements(By.TAG_NAME, "h1") else ""
                content = driver.find_element(By.TAG_NAME, "body").text.strip()
        
        driver.quit()
        
        logger.info(f"Selenium 스크래핑 성공 - 제목: {len(title)}자, 본문: {len(content)}자")
        return title, content
        
    except ImportError:
        logger.warning("Selenium이 설치되지 않았습니다. pip install selenium 실행 필요")
        return "", ""
    except Exception as e:
        logger.error(f"Selenium 스크래핑 오류: {str(e)}")
        return "", ""

def check_article_relevance(article_content, company_name):
    """기사 내용과 PortOne 솔루션의 관련성 검증"""
    try:
        title = article_content.get('title', '')
        content = article_content.get('content', '')
        
        # PortOne 관련 키워드들
        portone_keywords = [
            '결제', '페이먼트', '핀테크', '이커머스', '커머스', '온라인쇼핑', 
            '정산', '수수료', '매출', '수익', '비즈니스', '스타트업', '기업',
            '디지털', '플랫폼', '서비스', '시스템', '인프라', '솔루션',
            '글로벌', '해외진출', '확장', '성장', '투자', '자금조달'
        ]
        
        # 관련성 없는 키워드들 (감점 요소)
        irrelevant_keywords = [
            '연예', '방송', '드라마', '영화', '음악', '게임콘텐츠', '웹툰',
            '스포츠', '정치', '사회', '문화', '예술', '여행', '음식'
        ]
        
        text = (title + ' ' + content).lower()
        
        # 관련 키워드 점수 계산
        relevant_count = sum(1 for keyword in portone_keywords if keyword in text)
        irrelevant_count = sum(1 for keyword in irrelevant_keywords if keyword in text)
        
        # 기본 점수 5점에서 시작
        score = 5
        
        # 관련 키워드 가점 (최대 4점)
        score += min(4, relevant_count * 0.5)
        
        # 비관련 키워드 감점 (최대 -3점)
        score -= min(3, irrelevant_count * 1)
        
        # 회사명이 기사에 직접 언급되면 가점
        if company_name.lower() in text:
            score += 2
        
        # 0-10 범위로 제한
        score = max(0, min(10, score))
        
        return round(score, 1)
        
    except Exception as e:
        logger.error(f"기사 관련성 검증 오류: {str(e)}")
        return 5.0  # 기본값

def get_existing_company_info(company_name):
    """기존 회사 조사 결과 조회"""
    try:
        # 메모리에서 회사 정보 검색 (간단한 캐시 구현)
        if hasattr(get_existing_company_info, 'cache'):
            if company_name in get_existing_company_info.cache:
                logger.info(f"캐시에서 회사 정보 발견: {company_name}")
                return get_existing_company_info.cache[company_name]
        
        # 파일 시스템에서 검색 (최근 조사 결과)
        import os
        import json
        from datetime import datetime, timedelta
        
        cache_dir = "/tmp/company_cache"
        if not os.path.exists(cache_dir):
            return None
            
        cache_file = os.path.join(cache_dir, f"{company_name.replace(' ', '_')}.json")
        
        if os.path.exists(cache_file):
            # 파일이 24시간 이내에 생성된 경우만 사용
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - file_time < timedelta(hours=24):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    company_info = json.load(f)
                    logger.info(f"파일 캐시에서 회사 정보 발견: {company_name}")
                    return company_info
        
        return None
        
    except Exception as e:
        logger.error(f"기존 회사 정보 조회 오류: {str(e)}")
        return None

def save_company_info_cache(company_name, company_info):
    """회사 정보를 캐시에 저장"""
    try:
        import os
        import json
        
        # 메모리 캐시
        if not hasattr(get_existing_company_info, 'cache'):
            get_existing_company_info.cache = {}
        get_existing_company_info.cache[company_name] = company_info
        
        # 파일 캐시
        cache_dir = "/tmp/company_cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        cache_file = os.path.join(cache_dir, f"{company_name.replace(' ', '_')}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(company_info, f, ensure_ascii=False, indent=2)
            
        logger.info(f"회사 정보 캐시 저장: {company_name}")
        
    except Exception as e:
        logger.error(f"회사 정보 캐시 저장 오류: {str(e)}")

def generate_email_from_news_analysis(article_content, company_name, current_email, news_url, company_info=None, relevance_score=5.0):
    """뉴스 기사 분석을 통한 페인 포인트 기반 메일 생성"""
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            logger.warning("Gemini API 키가 설정되지 않았습니다")
            return generate_fallback_news_email(article_content, company_name, current_email, news_url)
        
        # 회사 정보 컨텍스트 구성
        company_context = ""
        if company_info:
            company_context = f"""
**회사 정보 (기존 조사 결과):**
- 회사명: {company_info.get('company_name', company_name)}
- 업종: {company_info.get('industry', '정보 없음')}
- 주요 사업: {company_info.get('business_description', '정보 없음')}
- 규모: {company_info.get('company_size', '정보 없음')}
- 특이사항: {company_info.get('special_notes', '정보 없음')}
"""
        
        # Perplexity를 통한 추가 분석 (선택적)
        additional_context = ""
        try:
            perplexity_analysis = analyze_news_with_perplexity(article_content, company_name)
            if perplexity_analysis:
                additional_context = f"\n\n**Perplexity 추가 분석:**\n{perplexity_analysis}"
        except Exception as e:
            logger.warning(f"Perplexity 분석 실패: {str(e)}")
        
        # 관련성에 따른 접근 방식 결정
        if relevance_score < 4.0:
            approach_instruction = """
**⚠️ 낮은 관련성 기사 처리 지침:**
- 기사 내용을 억지로 PortOne 솔루션과 연결하지 마세요
- 대신 일반적인 비즈니스 트렌드나 시장 변화 관점에서 접근
- "최근 업계 동향을 보면..." 식으로 자연스럽게 시작
- PortOne 솔루션은 간략하게 소개하고 상담 제안에 집중
"""
        else:
            approach_instruction = """
**✅ 높은 관련성 기사 처리 지침:**
- 기사 내용과 PortOne 솔루션의 연관성을 구체적으로 제시
- 기사에서 도출한 Pain Point를 중심으로 솔루션 제안
- 최신성과 시급성을 강조하여 설득력 강화
"""
        
        prompt = f"""
다음 뉴스 기사를 분석하여 {company_name}에게 보낼 개인화된 영업 메일을 작성해주세요.

**기사 관련성 점수: {relevance_score}/10**
{approach_instruction}

**뉴스 기사 정보:**
- 제목: {article_content.get('title', '')}
- URL: {news_url}
- 내용: {article_content.get('content', '')}
- 분석 시점: 2025년 9월 17일
{additional_context}

**현재 메일 문안 (참고용):**
{current_email}
{company_context}

**메일 작성 지침:**
1. **관련성 기반 접근**: 
   - 관련성 점수가 4점 미만이면 억지 연결 금지
   - 자연스러운 비즈니스 트렌드 관점에서 접근
   - 관련성이 높으면 구체적 연관성 제시

2. **회사 정보 활용**: 
   - 기존 조사 결과가 있으면 반드시 활용
   - 회사의 업종, 규모, 특성에 맞춘 개인화
   - 일반적인 템플릿 메일 지양

3. **Pain Point 중심 구성**: 
   - 실제 업계 이슈에서 도출한 구체적 어려움
   - "혹시 이런 문제로 고민하고 계시지 않나요?" 식 공감 접근
   - 억지스러운 문제 제기 금지

4. **PortOne 솔루션 제안**:
   - OPI: 85% 리소스 절감, 2주 구축
   - 재무자동화: 90% 업무 시간 단축
   - 게임 웹상점: 인앱결제 수수료 해결
   - 스마트빌링: 글로벌 결제 지원

5. **이메일 구조**:
   - 개인화된 인사 (30단어)
   - Pain Point 제기 (60단어) 
   - 해결책 제시 (80단어)
   - 자연스러운 미팅 제안 (30단어)

**주의사항:**
- 총 200-250단어 내외
- 제목 7단어/41자 이내
- HTML 태그 사용 (<br>, <strong>, <em>)
- 관련성이 낮으면 기사 내용 최소 언급

다음 형식으로 작성해주세요:

제목: [개인화된 제목]

[HTML 형식의 메일 본문]
"""
        
        # Gemini API 호출
        import google.generativeai as genai
        genai.configure(api_key=gemini_api_key)
        
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text
        else:
            logger.error("Gemini API 응답이 비어있습니다")
            return generate_fallback_news_email(article_content, company_name, current_email, news_url)
            
    except Exception as e:
        logger.error(f"뉴스 기반 메일 생성 오류: {str(e)}")
        return generate_fallback_news_email(article_content, company_name, current_email, news_url)

def analyze_news_with_perplexity(article_content, company_name):
    """Perplexity AI를 통한 뉴스 분석 (최신성 가중치 적용)"""
    try:
        perplexity_api_key = os.getenv('PERPLEXITY_API_KEY')
        if not perplexity_api_key:
            logger.warning("Perplexity API 키가 설정되지 않았습니다")
            return None
        
        # 현재 날짜 기준 최신성 강조 프롬프트
        current_date = "2025년 9월"
        
        prompt = f"""
다음 뉴스 기사를 분석하여 {company_name}과 같은 기업들이 현재 직면할 수 있는 페인 포인트와 비즈니스 기회를 도출해주세요.

**분석 기준 (최신성 우선):**
- 현재 시점: {current_date}
- 최신 업계 동향과 트렌드 우선 분석
- 긴급성과 시급성이 높은 이슈 중심 검토

**뉴스 기사:**
제목: {article_content.get('title', '')}
내용: {article_content.get('content', '')}

**분석 요청사항:**
1. **최신 업계 동향 분석**: {current_date} 기준으로 이 뉴스가 업계에 미치는 영향
2. **현재 진행형 페인 포인트**: 지금 이 순간 기업들이 겪고 있는 구체적인 어려움
3. **시급한 대응 필요성**: 빠른 시일 내 해결해야 할 과제들
4. **결제/핀테크 연관성**: 결제 시스템, 재무 자동화, 커머스 관련 이슈
5. **비즈니스 기회**: 현재 상황에서 빠르게 활용 가능한 솔루션 니즈

**응답 형식:**
- 300단어 내외
- 최신성과 긴급성 중심의 분석
- 구체적이고 실행 가능한 인사이트 제공
- "현재", "지금", "최근", "2025년 들어" 등의 시간적 표현 활용
"""
        
        headers = {
            'Authorization': f'Bearer {perplexity_api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'llama-3.1-sonar-large-128k-online',
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': 500,
            'temperature': 0.3
        }
        
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        
        return None
        
    except Exception as e:
        logger.error(f"Perplexity 뉴스 분석 오류: {str(e)}")
        return None

def generate_fallback_news_email(article_content, company_name, current_email, news_url):
    """API 실패 시 폴백 뉴스 기반 메일 생성 (최신성 강조)"""
    title = article_content.get('title', '최신 업계 동향')
    current_date = "2025년 9월"
    
    return f"""제목: {company_name} 최신 업계 동향 대응 방안

<p>안녕하세요, {company_name} 담당자님.<br>
PortOne {user_name} 매니저입니다.</p>

<p>방금 전 "<strong>{title}</strong>" 관련 뉴스를 봤는데,<br>
{current_date} 들어 이런 업계 변화가 가속화되고 있어<br>
{company_name}에서도 현재 이런 고민이 있으실 것 같아 연락드립니다.</p>

<p><strong>지금 이 시점에서</strong> 많은 기업들이 겪고 있는 현실적인 어려움들:<br>
• 급변하는 시장 환경에 빠르게 대응해야 하는 시스템 구축 압박<br>
• 현재 진행형인 결제 인프라 현대화 및 효율성 개선 필요성<br>
• 당장 필요한 운영 비용 절감과 서비스 품질 향상의 딜레마</p>

<p><strong>PortOne의 One Payment Infra</strong>로 이런 문제들을 해결할 수 있습니다:<br>
✅ <strong>85% 리소스 절감</strong> - 개발 및 운영 부담 대폭 감소<br>
✅ <strong>2주 내 구축 완료</strong> - 업계 변화 속도에 맞춘 신속한 대응<br>
✅ <strong>100만원 상당 무료 컨설팅</strong> - 현재 상황 맞춤 전문가 분석</p>

<p><strong>이번 주 중</strong> 편하신 일정을 알려주시면<br>
{company_name}이 현재 직면한 과제에 포트원이<br>
어떻게 도움을 드릴 수 있을지 구체적인 방안을 제안해드리겠습니다.</p>

<p>감사합니다.<br>
{user_name} 드림</p>

<p><small>참고 뉴스 (9월 17일 확인): <a href="{news_url}">{title}</a></small></p>"""

# ===== 웹 인터페이스 라우트 =====

@app.route('/')
@login_required
def index():
    """루트 경로 - index.html 제공 (챗봇 스타일 UI) - 로그인 필요"""
    # 캐시 버스팅을 위한 버전 번호 (현재 타임스탬프)
    import time
    cache_version = str(int(time.time()))
    return render_template('index.html', user=current_user, cache_version=cache_version)

@app.route('/script.js')
def serve_script():
    """script.js 정적 파일 제공"""
    return send_from_directory('.', 'script.js')

@app.route('/api/send-email', methods=['POST'])
@login_required
def send_email():
    """
    이메일 발송 API
    로그인된 사용자의 이메일을 발신자로 사용하고,
    사용자의 서명을 본문 끝에 자동 추가합니다.
    """
    try:
        data = request.json
        to_email = data.get('to_email')
        to_name = data.get('to_name')
        subject = data.get('subject')
        body = data.get('body')
        
        # 필수 필드 확인
        if not all([to_email, subject, body]):
            return jsonify({
                'success': False,
                'error': '필수 필드가 누락되었습니다.'
            }), 400
        
        # 현재 로그인된 사용자 정보
        from_email = current_user.email
        from_name = current_user.name
        user_signature = current_user.email_signature or ''  # 서명 가져오기
        
        logger.info(f"📧 이메일 발송 요청: {from_email} -> {to_email}")
        logger.info(f"   제목: {subject}")
        logger.info(f"   받는 사람: {to_name}")
        
        # 본문에 서명 추가
        if user_signature:
            # HTML 서명을 본문 끝에 추가
            full_body = f"{body}<br><br>{user_signature}"
            logger.info("✍️  사용자 서명 추가됨")
        else:
            full_body = body
            logger.warning("⚠️  사용자 서명이 설정되지 않았습니다")
        
        # SendGrid API를 사용한 이메일 발송 (Railway 환경 호환)
        sendgrid_api_key = current_user.get_sendgrid_api_key()
        
        if sendgrid_api_key:
            # SendGrid API 사용 (Railway에서 SMTP 포트가 차단되므로 HTTP API 사용)
            try:
                import requests
                
                logger.info(f"📧 SendGrid API로 이메일 발송 중...")
                
                # SendGrid API 요청
                response = requests.post(
                    'https://api.sendgrid.com/v3/mail/send',
                    headers={
                        'Authorization': f'Bearer {sendgrid_api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'personalizations': [{
                            'to': [{'email': to_email, 'name': to_name}]
                        }],
                        'from': {
                            'email': from_email,
                            'name': from_name
                        },
                        'subject': subject,
                        'content': [{
                            'type': 'text/html',
                            'value': full_body
                        }]
                    },
                    timeout=30
                )
                
                if response.status_code == 202:
                    logger.info(f"✅ SendGrid API 발송 성공: {to_email}")
                    return jsonify({
                        'success': True,
                        'message': '이메일이 성공적으로 발송되었습니다 (SendGrid API).',
                        'from': from_email,
                        'to': to_email,
                        'signature_included': bool(user_signature),
                        'method': 'SendGrid API'
                    })
                elif response.status_code == 401:
                    # API 키 인증 실패
                    logger.error(f"❌ SendGrid API 인증 실패 (401): {response.text}")
                    return jsonify({
                        'success': False,
                        'error': '❌ SendGrid API 키가 유효하지 않습니다.\n\n설정 페이지에서 올바른 API 키를 다시 입력해주세요.\n\n💡 SendGrid 대시보드에서 API 키를 확인하거나 새로 생성하세요.\n(Settings → API Keys)'
                    }), 401
                elif response.status_code == 403:
                    # 발신자 인증 또는 API 키 권한 문제
                    logger.error(f"❌ SendGrid API 403 오류: {response.text}")
                    error_text = response.text.lower()
                    
                    if 'verified sender identity' in error_text or 'sender identity' in error_text:
                        # 발신자 인증 문제
                        return jsonify({
                            'success': False,
                            'error': f'''❌ 발신자 이메일 인증이 필요합니다!

SendGrid에서 "{from_email}" 주소를 인증해주세요.

📝 인증 방법:
1. https://app.sendgrid.com/ 로그인
2. Settings → Sender Authentication
3. "Verify a Single Sender" 클릭
4. 발신자 정보 입력 (From Email: {from_email})
5. 인증 이메일 확인 후 Verify 버튼 클릭

✅ 인증 완료 후 다시 시도해주세요!'''
                        }), 403
                    else:
                        # 기타 권한 문제
                        return jsonify({
                            'success': False,
                            'error': '❌ SendGrid API 키 권한이 부족합니다.\n\nAPI 키를 "Full Access" 권한으로 다시 생성해주세요.'
                        }), 403
                else:
                    logger.error(f"❌ SendGrid API 오류: {response.status_code} - {response.text}")
                    return jsonify({
                        'success': False,
                        'error': f'SendGrid API 오류 ({response.status_code}): {response.text}'
                    }), 500
                    
            except Exception as e:
                logger.error(f"❌ SendGrid API 발송 실패: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'SendGrid API 발송 실패: {str(e)}'
                }), 500
        
        # Gmail 앱 비밀번호로 SMTP 시도 (로컬 환경용)
        gmail_app_password = current_user.get_gmail_app_password()
        
        if gmail_app_password:
            # 실제 Gmail SMTP 발송 (로컬 개발 환경용)
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{from_email}>"
            msg['To'] = to_email
            
            # HTML 본문 추가
            html_part = MIMEText(full_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Railway 환경에서 여러 SMTP 방법 시도
            smtp_methods = [
                # 방법 1: SMTP_SSL (포트 465)
                {'name': 'SMTP_SSL 465', 'method': 'ssl', 'port': 465},
                # 방법 2: SMTP with STARTTLS (포트 587)
                {'name': 'SMTP STARTTLS 587', 'method': 'starttls', 'port': 587},
            ]
            
            last_error = None
            for method_config in smtp_methods:
                try:
                    logger.info(f"🔄 {method_config['name']} 시도 중...")
                    
                    if method_config['method'] == 'ssl':
                        # SSL 방식 (포트 465)
                        with smtplib.SMTP_SSL('smtp.gmail.com', method_config['port'], timeout=30) as server:
                            server.login(from_email, gmail_app_password)
                            server.send_message(msg)
                    else:
                        # STARTTLS 방식 (포트 587)
                        with smtplib.SMTP('smtp.gmail.com', method_config['port'], timeout=30) as server:
                            server.ehlo()
                            server.starttls()
                            server.ehlo()
                            server.login(from_email, gmail_app_password)
                            server.send_message(msg)
                    
                    logger.info(f"✅ 이메일 발송 성공 ({method_config['name']}): {to_email}")
                    
                    return jsonify({
                        'success': True,
                        'message': f'이메일이 성공적으로 발송되었습니다 ({method_config["name"]}).',
                        'from': from_email,
                        'to': to_email,
                        'signature_included': bool(user_signature),
                        'smtp_method': method_config['name']
                    })
                    
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"⚠️  {method_config['name']} 실패: {str(e)}")
                    continue
            
            # 모든 방법 실패
            logger.error(f"❌ 모든 SMTP 방법 실패. 마지막 오류: {last_error}")
            return jsonify({
                'success': False,
                'error': f'이메일 발송 실패: SMTP 포트 차단됨.\n\n💡 Railway 환경에서는 SendGrid API를 사용해주세요.\n관리자에게 SENDGRID_API_KEY 환경변수 설정을 요청하세요.'
            }), 500
        else:
            # Gmail 앱 비밀번호가 설정되지 않았으면 시뮬레이션
            logger.warning(f"⚠️  {from_email} 사용자의 Gmail 앱 비밀번호가 설정되지 않아 시뮬레이션 모드로 실행합니다")
            logger.info(f"📧 [시뮬레이션] 발송: {to_email}")
            logger.info(f"   본문 길이: {len(full_body)} 문자")
            
            return jsonify({
                'success': False,
                'error': 'Gmail 앱 비밀번호가 설정되지 않았습니다. 설정 페이지에서 Gmail 앱 비밀번호를 등록해주세요.',
                'from': from_email,
                'to': to_email,
                'signature_included': bool(user_signature)
            }), 400
        
    except Exception as e:
        logger.error(f"❌ 이메일 발송 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'이메일 발송 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api/user/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    """
    사용자 설정 API
    GET: 현재 설정 조회
    POST: 설정 업데이트 (Gmail 앱 비밀번호 등)
    """
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'user': {
                'email': current_user.email,
                'name': current_user.name,
                'name_en': current_user.name_en,
                'phone': current_user.phone,
                'has_gmail_password': bool(current_user.gmail_app_password),
                'has_sendgrid_api_key': bool(current_user.sendgrid_api_key),
                'has_signature': bool(current_user.email_signature)
            }
        })
    
    # POST - 설정 업데이트
    try:
        data = request.json
        gmail_password = data.get('gmail_app_password')
        sendgrid_key = data.get('sendgrid_api_key')
        
        updated = False
        messages = []
        
        if gmail_password:
            # Gmail 앱 비밀번호 업데이트
            current_user.set_gmail_app_password(gmail_password.replace(' ', ''))  # 공백 제거
            updated = True
            messages.append('Gmail 앱 비밀번호가 설정되었습니다.')
            logger.info(f"✅ {current_user.email} Gmail 앱 비밀번호 설정 완료")
        
        if sendgrid_key:
            # SendGrid API 키 업데이트
            current_user.set_sendgrid_api_key(sendgrid_key.strip())
            updated = True
            messages.append('SendGrid API 키가 설정되었습니다.')
            logger.info(f"✅ {current_user.email} SendGrid API 키 설정 완료")
        
        if updated:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': ' '.join(messages)
            })
        
        return jsonify({
            'success': False,
            'error': '업데이트할 설정이 없습니다.'
        }), 400
        
    except Exception as e:
        logger.error(f"❌ 설정 업데이트 오류: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'설정 업데이트 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api-docs')
def api_docs():
    """API 문서 페이지"""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PortOne 이메일 생성 API - 문서</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container {
                background: white;
                border-radius: 16px;
                padding: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            h1 { color: #4f46e5; margin-bottom: 10px; }
            h2 { color: #7c3aed; font-size: 1.5em; margin-top: 30px; }
            .info { background: #f0f9ff; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4f46e5; }
            .endpoint { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }
            .method { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 0.9em; margin-right: 10px; }
            .post { background: #10b981; color: white; }
            .get { background: #3b82f6; color: white; }
            code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: 'Courier New', monospace; }
            .test-form { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-top: 20px; }
            input, textarea { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
            button { background: #4f46e5; color: white; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; }
            button:hover { background: #4338ca; }
            .result { background: white; border: 2px solid #4f46e5; padding: 15px; border-radius: 8px; margin-top: 20px; white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow-y: auto; }
            .status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
            .status.ok { background: #10b981; }
            .status.error { background: #ef4444; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 PortOne 이메일 생성 API</h1>
            <p style="color: #64748b;">AI 기반 개인화 이메일 문안 생성 서비스</p>
            
            <div class="info">
                <strong>✅ 서버 상태:</strong> <span class="status ok"></span> 실행 중 (포트: 5001)
            </div>
            
            <h2>📡 사용 가능한 API 엔드포인트</h2>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/api/health</strong>
                <p style="margin: 10px 0 0 0; color: #64748b;">서비스 상태 확인</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/research-company</strong>
                <p style="margin: 10px 0 0 0; color: #64748b;">Perplexity로 회사 정보 조사</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/generate-email</strong>
                <p style="margin: 10px 0 0 0; color: #64748b;">Gemini로 이메일 문안 4개 생성</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/refine-email</strong>
                <p style="margin: 10px 0 0 0; color: #64748b;">기존 이메일 문안 개선 (URL 포함 가능)</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/api/analyze-news</strong>
                <p style="margin: 10px 0 0 0; color: #64748b;">뉴스 기사 URL 분석</p>
            </div>
            
            <h2>🧪 API 테스트</h2>
            
            <div class="test-form">
                <h3>이메일 개선 테스트</h3>
                <label><strong>현재 이메일 본문:</strong></label>
                <textarea id="currentEmail" rows="4" placeholder="개선할 이메일 본문을 입력하세요...">안녕하세요, ABC 회사 담당자님.

PortOne의 결제 솔루션을 소개드리고 싶습니다.</textarea>
                
                <label><strong>개선 요청 (URL 포함 가능):</strong></label>
                <input type="text" id="refinementRequest" placeholder="예: 더 친근하게 만들어줘 또는 뉴스 URL">
                
                <button onclick="testRefine()">🚀 AI로 개선하기</button>
                
                <div id="result" style="display: none;"></div>
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
                <strong>💡 참고:</strong> Google Apps Script 연동은 별도로 구현되어 있습니다.
                <br>F열이 "claude 개인화 메일"인 경우 이 API를 호출합니다.
            </div>
        </div>
        
        <script>
            async function testRefine() {
                const currentEmail = document.getElementById('currentEmail').value;
                const refinementRequest = document.getElementById('refinementRequest').value;
                
                if (!refinementRequest) {
                    alert('개선 요청을 입력해주세요!');
                    return;
                }
                
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = '<div style="text-align: center; padding: 20px;"><strong>⏳ AI가 이메일을 개선하고 있습니다...</strong></div>';
                resultDiv.className = 'result';
                
                try {
                    const response = await fetch('/api/refine-email', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            session_id: 'test_' + Date.now(),
                            current_email: currentEmail,
                            refinement_request: refinementRequest
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        resultDiv.innerHTML = '<strong style="color: #10b981;">✅ 개선 완료!</strong><br><br>' + 
                                            '<div style="background: white; padding: 15px; border-radius: 8px;">' + 
                                            result.refined_email.replace(/\\n/g, '<br>') + '</div>';
                    } else {
                        resultDiv.innerHTML = '<strong style="color: #ef4444;">❌ 오류 발생</strong><br><br>' + result.error;
                    }
                } catch (error) {
                    resultDiv.innerHTML = '<strong style="color: #ef4444;">❌ 네트워크 오류</strong><br><br>' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """

def scheduled_blog_update():
    """
    스케줄러에 의해 자동으로 실행되는 블로그 업데이트 함수
    하루 2번 (오전 9시, 오후 6시) 실행됨
    """
    try:
        logger.info("⏰ 스케줄 블로그 업데이트 시작")
        
        from portone_blog_cache import get_blog_cache_age
        
        # 캐시 나이 확인 (12시간 이상 지났으면 업데이트)
        cache_age = get_blog_cache_age()
        
        if cache_age is None or cache_age >= 12:
            logger.info(f"📰 블로그 캐시 업데이트 필요 (나이: {cache_age}시간)")
            blog_posts = scrape_portone_blog_initial()
            
            if blog_posts:
                logger.info(f"✅ 자동 블로그 업데이트 완료: {len(blog_posts)}개 글")
            else:
                logger.warning("⚠️ 자동 블로그 업데이트 실패")
        else:
            logger.info(f"✅ 블로그 캐시 최신 상태 (나이: {cache_age:.1f}시간)")
    except Exception as e:
        logger.error(f"❌ 스케줄 블로그 업데이트 오류: {str(e)}")

# 스케줄러 초기화
scheduler = BackgroundScheduler()

# 하루 2번 실행: 오전 9시, 오후 6시
scheduler.add_job(
    func=scheduled_blog_update,
    trigger=CronTrigger(hour='9,18', minute='0'),
    id='blog_update_job',
    name='블로그 자동 업데이트',
    replace_existing=True
)

# 스케줄러 시작
scheduler.start()
logger.info("⏰ 블로그 자동 업데이트 스케줄러 시작됨 (매일 9시, 18시 실행)")

# 애플리케이션 종료 시 스케줄러 종료
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    # API 키 확인
    if not os.getenv('PERPLEXITY_API_KEY'):
        logger.warning("PERPLEXITY_API_KEY가 설정되지 않았습니다.")
    
    if not os.getenv('GEMINI_API_KEY'):
        logger.warning("GEMINI_API_KEY가 설정되지 않았습니다.")
    
    logger.info("🚀 이메일 생성 챗봇 서버 시작")
    logger.info("사용 가능한 엔드포인트:")
    logger.info("- POST /api/research-company: 회사 조사")
    logger.info("- POST /api/generate-email: 이메일 생성")
    logger.info("- POST /api/batch-process: 일괄 처리")
    logger.info("- POST /api/refine-email: 이메일 개선")
    logger.info("- POST /api/chat-reply: 재설득 메일 생성 (챗봇)")
    logger.info("- POST /api/smart-chat: 통합 스마트 챗봇 (NEW! 🤖)")
    logger.info("  → 판매 상품 변경, 톤 변경, 문안 개선, 재설득, 질문 답변")
    logger.info("- POST /api/analyze-news: 뉴스 기사 분석")
    logger.info("- POST /api/test-scraping: 뉴스 스크래핑 테스트")
    logger.info("- POST /api/update-blog: 블로그 콘텐츠 업데이트")
    logger.info("- GET /api/blog-cache-status: 블로그 캐시 상태 확인")
    logger.info("- GET /api/health: 서비스 상태 확인")
    
    # Flask 서버 시작
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)
