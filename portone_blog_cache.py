"""
포트원 블로그 콘텐츠 데이터베이스 시스템
"""

import sqlite3
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

DB_FILE = 'portone_blog.db'

def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 블로그 포스트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE,
                summary TEXT,
                content TEXT,
                category TEXT,
                keywords TEXT,
                industry_tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 캐시 메타데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_updated TIMESTAMP,
                posts_count INTEGER
            )
        ''')
        
        # 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON blog_posts(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_category 
            ON blog_posts(category)
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("✅ 블로그 데이터베이스 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"데이터베이스 초기화 오류: {str(e)}")
        return False

def save_blog_cache(blog_posts, replace_all=True):
    """블로그 포스트를 데이터베이스에 저장"""
    try:
        init_db()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # replace_all이 True면 기존 포스트 삭제
        if replace_all:
            cursor.execute('DELETE FROM blog_posts')
        
        # 새 포스트 삽입 (중복은 무시)
        inserted_count = 0
        for post in blog_posts:
            try:
                cursor.execute('''
                    INSERT INTO blog_posts (title, link, summary, content, category, keywords, industry_tags, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    post.get('title', ''),
                    post.get('link', ''),
                    post.get('summary', ''),
                    post.get('content', ''),
                    post.get('category', ''),
                    post.get('keywords', ''),
                    post.get('industry_tags', ''),
                    datetime.now(),
                    datetime.now()
                ))
                inserted_count += 1
            except sqlite3.IntegrityError:
                # 중복 링크는 업데이트
                cursor.execute('''
                    UPDATE blog_posts 
                    SET title=?, summary=?, content=?, category=?, keywords=?, industry_tags=?, updated_at=?
                    WHERE link=?
                ''', (
                    post.get('title', ''),
                    post.get('summary', ''),
                    post.get('content', ''),
                    post.get('category', ''),
                    post.get('keywords', ''),
                    post.get('industry_tags', ''),
                    datetime.now(),
                    post.get('link', '')
                ))
                inserted_count += 1
        
        # 메타데이터 업데이트
        cursor.execute('SELECT COUNT(*) FROM blog_posts')
        total_count = cursor.fetchone()[0]
        
        cursor.execute('''
            INSERT OR REPLACE INTO cache_metadata (id, last_updated, posts_count)
            VALUES (1, ?, ?)
        ''', (datetime.now(), total_count))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ 블로그 DB 저장 완료: {inserted_count}개 글 처리, 총 {total_count}개")
        return True
    except Exception as e:
        logger.error(f"블로그 DB 저장 오류: {str(e)}")
        return False

def load_blog_cache():
    """데이터베이스에서 블로그 포스트 로드"""
    try:
        init_db()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title, link, summary, content, category, keywords, industry_tags, created_at
            FROM blog_posts
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            logger.info("📝 블로그 DB에 데이터 없음")
            return None
        
        posts = []
        for row in rows:
            posts.append({
                'title': row[0],
                'link': row[1],
                'summary': row[2],
                'content': row[3],
                'category': row[4],
                'keywords': row[5],
                'industry_tags': row[6],
                'created_at': row[7]
            })
        
        logger.info(f"📚 블로그 DB 로드 완료: {len(posts)}개 글")
        return posts
    except Exception as e:
        logger.error(f"블로그 DB 로드 오류: {str(e)}")
        return None

def get_blog_cache_age():
    """데이터베이스의 업데이트 시간 확인"""
    try:
        init_db()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_updated FROM cache_metadata WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            return None
        
        # SQLite datetime을 Python datetime으로 변환
        if isinstance(row[0], str):
            updated_time = datetime.fromisoformat(row[0].replace(' ', 'T'))
        else:
            updated_time = row[0]
        
        age_hours = (datetime.now() - updated_time).total_seconds() / 3600
        return age_hours
    except Exception as e:
        logger.error(f"캐시 시간 확인 오류: {str(e)}")
        return None

def format_blog_content_for_email(blog_posts):
    """블로그 포스트를 이메일용 텍스트로 포맷팅"""
    if not blog_posts:
        return ""
    
    content = "\n\n**📰 포트원 최신 블로그 콘텐츠 (참고용):**\n"
    content += "아래 최신 콘텐츠를 참고하여 메일 작성 시 자연스럽게 활용할 수 있습니다.\n\n"
    
    for i, post in enumerate(blog_posts[:5], 1):  # 최대 5개
        content += f"{i}. **{post['title']}**\n"
        if post.get('summary'):
            content += f"   {post['summary'][:150]}...\n"
        if post.get('link'):
            content += f"   링크: {post['link']}\n"
        content += "\n"
    
    content += "💡 위 콘텐츠를 활용하여 최신 트렌드나 포트원의 새로운 기능을 자연스럽게 언급할 수 있습니다.\n"
    
    return content

def extract_keywords_from_post(post):
    """블로그 글에서 키워드 추출 (Gemini 활용)"""
    try:
        content = post.get('content', '')
        title = post.get('title', '')
        
        if not content or len(content) < 50:
            return '', ''
        
        # 간단한 키워드 추출 (나중에 Gemini로 강화 가능)
        # 현재는 카테고리 기반으로 단순 태그 생성
        category = post.get('category', '')
        
        # 기본 키워드
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
    회사 정보를 기반으로 관련 블로그 글 조회
    
    Args:
        company_info: 회사 정보 딕셔너리 (industry, category, description 등)
        max_posts: 최대 반환 글 수
        service_type: 서비스 타입 ('OPI' 또는 'Recon', None이면 모두 조회)
    
    Returns:
        list: 관련 블로그 글 리스트
    """
    try:
        init_db()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 회사 업종/카테고리 추출
        industry = company_info.get('industry', '')
        category = company_info.get('category', '')
        description = company_info.get('description', '')
        
        # 검색 키워드 구성
        search_terms = []
        if industry:
            search_terms.append(industry)
        if category:
            search_terms.append(category)
        
        # 설명에서 주요 키워드 추출
        if description:
            desc_lower = description.lower()
            if '게임' in desc_lower or 'game' in desc_lower:
                search_terms.append('게임')
            if '이커머스' in desc_lower or '쇼핑몰' in desc_lower:
                search_terms.append('이커머스')
            if '여행' in desc_lower or 'travel' in desc_lower:
                search_terms.append('여행')
            if '교육' in desc_lower or 'education' in desc_lower:
                search_terms.append('교육')
            if '금융' in desc_lower or 'fintech' in desc_lower:
                search_terms.append('금융')
        
        # 서비스 타입 조건 추가
        service_condition = ''
        params = []
        
        if service_type:
            service_condition = 'category = ?'
            params.append(service_type)
        
        if not search_terms:
            # 검색어가 없으면 최신 글 반환 (서비스 타입 필터링)
            if service_condition:
                query = f'''
                    SELECT title, link, summary, content, category, keywords, industry_tags
                    FROM blog_posts
                    WHERE {service_condition}
                    ORDER BY created_at DESC
                    LIMIT ?
                '''
                params.append(max_posts)
            else:
                query = '''
                    SELECT title, link, summary, content, category, keywords, industry_tags
                    FROM blog_posts
                    ORDER BY created_at DESC
                    LIMIT ?
                '''
                params = [max_posts]
            
            cursor.execute(query, params)
        else:
            # 업종 태그 또는 키워드 매칭 + 서비스 타입 필터링
            search_pattern = '%' + '%'.join(search_terms) + '%'
            
            if service_condition:
                query = f'''
                    SELECT title, link, summary, content, category, keywords, industry_tags
                    FROM blog_posts
                    WHERE {service_condition}
                      AND (industry_tags LIKE ? OR keywords LIKE ? OR title LIKE ? OR content LIKE ?)
                    ORDER BY created_at DESC
                    LIMIT ?
                '''
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern, max_posts])
            else:
                query = '''
                    SELECT title, link, summary, content, category, keywords, industry_tags
                    FROM blog_posts
                    WHERE industry_tags LIKE ? OR keywords LIKE ? OR title LIKE ? OR content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                '''
                params = [search_pattern, search_pattern, search_pattern, search_pattern, max_posts]
            
            cursor.execute(query, params)
        
        rows = cursor.fetchall()
        conn.close()
        
        service_label = f"[{service_type}] " if service_type else ""
        
        if not rows:
            if search_terms:
                logger.info(f"🔍 {service_label}'{', '.join(search_terms)}' 관련 블로그 글 없음")
            else:
                logger.info(f"🔍 {service_label}블로그 글 없음")
            return []
        
        posts = []
        for row in rows:
            posts.append({
                'title': row[0],
                'link': row[1],
                'summary': row[2],
                'content': row[3],
                'category': row[4],
                'keywords': row[5],
                'industry_tags': row[6]
            })
        
        if search_terms:
            logger.info(f"✅ {service_label}'{', '.join(search_terms)}' 관련 블로그 글 {len(posts)}개 조회")
        else:
            logger.info(f"✅ {service_label}블로그 글 {len(posts)}개 조회")
        return posts
    except Exception as e:
        logger.error(f"업종별 블로그 조회 오류: {str(e)}")
        return []

def format_relevant_blog_for_email(blog_posts, company_name='', service_type=''):
    """
    업종별 관련 블로그 글을 RAG 방식으로 포맷팅 (직접 언급 제거)
    
    Args:
        blog_posts: 블로그 글 리스트
        company_name: 회사명 (개인화용)
        service_type: 서비스 타입 ('OPI' 또는 'Recon')
    
    Returns:
        str: 포맷팅된 텍스트 (RAG용 컨텍스트)
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
        
        # 제목은 표시하되, 이메일에 직접 쓰지 말라고 명시
        content += f"주제: {post['title']}\n\n"
        
        # 핵심 내용 추출 (요약 + 본문 일부)
        summary = post.get('summary', '')
        full_content = post.get('content', '')
        
        if summary:
            content += f"핵심 내용:\n{summary}\n\n"
        
        # 본문에서 추가 정보 추출 (수치, 통계, 사례 등)
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
        service_type: 'OPI', 'Recon', 또는 'Prism'
    
    Returns:
        str: 통합된 지식베이스 텍스트
    """
    knowledge = ""
    
    # 블로그 스크래핑은 app.py의 generate_email_with_gemini에서 처리됨
    # 여기서는 이미 스크래핑된 데이터를 로드만 함
    
    # 1. 서비스 소개서 로드
    if service_type == 'OPI':
        try:
            with open('opi_service_info.txt', 'r', encoding='utf-8') as f:
                service_doc = f.read()
            knowledge += f"\n\n**📖 One Payment Infra (OPI) 서비스 소개:**\n\n"
            knowledge += f"{service_doc[:3000]}...\n\n"  # 처음 3000자
            logger.info("✅ OPI 서비스 소개서 로드 완료")
        except:
            logger.warning("⚠️ OPI 서비스 소개서 파일 없음")
    
    elif service_type == 'Recon':
        try:
            with open('recon_service_info.txt', 'r', encoding='utf-8') as f:
                service_doc = f.read()
            knowledge += f"\n\n**📖 재무자동화 솔루션 (Recon) 서비스 소개:**\n\n"
            knowledge += f"{service_doc[:2000]}...\n\n"  # 처음 2000자
            logger.info("✅ Recon 서비스 소개서 로드 완료")
        except:
            logger.warning("⚠️ Recon 서비스 소개서 파일 없음")
    
    elif service_type == 'Prism':
        try:
            with open('prism_service_info.txt', 'r', encoding='utf-8') as f:
                service_doc = f.read()
            knowledge += f"\n\n**📖 멀티 오픈마켓 정산 통합 솔루션 (Prism) 서비스 소개:**\n\n"
            knowledge += f"{service_doc[:3000]}...\n\n"  # 처음 3000자
            logger.info("✅ Prism 서비스 소개서 로드 완료")
        except:
            logger.warning("⚠️ Prism 서비스 소개서 파일 없음")
    
    elif service_type == 'PS':
        try:
            with open('ps_service_info.txt', 'r', encoding='utf-8') as f:
                service_doc = f.read()
            knowledge += f"\n\n**📖 플랫폼 정산 자동화 (파트너 정산+세금계산서+지급대행) 서비스 소개:**\n\n"
            knowledge += f"{service_doc[:3500]}...\n\n"  # 처음 3500자
            logger.info("✅ 플랫폼 정산(PS) 서비스 소개서 로드 완료")
        except:
            logger.warning("⚠️ 플랫폼 정산(PS) 서비스 소개서 파일 없음")
    
    # 2. 블로그 전체 요약 (해당 카테고리)
    try:
        init_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title, summary, keywords
            FROM blog_posts
            WHERE category = ?
            ORDER BY created_at DESC
        ''', (service_type,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            knowledge += f"\n\n**📚 {service_type} 관련 블로그 인사이트 ({len(rows)}개 글):**\n\n"
            knowledge += f"다음은 포트원 공식 블로그에서 {service_type} 관련 {len(rows)}개 글의 핵심 내용입니다.\n"
            knowledge += "이 정보들을 바탕으로 업계 트렌드, Pain Point, 사례 등을 자연스럽게 언급하세요.\n\n"
            
            # 주요 키워드 추출
            all_keywords = []
            for row in rows:
                keywords = row[2].split(',') if row[2] else []
                all_keywords.extend(keywords)
            
            # 키워드 빈도 계산
            from collections import Counter
            keyword_freq = Counter(all_keywords)
            top_keywords = [k for k, v in keyword_freq.most_common(10)]
            
            knowledge += f"**주요 키워드**: {', '.join(top_keywords)}\n\n"
            
            # 대표 글 5개 요약
            knowledge += f"**대표 인사이트:**\n\n"
            for i, row in enumerate(rows[:5], 1):
                title, summary = row[0], row[1]
                knowledge += f"{i}. {title}\n"
                if summary:
                    knowledge += f"   → {summary[:150]}...\n\n"
            
            logger.info(f"✅ {service_type} 블로그 {len(rows)}개 요약 완료")
        
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
