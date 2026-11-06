"""Google Identity Services popup authentication; our own same-origin CSRF form is used."""
import secrets
from flask import Blueprint, current_app, flash, g, redirect, request, session, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import User, Member, GoogleIdentity
from app.auth import landing_url, registration_blocked, account_guard

google_auth = Blueprint('google_auth', __name__)


def google_context():
    if 'google_nonce' not in session:
        session['google_nonce'] = secrets.token_urlsafe(32)
    return {'google_client_id': current_app.config.get('GOOGLE_CLIENT_ID', ''),
            'google_nonce': session['google_nonce']}


def verify_credential(credential, client_id):
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request
    # Signature, audience, issuer and expiry are checked by Google's library.
    return id_token.verify_oauth2_token(credential, Request(), audience=client_id, clock_skew_in_seconds=30)


@google_auth.post('/auth/google')
def sign_in():
    linking = request.form.get('intent') == 'link'
    target = url_for('auth.profile' if linking and g.user else 'auth.login')
    def fail(message):
        flash(message, 'danger')
        return redirect(target, code=303)
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    if not client_id:
        return fail('Đăng nhập Google chưa được cấu hình.')
    credential = request.form.get('credential', '')
    if not credential or len(credential) > 16384:
        return fail('Không nhận được thông tin Google. Vui lòng thử lại.')
    try:
        claims = verify_credential(credential, client_id)
    except ValueError as error:
        # Log only a category, never the token, account data or exception payload.
        reason = str(error).lower()
        if 'too early' in reason or 'expired' in reason or 'iat' in reason or 'exp' in reason:
            code = 'token_time'
            message = 'Thông tin Google chưa đến hạn hoặc đã hết hạn. Hãy tải lại trang và kiểm tra đồng bộ giờ Windows.'
        elif 'audience' in reason:
            code = 'wrong_audience'
            message = 'Client ID Google không khớp. Vui lòng tải lại trang đăng nhập.'
        elif 'certificate' in reason or 'signature' in reason:
            code = 'signature_or_certificate'
            message = 'Chưa xác minh được chữ ký Google. Vui lòng thử lại sau.'
        else:
            code = 'invalid_token'
            message = 'Thông tin đăng nhập Google không hợp lệ. Vui lòng tải lại trang và thử lại.'
        current_app.logger.warning('Google login rejected: %s (%s)', code, type(error).__name__)
        return fail(message)
    except Exception:
        current_app.logger.warning('Google credential verification unavailable')
        return fail('Chưa thể kết nối Google để xác minh. Vui lòng thử lại sau.')
    nonce = session.get('google_nonce', '')
    received_nonce = claims.get('nonce')
    if not nonce or not isinstance(received_nonce, str) or not secrets.compare_digest(nonce, received_nonce):
        return fail('Phiên đăng nhập Google đã thay đổi. Vui lòng thử lại.')
    subject = claims.get('sub')
    email = claims.get('email', '').strip().lower()
    if (not isinstance(subject, str) or not subject or len(subject) > 255
            or claims.get('email_verified') is not True or '@' not in email or len(email) > 120):
        return fail('Google chưa xác minh email hoặc thông tin tài khoản không hợp lệ.')
    if registration_blocked(email, subject):
        return fail('Tài khoản này đã bị chặn đăng ký. Vui lòng liên hệ quản trị viên.')
    identity = GoogleIdentity.query.filter_by(subject=subject).first()
    if linking:
        if not g.user:
            return fail('Vui lòng đăng nhập bằng mật khẩu trước khi liên kết Google.')
        if not g.user.check_password(request.form.get('link_password', '')):
            return fail('Mật khẩu hiện tại không đúng. Chưa liên kết Google.')
        if email != g.user.email.lower():
            return fail('Hãy chọn tài khoản Google có cùng email đăng nhập của bạn.')
        if identity or g.user.google_identity:
            return fail('Tài khoản Google hoặc tài khoản thư viện này đã được liên kết.')
        db.session.add(GoogleIdentity(subject=subject, user_id=g.user.id))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return fail('Tài khoản đã được liên kết. Vui lòng tải lại trang.')
        session.pop('google_nonce', None)
        flash('Đã liên kết Google. Lần sau bạn có thể đăng nhập bằng Google.', 'success')
        return redirect(url_for('auth.profile'), code=303)
    if g.user:
        return redirect(landing_url(g.user), code=303)
    if identity:
        user = identity.user
        if not user.active:
            return fail('Tài khoản thư viện đã bị khóa. Vui lòng liên hệ thủ thư.')
    else:
        if User.query.filter(func.lower(User.email) == email).first():
            return fail('Email đã có tài khoản. Hãy đăng nhập bằng mật khẩu, vào Hồ sơ cá nhân và liên kết Google.')
        if Member.query.filter(func.lower(Member.email) == email).first():
            return fail('Email đã có trong danh bạ. Vui lòng nhờ quản trị viên cấp tài khoản rồi liên kết Google.')
        if not email.endswith('@gmail.com') and not claims.get('hd'):
            return fail('Vui lòng dùng Gmail hoặc tài khoản Google Workspace, hoặc đăng ký bằng email và mật khẩu.')
        name = str(claims.get('name') or email.split('@')[0])[:100]
        member = Member(name=name, email=email, member_id='MEM' + secrets.token_hex(5).upper())
        user = User(email=email, password_hash='', role='reader', member=member)
        db.session.add(user)
        try:
            db.session.flush()
            db.session.add(GoogleIdentity(subject=subject, user_id=user.id))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return fail('Tài khoản vừa được tạo hoặc liên kết. Vui lòng đăng nhập lại.')
    session.clear()
    session['user_id'] = user.id
    session['account_guard'] = account_guard(user)
    return redirect(landing_url(user), code=303)
