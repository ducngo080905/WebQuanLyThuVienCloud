from datetime import datetime, timedelta
from functools import wraps
import secrets
import hashlib
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import User, Member, Issue, Book, BorrowRequest, RegistrationBlock, DeletedAccountId, PasswordChangeRequired, GoogleIdentity

auth = Blueprint('auth', __name__)
ROLES = {'admin': 'Quản trị viên', 'librarian': 'Thủ thư', 'reader': 'Độc giả'}


def install_auth(app):
    @app.before_request
    def authenticate():
        g.activity_logout_session = None
        # Public static assets never need a session or database lookup.
        if request.endpoint == 'static':
            g.user = None
            return
        g.user = db.session.get(User, session.get('user_id')) if session.get('user_id') else None
        if session.get('user_id') and not g.user:
            session.clear()
        if g.user:
            expected = account_guard(g.user)
            supplied = session.get('account_guard')
            if (supplied and not secrets.compare_digest(supplied, expected)) or (not supplied and db.session.get(DeletedAccountId, g.user.id)):
                session.clear()
                g.user = None
            elif not supplied:
                session['account_guard'] = expected
        if g.user and not g.user.active:
            session.clear()
            g.user = None
        from app.operations import maintenance_gate
        blocked=maintenance_gate()
        if blocked is not None:return blocked
        if g.user and g.user.password_change_required and (request.endpoint or '').startswith('mobile.') and request.endpoint not in ('mobile.logout', 'mobile.confirm_connection'):
            from flask import jsonify
            return jsonify(error='Hãy đổi mật khẩu tạm trên web rồi đăng nhập lại.'), 403
        if g.user and g.user.password_change_required and request.endpoint not in ('auth.profile','auth.logout','static','activity.heartbeat','messages.live','messages.phone','messages.read','operations.status','operations.page','operations.toggle','mobile.logout','mobile.confirm_connection'):
            return redirect(url_for('auth.profile'))
        # An old login tab may be submitted after another tab has signed in.
        if g.user and request.endpoint == 'auth.login':
            return redirect(landing_url(g.user), code=303)
        if request.method == 'POST' and app.config.get('WTF_CSRF_ENABLED', True):
            token = session.get('csrf_token', '')
            if not token or not secrets.compare_digest(token, request.form.get('csrf_token', '')):
                if (request.endpoint or '').startswith('mobile.'):
                    from flask import jsonify
                    return jsonify(error='Phiên đăng nhập đã thay đổi. Vui lòng thử lại.'), 403
                flash('Biểu mẫu đã cũ hoặc phiên làm việc đã thay đổi. Vui lòng thử lại trên trang vừa tải.', 'info')
                safe_pages = {'auth.login': 'auth.login', 'auth.register': 'auth.register',
                              'auth.profile': 'auth.profile', 'auth.accounts': 'auth.accounts',
                              'auth.setup': 'auth.setup'}
                target = url_for(safe_pages.get(request.endpoint, 'auth.library_home'))
                if request.endpoint == 'auth.setup':
                    target = url_for('auth.setup', token=request.args.get('token', ''))
                return redirect(target, code=303)
        endpoint = request.endpoint or ''
        if endpoint.startswith('main.') and endpoint not in ('main.health', 'main.book_cover', 'main.download_android'):
            if not g.user:
                if endpoint.startswith('main.api_'):
                    abort(401)
                return redirect(url_for('auth.login'))
            if g.user.role == 'reader':
                if endpoint == 'main.books':
                    return redirect(url_for('auth.catalog'))
                if endpoint != 'main.api_books':
                    abort(403)

    @app.after_request
    def prevent_stale_forms(response):
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.context_processor
    def account_context():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return {'current_user': g.get('user'), 'role_names': ROLES,
                'csrf_token': session['csrf_token'],
                'is_staff': bool(g.get('user') and g.user.role in ('admin', 'librarian'))}

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('message.html', heading='Không có quyền truy cập',
                               message='Tài khoản của bạn không được phép thực hiện thao tác này.'), 403


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped


def valid_fields(name, email, password, phone=''):
    return (bool(name) and len(name) <= 100 and len(email) <= 120
            and '@' in email and '.' in email.rsplit('@', 1)[-1]
            and 8 <= len(password) <= 128 and len(phone) <= 20)


def create_account(name, email, password, phone='', role='reader', link_existing=False, google_subject=None):
    if registration_blocked(email, google_subject):
        raise ValueError('Email này đã bị chặn đăng ký. Vui lòng liên hệ quản trị viên.')
    member = Member.query.filter(func.lower(Member.email) == email).first()
    if member and not link_existing:
        raise ValueError('Email đã có trong danh bạ. Vui lòng nhờ quản trị viên cấp tài khoản.')
    if User.query.filter(func.lower(User.email) == email).first():
        raise ValueError('Email đã được sử dụng.')
    if not member:
        member = Member(name=name, email=email, phone=phone, member_id='MEM' + secrets.token_hex(5).upper())
        db.session.add(member)
        db.session.flush()
    user = User(email=email, role=role, member_id=member.id)
    user.set_password(password)
    db.session.add(user)
    if google_subject:
        db.session.flush()
        db.session.add(GoogleIdentity(subject=google_subject,user_id=user.id))
    db.session.commit()
    return user


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(landing_url(g.user))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        attempts = session.get('login_attempts', 0)
        until = session.get('login_until', 0)
        if until > datetime.now().timestamp() and attempts >= 5:
            flash('Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 5 phút.', 'danger')
        else:
            if until <= datetime.now().timestamp():
                attempts = 0
            user = User.query.filter(func.lower(User.email) == email).first()
            if user and user.active and user.check_password(request.form.get('password', '')):
                return redirect(start_user_session(user))
            session['login_attempts'] = attempts + 1
            session['login_until'] = (datetime.now() + timedelta(minutes=5)).timestamp()
            flash('Email hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.', 'danger')
    return render_template('auth.html', mode='login')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(landing_url(g.user))
    return account_form('register')


@auth.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.filter_by(role='admin').first():
        abort(404)
    token = request.values.get('token', '')
    if not token or not secrets.compare_digest(token, current_app.config.get('SETUP_TOKEN', '')):
        abort(403)
    return account_form('setup')


def account_form(mode):
    if request.method == 'POST':
        proof = None
        if mode == 'register':
            from app.google_login import registration_google_claims
            try:
                proof = registration_google_claims(request.form.get('google_credential',''))
            except ValueError as error:
                flash(str(error),'danger')
                return render_template('auth.html',mode=mode),400
        name = request.form.get('name', '').strip()
        submitted_email = request.form.get('email', '').strip().lower()
        email = proof['email'] if proof else submitted_email
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        if proof and submitted_email and submitted_email != proof['email']:
            flash('Email đăng ký phải khớp tài khoản Google vừa xác nhận. Vui lòng chọn lại Google.','danger')
        elif not valid_fields(name, email, password, phone):
            flash('Nhập họ tên, email hợp lệ, mật khẩu từ 8 đến 128 ký tự và điện thoại tối đa 20 ký tự.', 'danger')
        elif password != request.form.get('confirm_password'):
            flash('Mật khẩu xác nhận chưa khớp.', 'danger')
        else:
            try:
                user = create_account(name, email, password, phone, 'admin' if mode == 'setup' else 'reader', mode == 'setup', google_subject=proof['subject'] if proof else None)
            except (ValueError, IntegrityError) as error:
                db.session.rollback()
                flash(str(error) if isinstance(error, ValueError) else 'Email đã được sử dụng.', 'danger')
            else:
                target = start_user_session(user)
                flash('Tạo tài khoản thành công!', 'success')
                return redirect(target)
    return render_template('auth.html', mode=mode)


@auth.post('/logout')
def logout():
    g.activity_logout_session = session.get('presence_session')
    session.clear()
    return redirect(url_for('auth.login'))


@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        if g.user.password_change_required and not password:
            flash('Bạn phải đổi mật khẩu tạm trước khi tiếp tục sử dụng web.', 'danger')
        elif not name or len(name) > 100 or len(phone) > 20:
            flash('Họ tên hoặc điện thoại không hợp lệ.', 'danger')
        elif password and (not 8 <= len(password) <= 128 or password != request.form.get('confirm_password')):
            flash('Mật khẩu cần từ 8 đến 128 ký tự và xác nhận phải khớp.', 'danger')
        elif g.user.password_change_required and password == request.form.get('current_password'):
            flash('Mật khẩu mới phải khác mật khẩu tạm.', 'danger')
        elif password and not g.user.check_password(request.form.get('current_password', '')):
            flash('Mật khẩu hiện tại không đúng.', 'danger')
        else:
            g.user.member.name, g.user.member.phone = name, phone
            if password:
                g.user.set_password(password)
                if g.user.password_change_required:
                    db.session.delete(g.user.password_change_required)
                session.clear()
                session['user_id'] = g.user.id
                session['account_guard'] = account_guard(g.user)
            db.session.commit()
            flash('Đã cập nhật hồ sơ.', 'success')
            return redirect(url_for('auth.profile'))
    return render_template('profile.html')


@auth.get('/my-books')
@login_required
def my_books():
    loans = Issue.query.options(joinedload(Issue.book).joinedload(Book.cover), selectinload(Issue.renewals)).filter_by(member_id=g.user.member_id).order_by(Issue.issue_date.desc()).all()
    requests = BorrowRequest.query.options(joinedload(BorrowRequest.book).joinedload(Book.cover)).filter_by(member_id=g.user.member_id).order_by(BorrowRequest.created_at.desc()).all()
    today = datetime.now().date()
    active_loans = sorted((loan for loan in loans if loan.status == 'issued'), key=lambda loan: loan.due_date)
    return render_template('my_books.html', today=today,
                           active_loans=active_loans,
                           overdue_count=sum(loan.due_date.date() < today for loan in active_loans),
                           returned_loans=sorted((loan for loan in loans if loan.status == 'returned'),
                                                 key=lambda loan: loan.return_date or loan.issue_date, reverse=True),
                           pending_requests=[item for item in requests if item.status == 'pending'],
                           processed_requests=[item for item in requests if item.status != 'pending'])


@auth.route('/accounts', methods=['GET', 'POST'])
@login_required
def accounts():
    if g.user.role != 'admin':
        abort(403)
    if request.method == 'POST':
        if request.form.get('action') == 'create':
            name, email, password = (request.form.get(k, '').strip() for k in ('name', 'email', 'password'))
            role = request.form.get('role', 'reader')
            if role not in ROLES or not valid_fields(name, email, password):
                flash('Thông tin tài khoản không hợp lệ.', 'danger')
            else:
                try:
                    create_account(name, email.lower(), password, role=role, link_existing=True)
                    flash('Đã cấp tài khoản.', 'success')
                except (ValueError, IntegrityError) as error:
                    db.session.rollback()
                    flash(str(error) if isinstance(error, ValueError) else 'Email đã được sử dụng.', 'danger')
        else:
            user = db.get_or_404(User, request.form.get('user_id', type=int))
            role = request.form.get('role')
            active = request.form.get('active') == '1'
            if role not in ROLES:
                abort(400)
            if user.id == g.user.id and (role != 'admin' or not active):
                flash('Không thể tự khóa hoặc hạ quyền tài khoản đang sử dụng.', 'danger')
            else:
                user.role, user.active = role, active
                db.session.commit()
                flash('Đã cập nhật quyền tài khoản.', 'success')
        return redirect(url_for('auth.accounts'))
    return render_template('accounts.html', users=User.query.options(joinedload(User.member), joinedload(User.google_identity)).order_by(User.id).all(),
                           unlinked_members=Member.query.filter(~Member.account.has(),~Member.email.like('%@deleted.invalid')).all(),
                           registration_blocks=RegistrationBlock.query.order_by(RegistrationBlock.created_at.desc()).all())


def start_user_session(user):
    mobile_connection = session.get('mobile_connection')
    session.clear()
    session['user_id'] = user.id
    session['account_guard'] = account_guard(user)
    if mobile_connection:
        session['mobile_connection'] = mobile_connection
        return url_for('mobile.confirm_connection')
    return landing_url(user)


def landing_url(user):
    return url_for('main.index' if user and user.role in ('admin', 'librarian') else 'auth.library_home')


@auth.get('/')
def library_home():
    return render_catalog()


@auth.get('/catalog')
def catalog():
    from app.catalog import catalog_page
    return catalog_page()


def render_catalog():
    pending, active = set(), set()
    if g.user:
        pending = {r.book_id for r in BorrowRequest.query.filter_by(member_id=g.user.member_id, status='pending')}
        active = {i.book_id for i in Issue.query.filter_by(member_id=g.user.member_id, status='issued')}
    return render_template('library.html', books=Book.query.options(joinedload(Book.cover)).order_by(Book.created_at.desc()).all(),
                           pending_books=pending, active_books=active)


@auth.post('/borrow/request/<int:book_id>')
@login_required
def request_book(book_id):
    if g.user.role != 'reader':
        abort(403)
    book = db.get_or_404(Book, book_id)
    if book.available < 1:
        flash('Sách đã được mượn hết. Vui lòng chọn sách khác.', 'info')
    elif Issue.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='issued').first():
        flash('Bạn đang mượn sách này.', 'info')
    elif BorrowRequest.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='pending').first():
        flash('Bạn đã gửi yêu cầu cho sách này. Vui lòng chờ thủ thư duyệt.', 'info')
    else:
        db.session.add(BorrowRequest(book_id=book.id, member_id=g.user.member_id))
        try:
            db.session.commit()
            flash('Đã gửi yêu cầu mượn! Theo dõi trạng thái tại Sách của tôi.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Yêu cầu đã tồn tại. Vui lòng chờ thủ thư duyệt.', 'info')
    path, separator, query = request.headers.get('X-Library-Page', '').partition('?')
    allowed = (url_for('auth.library_home'), url_for('auth.catalog'),
               url_for('features.detail', book_id=book_id))
    if path in allowed:
        return redirect(path + separator + query, code=303)
    return redirect(url_for('auth.my_books'))


@auth.post('/borrow/requests/<int:request_id>/cancel')
@login_required
def cancel_request(request_id):
    item = db.get_or_404(BorrowRequest, request_id)
    if item.member_id != g.user.member_id:
        abort(403)
    changed = BorrowRequest.query.filter_by(id=item.id, member_id=g.user.member_id, status='pending').update(
        {'status':'cancelled', 'resolved_at':datetime.now()}, synchronize_session=False)
    db.session.commit()
    flash('Đã hủy yêu cầu.' if changed else 'Yêu cầu đã được xử lý, không thể hủy.', 'info')
    return redirect(url_for('auth.my_books'))


@auth.route('/admin/borrow-requests', methods=['GET'])
@login_required
def borrow_requests():
    if g.user.role not in ('admin', 'librarian'):
        abort(403)
    items = BorrowRequest.query.order_by(BorrowRequest.created_at.desc()).all()
    return render_template('borrow_requests.html', items=items, today=datetime.now().date().isoformat(),
                           default_due=(datetime.now()+timedelta(days=14)).date().isoformat())


@auth.post('/admin/borrow-requests/<int:request_id>/review')
@login_required
def review_request(request_id):
    if g.user.role not in ('admin', 'librarian'):
        abort(403)
    item = db.get_or_404(BorrowRequest, request_id)
    action = request.form.get('action')
    if action not in ('approve', 'reject'):
        abort(400)
    if item.status != 'pending':
        flash('Yêu cầu này đã được xử lý.', 'info')
        return redirect(url_for('auth.borrow_requests'))
    due_date = None
    if action == 'approve':
        try:
            due_date = datetime.strptime(request.form.get('due_date', ''), '%Y-%m-%d')
            if due_date.date() < datetime.now().date():
                raise ValueError()
        except ValueError:
            flash('Hạn trả phải hợp lệ và không trước hôm nay.', 'danger')
            return redirect(url_for('auth.borrow_requests'))
        if not item.member.account or not item.member.account.active:
            flash('Tài khoản độc giả đã bị khóa hoặc không còn tồn tại.', 'danger')
            return redirect(url_for('auth.borrow_requests'))
        if Issue.query.filter_by(book_id=item.book_id, member_id=item.member_id, status='issued').first():
            flash('Độc giả đang mượn sách này. Hãy từ chối yêu cầu trùng.', 'info')
            return redirect(url_for('auth.borrow_requests'))
    changed = BorrowRequest.query.filter_by(id=item.id, status='pending').update(
        {'status':'approved' if action == 'approve' else 'rejected', 'resolved_at':datetime.now()},
        synchronize_session=False)
    if not changed:
        db.session.rollback()
        flash('Yêu cầu đã được xử lý.', 'info')
    elif action == 'reject':
        db.session.commit()
        flash('Đã từ chối yêu cầu.', 'info')
    else:
        stock = Book.query.filter(Book.id == item.book_id, Book.available > 0).update(
            {Book.available:Book.available-1}, synchronize_session=False)
        if not stock:
            db.session.rollback()
            flash('Sách không còn bản sẵn sàng. Yêu cầu vẫn chờ duyệt.', 'danger')
        else:
            issue = Issue(book_id=item.book_id, member_id=item.member_id,
                          issue_date=datetime.combine(datetime.now().date(), datetime.min.time()), due_date=due_date)
            db.session.add(issue)
            db.session.flush()
            db.session.execute(db.update(BorrowRequest).where(BorrowRequest.id == item.id).values(issue_id=issue.id))
            db.session.commit()
            flash('Đã duyệt và lập phiếu mượn. Vui lòng giao sách cho độc giả.', 'success')
    return redirect(url_for('auth.borrow_requests'))


def registration_email(email):
    email = email.strip().lower()
    local, separator, domain = email.partition('@')
    if domain in ('gmail.com', 'googlemail.com'):
        return local.split('+', 1)[0].replace('.', '') + '@gmail.com'
    return email


def registration_blocked(email, subject=None):
    query = RegistrationBlock.query.filter_by(email=registration_email(email))
    if subject:
        query = RegistrationBlock.query.filter(db.or_(RegistrationBlock.email == registration_email(email),
                                                      RegistrationBlock.google_subject == subject))
    return query.first() is not None


@auth.post('/accounts/<int:user_id>/delete')
@login_required
def delete_account(user_id):
    if g.user.role != 'admin':
        abort(403)
    user = db.get_or_404(User, user_id)
    if user.role == 'admin':
        flash('Không thể xóa tài khoản quản trị. Hãy chuyển tài khoản khác làm quản trị rồi hạ quyền tài khoản cần xóa.', 'danger')
        return redirect(url_for('auth.accounts'))
    mode = request.form.get('mode')
    if mode not in ('delete', 'block'):
        abort(400)
    if mode == 'block':
        email = registration_email(user.email)
        block = RegistrationBlock.query.filter_by(email=email).first()
        if not block:
            block = RegistrationBlock(email=email)
            db.session.add(block)
        if user.google_identity:
            block.google_subject = user.google_identity.subject
    # Keep library records and outstanding loans, but detach the original email.
    # Re-registration creates a new member and never inherits the deleted account's history.
    member = user.member
    if member:
        member.email = f'archived-{member.id}-{secrets.token_hex(6)}@deleted.invalid'
        BorrowRequest.query.filter_by(member_id=member.id, status='pending').update(
            {'status':'cancelled', 'resolved_at':datetime.now()}, synchronize_session=False)
    if not db.session.get(DeletedAccountId, user.id):
        db.session.add(DeletedAccountId(user_id=user.id))
    db.session.delete(user)
    db.session.commit()
    flash('Đã xóa tài khoản và chặn đăng ký lại.' if mode == 'block' else
          'Đã xóa tài khoản. Email này có thể đăng ký lại với tài khoản mới.', 'success')
    return redirect(url_for('auth.accounts'))


@auth.post('/accounts/<int:user_id>/transfer-admin')
@login_required
def transfer_admin(user_id):
    if g.user.role != 'admin':
        abort(403)
    source = db.get_or_404(User, user_id)
    target = db.get_or_404(User, request.form.get('target_id', type=int))
    if source.role != 'admin' or source.id == target.id or not target.active:
        flash('Chọn một tài khoản khác đang hoạt động để nhận quyền quản trị.', 'danger')
        return redirect(url_for('auth.accounts'))
    target.role = 'admin'
    source.role = 'librarian'
    db.session.commit()
    flash('Đã chuyển quyền quản trị. Tài khoản cũ trở thành thủ thư; quản trị viên có thể xóa tài khoản đó.', 'success')
    return redirect(url_for('main.index') if source.id == g.user.id else url_for('auth.accounts'))


@auth.post('/accounts/registration-blocks/<int:block_id>/remove')
@login_required
def unblock_registration(block_id):
    if g.user.role != 'admin':
        abort(403)
    block = db.get_or_404(RegistrationBlock, block_id)
    db.session.delete(block)
    db.session.commit()
    flash('Đã bỏ chặn. Người dùng có thể đăng ký lại.', 'success')
    return redirect(url_for('auth.accounts'))


def account_guard(user):
    fingerprint = f'{user.id}:{user.member_id}:{user.email}:{user.password_hash}'
    return hashlib.sha256(fingerprint.encode()).hexdigest()


@auth.route('/accounts/<int:user_id>/edit', methods=['GET','POST'])
@login_required
def edit_account(user_id):
    if g.user.role!='admin':
        abort(403)
    user=db.get_or_404(User,user_id)
    if request.method=='POST':
        form=request.form
        name,email,phone,code=(form.get(key,'').strip() for key in ('name','email','phone','member_code'))
        email=email.lower()
        role=form.get('role')
        active=form.get('active')=='1'
        password=form.get('password','')
        unlink=form.get('unlink_google')=='1'
        try:
            if not name or len(name)>100 or '@' not in email or len(email)>120 or len(phone)>20 or not code or len(code)>20:
                raise ValueError('Nhập họ tên, email, điện thoại và mã thành viên hợp lệ (mã tối đa 20 ký tự).')
            if role not in ROLES:
                raise ValueError('Vai trò tài khoản không hợp lệ.')
            if registration_blocked(email):
                raise ValueError('Email này đang bị chặn đăng ký. Hãy bỏ chặn trước khi sử dụng.')
            if password and (not 8<=len(password)<=128 or password!=form.get('confirm_password')):
                raise ValueError('Mật khẩu mới phải từ 8 đến 128 ký tự và xác nhận trùng khớp.')
            if user.id==g.user.id and (role!='admin' or not active):
                raise ValueError('Không thể tự khóa hoặc hạ quyền. Hãy dùng chức năng chuyển quyền quản trị trước.')
            joined=datetime.strptime(form.get('joined_at',''),'%Y-%m-%d')
            if joined.date()>datetime.now().date():
                raise ValueError('Ngày đăng ký không được nằm trong tương lai.')
            if email!=user.email.lower() and user.google_identity and not unlink:
                raise ValueError('Cần chọn gỡ liên kết Google khi thay email đăng nhập, rồi liên kết lại với Google phù hợp.')
            if unlink and not user.password_hash and not password:
                raise ValueError('Tài khoản chỉ dùng Google. Hãy đặt mật khẩu trước khi gỡ liên kết để tránh mất quyền đăng nhập.')
            user.member.name,user.member.phone,user.member.member_id=name,phone,code
            user.member.email,user.member.joined_at=email,joined
            user.email,user.role,user.active=email,role,active
            if unlink and user.google_identity:
                db.session.delete(user.google_identity)
            if password:
                user.set_password(password)
                if user.id!=g.user.id and not user.password_change_required:
                    db.session.add(PasswordChangeRequired(user_id=user.id))
            db.session.commit()
        except (ValueError,IntegrityError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error,ValueError) else 'Email hoặc mã thành viên đã được sử dụng bởi tài khoản/hồ sơ khác.','danger')
        else:
            if user.id==g.user.id:
                session['account_guard']=account_guard(user)
            flash('Đã cập nhật tài khoản và hồ sơ thành viên.','success')
            return redirect(url_for('auth.accounts'))
    return render_template('account_edit.html',user=user,today=datetime.now().date().isoformat())
