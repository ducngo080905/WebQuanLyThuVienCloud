from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, timezone
import re
from flask import Blueprint,abort,g,jsonify,request,render_template,flash,redirect,url_for
from app import db
from app.auth import login_required
from app.models import Announcement, AnnouncementReceipt, Issue, DueReminder

messages=Blueprint('messages',__name__)


def valid_phone(value):
    cleaned=re.sub(r'[\s().-]','',value or '')
    return cleaned if re.fullmatch(r'\+?[0-9]{9,15}',cleaned) else None


def install_messages(app):
    @app.before_request
    def require_contact_for_transactions():
        if (g.get('user') and g.user.role!='admin' and not valid_phone(g.user.member.phone) and request.method=='POST'
            and request.endpoint in ('auth.request_book','features.request_renewal')):
            return jsonify(error='Vui lòng bổ sung số điện thoại trước khi mượn sách.',phone_required=True),428


@messages.get('/live-updates')
@login_required
def live():
    if g.user.role=='admin':
        response=jsonify(phone_required=False,google_link_required=not bool(g.user.google_identity),announcements=[])
        response.headers['Cache-Control']='no-store'
        return response
    received = AnnouncementReceipt.query.filter(
        AnnouncementReceipt.announcement_id == Announcement.id,
        AnnouncementReceipt.user_id == g.user.id,
    ).exists()
    active = Announcement.query.filter(
        or_(Announcement.audience == 'broadcast', received),
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > utc_now()),
    ).order_by(Announcement.id.desc()).all()
    reminders = due_reminders(g.user)
    announcements = [
        {'id': item.id, 'title': item.title, 'body': item.body, 'color': item.color}
        for item in active
    ]
    announcements.extend({
        'id': f'due-{item.id}', 'title': 'Hạn trả sách',
        'body': f'{item.book_title} · Phiếu #{item.issue_id} · Hạn trả {item.due_date:%d/%m/%Y}',
    } for item in reminders)
    response=jsonify(phone_required=not bool(valid_phone(g.user.member.phone)),google_link_required=not bool(g.user.google_identity),
        announcements=announcements)
    response.headers['Cache-Control']='no-store'
    return response


def due_reminders(user):
    cutoff = datetime.combine(datetime.now().date() + timedelta(days=4), datetime.min.time())
    recorded = db.session.query(DueReminder.id).filter(
        DueReminder.user_id == user.id, DueReminder.issue_id == Issue.id,
        DueReminder.due_date == func.date(Issue.due_date),
    ).exists()
    loans = Issue.query.options(joinedload(Issue.book)).filter(
        Issue.member_id == user.member_id, Issue.status == 'issued',
        Issue.due_date < cutoff, ~recorded,
    ).all()
    for loan in loans:
        try:
            with db.session.begin_nested():
                db.session.add(DueReminder(user_id=user.id, issue_id=loan.id,
                                           due_date=loan.due_date.date(), book_title=loan.book.title))
        except IntegrityError:
            # Another tab may have recorded the same deadline while this request was running.
            pass
    if loans:
        db.session.commit()
    return DueReminder.query.filter_by(user_id=user.id, removed=False).order_by(DueReminder.due_date).all()


@messages.post('/profile/required-phone')
@login_required
def phone():
    value=valid_phone(request.form.get('phone',''))
    if not value:
        return jsonify(error='Nhập số điện thoại gồm 9–15 chữ số, có thể bắt đầu bằng +.'),400
    g.user.member.phone=value
    db.session.commit()
    return jsonify(ok=True)


@messages.post('/announcements/<int:item_id>/read')
@login_required
def read(item_id):
    row=db.session.get(AnnouncementReceipt,(item_id,g.user.id))
    if not row: abort(404)
    if row.read_at is None:
        row.read_at=datetime.utcnow();db.session.commit()
    if request.form.get('return_to')=='inbox':
        return redirect(url_for('auth.library_home'),code=303)
    return jsonify(ok=True)


NOTICE_OFFSET = timedelta(hours=7)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@messages.route('/admin/announcements', methods=['GET', 'POST'])
@login_required
def compose():
    if g.user.role != 'admin':
        abort(403)
    source = request.form if request.method == 'POST' else request.args
    edit_id = source.get('edit', type=int)
    editing = db.get_or_404(Announcement, edit_id) if edit_id else None
    error = None
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        color = request.form.get('color', '')
        end = request.form.get('expires_at', '')
        expiry_date = request.form.get('expiry_date', '')
        expiry_time = request.form.get('expiry_time', '')
        try:
            if not body or len(body) > 5000 or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ValueError
            if expiry_date or expiry_time:
                if not expiry_date or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', expiry_time):
                    raise ValueError
                end = f'{expiry_date}T{expiry_time}'
            expires_at = datetime.strptime(end, '%Y-%m-%dT%H:%M') - NOTICE_OFFSET if end else None
        except (ValueError, OverflowError):
            error = 'Kiểm tra nội dung, màu chữ và thời điểm tự tắt (HH:MM).'
        else:
            item = editing or Announcement(title='', audience='broadcast', sender_id=g.user.id)
            item.body = body
            item.color = color
            item.expires_at = expires_at
            db.session.add(item)
            db.session.commit()
            if not editing:
                flash('Đã đăng thông báo.', 'success')
            return redirect(url_for('messages.compose'), code=303)
    items = Announcement.query.order_by(Announcement.id.desc()).all()
    reminders = DueReminder.query.options(joinedload(DueReminder.user)).filter_by(removed=False).order_by(DueReminder.due_date).all()
    return render_template('announcements.html', items=items, editing=editing, error=error,
                           reminders=reminders, now=utc_now(), notice_offset=NOTICE_OFFSET)


@messages.post('/admin/announcements/<int:item_id>/delete')
@login_required
def delete_announcement(item_id):
    if g.user.role != 'admin':
        abort(403)
    db.session.delete(db.get_or_404(Announcement, item_id))
    db.session.commit()
    flash('Đã xóa thông báo.', 'success')
    return redirect(url_for('messages.compose'), code=303)


@messages.post('/admin/due-reminders/<int:item_id>/delete')
@login_required
def delete_due_reminder(item_id):
    if g.user.role != 'admin':
        abort(403)
    # Keep the deadline key so the next poll cannot recreate a removed reminder.
    db.get_or_404(DueReminder, item_id).removed = True
    db.session.commit()
    flash('Đã gỡ nhắc hạn.', 'success')
    return redirect(url_for('messages.compose'), code=303)


@messages.get('/inbox')
@login_required
def inbox():
    return redirect(url_for('auth.library_home'))


@messages.post('/inbox/read-all')
@login_required
def read_all():
    AnnouncementReceipt.query.filter_by(user_id=g.user.id,read_at=None).update(
        {'read_at':datetime.utcnow()},synchronize_session=False)
    db.session.commit()
    if request.form.get('return_to')=='inbox':
        return redirect(url_for('auth.library_home'),code=303)
    return jsonify(ok=True)
