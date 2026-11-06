from datetime import datetime
import re
from flask import Blueprint,abort,g,jsonify,request,render_template,flash,redirect,url_for
from app import db
from app.auth import login_required
from app.models import User,Announcement,AnnouncementReceipt

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
    receipts=AnnouncementReceipt.query.filter_by(user_id=g.user.id,read_at=None).order_by(AnnouncementReceipt.announcement_id).limit(20).all()
    response=jsonify(phone_required=not bool(valid_phone(g.user.member.phone)),google_link_required=not bool(g.user.google_identity),
        announcements=[{'id':row.announcement.id,'title':row.announcement.title,'body':row.announcement.body,
                         'created_at':row.announcement.created_at.isoformat()+'Z'} for row in receipts])
    response.headers['Cache-Control']='no-store'
    return response


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
    row.read_at=datetime.utcnow();db.session.commit()
    return jsonify(ok=True)


@messages.route('/admin/announcements',methods=['GET','POST'])
@login_required
def compose():
    if g.user.role!='admin': abort(403)
    if request.method=='POST':
        title=request.form.get('title','').strip();body=request.form.get('body','').strip()
        audience=request.form.get('audience')
        target_id=request.form.get('target_id',type=int)
        if not title or len(title)>150 or not body or len(body)>5000 or audience not in ('all','reader','librarian','one'):
            flash('Nhập tiêu đề (tối đa 150 ký tự), nội dung (tối đa 5.000 ký tự) và nhóm nhận hợp lệ.','danger')
        else:
            query=User.query.filter(User.active.is_(True),User.role!='admin')
            if audience=='one': query=query.filter_by(id=target_id)
            elif audience!='all': query=query.filter_by(role=audience)
            recipients=query.all()
            if not recipients:
                flash('Không có tài khoản đang hoạt động phù hợp để nhận.','danger')
            else:
                item=Announcement(title=title,body=body,audience=audience,target_id=target_id if audience=='one' else None,sender_id=g.user.id)
                db.session.add(item);db.session.flush()
                db.session.add_all([AnnouncementReceipt(announcement_id=item.id,user_id=user.id) for user in recipients])
                db.session.commit();flash(f'Đã gửi thông báo đến {len(recipients)} tài khoản.','success')
                return redirect(url_for('messages.compose'))
    items=Announcement.query.order_by(Announcement.created_at.desc()).limit(50).all()
    return render_template('announcements.html',users=User.query.filter(User.active.is_(True),User.role!='admin').order_by(User.email).all(),items=items)


@messages.get('/inbox')
@login_required
def inbox():
    rows=AnnouncementReceipt.query.filter_by(user_id=g.user.id).order_by(AnnouncementReceipt.announcement_id.desc()).limit(100).all()
    return render_template('inbox.html',rows=rows)
