"""
인증 시스템 - 회원가입, 로그인, 로그아웃
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """회원가입"""
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
        data = request.form
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        name_en = data.get('name_en', '').strip()  # 영문 이름 (선택사항)
        company_nickname = data.get('company_nickname', '').strip()
        phone = data.get('phone', '').strip()
        
        # 유효성 검사 (필수 필드)
        if not all([email, password, name, company_nickname, phone]):
            flash('모든 필수 필드를 입력해주세요.', 'error')
            return redirect(url_for('auth.register'))
        
        # 이메일 중복 확인
        if User.query.filter_by(email=email).first():
            flash('이미 등록된 이메일입니다.', 'error')
            return redirect(url_for('auth.register'))
        
        # 새 사용자 생성
        user = User(
            email=email,
            name=name,
            name_en=name_en if name_en else None,
            company_nickname=company_nickname,
            phone=phone
        )
        user.set_password(password)
        
        # 서명 자동 생성
        user.email_signature = user.generate_email_signature()
        
        # ocean@portone.io는 자동 승인 및 관리자 권한
        if email == 'ocean@portone.io':
            user.is_approved = True
            user.is_admin = True
            user.approved_at = datetime.utcnow()
            logger.info(f"🔑 관리자 계정 생성: {email}")
        else:
            user.is_approved = False
            user.is_admin = False
            logger.info(f"👤 신규 가입 대기: {email} ({name})")
        
        db.session.add(user)
        db.session.commit()
        
        if user.is_approved:
            flash(f'관리자 계정으로 가입되었습니다! 로그인해주세요.', 'success')
        else:
            flash(f'회원가입이 완료되었습니다! 관리자 승인 후 이용 가능합니다.', 'info')
        
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"회원가입 오류: {e}")
        flash('회원가입 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('auth.register'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인"""
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        data = request.form
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        
        if not email or not password:
            flash('이메일과 비밀번호를 입력해주세요.', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
            return redirect(url_for('auth.login'))
        
        if not user.is_approved:
            flash('아직 관리자 승인이 완료되지 않았습니다. 승인 후 이용 가능합니다.', 'warning')
            return redirect(url_for('auth.login'))
        
        # 로그인 성공
        login_user(user, remember=True)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"✅ 로그인 성공: {email}")
        flash(f'{user.name}님, 환영합니다!', 'success')
        
        # 관리자면 관리자 페이지로
        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"로그인 오류: {e}")
        flash('로그인 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    """로그아웃"""
    logger.info(f"👋 로그아웃: {current_user.email}")
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/check-email', methods=['POST'])
def check_email():
    """이메일 중복 확인 API"""
    try:
        email = request.json.get('email', '').strip().lower()
        exists = User.query.filter_by(email=email).first() is not None
        return jsonify({'exists': exists})
    except Exception as e:
        logger.error(f"이메일 확인 오류: {e}")
        return jsonify({'error': str(e)}), 500
