"""
관리자 시스템 - 사용자 승인, 통계 관리
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, EmailGeneration
from datetime import datetime
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """관리자 권한 체크 데코레이터"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """관리자 대시보드"""
    # 승인 대기 중인 사용자
    pending_users = User.query.filter_by(is_approved=False).order_by(User.created_at.desc()).all()
    
    # 승인된 사용자 (관리자 제외)
    approved_users = User.query.filter_by(is_approved=True, is_admin=False).order_by(User.created_at.desc()).all()
    
    # 전체 통계
    total_users = User.query.filter_by(is_approved=True).count()
    pending_count = User.query.filter_by(is_approved=False).count()
    total_emails = EmailGeneration.query.count()
    
    # 사용자별 이메일 생성 통계
    user_stats = db.session.query(
        User.id,
        User.name,
        User.email,
        User.company_nickname,
        func.count(EmailGeneration.id).label('email_count')
    ).join(EmailGeneration, User.id == EmailGeneration.user_id, isouter=True)\
     .filter(User.is_approved == True)\
     .group_by(User.id)\
     .order_by(func.count(EmailGeneration.id).desc())\
     .all()
    
    return render_template('admin_dashboard.html',
                         pending_users=pending_users,
                         approved_users=approved_users,
                         user_stats=user_stats,
                         total_users=total_users,
                         pending_count=pending_count,
                         total_emails=total_emails)


@admin_bp.route('/approve/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    """사용자 승인"""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.is_approved:
            flash('이미 승인된 사용자입니다.', 'info')
        else:
            user.is_approved = True
            user.approved_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"✅ 사용자 승인: {user.email} ({user.name}) by {current_user.email}")
            flash(f'{user.name}({user.email}) 사용자가 승인되었습니다.', 'success')
        
        return redirect(url_for('admin.dashboard'))
        
    except Exception as e:
        logger.error(f"사용자 승인 오류: {e}")
        flash('승인 처리 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/reject/<int:user_id>', methods=['POST'])
@admin_required
def reject_user(user_id):
    """사용자 거부 (삭제)"""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.is_admin:
            flash('관리자 계정은 삭제할 수 없습니다.', 'error')
            return redirect(url_for('admin.dashboard'))
        
        email = user.email
        name = user.name
        
        db.session.delete(user)
        db.session.commit()
        
        logger.info(f"🚫 사용자 거부: {email} ({name}) by {current_user.email}")
        flash(f'{name}({email}) 사용자가 거부되었습니다.', 'success')
        
        return redirect(url_for('admin.dashboard'))
        
    except Exception as e:
        logger.error(f"사용자 거부 오류: {e}")
        flash('거부 처리 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """통계 API"""
    try:
        # 오늘 생성된 이메일
        today = datetime.utcnow().date()
        today_emails = EmailGeneration.query.filter(
            func.date(EmailGeneration.created_at) == today
        ).count()
        
        # 이번 주 생성된 이메일
        # ... (추가 구현 가능)
        
        return jsonify({
            'today_emails': today_emails,
            'total_users': User.query.filter_by(is_approved=True).count(),
            'pending_users': User.query.filter_by(is_approved=False).count()
        })
        
    except Exception as e:
        logger.error(f"통계 API 오류: {e}")
        return jsonify({'error': str(e)}), 500
