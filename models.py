"""
데이터베이스 모델
- User: 사용자 정보 및 인증
- EmailGeneration: 이메일 문안 생성 기록
- BlogPost: 포트원 블로그 포스트 캐시 (PostgreSQL 영구 저장)
- BlogCacheMetadata: 블로그 캐시 메타데이터
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 한글 이름
    name_en = db.Column(db.String(100), nullable=True)  # 영문 이름 (선택사항)
    company_nickname = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    
    # 이메일 서명 (HTML 형식)
    email_signature = db.Column(db.Text, nullable=True)
    
    # Gmail 앱 비밀번호 (암호화 저장)
    gmail_app_password = db.Column(db.String(200), nullable=True)
    
    # SendGrid API 키 (Railway 환경 이메일 발송용)
    sendgrid_api_key = db.Column(db.String(200), nullable=True)
    
    # 승인 시스템
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # 관계
    email_generations = db.relationship('EmailGeneration', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """비밀번호 해시 설정"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """비밀번호 검증"""
        return check_password_hash(self.password_hash, password)
    
    def set_gmail_app_password(self, app_password):
        """Gmail 앱 비밀번호 저장 (평문)"""
        # 주의: 평문 저장이지만 Gmail 앱 비밀번호는 계정 비밀번호와 다르며
        # 언제든지 삭제/재생성 가능하므로 상대적으로 안전함
        self.gmail_app_password = app_password
    
    def get_gmail_app_password(self):
        """Gmail 앱 비밀번호 조회"""
        return self.gmail_app_password
    
    def set_sendgrid_api_key(self, api_key):
        """SendGrid API 키 저장 (평문)"""
        # Railway 환경에서 이메일 발송을 위한 SendGrid API 키
        self.sendgrid_api_key = api_key
    
    def get_sendgrid_api_key(self):
        """SendGrid API 키 조회"""
        return self.sendgrid_api_key
    
    def get_email_count(self):
        """생성한 이메일 문안 개수"""
        return self.email_generations.count()
    
    def generate_email_signature(self):
        """
        사용자 서명 자동 생성
        로고 + 이름 + 연락처 + 회사 주소
        """
        # 이름 형식: "한글이름 영문이름" 또는 "한글이름"
        if self.name_en:
            full_name = f"{self.name} {self.name_en}"
        else:
            full_name = self.name
        
        signature = f'''<br><br>
<img src="/static/images/PortOne_Logo_Black.png" alt="PortOne Logo" style="height: 40px; margin-bottom: 5px;"><br>
<div style="border-bottom: 1px solid #e0e0e0; width: 200px; margin: 5px 0 10px 0;"></div>
{full_name}<br>
Sales team | SDR<br>
E <a href="mailto:{self.email}">{self.email}</a> | M {self.phone}<br>
서울시 성동구 성수이로 20길 16 JK타워 4층<br>
<a href="https://www.portone.io">https://www.portone.io</a>'''
        
        return signature
    
    def __repr__(self):
        return f'<User {self.email} - {self.name}>'


class EmailGeneration(db.Model):
    __tablename__ = 'email_generations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 회사 정보
    company_name = db.Column(db.String(200), nullable=False)
    company_email = db.Column(db.String(120), nullable=True)
    
    # 생성된 이메일 정보
    email_type = db.Column(db.String(50), nullable=False)  # opi_professional, finance_curiosity 등
    selected = db.Column(db.Boolean, default=False)  # 사용자가 선택한 문안인지
    
    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 생성 방식
    generation_mode = db.Column(db.String(20), default='ssr')  # ssr, user_template, user_request
    
    def __repr__(self):
        return f'<EmailGeneration {self.company_name} - {self.email_type}>'


class BlogPost(db.Model):
    """포트원 블로그 포스트 캐시 (PostgreSQL 영구 저장)"""
    __tablename__ = 'blog_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500), unique=True, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True, index=True)
    keywords = db.Column(db.Text, nullable=True)  # JSON 문자열
    industry_tags = db.Column(db.Text, nullable=True)  # JSON 문자열
    
    # 🆕 AI 요약 컬럼 - 블로그 매칭 정확도 향상
    ai_summary = db.Column(db.Text, nullable=True)  # AI가 생성한 핵심 요약
    target_audience = db.Column(db.Text, nullable=True)  # 타겟 고객 (예: "글로벌 진출 계획 기업", "PG 수수료 고민 기업")
    key_benefits = db.Column(db.Text, nullable=True)  # 핵심 효과 (예: "수수료 15% 절감", "개발 리소스 85% 절감")
    pain_points_addressed = db.Column(db.Text, nullable=True)  # 해결하는 문제점들
    case_company = db.Column(db.String(100), nullable=True)  # 사례 고객사명 (예: "핏펫", "혼다코리아")
    case_industry = db.Column(db.String(50), nullable=True)  # 사례 고객사 업종
    
    # 메타데이터
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BlogPost {self.title}>'
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'title': self.title,
            'link': self.link,
            'summary': self.summary,
            'content': self.content,
            'category': self.category,
            'keywords': self.keywords,
            'industry_tags': self.industry_tags,
            'ai_summary': self.ai_summary,
            'target_audience': self.target_audience,
            'key_benefits': self.key_benefits,
            'pain_points_addressed': self.pain_points_addressed,
            'case_company': self.case_company,
            'case_industry': self.case_industry,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class BlogCacheMetadata(db.Model):
    """블로그 캐시 메타데이터"""
    __tablename__ = 'blog_cache_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    posts_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<BlogCacheMetadata posts={self.posts_count} updated={self.last_updated}>'
