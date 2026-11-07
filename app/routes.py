from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, g, abort, send_file
from app import db
from app.models import Book, Member, Issue, User, BookCover
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import joinedload

main = Blueprint('main', __name__)

@main.app_context_processor
def interface_stats():
    # Only dashboard/loan tables use this data. Aggregate in SQL instead of
    # materializing the entire loan history on every page, including login.
    if request.endpoint not in ('main.index', 'main.issues', 'main.members'):
        return {}
    overdue = (Issue.status == 'issued') & (Issue.due_date < datetime.combine(datetime.now().date(), datetime.min.time()))
    active = Issue.status == 'issued'
    query = db.session.query(func.count(Issue.id),
        func.coalesce(func.sum(case((active, 1), else_=0)), 0),
        func.coalesce(func.sum(case((overdue, 1), else_=0)), 0),
        func.count(distinct(case((active, Issue.member_id)))),
        func.count(distinct(case((overdue, Issue.member_id)))))
    if g.get('user') and g.user.role == 'reader':
        query = query.filter(Issue.member_id == g.user.member_id)
    total, active_count, overdue_count, borrowers, overdue_members = query.one()
    return {'ui_stats': {'total': total, 'active': active_count,
        'returned': total - active_count, 'overdue': overdue_count,
        'borrowers': borrowers, 'overdue_members': overdue_members,
        'active_percent': round(active_count / total * 100) if total else 0}}

# ─── Dashboard ───────────────────────────────────────────────────────────────

@main.route('/admin')
def index():
    total_books   = Book.query.count()
    total_accounts = User.query.count()
    admin_accounts = User.query.filter_by(role='admin').count()
    active_issues = Issue.query.filter_by(status='issued').count()
    overdue = Issue.query.filter(
        Issue.status == 'issued',
        Issue.due_date < datetime.combine(datetime.now().date(), datetime.min.time())
    ).count()
    recent_issues = Issue.query.options(joinedload(Issue.book), joinedload(Issue.member)).order_by(Issue.issue_date.desc()).limit(5).all()
    return render_template('index.html',
                           total_books=total_books,
                           total_accounts=total_accounts,
                           admin_accounts=admin_accounts,
                           active_issues=active_issues,
                           overdue=overdue,
                           recent_issues=recent_issues,
                           now=datetime.utcnow())

# ─── Books ────────────────────────────────────────────────────────────────────

@main.route('/books')
def books():
    all_books = Book.query.options(joinedload(Book.cover)).all()
    return render_template('books.html', books=all_books)

@main.route('/books/add', methods=['POST'])
def add_book():
    from app.covers import read_cover
    import secrets
    data = request.form
    try:
        quantity = int(data.get('quantity', 1))
        if quantity < 1:
            raise ValueError('Số lượng phải lớn hơn 0.')
        title, author, isbn = (data.get(key, '').strip() for key in ('title','author','isbn'))
        if not title or not author or not isbn or len(title)>200 or len(author)>100 or len(isbn)>20:
            raise ValueError('Nhập đầy đủ tên sách, tác giả và ISBN hợp lệ.')
        image = read_cover(request.files.get('cover'))
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('main.books'))
    book = Book(title=title, author=author, isbn=isbn, genre=data.get('genre',''),
                quantity=quantity, available=quantity)
    if image:
        book.cover = BookCover(data=image, version=secrets.token_hex(8))
    db.session.add(book)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('ISBN đã có trong danh mục. Vui lòng kiểm tra lại.', 'danger')
    else:
        flash('Thêm sách thành công!', 'success')
    return redirect(url_for('main.books'))


@main.route('/covers/<int:book_id>')
def book_cover(book_id):
    from io import BytesIO
    cover = db.get_or_404(BookCover, book_id)
    response = send_file(BytesIO(cover.data), mimetype='image/jpeg',
                         download_name=f'book-{book_id}.jpg', etag=cover.version,
                         conditional=True, max_age=0)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@main.post('/books/<int:book_id>/cover')
def update_book_cover(book_id):
    from app.covers import read_cover
    import secrets
    book = db.get_or_404(Book, book_id)
    if request.form.get('remove_cover') == '1':
        if book.cover:
            db.session.delete(book.cover)
        db.session.commit()
        flash('Đã gỡ ảnh bìa.', 'success')
        return redirect(url_for('main.books'))
    try:
        image = read_cover(request.files.get('cover'))
        if not image:
            raise ValueError('Vui lòng chọn ảnh bìa cần tải lên.')
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('main.books'))
    if not book.cover:
        book.cover = BookCover()
    book.cover.data = image
    book.cover.version = secrets.token_hex(8)
    db.session.commit()
    flash('Đã cập nhật ảnh bìa.', 'success')
    return redirect(url_for('main.books'))

@main.route('/books/delete/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    for issue in book.issues:
        db.session.delete(issue)
    db.session.delete(book)
    db.session.commit()
    flash('Đã xóa sách.', 'info')
    return redirect(url_for('main.books'))

# ─── Members ─────────────────────────────────────────────────────────────────

@main.route('/members')
def members():
    all_members = Member.query.all()
    return redirect(url_for('auth.accounts') if g.user.role=='admin' else url_for('main.issues'))

@main.route('/members/add', methods=['POST'])
def add_member():
    data = request.form
    import random, string
    mid = 'MEM' + ''.join(random.choices(string.digits, k=5))
    member = Member(
        name      = data['name'],
        email     = data['email'],
        phone     = data.get('phone', ''),
        member_id = mid
    )
    db.session.add(member)
    db.session.commit()
    flash(f'Đã thêm thành viên! Mã: {mid}', 'success')
    return redirect(url_for('main.members'))

@main.route('/members/edit/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if member.account:
        if g.user.role!='admin':
            abort(403)
        return redirect(url_for('auth.edit_account',user_id=member.account.id))
    if member.account and member.account.role != 'reader' and g.user.role != 'admin':
        abort(403)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name or not email or '@' not in email or len(name) > 100 or len(email) > 120 or len(phone) > 20:
            flash('Vui lòng nhập họ tên, email hợp lệ và số điện thoại không quá 20 ký tự.', 'danger')
        else:
            member.name, member.email, member.phone = name, email, phone
            if member.account:
                member.account.email = email.lower()
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Email này đã được sử dụng bởi thành viên khác.', 'danger')
            else:
                flash('Đã cập nhật thông tin thành viên.', 'success')
                return redirect(url_for('main.members'))
    if g.user.role=='admin' and member.account:
        return redirect(url_for('auth.edit_account',user_id=member.account.id))
    return redirect(url_for('auth.accounts') if g.user.role=='admin' else url_for('main.issues'))


@main.route('/members/delete/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    member = Member.query.get_or_404(member_id)
    if member.account:
        flash('Thành viên có tài khoản đăng nhập. Hãy khóa tài khoản thay vì xóa.', 'danger')
        return redirect(url_for('main.members'))
    for issue in member.issues:
        if issue.status == 'issued':
            issue.book.available += 1
        db.session.delete(issue)
    db.session.delete(member)
    db.session.commit()
    flash('Đã xóa thành viên.', 'info')
    return redirect(url_for('main.members'))

# ─── Issues ──────────────────────────────────────────────────────────────────

@main.route('/issues')
def issues():
    all_issues = Issue.query.options(joinedload(Issue.book), joinedload(Issue.member)).order_by(Issue.issue_date.desc()).all()
    books   = Book.query.filter(Book.available > 0).all()
    members = Member.query.all()
    return render_template('issues.html', issues=all_issues, books=books, members=members,
                           today=datetime.now().date().isoformat())

@main.route('/issues/add', methods=['POST'])
def add_issue():
    data    = request.form
    try:
        issue_date = datetime.strptime(data.get('issue_date', ''), '%Y-%m-%d')
        due_date = datetime.strptime(data.get('due_date', ''), '%Y-%m-%d')
    except ValueError:
        flash('Vui lòng chọn ngày mượn và hạn trả hợp lệ.', 'danger')
        return redirect(url_for('main.issues'))
    if due_date < issue_date:
        flash('Hạn trả không được trước ngày mượn.', 'danger')
        return redirect(url_for('main.issues'))
    book    = Book.query.get_or_404(int(data['book_id']))
    member = Member.query.get_or_404(int(data['member_id']))
    if book.available < 1:
        flash('Sách hiện không còn bản nào để cho mượn!', 'danger')
        return redirect(url_for('main.issues'))
    issue = Issue(
        book_id   = book.id,
        member_id = member.id,
        issue_date = issue_date,
        due_date  = due_date
    )
    book.available -= 1
    db.session.add(issue)
    db.session.commit()
    flash('Lập phiếu mượn sách thành công!', 'success')
    return redirect(url_for('main.issues'))

@main.route('/issues/return/<int:issue_id>', methods=['POST'])
def return_book(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    if issue.status == 'returned':
        flash('Phiếu mượn này đã được trả sách.', 'info')
        return redirect(url_for('main.issues'))
    try:
        return_date = datetime.strptime(request.form.get('return_date', ''), '%Y-%m-%d')
    except ValueError:
        flash('Vui lòng chọn ngày trả sách hợp lệ.', 'danger')
        return redirect(url_for('main.issues'))
    if return_date.date() < issue.issue_date.date():
        flash('Ngày trả không được trước ngày mượn.', 'danger')
        return redirect(url_for('main.issues'))
    issue.status      = 'returned'
    issue.return_date = return_date
    issue.book.available += 1
    db.session.commit()
    flash('Trả sách thành công!', 'success')
    return redirect(url_for('main.issues'))

# ─── Health check (for Docker/Jenkins) ───────────────────────────────────────

@main.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Library Management System'}), 200

# ─── API endpoints ────────────────────────────────────────────────────────────

@main.route('/api/books')
def api_books():
    return jsonify([b.to_dict() for b in Book.query.all()])

@main.route('/api/members')
def api_members():
    return jsonify([m.to_dict() for m in Member.query.all()])

@main.route('/api/issues')
def api_issues():
    return jsonify([i.to_dict() for i in Issue.query.all()])
