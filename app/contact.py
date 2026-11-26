"""Private, request-based reader support; no background chat polling."""
from datetime import datetime, timedelta
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload
from app import db
from app.auth import login_required
from app.models import ContactRequest, ContactReply

contact = Blueprint('contact', __name__)
STATUS = {'waiting': 'Chờ admin phản hồi', 'replied': 'Admin đã phản hồi', 'closed': 'Đã giải quyết'}


def admin_required():
    if g.user.role != 'admin':
        abort(403)


def visible_request(request_id):
    item = db.get_or_404(ContactRequest, request_id)
    if g.user.role != 'admin' and item.user_id != g.user.id:
        abort(404)
    return item


@contact.app_template_filter('contact_time')
def contact_time(value):
    return (value + timedelta(hours=7)).strftime('%d/%m/%Y · %H:%M')


@contact.route('/contact', methods=['GET', 'POST'])
@login_required
def index():
    if g.user.role == 'admin':
        return redirect(url_for('contact.admin'))
    error = None
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        if not 1 <= len(subject) <= 160 or not 1 <= len(body) <= 5000:
            error = 'Nhập tiêu đề tối đa 160 ký tự và nội dung tối đa 5.000 ký tự.'
        else:
            item = ContactRequest(user_id=g.user.id, subject=subject)
            db.session.add(item)
            db.session.flush()
            db.session.add(ContactReply(request=item, sender_id=g.user.id, body=body))
            db.session.commit()
            flash('Đã gửi yêu cầu đến admin.', 'success')
            return redirect(url_for('contact.detail', request_id=item.id), code=303)
    items = ContactRequest.query.filter_by(user_id=g.user.id).order_by(ContactRequest.updated_at.desc(), ContactRequest.id.desc()).paginate(per_page=15, max_per_page=15)
    return render_template('contact.html', items=items, statuses=STATUS, error=error, admin_view=False), 400 if error else 200


@contact.get('/admin/contact')
@login_required
def admin():
    admin_required()
    state = request.args.get('status', '')
    query = ContactRequest.query.options(joinedload(ContactRequest.user))
    if state in STATUS:
        query = query.filter_by(status=state)
    items = query.order_by(ContactRequest.updated_at.desc(), ContactRequest.id.desc()).paginate(per_page=20, max_per_page=20)
    return render_template('contact.html', items=items, statuses=STATUS, error=None, admin_view=True, selected_status=state)


@contact.route('/contact/<int:request_id>', methods=['GET', 'POST'])
@login_required
def detail(request_id):
    item = visible_request(request_id)
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not 1 <= len(body) <= 5000:
            flash('Nội dung cần có từ 1 đến 5.000 ký tự.', 'danger')
        elif item.status == 'closed':
            flash('Yêu cầu đã giải quyết. Hãy mở lại yêu cầu trước khi gửi thêm.', 'danger')
        else:
            db.session.add(ContactReply(request=item, sender_id=g.user.id, body=body, from_admin=g.user.role == 'admin'))
            item.updated_at = datetime.utcnow()
            item.status = 'replied' if g.user.role == 'admin' else 'waiting'
            db.session.commit()
            flash('Đã gửi phản hồi.', 'success')
        return redirect(url_for('contact.detail', request_id=item.id), code=303)
    replies = item.replies.options(joinedload(ContactReply.sender)).order_by(ContactReply.id.desc()).paginate(per_page=50, max_per_page=50)
    return render_template('contact_detail.html', item=item, replies=replies, statuses=STATUS)


@contact.post('/contact/<int:request_id>/status')
@login_required
def status(request_id):
    item = visible_request(request_id)
    state = request.form.get('status')
    if state not in ('closed', 'waiting'):
        abort(400)
    item.status = state
    item.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Đã đóng yêu cầu.' if state == 'closed' else 'Đã mở lại yêu cầu.', 'success')
    return redirect(url_for('contact.detail', request_id=item.id), code=303)
