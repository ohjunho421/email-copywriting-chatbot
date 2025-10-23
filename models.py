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
    name = db.Column(db.String(100), nullable=False)
    company_nickname = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    
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
    
    def get_email_count(self):
        """생성한 이메일 문안 개수"""
        return self.email_generations.count()
    
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
