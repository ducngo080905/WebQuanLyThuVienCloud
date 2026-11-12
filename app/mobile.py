"""JSON interface for the native Android client, backed by the web workflows."""
from datetime import date, datetime, timedelta, timezone
from functools import wraps
import hashlib
import re
import secrets

from flask import Blueprint, abort, g, get_flashed_messages, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.orm import joinedload, selectinload

from app import db
from app import auth, features, messages, operations, routes
from app.models import AccountRecovery, Announcement, Book, BorrowRequest, Issue, MobileConnection, RenewalRequest, User

mobile = Blueprint('mobile', __name__, url_prefix='/api/mobile')


@mobile.after_request
def no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@mobile.errorhandler(400)
@mobile.errorhandler(403)
@mobile.errorhandler(404)
def action_error(error):
    labels = {400: 'Thông tin gửi lên không hợp lệ.', 403: 'Bạn không có quyền thực hiện.', 404: 'Không tìm thấy dữ liệu.'}
    return jsonify(error=labels[error.code]), error.code


def require_role(*roles):
    def decorate(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            if not g.user:
                return jsonify(error='Phiên đăng nhập đã hết. Vui lòng đăng nhập lại.'), 401
            if roles and g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return guarded
    return decorate


def session_payload(user):
    token = session.setdefault('csrf_token', secrets.token_urlsafe(32))
    return jsonify(csrf_token=token, user=(
        {'name': user.member.name, 'role': user.role, 'email': user.email}
        if user else None
    ))


@mobile.get('/session')
def session_info():
    return session_payload(g.user)


@mobile.post('/login')
def login():
    if g.user:
        return session_payload(g.user)
    auth.login()
    user_id = session.get('user_id')
    user = db.session.get(User, user_id) if user_id else None
    if not user:
        alerts = get_flashed_messages()
        return jsonify(error=alerts[-1] if alerts else 'Không đăng nhập được.'), 401
    if user.password_change_required:
        session.clear()
        return jsonify(error='Hãy đổi mật khẩu tạm trên web rồi đăng nhập lại.'), 403
    return session_payload(user)


@mobile.post('/logout')
def logout():
    auth.logout()
    return jsonify(ok=True)


def connection_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@mobile.post('/connect')
def start_connection():
    proof_hash = request.form.get('proof_hash', '')
    mode = request.form.get('mode', 'login')
    if not re.fullmatch(r'[a-f0-9]{64}', proof_hash) or mode not in ('login', 'register'):
        abort(400)
    now = connection_now()
    MobileConnection.query.filter(MobileConnection.expires_at <= now).delete()
    item = MobileConnection(id=secrets.token_urlsafe(32), proof_hash=proof_hash,
                            expires_at=now + timedelta(minutes=10))
    db.session.add(item)
    db.session.commit()
    return jsonify(id=item.id, path=url_for('mobile.open_connection', connection_id=item.id, mode=mode))


@mobile.get('/connect/<connection_id>')
def open_connection(connection_id):
    item = db.session.get(MobileConnection, connection_id)
    if not item or item.expires_at <= connection_now() or item.user_id:
        return render_template('mobile_connect.html', expired=True), 410
    session['mobile_connection'] = item.id
    mode = 'register' if request.args.get('mode') == 'register' else 'login'
    return redirect(url_for('mobile.confirm_connection') if g.user else url_for('auth.' + mode))


@mobile.route('/connect/confirm', methods=['GET', 'POST'])
def confirm_connection():
    item = db.session.get(MobileConnection, session['mobile_connection']) if session.get('mobile_connection') else None
    if not item or item.expires_at <= connection_now() or item.user_id:
        session.pop('mobile_connection', None)
        return render_template('mobile_connect.html', expired=True), 410
    if not g.user:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        if request.form.get('action') in ('switch', 'register'):
            mode = 'register' if request.form['action'] == 'register' else 'login'
            auth.logout()
            session['mobile_connection'] = item.id
            return redirect(url_for('auth.' + mode), code=303)
        if g.user.password_change_required:
            return render_template('mobile_connect.html', must_change=True), 403
        changed = MobileConnection.query.filter_by(id=item.id, user_id=None).filter(
            MobileConnection.expires_at > connection_now()
        ).update({'user_id': g.user.id, 'account_guard': auth.account_guard(g.user)})
        if not changed:
            db.session.rollback()
            return render_template('mobile_connect.html', expired=True), 410
        db.session.commit()
        session.pop('mobile_connection', None)
        return render_template('mobile_connect.html', completed=True)
    return render_template('mobile_connect.html')


@mobile.post('/connect/exchange')
def exchange_connection():
    proof = request.form.get('proof', '')
    if not re.fullmatch(r'[a-f0-9]{64}', proof):
        abort(400)
    item = db.session.get(MobileConnection, request.form.get('id', ''))
    if not item or item.expires_at <= connection_now() or not secrets.compare_digest(
        item.proof_hash, hashlib.sha256(proof.encode()).hexdigest()
    ):
        return jsonify(error='Yêu cầu kết nối đã hết hạn. Hãy bắt đầu lại.'), 410
    if item.user_id is None:
        return jsonify(pending=True), 202
    user = db.session.get(User, item.user_id)
    if not user or not user.active or user.password_change_required or item.account_guard != auth.account_guard(user):
        return jsonify(error='Tài khoản đã thay đổi. Hãy đăng nhập lại.'), 403
    consumed = MobileConnection.query.filter_by(id=item.id, user_id=user.id, proof_hash=item.proof_hash).filter(
        MobileConnection.expires_at > connection_now()).delete()
    db.session.commit()
    if not consumed:
        return jsonify(error='Yêu cầu kết nối đã được sử dụng.'), 410
    auth.start_user_session(user)
    return session_payload(user)


def serialize_book(book):
    info = book.info
    return dict(book.to_dict(), cover=url_for('main.book_cover', book_id=book.id, v=book.cover.version) if book.cover else '',
                description=(info.description or '') if info else '',
                publisher=(info.publisher or '') if info else '', language=(info.language or '') if info else '',
                shelf=(info.shelf or '') if info else '', year=info.year if info else None, pages=info.pages if info else None,
                samples=[{'url': url_for('features.sample_image', page_id=sample.id),
                          'type': sample.mimetype, 'pages': sample.page_count} for sample in book.sample_pages])


@mobile.get('/library')
@require_role()
def library():
    staff = g.user.role in ('admin', 'librarian')
    books = Book.query.options(joinedload(Book.cover), joinedload(Book.info), selectinload(Book.sample_pages)).order_by(Book.id.desc()).all()
    loans = Issue.query.options(joinedload(Issue.book), joinedload(Issue.member), selectinload(Issue.renewals))
    requests = BorrowRequest.query.options(joinedload(BorrowRequest.book), joinedload(BorrowRequest.member))
    if not staff:
        loans = loans.filter_by(member_id=g.user.member_id)
        requests = requests.filter_by(member_id=g.user.member_id)
    loan_rows = [dict(loan.to_dict(), book_id=loan.book_id,
                      can_renew=loan.status == 'issued' and loan.due_date.date() >= date.today()
                      and not any(r.status == 'pending' for r in loan.renewals)
                      and sum(r.status == 'approved' for r in loan.renewals) < 2,
                      renewal_pending=any(r.status == 'pending' for r in loan.renewals))
                 for loan in loans.order_by(Issue.id.desc()).all()]
    request_rows = [{'id': item.id, 'book_id': item.book_id, 'book': item.book.title,
                     'member': item.member.name, 'status': item.status}
                    for item in requests.order_by(BorrowRequest.id.desc()).all()]
    renewals = []
    if staff:
        pending = RenewalRequest.query.options(joinedload(RenewalRequest.issue).joinedload(Issue.book),
                                               joinedload(RenewalRequest.issue).joinedload(Issue.member))
        renewals = [{'id': item.id, 'book': item.issue.book.title, 'member': item.issue.member.name,
                     'days': item.requested_days} for item in pending.filter_by(status='pending').order_by(RenewalRequest.id.desc()).all()]
    updates = messages.live().get_json()
    sent = [{'id': item.id, 'body': item.body, 'color': item.color,
             'expires_at': (item.expires_at + messages.NOTICE_OFFSET).strftime('%Y-%m-%dT%H:%M') if item.expires_at else ''}
            for item in Announcement.query.order_by(Announcement.id.desc()).all()] if g.user.role == 'admin' else []
    accounts = [{'id': user.id, 'name': user.member.name, 'email': user.email,
                 'role': user.role, 'active': user.active}
                for user in User.query.options(joinedload(User.member)).order_by(User.id).all()] if g.user.role == 'admin' else []
    return jsonify(books=[serialize_book(book) for book in books], loans=loan_rows, requests=request_rows,
                   renewals=renewals, notices=updates['announcements'], sent=sent,
                   accounts=accounts, maintenance=bool(g.get('maintenance_enabled')),
                   phone_required=updates['phone_required'], default_due=(date.today()+timedelta(days=14)).isoformat())


def web_action(view, *args):
    response = view(*args)
    alerts = get_flashed_messages(with_categories=True)
    error = next((message for category, message in alerts if category == 'danger'), None)
    if error:
        return jsonify(error=error), 400
    if getattr(response, 'status_code', 200) not in (302, 303):
        return jsonify(error='Máy chủ chưa lưu được thay đổi.'), 400
    return jsonify(ok=True, message=alerts[-1][1] if alerts else 'Đã cập nhật.')


@mobile.post('/phone')
@require_role()
def update_phone():
    return messages.phone()


@mobile.post('/borrow/<int:book_id>')
@require_role('reader')
def borrow(book_id):
    if not messages.valid_phone(g.user.member.phone):
        return jsonify(error='Vui lòng bổ sung số điện thoại trước khi mượn sách.'), 428
    return web_action(auth.request_book, book_id)


@mobile.post('/cancel/<int:item_id>')
@require_role('reader')
def cancel(item_id):
    return web_action(auth.cancel_request, item_id)


@mobile.post('/renew/<int:issue_id>')
@require_role('reader')
def renew(issue_id):
    if not messages.valid_phone(g.user.member.phone):
        return jsonify(error='Vui lòng bổ sung số điện thoại trước khi gia hạn.'), 428
    return web_action(features.request_renewal, issue_id)


@mobile.post('/requests/<int:item_id>')
@require_role('admin', 'librarian')
def review_request(item_id):
    return web_action(auth.review_request, item_id)


@mobile.post('/renewals/<int:item_id>')
@require_role('admin', 'librarian')
def review_renewal(item_id):
    return web_action(features.review_renewal, item_id)


@mobile.post('/returns/<int:issue_id>')
@require_role('admin', 'librarian')
def return_book(issue_id):
    return web_action(routes.return_book, issue_id)


@mobile.post('/books')
@require_role('admin', 'librarian')
def add_book():
    return web_action(routes.add_book)


@mobile.post('/books/<int:book_id>')
@require_role('admin', 'librarian')
def edit_book(book_id):
    return web_action(features.edit_book, book_id)


@mobile.post('/books/<int:book_id>/delete')
@require_role('admin', 'librarian')
def delete_book(book_id):
    return web_action(routes.delete_book, book_id)


@mobile.post('/notices')
@require_role('admin')
def publish():
    return web_action(messages.compose)


@mobile.post('/notices/<int:item_id>/delete')
@require_role('admin')
def remove_notice(item_id):
    return web_action(messages.delete_announcement, item_id)


@mobile.post('/accounts')
@require_role('admin')
def manage_account():
    if request.form.get('action') == 'create' or request.form.get('user_id', type=int) is None:
        abort(400)
    return web_action(auth.accounts)


@mobile.post('/accounts/<int:user_id>/delete')
@require_role('admin')
def remove_account(user_id):
    return web_action(auth.delete_account, user_id)


@mobile.get('/recoveries')
@require_role('admin')
def recoveries():
    items = AccountRecovery.query.order_by(AccountRecovery.created_at.desc()).limit(100).all()
    return jsonify(items=[{key: getattr(item, key) for key in
                           ('id', 'email', 'name', 'phone', 'member_code', 'contact', 'evidence', 'status')}
                          for item in items])


@mobile.post('/recoveries/<int:item_id>')
@require_role('admin')
def review_recovery(item_id):
    response = features.review_recovery(item_id)
    if request.form.get('action') == 'approve' and response.status_code == 200:
        item = db.get_or_404(AccountRecovery, item_id)
        return jsonify(ok=True, temporary=features.read_recovery_password(item), contact=item.contact)
    return web_action(lambda: response)


@mobile.route('/reports', methods=['GET', 'POST'])
@require_role('admin', 'librarian')
def reports():
    if request.method == 'POST':
        return web_action(features.reports)
    if request.args.get('format') == 'xlsx':
        return features.reports()
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        start = datetime.strptime(month, '%Y-%m')
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    except (ValueError, OverflowError):
        abort(400)
    loans = Issue.query.options(joinedload(Issue.book), joinedload(Issue.member)).filter(
        Issue.issue_date >= start, Issue.issue_date < end).order_by(Issue.issue_date.desc()).all()
    return jsonify(month=month, rate=features.setting('fine_per_day'),
                   loans=[dict(issue.to_dict(), fine=features.fine_amount(issue)) for issue in loans])


@mobile.post('/maintenance')
@require_role('admin')
def maintenance():
    return operations.toggle()
