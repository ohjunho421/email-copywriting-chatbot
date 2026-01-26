"""
포트원 블로그 콘텐츠 데이터베이스 시스템 (PostgreSQL)
SQLite 대신 PostgreSQL을 사용하여 Railway에서 영구 저장
"""

from datetime import datetime
import logging
import json
from collections import Counter
from flask import has_app_context
import requests

logger = logging.getLogger(__name__)

def verify_url_exists(url, timeout=3):
    """
    URL이 실제로 접근 가능한지 확인 (HEAD 요청)
    
    Args:
        url: 확인할 URL
        timeout: 타임아웃 (초)
    
    Returns:
        bool: URL이 접근 가능하면 True, 아니면 False
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return True
        # 404나 다른 에러
        logger.warning(f"❌ URL 접근 실패 ({response.status_code}): {url}")
        return False
    except Exception as e:
        logger.warning(f"❌ URL 접근 오류: {url} - {str(e)}")
        return False

# 모듈 레벨에서 import (app context 체크 포함)
def get_db():
    """Flask app의 db 객체 가져오기 (app context 필수)"""
    if not has_app_context():
        raise RuntimeError("This function requires Flask app context. Call within 'with app.app_context():'")
    from models import db
    return db

def get_blog_post_model():
    """BlogPost 모델 가져오기 (app context 필수)"""
    if not has_app_context():
        raise RuntimeError("This function requires Flask app context. Call within 'with app.app_context():'")
    from models import BlogPost
    return BlogPost

def get_metadata_model():
    """BlogCacheMetadata 모델 가져오기 (app context 필수)"""
    if not has_app_context():
        raise RuntimeError("This function requires Flask app context. Call within 'with app.app_context():'")
    from models import BlogCacheMetadata
    return BlogCacheMetadata

def init_db():
    """데이터베이스 초기화 (SQLAlchemy가 자동으로 처리)"""
    # Flask app context에서 db.create_all()이 호출되므로
    # 여기서는 특별한 작업 불필요
    logger.info("✅ 블로그 데이터베이스 초기화 완료 (PostgreSQL)")
    return True

def save_blog_cache(blog_posts, replace_all=True):
    """
    블로그 포스트를 PostgreSQL 데이터베이스에 저장
    
    Args:
        blog_posts: 블로그 포스트 리스트 (dict)
        replace_all: True면 기존 포스트 전체 삭제 후 저장, False면 추가/업데이트만
    
    Returns:
        bool: 성공 여부
    """
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        BlogCacheMetadata = get_metadata_model()
        
        # replace_all이 True면 기존 포스트 삭제
        if replace_all:
            db.session.query(BlogPost).delete()
            logger.info("🗑️ 기존 블로그 포스트 전체 삭제")
        
        # 새 포스트 삽입 또는 업데이트
        inserted_count = 0
        updated_count = 0
        
        for post in blog_posts:
            link = post.get('link', '')
            if not link:
                continue
            
            # 기존 포스트 확인 (link로 중복 체크)
            existing_post = db.session.query(BlogPost).filter_by(link=link).first()
            
            if existing_post:
                # 업데이트
                existing_post.title = post.get('title', '')
                existing_post.summary = post.get('summary', '')
                existing_post.content = post.get('content', '')
                existing_post.category = post.get('category', '')
                existing_post.keywords = post.get('keywords', '')
                existing_post.industry_tags = post.get('industry_tags', '')
                existing_post.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # 새 포스트 삽입
                new_post = BlogPost(
                    title=post.get('title', ''),
                    link=link,
                    summary=post.get('summary', ''),
                    content=post.get('content', ''),
                    category=post.get('category', ''),
                    keywords=post.get('keywords', ''),
                    industry_tags=post.get('industry_tags', ''),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_post)
                inserted_count += 1
        
        # 커밋
        db.session.commit()
        
        # 전체 개수 확인
        total_count = db.session.query(BlogPost).count()
        
        # 메타데이터 업데이트
        metadata = db.session.query(BlogCacheMetadata).first()
        if metadata:
            metadata.last_updated = datetime.utcnow()
            metadata.posts_count = total_count
        else:
            metadata = BlogCacheMetadata(
                last_updated=datetime.utcnow(),
                posts_count=total_count
            )
            db.session.add(metadata)
        
        db.session.commit()
        
        logger.info(f"✅ 블로그 DB 저장 완료: 신규 {inserted_count}개, 업데이트 {updated_count}개, 총 {total_count}개 (PostgreSQL)")
        return True
        
    except Exception as e:
        logger.error(f"블로그 DB 저장 오류: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def load_blog_cache():
    """
    PostgreSQL 데이터베이스에서 블로그 포스트 로드
    
    Returns:
        list: 블로그 포스트 리스트 (dict)
    """
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        
        # 최신 글부터 조회
        posts_query = db.session.query(BlogPost).order_by(BlogPost.created_at.desc()).all()
        
        if not posts_query:
            logger.info("📝 블로그 DB에 데이터 없음 (PostgreSQL)")
            return None
        
        # dict 형태로 변환
        posts = []
        for post in posts_query:
            posts.append({
                'title': post.title,
                'link': post.link,
                'summary': post.summary,
                'content': post.content,
                'category': post.category,
                'keywords': post.keywords,
                'industry_tags': post.industry_tags,
                'created_at': post.created_at.isoformat() if post.created_at else None
            })
        
        logger.info(f"📚 블로그 DB 로드 완료: {len(posts)}개 글 (PostgreSQL)")
        return posts
        
    except Exception as e:
        logger.error(f"블로그 DB 로드 오류: {str(e)}")
        return None

def get_blog_cache_age():
    """
    데이터베이스의 업데이트 시간 확인
    
    Returns:
        float: 캐시 나이 (시간 단위) 또는 None
    """
    try:
        db = get_db()
        BlogCacheMetadata = get_metadata_model()
        
        metadata = db.session.query(BlogCacheMetadata).first()
        
        if not metadata or not metadata.last_updated:
            return None
        
        age_hours = (datetime.utcnow() - metadata.last_updated).total_seconds() / 3600
        return age_hours
        
    except Exception as e:
        logger.error(f"캐시 시간 확인 오류: {str(e)}")
        return None

# 🆕 알려진 고객사 → 업종 매핑 (블로그 사례에서 추출)
KNOWN_CUSTOMER_INDUSTRIES = {
    # 게임
    '넥슨': '게임', '엔씨소프트': '게임', 'nc': '게임', '넷마블': '게임', '크래프톤': '게임',
    '카카오게임즈': '게임', '스마일게이트': '게임', '펄어비스': '게임', '컴투스': '게임',
    '데브시스터즈': '게임', '쿠키런': '게임', '슈퍼셀': '게임', '라이엇': '게임',
    
    # 이커머스/쇼핑
    '무신사': '패션', '29cm': '패션', 'w컨셉': '패션', '지그재그': '패션', '에이블리': '패션',
    '브랜디': '패션', '하이버': '패션', '오늘의집': '이커머스', '마켓컬리': '푸드', '컬리': '푸드',
    '쿠팡': '이커머스', '11번가': '이커머스', 'ssg': '이커머스', '롯데온': '이커머스',
    '티몬': '이커머스', '위메프': '이커머스', '인터파크': '이커머스',
    
    # 뷰티
    '올리브영': '뷰티', '아모레퍼시픽': '뷰티', 'lg생활건강': '뷰티', '이니스프리': '뷰티',
    '에뛰드': '뷰티', '토니모리': '뷰티', '미샤': '뷰티', '더페이스샵': '뷰티',
    '화해': '뷰티', '글로우픽': '뷰티',
    
    # 자동차/모빌리티
    '현대자동차': '자동차', '기아': '자동차', '현대차': '자동차', '제네시스': '자동차',
    '쏘카': '자동차', '타다': '자동차', '카카오모빌리티': '자동차', '티맵모빌리티': '자동차',
    
    # 여행
    '야놀자': '여행', '여기어때': '여행', '마이리얼트립': '여행', '클룩': '여행',
    '인터파크투어': '여행', '하나투어': '여행', '모두투어': '여행', '트립닷컴': '여행',
    '아고다': '여행', '에어비앤비': '여행', '익스피디아': '여행',
    
    # 교육
    '메가스터디': '교육', '대성마이맥': '교육', '에듀윌': '교육', '클래스101': '교육',
    '탈잉': '교육', '크몽': '교육', '패스트캠퍼스': '교육', '인프런': '교육',
    '노마드코더': '교육', '코드잇': '교육',
    
    # 금융
    '토스': '금융', '카카오뱅크': '금융', '케이뱅크': '금융', '뱅크샐러드': '금융',
    '핀다': '금융', '렌딧': '금융', '8퍼센트': '금융', '피플펀드': '금융',
    
    # 미디어/콘텐츠
    '왓챠': '미디어', '웨이브': '미디어', '티빙': '미디어', '시즌': '미디어',
    '멜론': '미디어', '지니뮤직': '미디어', '플로': '미디어', '밀리의서재': '미디어',
    '리디북스': '미디어', '리디': '미디어',
    
    # SaaS/B2B
    '토스페이먼츠': 'SaaS', '채널톡': 'SaaS', '센드버드': 'SaaS', '스티비': 'SaaS',
    '노션': 'SaaS', '슬랙': 'SaaS', '잔디': 'SaaS', '플렉스': 'SaaS', '시프티': 'SaaS',
    
    # 물류/배달
    '배달의민족': '푸드', '요기요': '푸드', '쿠팡이츠': '푸드',
    'cj대한통운': '물류', '한진': '물류', '롯데택배': '물류', '로젠택배': '물류',
    
    # 플랫폼
    '카카오': '플랫폼', '네이버': '플랫폼', '라인': '플랫폼', '당근마켓': '플랫폼',
    '번개장터': '리셀', '중고나라': '리셀', '크림': '리셀',
    
    # 헬스케어
    '굿닥': '헬스케어', '똑닥': '헬스케어', '닥터나우': '헬스케어', '휴레이포지티브': '헬스케어',
    
    # 부동산
    '직방': '부동산', '다방': '부동산', '호갱노노': '부동산', '집토스': '부동산',
}


def extract_case_companies_from_blog(content, title=''):
    """
    블로그 내용에서 고객사례로 언급된 회사명과 업종을 추출
    
    Args:
        content: 블로그 본문
        title: 블로그 제목
        
    Returns:
        list: [{'company': '회사명', 'industry': '업종'}, ...]
    """
    found_companies = []
    text = (title + ' ' + content).lower()
    
    for company, industry in KNOWN_CUSTOMER_INDUSTRIES.items():
        if company.lower() in text:
            found_companies.append({
                'company': company,
                'industry': industry
            })
    
    return found_companies


def extract_keywords_from_post(post):
    """
    블로그 글에서 키워드 추출 (규칙 기반 + 고객사례 분석)
    
    Args:
        post: 블로그 포스트 dict
    
    Returns:
        tuple: (keywords, industry_tags)
    """
    try:
        content = post.get('content', '')
        title = post.get('title', '')
        
        if not content or len(content) < 50:
            return '', ''
        
        # 키워드 초기화
        keywords = []
        industry_tags = []
        
        # 제목과 내용에서 주요 키워드 찾기
        text_lower = (title + ' ' + content[:2000]).lower()
        
        # 🆕 고객사례에서 회사명 추출 → 업종 파악
        case_companies = extract_case_companies_from_blog(content, title)
        if case_companies:
            keywords.append('고객사례')
            for case in case_companies:
                if case['industry'] not in industry_tags:
                    industry_tags.append(case['industry'])
            logger.debug(f"블로그에서 고객사 발견: {[c['company'] for c in case_companies]}")
        
        # 업종 관련 키워드 (확장)
        industry_mapping = {
            '게임': ['게임', 'game', '인앱결제', 'd2c', '웹상점', '앱스토어', '구글플레이'],
            '이커머스': ['이커머스', 'e커머스', '쇼핑몰', 'commerce', '온라인몰', '마켓플레이스', '커머스', '리테일'],
            '여행': ['여행', 'travel', '항공', '호텔', '숙박', '예약', 'ota'],
            '교육': ['교육', 'education', '에듀테크', '학원', '강의', '온라인교육'],
            '금융': ['금융', 'fintech', '핀테크', '보험', '대출', '투자'],
            '미디어': ['미디어', 'media', '콘텐츠', 'ott', '스트리밍', '구독'],
            'SaaS': ['saas', '구독서비스', 'subscription', '소프트웨어', 'b2b'],
            '물류': ['물류', 'logistics', '배송', '배달', '풀필먼트'],
            '플랫폼': ['플랫폼', 'platform', '중개', '마켓', '파트너정산'],
            '패션': ['패션', 'fashion', '의류', '브랜드', '리셀'],
            '푸드': ['음식', 'food', '식품', 'f&b', '레스토랑', '배달'],
            '자동차': ['자동차', '차량', 'automotive', '모빌리티'],
            '뷰티': ['뷰티', '화장품', '코스메틱', 'beauty', '스킨케어'],
            '헬스케어': ['의료', '병원', '헬스', '건강', '제약'],
            '부동산': ['부동산', '건물', '임대', '분양'],
            '리셀': ['리셀', '중고', '세컨핸드', '빈티지']
        }
        
        for industry, keywords_list in industry_mapping.items():
            if any(kw in text_lower for kw in keywords_list):
                if industry not in industry_tags:
                    industry_tags.append(industry)
        
        # 기능/혜택 관련 키워드 (확장)
        benefit_mapping = {
            '수수료절감': ['수수료', '비용절감', '절감', '할인', '저렴', '15%', '30%'],
            '결제연동': ['결제', 'payment', 'pg연동', 'api', 'sdk'],
            '정산자동화': ['정산', '매출', '대사', '자동화', '재무', '마감'],
            'PG통합': ['pg', '간편결제', '멀티pg', '복수pg', '25개'],
            '글로벌': ['해외', 'global', '글로벌', '해외결제', '환율'],
            '정기결제': ['정기결제', 'subscription', '빌링키', '구독결제'],
            '리스크관리': ['장애', '백업', '라우팅', '리스크', '안정성'],
            '개발효율': ['개발', '리소스', '2주', '85%', '효율']
        }
        
        for benefit, keywords_list in benefit_mapping.items():
            if any(kw in text_lower for kw in keywords_list):
                keywords.append(benefit)
        
        # 고객사례 여부 확인 (이미 위에서 체크했지만, 키워드 기반도 추가)
        if '고객사례' not in keywords:
            if any(kw in text_lower for kw in ['고객사', '도입사례', '성공사례', '인터뷰', '케이스']):
                keywords.append('고객사례')
        
        # 구체적 수치 포함 여부
        import re
        if re.search(r'\d+%|\d+억|\d+만원|\d+배', text_lower):
            keywords.append('정량적효과')
        
        return ','.join(keywords), ','.join(industry_tags)
        
    except Exception as e:
        logger.error(f"키워드 추출 오류: {str(e)}")
        return '', ''


def analyze_blog_with_ai(post, gemini_model=None):
    """
    Gemini AI로 블로그 내용 심층 분석 (선택적 사용)
    
    Args:
        post: 블로그 포스트 dict
        gemini_model: Gemini 모델 객체
    
    Returns:
        dict: 분석 결과 (target_industry, benefits, case_company, summary)
    """
    if not gemini_model:
        return None
    
    try:
        content = post.get('content', '')[:3000]
        title = post.get('title', '')
        
        prompt = f"""다음 포트원 블로그 글을 분석해서 JSON으로 응답해주세요.

제목: {title}
내용: {content}

분석 항목:
1. target_industry: 이 글이 타겟으로 하는 업종 (게임, 이커머스, 여행, 교육, 금융, SaaS, 물류, 플랫폼, 일반 중 택1)
2. main_benefit: 주요 혜택/가치 (수수료절감, 개발효율, 정산자동화, 글로벌진출, 안정성 중 택1)
3. case_company: 언급된 고객사 이름 (없으면 빈 문자열)
4. one_line_summary: 한 줄 요약 (30자 이내)
5. quantitative_results: 정량적 성과 수치 (예: "수수료 15% 절감", 없으면 빈 문자열)

JSON 형식으로만 응답:
{{"target_industry": "", "main_benefit": "", "case_company": "", "one_line_summary": "", "quantitative_results": ""}}
"""
        
        response = gemini_model.generate_content(prompt)
        result = response.text.strip()
        
        # JSON 파싱
        import json
        if result.startswith('```'):
            result = result.split('```')[1]
            if result.startswith('json'):
                result = result[4:]
        
        return json.loads(result)
        
    except Exception as e:
        logger.error(f"AI 블로그 분석 오류: {str(e)}")
        return None


def reanalyze_all_blog_tags():
    """
    기존 블로그 데이터의 업종태그와 키워드를 재분석하여 업데이트
    업종태그가 비어있는 블로그에 대해 내용 기반으로 태그 추출
    """
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        
        all_posts = db.session.query(BlogPost).all()
        updated_count = 0
        
        for post in all_posts:
            # 현재 데이터로 재분석
            post_data = {
                'title': post.title or '',
                'content': post.content or '',
                'summary': post.summary or ''
            }
            
            # 키워드와 업종태그 재추출
            new_keywords, new_industry_tags = extract_keywords_from_post(post_data)
            
            # 업데이트가 필요한 경우에만 업데이트
            needs_update = False
            
            # 업종태그가 비어있는데 새로 추출된 태그가 있으면 업데이트
            if not post.industry_tags and new_industry_tags:
                post.industry_tags = new_industry_tags
                needs_update = True
            
            # 키워드가 비어있거나 더 풍부해지면 업데이트
            if new_keywords and (not post.keywords or len(new_keywords) > len(post.keywords or '')):
                post.keywords = new_keywords
                needs_update = True
            
            if needs_update:
                updated_count += 1
                logger.info(f"📝 블로그 태그 업데이트: {post.title[:30]}... → 업종: {post.industry_tags}, 키워드: {post.keywords}")
        
        db.session.commit()
        logger.info(f"✅ 블로그 태그 재분석 완료: {updated_count}/{len(all_posts)}개 업데이트됨")
        return updated_count
        
    except Exception as e:
        logger.error(f"블로그 태그 재분석 오류: {str(e)}")
        return 0


def get_relevant_blog_posts_by_industry(company_info, max_posts=3, service_type=None, pain_points=None):
    """
    회사 정보와 Pain Point를 기반으로 관련 블로그 글 조회 (PostgreSQL)
    
    Args:
        company_info: 회사 정보 딕셔너리
        max_posts: 최대 반환 글 수
        service_type: 서비스 타입 ('OPI', 'Recon', 'Prism', 'PS' 등)
        pain_points: Pain Point 키워드 리스트 (예: ['구독결제', 'PG관리', '정산'])
    
    Returns:
        list: 관련 블로그 글 리스트
    """
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        
        # 회사 정보에서 검색 키워드 추출
        industry = company_info.get('industry', '')
        category = company_info.get('category', '')
        description = company_info.get('description', '')
        
        search_terms = []
        if industry:
            search_terms.append(industry)
        if category:
            search_terms.append(category)
        
        # Pain Point 키워드 추가 (최우선)
        pain_point_terms = []
        if pain_points:
            pain_point_terms.extend(pain_points)
            logger.info(f"🎯 Pain Point 키워드: {', '.join(pain_points)}")
        
        # 설명에서 키워드 추출
        if description:
            desc_lower = description.lower()
            for keyword in ['게임', 'game', '이커머스', '쇼핑몰', '여행', 'travel', '교육', 'education', '금융', 'fintech']:
                if keyword in desc_lower:
                    search_terms.append(keyword)
        
        from sqlalchemy import or_
        
        # 두 단계 검색: 1) Pain Point 매칭 우선 2) 업종 매칭
        all_posts = []
        seen_ids = set()
        
        # 1단계: Pain Point 키워드로 검색 (최우선)
        if pain_point_terms:
            pain_query = db.session.query(BlogPost)
            if service_type:
                pain_query = pain_query.filter(BlogPost.category == service_type)
            
            pain_pattern = f"%{'%'.join(pain_point_terms)}%"
            pain_query = pain_query.filter(
                or_(
                    BlogPost.keywords.like(pain_pattern),
                    BlogPost.title.like(pain_pattern),
                    BlogPost.content.like(pain_pattern)
                )
            )
            
            pain_posts = pain_query.order_by(BlogPost.created_at.desc()).limit(max_posts).all()
            for post in pain_posts:
                if post.id not in seen_ids:
                    all_posts.append(post)
                    seen_ids.add(post.id)
                    logger.info(f"  ✅ Pain Point 매칭: {post.title[:50]}...")
        
        # 2단계: 업종 키워드로 검색 (Pain Point 매칭 후 부족하면 채우기)
        remaining_count = max_posts - len(all_posts)
        if remaining_count > 0 and search_terms:
            industry_query = db.session.query(BlogPost)
            if service_type:
                industry_query = industry_query.filter(BlogPost.category == service_type)
            
            search_pattern = f"%{'%'.join(search_terms)}%"
            industry_query = industry_query.filter(
                or_(
                    BlogPost.industry_tags.like(search_pattern),
                    BlogPost.keywords.like(search_pattern),
                    BlogPost.title.like(search_pattern),
                    BlogPost.content.like(search_pattern)
                )
            )
            
            industry_posts = industry_query.order_by(BlogPost.created_at.desc()).limit(remaining_count).all()
            for post in industry_posts:
                if post.id not in seen_ids:
                    all_posts.append(post)
                    seen_ids.add(post.id)
        
        posts_query = all_posts
        
        service_label = f"[{service_type}] " if service_type else ""
        
        if not posts_query:
            if search_terms:
                logger.info(f"🔍 {service_label}'{', '.join(search_terms)}' 관련 블로그 글 없음")
            else:
                logger.info(f"🔍 {service_label}블로그 글 없음")
            return []
        
        # dict 형태로 변환
        posts = []
        for post in posts_query:
            posts.append({
                'title': post.title,
                'link': post.link,
                'summary': post.summary,
                'content': post.content,
                'category': post.category,
                'keywords': post.keywords,
                'industry_tags': post.industry_tags
            })
        
        if search_terms:
            logger.info(f"✅ {service_label}'{', '.join(search_terms)}' 관련 블로그 글 {len(posts)}개 조회 (PostgreSQL)")
        else:
            logger.info(f"✅ {service_label}블로그 글 {len(posts)}개 조회 (PostgreSQL)")
        
        return posts
        
    except Exception as e:
        logger.error(f"업종별 블로그 조회 오류: {str(e)}")
        return []

def get_best_blog_for_email_mention(company_info, research_data=None, max_check=50, competitors=None, service_type=None):
    """
    이메일 본문에 언급할 가장 적합한 블로그 1개 선택
    
    선택 기준 (우선순위):
    1. 경쟁사 사례 블로그 (가장 설득력 있음)
    2. 동일 업종의 유사 기업 사례
    3. 관련 산업의 해결 사례
    4. 받을 수 있는 혜택(수수료 절감, 자동화 등)과 관련된 정보
    
    Args:
        company_info: 회사 정보 딕셔너리
        research_data: 조사 결과 딕셔너리 (pain_points 등)
        max_check: 확인할 최대 블로그 수
        competitors: 경쟁사 리스트 (문자열 또는 리스트)
        service_type: 서비스 유형 ('OPI', 'PS', 'Recon' 등) - 해당 카테고리 블로그만 매칭
    
    Returns:
        dict or None: 선택된 블로그 정보 (title, link, summary, match_reason)
    """
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        
        # 회사 정보에서 검색 키워드 추출
        industry = company_info.get('industry', '') or ''
        category = company_info.get('category', '') or ''
        description = company_info.get('description', '') or ''
        company_name = company_info.get('company_name', '') or company_info.get('회사명', '') or ''
        
        # research_data에서 pain_points, company_info 추출
        pain_points = ''
        research_company_info = ''
        if research_data:
            pain_points = research_data.get('pain_points', '') or ''
            research_company_info = research_data.get('company_info', '') or ''
        
        # 경쟁사 리스트 처리
        competitor_list = []
        if competitors:
            if isinstance(competitors, str):
                # 쉼표, 슬래시, 공백으로 분리
                import re
                competitor_list = [c.strip().lower() for c in re.split(r'[,/\s]+', competitors) if c.strip() and len(c.strip()) > 1]
            elif isinstance(competitors, list):
                competitor_list = [c.lower() for c in competitors if c and len(c) > 1]
        
        logger.info(f"🔍 블로그 매칭 - 경쟁사 리스트: {competitor_list}")
        
        # 모든 텍스트 합치기 (뉴스 기사 포함)
        news_content = research_data.get('news_summary', '') or research_data.get('news', '') or '' if research_data else ''
        all_text = f"{company_name} {industry} {category} {description} {pain_points} {research_company_info} {news_content}".lower()
        
        # 🆕 뉴스 기사에서 회사의 '의도/계획' 파악 → 시나리오 매칭
        # ⚠️ 의도 매칭은 최우선! 점수를 크게 높여 확실히 선택되도록 함
        intent_scenarios = {
            '글로벌진출': {
                'keywords': ['해외진출', '일본진출', '글로벌', '해외시장', '수출', '미국진출', '동남아', '중국진출', '크로스보더', '현지화', '해외매출', '글로벌확장', 'uae', '베트남', '태국', '인도네시아', '싱가포르', '해외', '다국가'],
                'blog_keywords': ['글로벌', '해외', 'global', '일본', '크로스보더', '우커머스', 'woocommerce'],
                'score': 100  # 🔥 의도 매칭은 최우선 (다른 매칭보다 확실히 높게)
            },
            '구독서비스': {
                'keywords': ['구독', '정기결제', '멤버십', 'saas', 'ott', '월정액', '구독모델', '정기배송', '구독경제'],
                'blog_keywords': ['빌링키', '구독', '정기결제', 'subscription'],
                'score': 100
            },
            '정산개선': {
                'keywords': ['정산', '매출관리', '재무', '회계', '대사', '마감', 'erp', '자동화', '효율화'],
                'blog_keywords': ['정산', '매출', '자동화', '대사', '마감'],
                'score': 100
            },
            '결제연동': {
                'keywords': ['결제도입', 'pg연동', '결제시스템', '결제수단', '간편결제', '페이', '결제솔루션'],
                'blog_keywords': ['결제', 'pg', '연동', 'api'],
                'score': 80
            },
            '비용절감': {
                'keywords': ['수수료', '비용절감', '원가', '효율', '인앱결제', '수수료인하'],
                'blog_keywords': ['수수료', '절감', '30%', '비용'],
                'score': 80
            }
        }
        
        # 뉴스에서 파악된 의도 찾기
        detected_intents = []
        for intent_name, intent_info in intent_scenarios.items():
            for kw in intent_info['keywords']:
                if kw in all_text:
                    detected_intents.append(intent_name)
                    break
        
        if detected_intents:
            logger.info(f"📰 뉴스 기사에서 파악된 회사 의도: {detected_intents}")
        
        # 🆕 확장된 산업 키워드 매칭 (더 세분화)
        industry_keywords = {
            # IT/테크
            '게임': ['게임', 'game', '인앱결제', 'd2c', '웹상점', '앱스토어', '구글플레이', '스팀'],
            'SaaS': ['saas', 'b2b', '소프트웨어', '클라우드', '솔루션', '플랫폼서비스'],
            'IT서비스': ['it', '테크', 'tech', '소프트웨어', '개발', '스타트업'],
            
            # 커머스
            '이커머스': ['이커머스', 'e커머스', '쇼핑몰', '커머스', '온라인몰', '마켓플레이스', '온라인쇼핑'],
            '리셀/중고': ['리셀', '중고', '세컨핸드', '빈티지', '번개장터', '당근'],
            '패션': ['패션', 'fashion', '의류', '브랜드', '옷', '신발', '액세서리'],
            '뷰티': ['뷰티', '화장품', '코스메틱', 'beauty', '스킨케어', '메이크업'],
            
            # 여행/숙박
            '여행': ['여행', 'travel', '항공', '호텔', '숙박', '예약', 'ota', '투어'],
            
            # 교육
            '교육': ['교육', 'education', '에듀테크', '학원', '강의', '온라인강의', '이러닝'],
            
            # 금융
            '금융': ['금융', 'fintech', '핀테크', '보험', '대출', '투자', '증권', '은행'],
            
            # 미디어/콘텐츠
            '미디어': ['미디어', 'media', '콘텐츠', 'ott', '스트리밍', '영상', '뉴스'],
            '엔터테인먼트': ['엔터', '연예', '공연', '티켓', '콘서트', '영화'],
            
            # 물류/배송
            '물류': ['물류', 'logistics', '배송', '배달', '풀필먼트', '택배'],
            '푸드': ['음식', 'food', '식품', 'f&b', '레스토랑', '배달', '식자재'],
            
            # 플랫폼
            '플랫폼': ['플랫폼', 'platform', '중개', '마켓', '파트너정산'],
            
            # 제조/산업
            '자동차': ['자동차', '차량', 'automotive', '모빌리티', '카', '오토'],
            '제조': ['제조', 'manufacturing', '공장', '생산', '부품'],
            
            # 헬스케어
            '헬스케어': ['의료', '병원', '헬스', '건강', '제약', '바이오'],
            
            # 부동산
            '부동산': ['부동산', '건물', '임대', '분양', '중개'],
            
            # 글로벌
            '글로벌': ['해외', '글로벌', 'global', '수출', '해외진출', '크로스보더']
        }
        
        # 🆕 상호 배타적 업종 그룹 (이 그룹 내 다른 업종 블로그는 추천 안함)
        exclusive_groups = [
            ['자동차', '제조'],  # 제조업
            ['뷰티', '패션'],     # 소비재
            ['헬스케어'],         # 의료
            ['부동산'],           # 부동산
            ['금융'],             # 금융
        ]
        
        # 혜택 키워드 매칭 (세일즈 시나리오별 강화)
        benefit_keywords = {
            # 🌏 글로벌 진출 시나리오
            '글로벌': ['해외', '글로벌', 'global', '해외결제', '환율', '크로스보더', '일본', '동남아', '미국', '중국', 'paypay', 'alipay', '진출', '수출'],
            # 🔄 구독 서비스 시나리오
            '구독': ['구독', 'saas', '멤버십', '정기결제', '빌링키', '빌링', 'ott', '정기배송', '월정액', '연간구독'],
            # 1️⃣ 단일/복수 PG 시나리오
            '수수료절감': ['수수료', '비용', '절감', '할인', '저렴', '15%', '30%', '단일pg', '멀티pg', '복수pg'],
            '정산': ['정산', '매출', '재무', '회계', '대사', '대시보드', '통합관리', '자동대사'],
            # 공통
            '자동화': ['자동화', '자동', '효율', '리소스', '시간절약', '90%', '단축'],
            '안정성': ['안정', '장애', '리스크', '백업', '라우팅', '스마트라우팅', '자동전환', '이탈률'],
            '개발효율': ['개발', 'api', 'sdk', '연동', '2주', '85%', '구축']
        }
        
        # 회사에 해당하는 산업 찾기
        matched_industries = []
        for ind, keywords in industry_keywords.items():
            for kw in keywords:
                if kw in all_text:
                    matched_industries.append(ind)
                    break
        
        # 관심 혜택 찾기
        matched_benefits = []
        for benefit, keywords in benefit_keywords.items():
            for kw in keywords:
                if kw in all_text:
                    matched_benefits.append(benefit)
                    break
        
        logger.info(f"🎯 블로그 선택 - 회사: {company_name}, 매칭된 산업: {matched_industries}, 혜택: {matched_benefits}")
        
        # 🆕 회사의 배타적 그룹 찾기
        company_exclusive_group = None
        for group in exclusive_groups:
            if any(ind in matched_industries for ind in group):
                company_exclusive_group = group
                break
        
        from sqlalchemy import or_
        
        # 🆕 서비스 유형별 블로그 URL 패턴 필터링
        # OPI: 결제 연동/PG 관련
        # PS: 플랫폼 정산 (파트너 정산) - /ps_ 경로
        # Recon: 매출 마감/정산 조회 - /co- 경로 (Company 사례)
        service_url_patterns = {
            # OPI: 결제 연동/PG 관련 + 글로벌 결제
            'OPI': ['/opi_', '/payment_', '/pgcompare', '/onboarding', '/easypayment', '/billing-pay', '/case_', '/fitpet', '/v2-open', '/multi-pg', '/blue-garage', '/game', '/codemshop', '/global', '/woocommerce'],
            'PS': ['/ps_'],  # 플랫폼 정산 전용 (ps_odin, ps_news, ps_tech-lead) - ⚠️ 절대 OPI 메일에 넣지 말것
            'Recon': ['/co-', '/recon_', '/analytics']  # 매출 마감 (co-sabang, co-drg, co-skin1004)
        }
        
        # 블로그 검색 (최신순)
        query = db.session.query(BlogPost).order_by(BlogPost.created_at.desc())
        
        # 서비스 유형이 지정되면 해당 패턴만 필터링
        if service_type and service_type.upper() in service_url_patterns:
            patterns = service_url_patterns[service_type.upper()]
            # OR 조건으로 패턴 매칭
            pattern_filters = [BlogPost.link.like(f'%{p}%') for p in patterns]
            query = query.filter(or_(*pattern_filters))
            logger.info(f"🔍 {service_type} 블로그만 검색 (패턴: {patterns})")
        
        all_posts = query.limit(max_check).all()
        
        if not all_posts:
            logger.info(f"📝 블로그 DB에 {service_type or '전체'} 데이터 없음")
            return None
        
        best_match = None
        best_score = 0
        best_reason = ''
        industry_matched = False
        best_case_company = None  # 블로그에 언급된 고객사명
        
        for post in all_posts:
            score = 0
            reasons = []
            this_industry_matched = False
            case_company_name = None  # 블로그에 언급된 고객사명
            
            post_text = f"{post.title} {post.summary} {post.content} {post.industry_tags} {post.keywords}".lower()
            
            # 🆕 블로그에서 고객사례 회사 추출 → 업종 파악 (가장 정확)
            case_companies = extract_case_companies_from_blog(post.content or '', post.title or '')
            blog_industries = []
            
            if case_companies:
                for case in case_companies:
                    if case['industry'] not in blog_industries:
                        blog_industries.append(case['industry'])
                case_company_name = case_companies[0]['company']  # 첫 번째 고객사명 저장
            
            # 키워드 기반 업종도 추가
            for ind, keywords in industry_keywords.items():
                for kw in keywords:
                    if kw in post_text:
                        if ind not in blog_industries:
                            blog_industries.append(ind)
                        break
            
            # 🆕 배타적 그룹 체크 - 회사가 자동차인데 블로그가 뷰티면 제외
            if company_exclusive_group:
                blog_in_exclusive = False
                for group in exclusive_groups:
                    if any(ind in blog_industries for ind in group):
                        if group != company_exclusive_group:
                            # 다른 배타적 그룹의 블로그는 스킵
                            blog_in_exclusive = True
                            break
                if blog_in_exclusive:
                    continue
            
            # 🎯 뉴스 기사에서 파악된 의도와 블로그 매칭 (최우선!)
            title_lower = (post.title or '').lower()
            for intent_name in detected_intents:
                intent_info = intent_scenarios.get(intent_name, {})
                blog_kws = intent_info.get('blog_keywords', [])
                intent_score = intent_info.get('score', 30)
                
                # 블로그 제목에 의도 관련 키워드가 있으면 최고 점수
                if any(bk in title_lower for bk in blog_kws):
                    score += intent_score
                    this_industry_matched = True  # 업종 불일치 패널티 방지
                    reasons.insert(0, f"📰 {intent_name} 관련 전문 사례")
                    break
                # 블로그 본문에 의도 관련 키워드가 있으면 중간 점수
                elif any(bk in post_text for bk in blog_kws):
                    score += intent_score // 2
                    reasons.insert(0, f"{intent_name} 관련")
            
            # 🏆 경쟁사 매칭 (최고 점수 - 가장 설득력 있음!)
            competitor_matched = False
            if competitor_list:
                for comp in competitor_list:
                    if comp in post_text:
                        score += 25  # 경쟁사 언급 시 최고 점수
                        competitor_matched = True
                        reasons.insert(0, f"경쟁사 '{comp}' 사례")
                        logger.info(f"🏆 경쟁사 매칭! '{comp}' in blog: {post.title[:30]}...")
                        break
                    # 블로그에서 추출한 고객사가 경쟁사인 경우
                    if case_companies:
                        for case in case_companies:
                            if comp in case['company'].lower():
                                score += 25
                                competitor_matched = True
                                reasons.insert(0, f"경쟁사 '{case['company']}' 사례")
                                case_company_name = case['company']
                                break
                        if competitor_matched:
                            break
            
            # 산업 매칭 점수 (높은 가중치)
            for ind in matched_industries:
                if ind in blog_industries:
                    score += 15  # 정확히 같은 업종
                    this_industry_matched = True
                    # 🆕 고객사명이 있으면 더 구체적인 이유 표시
                    if case_company_name and f"{ind}" not in str(reasons):
                        reasons.append(f"{case_company_name}({ind})")
                    elif f"{ind} 업종" not in [r for r in reasons]:
                        reasons.append(f"{ind} 업종 사례")
                else:
                    # 키워드로 부분 매칭
                    for kw in industry_keywords.get(ind, []):
                        if kw in post_text:
                            score += 5
                            this_industry_matched = True
                            if f"{ind}" not in str(reasons):
                                reasons.append(f"{ind} 관련")
                            break
            
            # 혜택 매칭 점수
            for benefit in matched_benefits:
                for kw in benefit_keywords.get(benefit, []):
                    if kw in post_text:
                        score += 5
                        if benefit not in str(reasons):
                            reasons.append(f"{benefit}")
                        break
            
            # 일반 혜택 키워드 (회사 매칭 없어도)
            general_benefits = ['수수료', '절감', '자동화', '효율', '성공사례', '도입사례']
            for gb in general_benefits:
                if gb in post_text:
                    score += 1
            
            # 🆕 업종 매칭이 있는 블로그 우선 (업종 매칭 없으면 점수 감점)
            if not this_industry_matched and matched_industries:
                score = score // 2  # 업종 불일치 시 점수 반감
            
            # URL이 유효한지 확인
            if score > best_score and post.link:
                best_score = score
                best_match = post
                best_reason = ', '.join(reasons[:2]) if reasons else '포트원 도입 효과'
                industry_matched = this_industry_matched
                best_case_company = case_company_name  # 고객사명 저장
        
        # 🆕 최소 점수 기준 완화: 블로그 언급을 더 적극적으로 하기 위해
        # 업종 매칭 있으면 3점, 없으면 5점 이상이면 OK
        min_score = 3 if industry_matched else 5
        
        if best_match and best_score >= min_score:
            logger.info(f"✅ 블로그 선택: {best_match.title[:40]}... (점수: {best_score}, 이유: {best_reason}, 업종매칭: {industry_matched}, 고객사: {best_case_company})")
            return {
                'title': best_match.title,
                'link': best_match.link,
                'summary': best_match.summary[:200] if best_match.summary else '',
                'match_reason': best_reason,
                'industry_matched': industry_matched,
                'case_company': best_case_company  # 블로그에 언급된 고객사명
            }
        else:
            logger.info(f"📝 적합한 블로그 없음 (최고 점수: {best_score}, 최소 기준: {min_score})")
            return None
            
    except Exception as e:
        logger.error(f"블로그 선택 오류: {str(e)}")
        return None


def format_blog_mention_for_email(blog_info, company_name=''):
    """
    이메일에 삽입할 블로그 언급 문구 생성
    
    "3,000여개 고객사가..." 대신 사용할 수 있는 문구
    
    Args:
        blog_info: get_best_blog_for_email_mention() 결과
        company_name: 회사명
    
    Returns:
        dict: {
            'mention_text': 본문에 삽입할 텍스트,
            'blog_link': 블로그 링크,
            'blog_title': 블로그 제목
        }
    """
    if not blog_info:
        return None
    
    title = blog_info.get('title', '')
    link = blog_info.get('link', '')
    reason = blog_info.get('match_reason', '')
    
    # 본문에 자연스럽게 삽입할 문구
    mention_text = f"""
실제로 {reason}를 고민하셨던 고객사에서 포트원 도입 후 좋은 결과를 얻으셨는데요,
자세한 내용은 아래 글에서 확인해보실 수 있습니다.

👉 [{title}]({link})
"""
    
    return {
        'mention_text': mention_text.strip(),
        'blog_link': link,
        'blog_title': title,
        'match_reason': reason
    }


def format_relevant_blog_for_email(blog_posts, company_name='', service_type=''):
    """
    업종별 관련 블로그 글을 RAG 방식으로 포맷팅
    
    Args:
        blog_posts: 블로그 글 리스트
        company_name: 회사명
        service_type: 서비스 타입
    
    Returns:
        str: 포맷팅된 텍스트
    """
    if not blog_posts:
        return ''
    
    service_label = service_type if service_type else '포트원'
    
    content = f"\n\n**📚 {service_label} 관련 참고 정보 (RAG - Pain Point 매칭 사례 우선!):**\n\n"
    content += "⚠️ **중요 지침**: 아래 정보는 이메일 본문의 설득력을 높이기 위한 참고 자료입니다.\n"
    content += "- 블로그 글을 직접 언급하지 마세요 (\"최근 포트원 블로그에서...\" ❌)\n"
    content += "- **아래 블로그는 {company_name}의 Pain Point와 유사한 문제를 해결한 기존 고객 사례입니다**\n"
    content += "- **참고자료 1번이 가장 관련성 높은 사례**이므로 우선 활용하세요\n"
    content += "- 정보를 자연스럽게 활용하여 \"{company_name}님도 이런 문제 겪으시죠?\"라는 공감대 형성\n"
    content += "- 수치, 트렌드, 사례 등을 자신의 말로 녹여서 사용하세요\n\n"
    content += "---\n\n"
    
    for i, post in enumerate(blog_posts[:3], 1):
        content += f"**참고자료 {i}:**\n"
        content += f"주제: {post['title']}\n"
        content += f"🔗 **원본 링크 (이메일 출처로 사용 시 이 URL을 정확히 복사)**: {post.get('link', '')}\n\n"
        
        summary = post.get('summary', '')
        full_content = post.get('content', '')
        
        if summary:
            content += f"핵심 내용:\n{summary}\n\n"
        
        if full_content and len(full_content) > len(summary):
            additional = full_content[len(summary):min(len(summary)+300, len(full_content))]
            content += f"추가 정보:\n{additional}...\n\n"
        
        content += "---\n\n"
    
    content += f"💡 **Pain Point 매칭 사례 활용법**: \n"
    content += f"- 위 블로그는 {company_name}와 유사한 Pain Point를 겪은 기존 고객의 성공 사례입니다\n"
    content += f"- 이메일에서 \"{company_name}님도 이런 어려움 겪고 계시지 않나요?\"라는 공감으로 시작\n"
    content += f"- 기존 고객이 어떻게 문제를 해결했는지 구체적 수치와 함께 언급\n"
    content += f"- 예: \"유사한 업종의 X사는 포트원 도입 후 Y% 개선 효과를 보았습니다\"\n"
    content += f"- 출처를 명시할 경우 이메일 하단에 [참고] 형식으로만 표기\n"
    
    return content

def get_service_knowledge(service_type=''):
    """
    서비스 소개서와 블로그 전체 정보를 통합하여 RAG 지식베이스 생성
    
    Args:
        service_type: 'OPI', 'Recon', 'Prism', 'PS'
    
    Returns:
        str: 통합된 지식베이스 텍스트
    """
    knowledge = ""
    
    # 1. 서비스 소개서 로드
    service_files = {
        'OPI': 'opi_service_info.txt',
        'Recon': 'recon_service_info.txt',
        'Prism': 'prism_service_info.txt',
        'PS': 'ps_service_info.txt'
    }
    
    service_names = {
        'OPI': 'One Payment Infra (OPI)',
        'Recon': '재무자동화 솔루션 (Recon)',
        'Prism': '멀티 오픈마켓 정산 통합 솔루션 (Prism)',
        'PS': '플랫폼 정산 자동화'
    }
    
    if service_type in service_files:
        try:
            with open(service_files[service_type], 'r', encoding='utf-8') as f:
                service_doc = f.read()
            knowledge += f"\n\n**📖 {service_names[service_type]} 서비스 소개:**\n\n"
            knowledge += f"{service_doc[:3000]}...\n\n"
            logger.info(f"✅ {service_type} 서비스 소개서 로드 완료")
        except:
            logger.warning(f"⚠️ {service_type} 서비스 소개서 파일 없음")
    
    # 2. 블로그 전체 요약 (PostgreSQL에서 조회)
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        
        posts_query = db.session.query(BlogPost).filter_by(category=service_type).order_by(BlogPost.created_at.desc()).all()
        
        if posts_query:
            knowledge += f"\n\n**📚 {service_type} 관련 블로그 인사이트 ({len(posts_query)}개 글):**\n\n"
            knowledge += f"다음은 포트원 공식 블로그에서 {service_type} 관련 {len(posts_query)}개 글의 핵심 내용입니다.\n"
            knowledge += "이 정보들을 바탕으로 업계 트렌드, Pain Point, 사례 등을 자연스럽게 언급하세요.\n\n"
            
            # 주요 키워드 추출
            all_keywords = []
            for post in posts_query:
                if post.keywords:
                    keywords = post.keywords.split(',')
                    all_keywords.extend(keywords)
            
            if all_keywords:
                keyword_freq = Counter(all_keywords)
                top_keywords = [k for k, v in keyword_freq.most_common(10)]
                knowledge += f"**주요 키워드**: {', '.join(top_keywords)}\n\n"
            
            # 대표 글 5개 요약
            knowledge += f"**대표 인사이트:**\n\n"
            for i, post in enumerate(posts_query[:5], 1):
                knowledge += f"{i}. {post.title}\n"
                knowledge += f"   🔗 **원본 링크**: {post.link}\n"
                if post.summary:
                    knowledge += f"   → {post.summary[:150]}...\n\n"
            
            logger.info(f"✅ {service_type} 블로그 {len(posts_query)}개 요약 완료 (PostgreSQL)")
            
    except Exception as e:
        logger.error(f"블로그 요약 오류: {str(e)}")
    
    # 3. RAG 활용 지침
    knowledge += f"\n\n**💡 지식 활용 가이드:**\n"
    knowledge += "- 위 서비스 소개서와 블로그 인사이트를 깊이 이해하고 활용하세요\n"
    knowledge += "- 구체적인 수치, 기능, 효과를 정확하게 언급하세요\n"
    knowledge += "- 업계 트렌드나 Pain Point는 '업계에서는...', '많은 기업들이...' 형태로 자연스럽게\n"
    knowledge += "- 경쟁력 있는 차별점과 핵심 가치를 명확히 전달하세요\n"
    knowledge += f"- {service_type} 서비스에 대한 전문성과 신뢰성을 보여주세요\n"
    
    return knowledge

def get_existing_blog_links():
    """
    DB에 이미 저장된 블로그 링크 목록 조회
    
    Returns:
        set: 기존 블로그 링크 집합
    """
    try:
        db = get_db()
        BlogPost = get_blog_post_model()
        
        # 모든 링크 조회
        posts = db.session.query(BlogPost.link).all()
        existing_links = {post.link for post in posts if post.link}
        
        logger.info(f"📋 DB에 저장된 블로그: {len(existing_links)}개")
        return existing_links
        
    except Exception as e:
        logger.error(f"기존 링크 조회 오류: {str(e)}")
        return set()

def check_for_new_posts(category_url, existing_links, max_check_pages=2):
    """
    블로그 카테고리에서 새로운 포스트만 확인
    
    Args:
        category_url: 카테고리 URL
        existing_links: 기존 블로그 링크 집합
        max_check_pages: 확인할 최대 페이지 수 (기본 2페이지)
    
    Returns:
        list: 새로운 포스트 링크 목록
    """
    try:
        from bs4 import BeautifulSoup
        import requests
        
        new_post_links = []
        
        for page in range(1, max_check_pages + 1):
            page_url = f"{category_url}&page={page}" if page > 1 else category_url
            
            response = requests.get(page_url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"페이지 로드 실패: {page_url}")
                break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article', class_='post')
            
            if not articles:
                logger.info(f"더 이상 글이 없음 (페이지 {page})")
                break
            
            found_existing = False
            for article in articles:
                link_tag = article.find('a', href=True)
                if link_tag:
                    link = f"https://blog.portone.io{link_tag['href']}"
                    
                    # 기존 DB에 없는 새로운 글만 추가
                    if link not in existing_links:
                        new_post_links.append(link)
                    else:
                        found_existing = True
            
            # 기존 글을 발견하면 더 이상 확인 불필요
            if found_existing:
                logger.info(f"기존 글 발견 - {page}페이지에서 확인 중단")
                break
        
        return new_post_links
        
    except Exception as e:
        logger.error(f"새 포스트 확인 오류: {str(e)}")
        return []
