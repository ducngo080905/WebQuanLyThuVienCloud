"""Quick loans, FIFO reservations and staff-confirmed QR returns."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from functools import wraps
import secrets
from urllib.parse import urlsplit, parse_qs, urlencode

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for, session, jsonify
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from app import db
from app.auth import login_required, start_user_session
from app.features import fine_amount, setting
from app.models import User, Book, Member, Issue, BorrowRequest, BookReservation, CirculationConfig, ReturnReceipt, LibrarySetting, LibraryQRPass

circulation = Blueprint('circulation', __name__)


def portal_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get('user'):
            return redirect(url_for('circulation.portal_login'))
        if g.user.role not in ('admin', 'librarian'):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@circulation.route('/circulation/login', methods=['GET','POST'])
def portal_login():
    if g.get('user'):
        if g.user.role in ('admin','librarian'):
            return redirect(url_for('circulation.scan'))
        return render_template('qr_login.html', denied=True), 403
    if request.method=='POST':
        attempts=session.get('login_attempts',0)
        until=session.get('login_until',0)
        if attempts>=5 and until>datetime.now().timestamp():
            flash('Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 5 phút.', 'danger')
        else:
            if until<=datetime.now().timestamp():
                attempts=0
            user=User.query.filter(db.func.lower(User.email)==request.form.get('email','').strip().lower()).first()
            if user and user.active and user.role in ('admin','librarian') and user.check_password(request.form.get('password','')):
                start_user_session(user)
                return redirect(url_for('circulation.scan'),code=303)
            session['login_attempts']=attempts+1
            session['login_until']=(datetime.now()+timedelta(minutes=5)).timestamp()
            flash('Thông tin đăng nhập không hợp lệ hoặc tài khoản không có quyền admin/thủ thư.', 'danger')
    return render_template('qr_login.html', denied=False)


def settings_context():
    return dict(values={key:config(key) for key in ('bank_bin','bank_account','bank_owner')},
                days=config('loan_days','14'),rate=setting('fine_per_day',5000))


def today():
    return datetime.now(timezone(timedelta(hours=7))).date()


def config(key, default=''):
    item = db.session.get(CirculationConfig, key)
    return item.value if item else default


def signer():
    return URLSafeSerializer(current_app.secret_key, salt='library-circulation-v1')


def qr_token(kind, identifier):
    key = 'member_id' if kind == 'card' else 'issue_id'
    row = LibraryQRPass.query.filter_by(**{key: identifier}).first()
    if row is None:
        try:
            with db.session.begin_nested():
                row = LibraryQRPass(**{key: identifier}, nonce=secrets.token_hex(24))
                db.session.add(row)
                db.session.flush()
            db.session.commit()
        except IntegrityError:
            row = LibraryQRPass.query.filter_by(**{key: identifier}).one()
    return signer().dumps({'kind': kind, 'id': identifier, 'guard': row.nonce})


def qr_link(kind, identifier):
    # Relative content works on both localhost and the public HTTPS origin.
    return 'LIBQR:' + qr_token(kind, identifier)


def png(content):
    import qrcode
    image = qrcode.make(content)
    output = BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    response = send_file(output, mimetype='image/png')
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def lock_book(book_id):
    # Serialize lending/queue changes on PostgreSQL and SQLite alike.
    changed = Book.query.filter_by(id=book_id).update({Book.available: Book.available}, synchronize_session=False)
    if not changed:
        abort(404)
    return Book.query.populate_existing().filter_by(id=book_id).one()


def eligible_queue(book):
    return BookReservation.query.join(Member).filter(
        BookReservation.book_id == book.id, BookReservation.status == 'waiting',
        Member.account.has(active=True, role='reader')).order_by(BookReservation.id).all()


def borrow_now(book_id):
    if g.user.role != 'reader':
        abort(403)
    if not g.user.member.phone:
        flash('Vui lòng bổ sung số điện thoại trong hồ sơ trước khi mượn.', 'danger')
        return redirect(url_for('auth.profile'), code=303)
    book = lock_book(book_id)
    queue = eligible_queue(book)
    position = next((i for i, item in enumerate(queue) if item.member_id == g.user.member_id), len(queue))
    if Issue.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='issued').first():
        flash('Bạn đang mượn sách này.', 'info')
    elif book.available <= position:
        flash('Chưa có bản dành cho lượt của bạn. Hãy đặt chỗ hoặc theo dõi hàng đợi.', 'info')
    else:
        days = int(config('loan_days', '14'))
        start = datetime.combine(today(), datetime.min.time())
        issue = Issue(book_id=book.id, member_id=g.user.member_id, issue_date=start, due_date=start+timedelta(days=days))
        book.available -= 1
        db.session.add(issue)
        BookReservation.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='waiting').update({'status': 'borrowed'}, synchronize_session=False)
        BorrowRequest.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='pending').update({'status': 'cancelled', 'resolved_at': datetime.utcnow()}, synchronize_session=False)
        db.session.commit()
        flash('Mượn nhanh thành công! Phiếu và QR trả sách đã có trong Sách của tôi.', 'success')
    db.session.commit()
    path, sep, query = request.headers.get('X-Library-Page', '').partition('?')
    if path in ('/', '/catalog', url_for('features.detail', book_id=book_id)):
        return redirect(path + sep + query, code=303)
    return redirect(url_for('auth.my_books'), code=303)


@circulation.post('/borrow/quick/<int:book_id>')
@login_required
def quick(book_id):
    return borrow_now(book_id)


@circulation.post('/books/<int:book_id>/reserve')
@login_required
def reserve(book_id):
    if g.user.role != 'reader':
        abort(403)
    book = lock_book(book_id)
    if Issue.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='issued').first():
        flash('Bạn đang mượn sách này.', 'info')
    elif BookReservation.query.filter_by(book_id=book.id, member_id=g.user.member_id, status='waiting').first():
        flash('Bạn đã có trong hàng đợi.', 'info')
    elif book.available > len(eligible_queue(book)):
        flash('Sách đang có sẵn. Bạn có thể chọn Mượn nhanh.', 'info')
    else:
        db.session.add(BookReservation(book_id=book.id, member_id=g.user.member_id))
        flash('Đã đặt chỗ. Khi có sách, lượt mượn được ưu tiên theo thứ tự đăng ký.', 'success')
    db.session.commit()
    return redirect(url_for('features.detail', book_id=book.id), code=303)


@circulation.post('/reservations/<int:reservation_id>/cancel')
@login_required
def cancel_reservation(reservation_id):
    item = db.get_or_404(BookReservation, reservation_id)
    if item.member_id != g.user.member_id:
        abort(404)
    lock_book(item.book_id)
    BookReservation.query.filter_by(id=item.id, status='waiting').update({'status': 'cancelled'}, synchronize_session=False)
    db.session.commit()
    flash('Đã hủy đặt chỗ.', 'success')
    return redirect(url_for('circulation.home'), code=303)


def accessible_issue(issue_id):
    issue = db.get_or_404(Issue, issue_id)
    if g.user.role not in ('admin', 'librarian') and issue.member_id != g.user.member_id:
        abort(404)
    return issue


@circulation.get('/library-card.png')
@login_required
def card_qr():
    return png(qr_link('card', g.user.member_id))


@circulation.get('/loans/<int:issue_id>/return-qr.png')
@login_required
def return_qr(issue_id):
    issue = accessible_issue(issue_id)
    if issue.status != 'issued':
        abort(410)
    return png(qr_link('return', issue.id))


def payment_url(issue, amount):
    bank, account, owner = (config(key) for key in ('bank_bin', 'bank_account', 'bank_owner'))
    if amount <= 0 or not bank or not account or not owner:
        return None
    params = urlencode({'amount': amount, 'addInfo': f'TV PHIEU {issue.id}', 'accountName': owner})
    return f'https://img.vietqr.io/image/{bank}-{account}-compact2.svg?{params}'


@circulation.get('/loans/<int:issue_id>/return')
@login_required
def return_page(issue_id):
    issue = accessible_issue(issue_id)
    dialog = request.headers.get('X-QR-Dialog') == '1'
    if dialog and g.user.role not in ('admin','librarian'):
        abort(403)
    if g.user.role in ('admin','librarian') and not dialog:
        return redirect(url_for('circulation.scan',loan=issue.id))
    return loan_response(issue, dialog)


def loan_response(issue, dialog=False):
    receipt = issue.return_receipt
    amount = receipt.amount if receipt else fine_amount(issue)
    context = dict(issue=issue, amount=amount,
                           payment_qr=payment_url(issue, amount), receipt=receipt,
                           bank_account=config('bank_account'), bank_owner=config('bank_owner'), bank_bin=config('bank_bin'))
    if dialog:
        return jsonify(title=f'Phiếu #{issue.id} · {issue.book.title}',
                       html=render_template('_return_details.html',**context))
    return render_template('return_loan.html',**context)


@circulation.get('/loans/<int:issue_id>/live-status')
@login_required
def loan_live_status(issue_id):
    issue=accessible_issue(issue_id)
    receipt=issue.return_receipt
    state=f'{issue.status}:{int(receipt.paid) if receipt else "none"}'
    changed=state!=request.args.get('state','')
    data=dict(state=state,status=issue.status,changed=changed,
              complete=issue.status=='returned' and (not receipt or receipt.paid))
    if changed:
        amount=receipt.amount if receipt else fine_amount(issue)
        data.update(heading='Đã trả sách' if issue.status=='returned' else 'QR trả sách',
                    html=render_template('_return_details.html',issue=issue,receipt=receipt,amount=amount,
                    payment_qr=payment_url(issue,amount),bank_account=config('bank_account'),
                    bank_owner=config('bank_owner'),bank_bin=config('bank_bin')))
    response=jsonify(data)
    response.headers['Cache-Control']='private, no-store'
    return response


def complete_return(issue, returned_on, method, paid=False):
    lock_book(issue.book_id)
    db.session.refresh(issue)
    if issue.status != 'issued':
        return False
    amount = max(0, (returned_on-issue.due_date.date()).days)*setting('fine_per_day', 5000)
    changed = Issue.query.filter_by(id=issue.id, status='issued').update(
        {Issue.status: 'returned', Issue.return_date: datetime.combine(returned_on, datetime.min.time())}, synchronize_session=False)
    if not changed:
        return False
    Book.query.filter_by(id=issue.book_id).update({Book.available: Book.available+1}, synchronize_session=False)
    db.session.add(ReturnReceipt(issue_id=issue.id, method=method, confirmed_by=g.user.id,
                                 confirmed_name=g.user.member.name, amount=amount,
                                 paid=paid or amount == 0, paid_at=datetime.utcnow() if paid or amount == 0 else None))
    return True


@circulation.post('/loans/<int:issue_id>/confirm-return')
@portal_required
def confirm_return(issue_id):
    issue = accessible_issue(issue_id)
    dialog=request.headers.get('X-QR-Dialog')=='1'
    if request.form.get('received') != '1':
        if dialog:
            return jsonify(error='Hãy kiểm tra sách và xác nhận đã nhận sách thực tế.'),400
        flash('Hãy kiểm tra sách và xác nhận đã nhận sách thực tế.', 'danger')
    elif issue.issue_date.date() > today():
        if dialog:
            return jsonify(error='Phiếu có ngày bắt đầu trong tương lai. Hãy kiểm tra lại.'),400
        flash('Phiếu mượn có ngày bắt đầu trong tương lai. Hãy kiểm tra lại.', 'danger')
    else:
        changed = complete_return(issue, today(), 'qr', request.form.get('paid') == '1')
        db.session.commit()
        if dialog:
            db.session.expire_all()
            receipt=db.session.get(ReturnReceipt,issue.id)
            pending=receipt.amount if receipt and not receipt.paid else 0
            return jsonify(ok=True,message=(f'Đã nhận sách · Phiếu #{issue.id}.' if changed else f'Phiếu #{issue.id} đã trả trước đó.') +
                           (f' Còn {pending:,} đ chưa thu.' if pending else '') + ' Sẵn sàng quét mã tiếp theo.',
                           pending_fee=pending,loan_url=url_for('circulation.return_page',issue_id=issue.id))
        flash('Đã xác nhận trả sách và cập nhật kho.' if changed else 'Phiếu này đã trả trước đó; không tăng kho lần nữa.', 'success' if changed else 'info')
    return redirect(url_for('circulation.return_page', issue_id=issue.id), code=303)


@circulation.post('/loans/<int:issue_id>/confirm-payment')
@portal_required
def confirm_payment(issue_id):
    issue = accessible_issue(issue_id)
    receipt = issue.return_receipt
    if not receipt:
        abort(400)
    if request.form.get('verified') == '1':
        ReturnReceipt.query.filter_by(issue_id=issue.id, paid=False).update(
            {'paid': True, 'paid_at': datetime.utcnow()}, synchronize_session=False)
        db.session.commit()
        if request.headers.get('X-QR-Dialog')=='1':
            return jsonify(ok=True,message=f'Đã xác nhận thu phí · Phiếu #{issue.id}. Sẵn sàng quét mã tiếp theo.',pending_fee=0)
        flash('Đã xác nhận thu phí sau khi đối soát.', 'success')
    if request.headers.get('X-QR-Dialog')=='1':
        return jsonify(error='Hãy xác nhận đã đối soát khoản phí.'),400
    return redirect(url_for('circulation.return_page', issue_id=issue.id), code=303)


@circulation.get('/circulation')
@login_required
def home():
    staff = g.user.role in ('admin', 'librarian')
    if staff:
        return redirect(url_for('circulation.scan'))
    loans = Issue.query.options(joinedload(Issue.book), joinedload(Issue.member)).filter_by(status='issued')
    if not staff:
        loans = loans.filter_by(member_id=g.user.member_id)
    loans = loans.order_by(Issue.due_date).limit(100).all()
    reservations = BookReservation.query.options(joinedload(BookReservation.book)).filter_by(member_id=g.user.member_id, status='waiting').order_by(BookReservation.id).all()
    return render_template('circulation.html', loans=loans, reservations=reservations, staff=staff)


@circulation.route('/circulation/scan',methods=['GET','POST'])
@portal_required
def scan():
    if request.method=='POST':
        return settings()
    code = request.args.get('code', '').strip()
    if code:
        try:
            if len(code) > 2000:
                raise ValueError()
            if code.startswith(('https://', 'http://')):
                parts = urlsplit(code)
                # Read only the signed payload, never navigate to scanned external URLs.
                code = parse_qs(parts.query).get('code', [''])[0]
            payload = signer().loads(code.removeprefix('LIBQR:'))
            kind, identifier = payload['kind'], int(payload['id'])
            key = 'member_id' if kind == 'card' else 'issue_id'
            qr_pass = LibraryQRPass.query.filter_by(**{key: identifier}).first()
            if not qr_pass or not secrets.compare_digest(qr_pass.nonce, payload.get('guard','')):
                raise ValueError()
            if kind == 'return':
                issue=accessible_issue(identifier)
                if request.headers.get('X-QR-Dialog')=='1':
                    return loan_response(issue,True)
                return redirect(url_for('circulation.return_page', issue_id=identifier))
            if kind == 'card':
                member = db.get_or_404(Member, identifier)
                loans = Issue.query.filter_by(member_id=member.id, status='issued').order_by(Issue.due_date).all()
                if request.headers.get('X-QR-Dialog')=='1':
                    return jsonify(title=f'{member.library_code} · {member.name}',html=render_template('_qr_member.html',member=member,loans=loans))
                return render_template('scan_qr.html', member=member, loans=loans, initial_loan=None, card_html=render_template('_qr_member.html',member=member,loans=loans), **settings_context())
            raise ValueError()
        except (BadSignature, ValueError, KeyError, TypeError):
            if request.headers.get('X-QR-Dialog')=='1':
                return jsonify(error='QR không hợp lệ hoặc thuộc hệ thống khác.'),400
            flash('QR không hợp lệ hoặc thuộc một hệ thống khác.', 'danger')
    loan_id=request.args.get('loan',type=int)
    if loan_id:
        accessible_issue(loan_id)
    return render_template('scan_qr.html', member=None, loans=[], initial_loan=url_for('circulation.return_page',issue_id=loan_id) if loan_id else None, **settings_context())


@circulation.route('/admin/circulation-settings', methods=['GET', 'POST'])
@portal_required
def settings():
    if request.method=='GET':
        return redirect(url_for('circulation.scan')+'#settings')
    if request.method == 'POST':
        bank, account, owner = (request.form.get(key, '').strip() for key in ('bank_bin', 'bank_account', 'bank_owner'))
        try:
            days, rate = int(request.form.get('loan_days', '14')), int(request.form.get('fine_per_day', '5000'))
            if not 1 <= days <= 365 or not 0 <= rate <= 1000000:
                raise ValueError()
            if any((bank, account, owner)) and not (re.fullmatch(r'[0-9]{6}', bank) and re.fullmatch(r'[0-9]{4,30}', account) and 1 <= len(owner) <= 100):
                raise ValueError()
        except ValueError:
            flash('Kiểm tra số ngày (1–365), phí (0–1.000.000 đ), mã BIN 6 số, số tài khoản và chủ tài khoản. Có thể để trống cả ba thông tin ngân hàng.', 'danger')
        else:
            for key, value in dict(bank_bin=bank, bank_account=account, bank_owner=owner, loan_days=str(days)).items():
                row = db.session.get(CirculationConfig, key)
                if row:
                    row.value = value
                else:
                    db.session.add(CirculationConfig(key=key, value=value))
            row = db.session.get(LibrarySetting, 'fine_per_day')
            if row:
                row.value = rate
            else:
                db.session.add(LibrarySetting(key='fine_per_day', value=rate))
            db.session.commit()
            flash('Đã lưu cấu hình mượn trả và tài khoản nhận phí.', 'success')
            return redirect(url_for('circulation.scan')+'#settings', code=303)
    return render_template('scan_qr.html', member=None,loans=[],**settings_context())


def install_circulation(app):
    @app.context_processor
    def circulation_context():
        return {'library_today': today()}


