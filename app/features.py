from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
import secrets
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import (Book, BookInfo, SamplePage, Issue, User, BorrowRequest,
                        RenewalRequest, LibrarySetting, AccountRecovery, PasswordChangeRequired, RecoveryCredential)
from app.auth import login_required, account_guard
from app.covers import read_cover

features = Blueprint('features', __name__)


def staff_required(view):
    @login_required
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user.role not in ('admin', 'librarian'):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def setting(key, default=0):
    row = db.session.get(LibrarySetting, key)
    return row.value if row else default


def fine_amount(issue):
    end = (issue.return_date or datetime.now()).date()
    return max(0, (end-issue.due_date.date()).days)*setting('fine_per_day')


def install_features(app):
    @app.context_processor
    def feature_context():
        due_count=0
        pending_recovery_count=0
        if g.get('user'):
            due_count=Issue.query.filter(Issue.member_id==g.user.member_id,Issue.status=='issued',
                       Issue.due_date<datetime.combine(datetime.now().date()+timedelta(days=4),datetime.min.time())).count()
            if g.user.role=='admin':
                pending_recovery_count=AccountRecovery.query.filter_by(status='pending').count()
        return {'fine_amount':fine_amount,'fine_rate':setting('fine_per_day'),
                'due_notice_count':due_count,'pending_recovery_count':pending_recovery_count}


def read_samples(files):
    from pypdf import PdfReader, PdfWriter
    pages = []
    count = 0
    for upload in files:
        if not upload.filename:
            continue
        if upload.filename.lower().endswith('.pdf'):
            content=upload.stream.read(10*1024*1024+1)
            if len(content)>10*1024*1024:
                raise ValueError('PDF đọc thử tối đa 10 MB.')
            try:
                reader=PdfReader(BytesIO(content))
                if reader.is_encrypted:
                    raise ValueError('PDF đọc thử không được đặt mật khẩu.')
                page_count=len(reader.pages)
                if page_count<1 or count+page_count>10:
                    raise ValueError('Bản đọc thử tối đa 10 trang. Hãy chọn PDF chỉ chứa các trang đầu.')
                writer=PdfWriter()
                for page in reader.pages:
                    # Copy only page content; discard interactive annotations and actions.
                    writer.add_page(page,excluded_keys=['/Annots','/AA','/AF'])
                writer.add_metadata({'/Title':'Bản đọc thử thư viện'})
                output=BytesIO();writer.write(output)
                pages.append((output.getvalue(),'application/pdf',page_count));count+=page_count
            except ValueError:
                raise
            except Exception:
                raise ValueError('Không đọc được PDF. Chọn tệp PDF hợp lệ khác.') from None
        else:
            image=read_cover(upload)
            if image:
                pages.append((image,'image/jpeg',1));count+=1
        if count>10:
            raise ValueError('Bản đọc thử tối đa 10 trang.')
    return pages


@features.get('/book/<int:book_id>')
def detail(book_id):
    book = db.get_or_404(Book,book_id)
    pending = False
    active = False
    if g.user:
        pending = BorrowRequest.query.filter_by(book_id=book_id,member_id=g.user.member_id,status='pending').first() is not None
        active = Issue.query.filter_by(book_id=book_id,member_id=g.user.member_id,status='issued').first() is not None
    return render_template('book_detail.html',book=book,pending=pending,active=active)


@features.get('/book-samples/<int:page_id>')
def sample_image(page_id):
    row = db.get_or_404(SamplePage,page_id)
    response=send_file(BytesIO(row.data),mimetype=row.mimetype,download_name=f'preview-{page_id}.'+('pdf' if row.mimetype=='application/pdf' else 'jpg'),max_age=0)
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@features.route('/admin/books/<int:book_id>/edit',methods=['GET','POST'])
@staff_required
def edit_book(book_id):
    book=db.get_or_404(Book,book_id)
    if request.method=='POST':
        form=request.form
        try:
            title,author,isbn=(form.get(k,'').strip() for k in ('title','author','isbn'))
            if not title or len(title)>200 or not author or len(author)>100 or not isbn or len(isbn)>20:
                raise ValueError('Tên sách, tác giả hoặc ISBN không hợp lệ.')
            quantity=int(form.get('quantity',''))
            borrowed=book.quantity-book.available
            if quantity<max(1,borrowed):
                raise ValueError(f'Số lượng phải ít nhất {max(1,borrowed)} (đang mượn {borrowed} bản).')
            year=int(form['year']) if form.get('year') else None
            pages=int(form['pages']) if form.get('pages') else None
            if (year is not None and not 1<=year<=datetime.now().year+1) or (pages is not None and not 1<=pages<=100000):
                raise ValueError('Năm xuất bản hoặc số trang không hợp lệ.')
            for field,limit in [('genre',50),('publisher',150),('language',50),('shelf',60),('description',20000)]:
                if len(form.get(field,''))>limit:
                    raise ValueError(f'Thông tin {field} vượt quá độ dài cho phép.')
            sample_files=[f for f in request.files.getlist('samples') if f.filename]
            sample_pages=read_samples(sample_files)
            image=read_cover(request.files.get('cover'))
            old_qty,old_available=book.quantity,book.available
            changed=Book.query.filter_by(id=book.id,quantity=old_qty,available=old_available).update(
                {Book.quantity:quantity,Book.available:quantity-borrowed},synchronize_session=False)
            if not changed:
                raise ValueError('Kho sách vừa thay đổi. Hãy tải lại trang rồi thử lại.')
            book.title,book.author,book.isbn,book.genre=title,author,isbn,form.get('genre','').strip()
            if not book.info:
                book.info=BookInfo()
            for field in ('publisher','language','shelf','description'):
                setattr(book.info,field,form.get(field,'').strip())
            book.info.year,book.info.pages=year,pages
            if image:
                from app.models import BookCover
                if not book.cover:
                    book.cover=BookCover()
                book.cover.data,book.cover.version=image,secrets.token_hex(8)
            if sample_files or form.get('remove_samples')=='1':
                for old in list(book.sample_pages):
                    db.session.delete(old)
                for number,(data,mimetype,page_count) in enumerate(sample_pages,1):
                    db.session.add(SamplePage(book_id=book.id,position=number,data=data,mimetype=mimetype,page_count=page_count))
            db.session.commit()
        except (ValueError,IntegrityError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error,ValueError) else 'ISBN đã được dùng cho sách khác.','danger')
        else:
            flash('Đã cập nhật sách và bản đọc thử.','success')
            return redirect(url_for('features.detail',book_id=book.id))
    return render_template('book_edit.html',book=book)


@features.post('/my-books/<int:issue_id>/renew')
@login_required
def request_renewal(issue_id):
    issue=db.get_or_404(Issue,issue_id)
    if issue.member_id!=g.user.member_id:
        abort(403)
    if issue.status!='issued' or issue.due_date.date()<datetime.now().date():
        flash('Chỉ có thể xin gia hạn sách đang mượn và chưa quá hạn.','danger')
    elif sum(item.status=='approved' for item in issue.renewals)>=2:
        flash('Mỗi lượt mượn được gia hạn tối đa 2 lần.','info')
    elif any(item.status=='pending' for item in issue.renewals):
        flash('Bạn đã có yêu cầu gia hạn đang chờ duyệt.','info')
    else:
        db.session.add(RenewalRequest(issue_id=issue.id,original_due=issue.due_date))
        try:
            db.session.commit()
            flash('Đã gửi yêu cầu gia hạn thêm 7 ngày.','success')
        except IntegrityError:
            db.session.rollback()
            flash('Yêu cầu đang chờ duyệt.','info')
    return redirect(url_for('auth.my_books'))


@features.route('/admin/renewals',methods=['GET'])
@staff_required
def renewals():
    return render_template('renewals.html',items=RenewalRequest.query.order_by(RenewalRequest.created_at.desc()).all())


@features.post('/admin/renewals/<int:item_id>/review')
@staff_required
def review_renewal(item_id):
    item=db.get_or_404(RenewalRequest,item_id)
    action=request.form.get('action')
    if action not in ('approve','reject'):
        abort(400)
    if item.status!='pending':
        flash('Yêu cầu đã được xử lý.','info')
    elif action=='reject':
        RenewalRequest.query.filter_by(id=item.id,status='pending').update({'status':'rejected'},synchronize_session=False)
        db.session.commit();flash('Đã từ chối gia hạn.','info')
    else:
        issue=item.issue
        approved=RenewalRequest.query.filter_by(issue_id=issue.id,status='approved').count()
        if approved>=2 or issue.due_date.date()<datetime.now().date() or not issue.member.account or not issue.member.account.active:
            flash('Yêu cầu không còn đủ điều kiện gia hạn.','danger')
            return redirect(url_for('features.renewals'))
        changed=RenewalRequest.query.filter_by(id=item.id,status='pending').update({'status':'approved'},synchronize_session=False)
        extended=Issue.query.filter_by(id=issue.id,status='issued',due_date=item.original_due).update(
            {'due_date':item.original_due+timedelta(days=7)},synchronize_session=False) if changed else 0
        if not extended:
            db.session.rollback();flash('Sách đã trả hoặc hạn trả vừa thay đổi. Không gia hạn lặp.','danger')
        else:
            db.session.commit();flash('Đã gia hạn thêm 7 ngày.','success')
    return redirect(url_for('features.renewals'))



@features.route('/admin/reports',methods=['GET','POST'])
@staff_required
def reports():
    if request.method=='POST':
        if g.user.role!='admin': abort(403)
        try:
            rate=int(request.form.get('fine_per_day',''))
            if not 0<=rate<=1000000: raise ValueError()
            row=db.session.get(LibrarySetting,'fine_per_day')
            if not row: row=LibrarySetting(key='fine_per_day');db.session.add(row)
            row.value=rate;db.session.commit();flash('Đã lưu mức phí trễ hạn.','success')
        except ValueError: flash('Mức phí phải từ 0 đến 1.000.000 đồng/ngày.','danger')
        return redirect(url_for('features.reports'))
    month=request.args.get('month',datetime.now().strftime('%Y-%m'))
    try:
        start=datetime.strptime(month,'%Y-%m');end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    except (ValueError, OverflowError): abort(400)
    loans=Issue.query.filter(Issue.issue_date>=start,Issue.issue_date<end).order_by(Issue.issue_date.desc()).all()
    if request.args.get('format')=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font,PatternFill
        workbook=Workbook();sheet=workbook.active;sheet.title='Muon tra'
        sheet.append(['Mã phiếu','Sách','Thành viên','Ngày mượn','Hạn trả','Ngày trả','Trạng thái','Phí trễ hạn tạm tính (VND)'])
        safe=lambda text: "'"+text if str(text).startswith(('=','+','-','@')) else text
        for issue in loans:
            sheet.append([issue.id,safe(issue.book.title),safe(issue.member.name),issue.issue_date.strftime('%d/%m/%Y'),issue.due_date.strftime('%d/%m/%Y'),issue.return_date.strftime('%d/%m/%Y') if issue.return_date else '', 'Đã trả' if issue.status=='returned' else 'Đang mượn',fine_amount(issue)])
        for cell in sheet[1]: cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='1E40AF')
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width=min(55,max(15,max(len(str(cell.value or '')) for cell in column)+2))
        output=BytesIO();workbook.save(output);output.seek(0)
        return send_file(output,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name=f'bao-cao-thu-vien-{month}.xlsx')
    return render_template('reports.html',loans=loans,month=month,print_mode=request.args.get('format')=='print')


@features.route('/forgot-password',methods=['GET','POST'])
def forgot_password():
    if request.method=='POST':
        values={key:request.form.get(key,'').strip() for key in ('email','name','phone','member_code','contact','evidence')}
        values['email']=values['email'].lower()
        limits={'email':120,'name':100,'phone':20,'member_code':40,'contact':200,'evidence':2000}
        if any((not values[key] and key!='member_code') or len(values[key])>limit for key,limit in limits.items()) or '@' not in values['email']:
            flash('Vui lòng điền đầy đủ thông tin xác minh và cách admin có thể liên hệ bạn.','danger')
        else:
            # Do not disclose whether an email exists; identity is verified by an admin, never by auto-matching.
            recent=AccountRecovery.query.filter(AccountRecovery.email==values['email'],AccountRecovery.created_at>datetime.utcnow()-timedelta(hours=24)).count()
            if recent<3:
                user=User.query.filter(db.func.lower(User.email)==values['email']).first()
                db.session.add(AccountRecovery(**values,user_id=user.id if user else None,account_guard=account_guard(user) if user else None))
                db.session.commit()
            flash('Đã tiếp nhận yêu cầu. Admin sẽ kiểm tra thông tin và liên hệ qua kênh bạn cung cấp. Không gửi lại mật khẩu cũ.','success')
            return redirect(url_for('auth.login'))
    return render_template('password_reset.html')


@features.get('/reset-password/<token>')
def retired_reset(token):
    flash('Liên kết email cũ đã ngừng sử dụng. Hãy gửi yêu cầu xác minh cho admin.','info')
    return redirect(url_for('features.forgot_password'))


@features.get('/admin/account-recovery')
@login_required
def recoveries():
    if g.user.role!='admin': abort(403)
    items=AccountRecovery.query.order_by(AccountRecovery.created_at.desc()).all()
    passwords={item.id:read_recovery_password(item) for item in items if item.status=='approved'}
    return render_template('account_recovery.html',items=items,passwords=passwords)


@features.post('/admin/account-recovery/<int:item_id>/review')
@login_required
def review_recovery(item_id):
    if g.user.role!='admin': abort(403)
    item=db.get_or_404(AccountRecovery,item_id)
    action=request.form.get('action')
    if action not in ('approve','reject'): abort(400)
    if item.status!='pending':
        flash('Yêu cầu đã được xử lý.','info');return redirect(url_for('features.recoveries'))
    if action=='reject':
        AccountRecovery.query.filter_by(id=item.id,status='pending').update({'status':'rejected','resolved_at':datetime.utcnow()},synchronize_session=False)
        db.session.commit();flash('Đã từ chối yêu cầu.','info');return redirect(url_for('features.recoveries'))
    user=item.user
    if request.form.get('verified')!='1':
        flash('Cần xác minh trực tiếp và tích xác nhận trước khi đặt lại mật khẩu.','danger')
        return redirect(url_for('features.recoveries'))
    if not user or not user.active or not item.account_guard or not secrets.compare_digest(item.account_guard,account_guard(user)):
        flash('Tài khoản không tồn tại, bị khóa hoặc đã thay đổi. Không thể reset theo yêu cầu này.','danger')
        return redirect(url_for('features.recoveries'))
    if user.id==g.user.id:
        flash('Không thể tự duyệt khôi phục tài khoản của mình. Hãy nhờ quản trị viên khác.','danger')
        return redirect(url_for('features.recoveries'))
    claimed=AccountRecovery.query.filter_by(id=item.id,status='pending').update({'status':'approved','resolved_at':datetime.utcnow()},synchronize_session=False)
    if not claimed:
        db.session.rollback();return redirect(url_for('features.recoveries'))
    temporary=secrets.token_urlsafe(12)
    from werkzeug.security import generate_password_hash
    changed=User.query.filter_by(id=user.id,password_hash=user.password_hash,active=True).update(
        {'password_hash':generate_password_hash(temporary)},synchronize_session=False)
    if not changed:
        db.session.rollback()
        flash('Tài khoản vừa thay đổi. Hãy xác minh và xử lý yêu cầu mới.', 'danger')
        return redirect(url_for('features.recoveries'))
    if not user.password_change_required:
        db.session.add(PasswordChangeRequired(user_id=user.id))
    AccountRecovery.query.filter(AccountRecovery.user_id==user.id,AccountRecovery.status=='pending',AccountRecovery.id!=item.id).update({'status':'superseded','resolved_at':datetime.utcnow()},synchronize_session=False)
    db.session.flush()
    db.session.refresh(user)
    save_recovery_password(item,user,temporary)
    db.session.commit()
    # Plaintext appears only in authorized admin HTML, never in flash/session cookies.
    response=current_app.make_response(render_template('recovery_result.html',user=user,temporary=temporary,contact=item.contact))
    response.headers['Cache-Control']='no-store'
    return response


@features.get('/notifications')
@login_required
def notifications():
    loans=Issue.query.filter_by(member_id=g.user.member_id,status='issued').order_by(Issue.due_date).all()
    today=datetime.now().date()
    return render_template('notifications.html',loans=[loan for loan in loans if (loan.due_date.date()-today).days<=3],today=today)


def recovery_cipher():
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    key=hashlib.sha256(('recovery-password-v1:'+current_app.config['SECRET_KEY']).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def save_recovery_password(item,user,password):
    row=db.session.get(RecoveryCredential,item.id)
    if not row:
        row=RecoveryCredential(recovery_id=item.id)
        db.session.add(row)
    row.ciphertext=recovery_cipher().encrypt(password.encode())
    row.account_guard=account_guard(user)
    row.expires_at=datetime.utcnow()+timedelta(hours=24)


def read_recovery_password(item):
    from cryptography.fernet import InvalidToken
    row=item.credential
    user=item.user
    if not row or not user or not user.active or not user.password_change_required or row.expires_at<datetime.utcnow():
        return None
    if not secrets.compare_digest(row.account_guard,account_guard(user)):
        return None
    try:
        return recovery_cipher().decrypt(row.ciphertext).decode()
    except (InvalidToken,UnicodeDecodeError):
        return None


@features.post('/admin/account-recovery/<int:item_id>/reissue')
@login_required
def reissue_recovery(item_id):
    if g.user.role!='admin': abort(403)
    item=db.get_or_404(AccountRecovery,item_id)
    user=item.user
    latest=AccountRecovery.query.filter_by(user_id=item.user_id,status='approved').order_by(AccountRecovery.resolved_at.desc(),AccountRecovery.id.desc()).first() if user else None
    if (item.status!='approved' or not user or not user.active or user.id==g.user.id or
            not user.password_change_required or not latest or latest.id!=item.id):
        flash('Không thể cấp lại: tài khoản đã đổi mật khẩu, bị khóa hoặc có yêu cầu mới hơn.','danger')
        return redirect(url_for('features.recoveries'))
    if request.form.get('verified')!='1':
        flash('Cần xác minh lại chủ tài khoản trước khi cấp mật khẩu tạm mới.','danger')
        return redirect(url_for('features.recoveries'))
    temporary=secrets.token_urlsafe(12)
    from werkzeug.security import generate_password_hash
    changed=User.query.filter_by(id=user.id,password_hash=user.password_hash,active=True).update(
        {'password_hash':generate_password_hash(temporary)},synchronize_session=False)
    if not changed:
        db.session.rollback();return redirect(url_for('features.recoveries'))
    item.resolved_at=datetime.utcnow()
    db.session.flush();db.session.refresh(user)
    save_recovery_password(item,user,temporary)
    db.session.commit()
    flash('Đã cấp lại mật khẩu tạm. Mật khẩu tạm trước đó không còn hiệu lực.','success')
    return redirect(url_for('features.recoveries'))
