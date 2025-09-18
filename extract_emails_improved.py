import re
import urllib.parse
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def extract_emails_from_html(html_content, url=None):
    """HTML에서 이메일 주소를 체계적으로 추출 - 복사 제한 및 난독화 우회 포함, 확장된 이메일 형식 패턴 지원"""
    emails = set()
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. 확장된 이메일 패턴 정의 (더 넓은 범위의 이메일 형식 인식)
        email_patterns = [
            # 기본 이메일 패턴
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            # 한글 도메인 지원 (xn-- 형태)
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*xn--[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            # 더 긴 TLD 지원 (최대 6자리)
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,6}\b',
            # 숫자가 포함된 도메인
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*[0-9]+[A-Za-z0-9.-]*\.[A-Z|a-z]{2,}\b',
            # 특수 문자가 더 많이 포함된 패턴
            r'\b[A-Za-z0-9._%+=-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            # IP 주소 형태의 도메인
            r'\b[A-Za-z0-9._%+-]+@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            # 포트 번호가 포함된 경우
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}:\d+\b'
        ]
        
        # 모든 패턴으로 HTML 전체 텍스트에서 이메일 찾기
        text_content = soup.get_text()
        raw_html = str(html_content)
        
        # 각 패턴별로 검색 수행
        for pattern in email_patterns:
            # 텍스트 콘텐츠에서 검색
            found_emails = re.findall(pattern, text_content, re.IGNORECASE)
            emails.update(found_emails)
            
            # 복사 제한 우회: HTML 소스 직접 검색
            raw_emails = re.findall(pattern, raw_html, re.IGNORECASE)
            emails.update(raw_emails)

        
        for pattern in loose_email_patterns:
            loose_emails = re.findall(pattern, text_content + ' ' + raw_html, re.IGNORECASE)
            # 정규화: 공백 제거, 전각 문자 변환
            for email in loose_emails:
                normalized = email.strip().replace('＠', '@').replace('．', '.').replace(' ', '')
                # 괄호, 따옴표 제거
                normalized = re.sub(r'^[\(\[\{"\']+|[\)\]\}"\']+$', '', normalized)
                if '@' in normalized and '.' in normalized:
                    emails.add(normalized)

        # 2. 확장된 난독화 패턴 처리
        obfuscated_patterns = [
            # [at], (at), _at_, -at-, {at}, <at> 등 다양한 형태
            (r'([A-Za-z0-9._%+-]+)[\s]*[\[\(\{\_\-\<]at[\]\)\}\_\-\>][\s]*([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\2'),
            # [dot], (dot), _dot_, -dot-, {dot}, <dot> 등
            (r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*?)[\s]*[\[\(\{\_\-\<]dot[\]\)\}\_\-\>][\s]*([A-Za-z0-9.-]*\.[A-Z|a-z]{2,6})', r'\1.\2'),
            # 공백으로 분리된 이메일 (여러 공백 포함)
            (r'([A-Za-z0-9._%+-]+)\s+@\s+([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\2'),
            # HTML 엔티티들
            (r'([A-Za-z0-9._%+-]+)&#64;([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\2'),
            (r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*?)&#46;([A-Za-z0-9.-]*\.[A-Z|a-z]{2,6})', r'\1.\2'),
            # URL 인코딩
            (r'([A-Za-z0-9._%+-]+)%40([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\2'),
            (r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*?)%2E([A-Za-z0-9.-]*\.[A-Z|a-z]{2,6})', r'\1.\2'),
            # 단어로 된 난독화
            (r'([A-Za-z0-9._%+-]+)[\s]*\b(at)\b[\s]*([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\3'),
            (r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*?)[\s]*\b(dot)\b[\s]*([A-Za-z0-9.-]*\.[A-Z|a-z]{2,6})', r'\1.\3'),
            # 한글 난독화
            (r'([A-Za-z0-9._%+-]+)[\s]*골뱅이[\s]*([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\2'),
            (r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*?)[\s]*점[\s]*([A-Za-z0-9.-]*\.[A-Z|a-z]{2,6})', r'\1.\3'),
            # 별표나 기타 특수문자로 대체
            (r'([A-Za-z0-9._%+-]+)[\s]*[\*\#\$\&][\s]*([A-Za-z0-9.-]+\.[A-Z|a-z]{2,6})', r'\1@\2'),
        ]
        
        # 난독화 해제 적용
        deobfuscated_text = raw_html + " " + text_content
        for pattern, replacement in obfuscated_patterns:
            deobfuscated_text = re.sub(pattern, replacement, deobfuscated_text, flags=re.IGNORECASE)
        
        # 난독화 해제된 텍스트에서 모든 패턴으로 이메일 재검색
        for pattern in email_patterns:
            deobfuscated_emails = re.findall(pattern, deobfuscated_text, re.IGNORECASE)
            emails.update(deobfuscated_emails)

        # 3. mailto: 링크에서 추출 (확장된 패턴 적용)
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
        for link in mailto_links:
            href = link.get('href', '')
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0]  # 쿼리 파라미터 제거
                email = email.strip()
                # 모든 패턴으로 검증
                for pattern in email_patterns:
                    if re.match(pattern, email, re.IGNORECASE):
                        emails.add(email)
                        break

        # 4. CSS로 숨겨진 이메일 찾기 (display:none, visibility:hidden 등)
        hidden_elements = soup.find_all(attrs={'style': re.compile(r'display\s*:\s*none|visibility\s*:\s*hidden', re.I)})
        for element in hidden_elements:
            hidden_text = element.get_text()
            # 모든 패턴으로 검색
            for pattern in email_patterns:
                hidden_emails = re.findall(pattern, hidden_text, re.IGNORECASE)
                emails.update(hidden_emails)

        # 5. 확장된 특정 태그와 클래스에서 이메일 찾기
        email_selectors = [
            'span[class*="email"]', 'div[class*="email"]', 'p[class*="email"]',
            'span[class*="mail"]', 'div[class*="mail"]', 'p[class*="mail"]',
            'span[class*="contact"]', 'div[class*="contact"]', 'p[class*="contact"]',
            '.contact-info', '.contact-details', '.contact-data',
            '.email', '.mail', '.e-mail',
            '.contact-us', '.contact-form', '.contact-section',
            '.footer-contact', '.footer-info', '.footer-details',
            '[data-email]', '[data-mail]', '[data-contact]',
            '[id*="email"]', '[id*="mail"]', '[id*="contact"]',
            '[class*="info"]', '[class*="detail"]',
            # 한국어 클래스명
            '[class*="연락"]', '[class*="문의"]', '[class*="이메일"]',
            # 추가 일반적인 선택자
            '.about', '.team', '.staff', '.member',
            'address', '.address', '.location',
            '.sidebar', '.widget', '.box'
        ]
        
        for selector in email_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # 텍스트에서 모든 패턴으로 이메일 찾기
                    element_text = element.get_text()
                    for pattern in email_patterns:
                        found_emails = re.findall(pattern, element_text, re.IGNORECASE)
                        emails.update(found_emails)
                    
                    # HTML 속성에서 찾기 (확장된 속성 목록)
                    for attr in ['data-email', 'data-mail', 'data-contact', 'title', 'alt', 'placeholder', 'value', 'content']:
                        if element.get(attr):
                            attr_value = element.get(attr).strip()
                            for pattern in email_patterns:
                                if re.match(pattern, attr_value, re.IGNORECASE):
                                    emails.add(attr_value)
                                    break
            except Exception as e:
                # 선택자 오류 무시하고 계속 진행
                continue

        # 6. 푸터 및 주요 영역에서 집중 검색
        important_sections = soup.find_all(
            ['footer', 'div', 'section', 'aside', 'header'], 
            class_=re.compile(r'footer|contact|info|about|team|staff|member|연락|문의', re.I)
        )
        for section in important_sections:
            section_text = section.get_text()
            for pattern in email_patterns:
                found_emails = re.findall(pattern, section_text, re.IGNORECASE)
                emails.update(found_emails)

        # 7. 스크립트 태그 내 이메일 (JavaScript에 숨겨진 경우)
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                script_text = script.string
                
                # 확장된 JavaScript 난독화 해제
                replacements = {
                    '[at]': '@', '(at)': '@', '{at}': '@', '<at>': '@',
                    '[dot]': '.', '(dot)': '.', '{dot}': '.', '<dot>': '.',
                    '_at_': '@', '-at-': '@', '*at*': '@',
                    '_dot_': '.', '-dot-': '.', '*dot*': '.',
                    '골뱅이': '@', '점': '.'
                }
                
                for old, new in replacements.items():
                    script_text = script_text.replace(old, new)
                
                # 확장된 JavaScript 문자열 연결 패턴들
                js_patterns = [
                    r'"([^"]+)"\s*\+\s*"@"\s*\+\s*"([^"]+)"',  # "user" + "@" + "domain.com"
                    r"'([^']+)'\s*\+\s*'@'\s*\+\s*'([^']+)'",  # 'user' + '@' + 'domain.com'
                    r'"([^"]+)"\s*\+\s*"\@"\s*\+\s*"([^"]+)"',  # 이스케이프된 @
                    r'([a-zA-Z0-9._%-]+)\s*\+\s*"@"\s*\+\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})',  # 변수 + "@" + 도메인
                ]
                
                for js_pattern in js_patterns:
                    js_matches = re.findall(js_pattern, script_text, re.IGNORECASE)
                    for match in js_matches:
                        potential_email = match[0] + '@' + match[1]
                        # 모든 패턴으로 검증
                        for pattern in email_patterns:
                            if re.match(pattern, potential_email, re.IGNORECASE):
                                emails.add(potential_email)
                                break
                
                # 스크립트에서 직접 이메일 찾기
                for pattern in email_patterns:
                    found_emails = re.findall(pattern, script_text, re.IGNORECASE)
                    emails.update(found_emails)

        # 8. 이미지 alt 텍스트 및 기타 속성에서 찾기
        images = soup.find_all('img')
        for img in images:
            for attr in ['alt', 'title', 'data-email', 'data-original-title']:
                if img.get(attr):
                    attr_text = img.get(attr)
                    for pattern in email_patterns:
                        found_emails = re.findall(pattern, attr_text, re.IGNORECASE)
                        emails.update(found_emails)
        
        # 9. 메타 태그에서 찾기
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            for attr in ['content', 'name', 'property', 'value']:
                if meta.get(attr):
                    meta_value = meta.get(attr)
                    for pattern in email_patterns:
                        found_emails = re.findall(pattern, meta_value, re.IGNORECASE)
                        emails.update(found_emails)
        
        # 10. 입력 필드에서 찾기 (placeholder, value 등)
        input_fields = soup.find_all(['input', 'textarea'])
        for field in input_fields:
            for attr in ['placeholder', 'value', 'data-placeholder', 'title']:
                if field.get(attr):
                    field_value = field.get(attr)
                    for pattern in email_patterns:
                        found_emails = re.findall(pattern, field_value, re.IGNORECASE)
                        emails.update(found_emails)

        # 필터링: 확장된 제외 패턴
        filtered_emails = []
        exclude_patterns = [
            r'.*@example\.(com|org|net)',
            r'.*@test\.(com|org|net)',
            r'.*@placeholder\.(com|org|net)',
            r'.*@sample\.(com|org|net)',
            r'.*@demo\.(com|org|net)',
            r'noreply@.*', r'no-reply@.*', r'donotreply@.*',
            r'.*@localhost.*', r'.*@127\.0\.0\.1.*',
            r'.*@\[.*\].*',  # IP 주소 형태 제외
            r'admin@.*', r'webmaster@.*', r'postmaster@.*',
            r'.*@(spam|fake|invalid|null|void)\.',
            r'.*@.*\.(jpg|png|gif|pdf|doc|docx|xls|xlsx)$',  # 파일 확장자
        ]
        
        for email in emails:
            email = email.lower().strip()
            if email and not any(re.match(pattern, email, re.IGNORECASE) for pattern in exclude_patterns):
                # 도메인이 현재 웹사이트와 관련있는지 확인
                if url:
                    domain = email.split('@')[1]
                    url_domain = urllib.parse.urlparse(url).netloc.lower()
                    # 같은 도메인이거나 서브도메인인 경우 우선순위
                    if domain in url_domain or url_domain.endswith(domain):
                        filtered_emails.insert(0, email)  # 앞에 추가
                    else:
                        filtered_emails.append(email)
                else:
                    filtered_emails.append(email)
        
        logger.info(f"📧 HTML에서 {len(filtered_emails)}개 이메일 추출: {filtered_emails}")
        return filtered_emails
        
    except Exception as e:
        logger.error(f"이메일 추출 중 오류: {str(e)}")
        return []
