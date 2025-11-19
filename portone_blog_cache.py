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

def extract_keywords_from_post(post):
    """
    블로그 글에서 키워드 추출
    
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
        text_lower = (title + ' ' + content[:500]).lower()
        
        # 업종 관련 키워드
        if '게임' in text_lower or 'game' in text_lower:
            industry_tags.append('게임')
        if '이커머스' in text_lower or 'e커머스' in text_lower or '쇼핑몰' in text_lower or 'commerce' in text_lower:
            industry_tags.append('이커머스')
        if '여행' in text_lower or 'travel' in text_lower or '항공' in text_lower:
            industry_tags.append('여행')
        if '교육' in text_lower or 'education' in text_lower or '에듀테크' in text_lower:
            industry_tags.append('교육')
        if '금융' in text_lower or 'fintech' in text_lower or '핀테크' in text_lower:
            industry_tags.append('금융')
        if '미디어' in text_lower or 'media' in text_lower or '콘텐츠' in text_lower:
            industry_tags.append('미디어')
        if 'saas' in text_lower or '구독' in text_lower:
            industry_tags.append('SaaS')
        if '물류' in text_lower or 'logistics' in text_lower or '배송' in text_lower:
            industry_tags.append('물류')
        
        # 기능 관련 키워드
        if '결제' in text_lower or 'payment' in text_lower:
            keywords.append('결제')
        if '정산' in text_lower or '매출' in text_lower or 'reconciliation' in text_lower:
            keywords.append('매출관리')
        if '자동화' in text_lower or 'automation' in text_lower:
            keywords.append('자동화')
        if 'pg' in text_lower or '간편결제' in text_lower:
            keywords.append('PG')
        if '해외' in text_lower or 'global' in text_lower or '글로벌' in text_lower:
            keywords.append('글로벌')
        if '정기결제' in text_lower or 'subscription' in text_lower:
            keywords.append('정기결제')
        
        return ','.join(keywords), ','.join(industry_tags)
        
    except Exception as e:
        logger.error(f"키워드 추출 오류: {str(e)}")
        return '', ''

def get_relevant_blog_posts_by_industry(company_info, max_posts=3, service_type=None):
    """
    회사 정보를 기반으로 관련 블로그 글 조회 (PostgreSQL)
    
    Args:
        company_info: 회사 정보 딕셔너리
        max_posts: 최대 반환 글 수
        service_type: 서비스 타입 ('OPI', 'Recon', 'Prism', 'PS' 등)
    
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
        
        # 설명에서 키워드 추출
        if description:
            desc_lower = description.lower()
            for keyword in ['게임', 'game', '이커머스', '쇼핑몰', '여행', 'travel', '교육', 'education', '금융', 'fintech']:
                if keyword in desc_lower:
                    search_terms.append(keyword)
        
        # 쿼리 시작
        query = db.session.query(BlogPost)
        
        # 서비스 타입 필터링
        if service_type:
            query = query.filter(BlogPost.category == service_type)
        
        # 검색어로 필터링
        if search_terms:
            from sqlalchemy import or_
            search_pattern = f"%{'%'.join(search_terms)}%"
            query = query.filter(
                or_(
                    BlogPost.industry_tags.like(search_pattern),
                    BlogPost.keywords.like(search_pattern),
                    BlogPost.title.like(search_pattern),
                    BlogPost.content.like(search_pattern)
                )
            )
        
        # 최신순 정렬 및 개수 제한
        posts_query = query.order_by(BlogPost.created_at.desc()).limit(max_posts).all()
        
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
    
    content = f"\n\n**📚 {service_label} 관련 참고 정보 (RAG - 블로그 직접 언급 금지!):**\n\n"
    content += "⚠️ **중요 지침**: 아래 정보는 이메일 본문의 설득력을 높이기 위한 참고 자료입니다.\n"
    content += "- 블로그 글을 직접 언급하지 마세요 (\"최근 포트원 블로그에서...\" ❌)\n"
    content += "- 정보만 자연스럽게 활용하여 근거 있는 주장을 펼치세요\n"
    content += "- 수치, 트렌드, 사례 등을 자신의 말로 녹여서 사용하세요\n\n"
    content += "---\n\n"
    
    for i, post in enumerate(blog_posts[:3], 1):
        content += f"**참고자료 {i}:**\n"
        content += f"주제: {post['title']}\n"
        content += f"링크: {post.get('link', '')}\n\n"
        
        summary = post.get('summary', '')
        full_content = post.get('content', '')
        
        if summary:
            content += f"핵심 내용:\n{summary}\n\n"
        
        if full_content and len(full_content) > len(summary):
            additional = full_content[len(summary):min(len(summary)+300, len(full_content))]
            content += f"추가 정보:\n{additional}...\n\n"
        
        content += "---\n\n"
    
    content += f"💡 **활용 방법**: 위 정보를 바탕으로 {company_name}에게 {service_label} 서비스가 "
    content += "어떻게 도움이 되는지 구체적이고 설득력 있게 작성하세요.\n"
    content += "- 업계 트렌드나 Pain Point를 언급할 때 위 정보 활용\n"
    content += "- \"많은 기업들이 X 문제를 겪고 있습니다\" 같은 표현에 근거 제시\n"
    content += "- 수치나 사례가 있다면 \"업계 평균\", \"다른 기업 사례\" 등으로 자연스럽게 인용\n"
    
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
