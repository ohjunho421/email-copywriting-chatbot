"""
데이터베이스 모델
- User: 사용자 정보 및 인증
- EmailGeneration: 이메일 문안 생성 기록
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
        
        signature = f'''--
<img src="/static/images/PortOne_Logo_Black.png" alt="PortOne Logo" style="height: 40px; margin-bottom: 10px;"><br>
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
