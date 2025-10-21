"""
포트원 블로그 스크랩핑 및 업종별 매칭 테스트 스크립트
"""

import sys
import logging
from portone_blog_cache import (
    init_db,
    save_blog_cache,
    load_blog_cache,
    get_blog_cache_age,
    get_relevant_blog_posts_by_industry,
    format_relevant_blog_for_email,
    extract_keywords_from_post
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_database_init():
    """데이터베이스 초기화 테스트"""
    logger.info("=" * 60)
    logger.info("1. 데이터베이스 초기화 테스트")
    logger.info("=" * 60)
    
    result = init_db()
    if result:
        logger.info("✅ 데이터베이스 초기화 성공")
    else:
        logger.error("❌ 데이터베이스 초기화 실패")
    
    return result

def test_blog_scraping():
    """블로그 스크랩핑 테스트"""
    logger.info("\n" + "=" * 60)
    logger.info("2. 블로그 스크랩핑 테스트")
    logger.info("=" * 60)
    
    try:
        from app import scrape_portone_blog_initial
        
        logger.info("블로그 스크랩핑 시작...")
        blog_posts = scrape_portone_blog_initial()
        
        if blog_posts:
            logger.info(f"✅ 블로그 스크랩핑 성공: {len(blog_posts)}개 글")
            
            # 샘플 출력
            logger.info("\n📰 스크랩핑된 블로그 샘플 (최대 3개):")
            for i, post in enumerate(blog_posts[:3], 1):
                logger.info(f"\n{i}. {post['title']}")
                logger.info(f"   카테고리: {post.get('category', 'N/A')}")
                logger.info(f"   키워드: {post.get('keywords', 'N/A')}")
                logger.info(f"   업종태그: {post.get('industry_tags', 'N/A')}")
                logger.info(f"   링크: {post.get('link', 'N/A')}")
            
            return True
        else:
            logger.warning("⚠️ 스크랩핑된 글이 없습니다")
            return False
            
    except Exception as e:
        logger.error(f"❌ 블로그 스크랩핑 오류: {str(e)}")
        return False

def test_cache_load():
    """캐시 로드 테스트"""
    logger.info("\n" + "=" * 60)
    logger.info("3. 블로그 캐시 로드 테스트")
    logger.info("=" * 60)
    
    cached_posts = load_blog_cache()
    
    if cached_posts:
        logger.info(f"✅ 캐시 로드 성공: {len(cached_posts)}개 글")
        
        cache_age = get_blog_cache_age()
        if cache_age is not None:
            logger.info(f"📅 캐시 나이: {cache_age:.2f}시간")
        
        return True
    else:
        logger.warning("⚠️ 캐시가 비어있습니다")
        return False

def test_industry_matching():
    """업종별 블로그 매칭 테스트"""
    logger.info("\n" + "=" * 60)
    logger.info("4. 업종별 블로그 매칭 테스트")
    logger.info("=" * 60)
    
    # 테스트 케이스
    test_companies = [
        {
            'name': '게임 회사',
            'info': {
                'industry': '게임',
                'category': '모바일게임',
                'description': '모바일 게임 개발 및 퍼블리싱'
            }
        },
        {
            'name': '이커머스 회사',
            'info': {
                'industry': '이커머스',
                'category': '온라인쇼핑몰',
                'description': '패션 쇼핑몰 운영'
            }
        },
        {
            'name': '여행 회사',
            'info': {
                'industry': '여행',
                'category': '항공',
                'description': '항공권 예약 플랫폼'
            }
        }
    ]
    
    for test_case in test_companies:
        logger.info(f"\n🔍 테스트: {test_case['name']}")
        
        relevant_posts = get_relevant_blog_posts_by_industry(
            test_case['info'],
            max_posts=3
        )
        
        if relevant_posts:
            logger.info(f"   ✅ 관련 블로그 {len(relevant_posts)}개 발견")
            for post in relevant_posts:
                logger.info(f"      - {post['title']}")
                logger.info(f"        업종태그: {post.get('industry_tags', 'N/A')}")
        else:
            logger.info(f"   ℹ️ 관련 블로그 없음")
        
        # 이메일용 포맷팅 테스트
        formatted = format_relevant_blog_for_email(
            relevant_posts,
            test_case['name']
        )
        
        if formatted:
            logger.info(f"   📧 이메일 포맷팅 완료 ({len(formatted)} 자)")

def test_keyword_extraction():
    """키워드 추출 테스트"""
    logger.info("\n" + "=" * 60)
    logger.info("5. 키워드 추출 테스트")
    logger.info("=" * 60)
    
    # 테스트 포스트
    test_posts = [
        {
            'title': '게임 업계를 위한 글로벌 결제 솔루션',
            'content': '모바일 게임 회사들이 해외 진출 시 직면하는 결제 시스템 문제와 글로벌 PG 연동 방법에 대해...'
        },
        {
            'title': '이커머스 업체의 정산 자동화 가이드',
            'content': '쇼핑몰 운영자들을 위한 매출 정산 자동화 솔루션. 커머스 플랫폼에서 정기결제와 자동화를 통해...'
        }
    ]
    
    for post in test_posts:
        logger.info(f"\n📝 포스트: {post['title']}")
        keywords, industry_tags = extract_keywords_from_post(post)
        
        logger.info(f"   키워드: {keywords if keywords else '없음'}")
        logger.info(f"   업종태그: {industry_tags if industry_tags else '없음'}")

def main():
    """메인 테스트 함수"""
    logger.info("\n")
    logger.info("🚀 포트원 블로그 시스템 통합 테스트 시작")
    logger.info("=" * 60)
    
    # 1. 데이터베이스 초기화
    if not test_database_init():
        logger.error("데이터베이스 초기화 실패. 테스트 중단.")
        return
    
    # 2. 블로그 스크랩핑 (또는 캐시 로드)
    cache_age = get_blog_cache_age()
    if cache_age is None or cache_age >= 12:
        logger.info("\n캐시가 없거나 오래됨. 새로 스크랩핑...")
        if not test_blog_scraping():
            logger.warning("스크랩핑 실패. 기존 캐시로 테스트 진행...")
    else:
        logger.info(f"\n캐시가 최신 상태 (나이: {cache_age:.2f}시간). 스크랩핑 생략.")
    
    # 3. 캐시 로드
    if not test_cache_load():
        logger.error("캐시 로드 실패. 테스트 중단.")
        return
    
    # 4. 업종별 매칭
    test_industry_matching()
    
    # 5. 키워드 추출
    test_keyword_extraction()
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ 모든 테스트 완료!")
    logger.info("=" * 60)
    logger.info("\n💡 다음 단계:")
    logger.info("   1. 서버를 시작하면 자동으로 스케줄러가 작동합니다 (매일 9시, 18시)")
    logger.info("   2. 이메일 생성 시 자동으로 업종별 블로그가 조회됩니다")
    logger.info("   3. /api/update-blog 엔드포인트로 수동 업데이트 가능")
    logger.info("   4. /api/blog-cache-status 엔드포인트로 상태 확인 가능")

if __name__ == '__main__':
    main()
