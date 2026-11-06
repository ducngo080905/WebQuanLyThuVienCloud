"""Private, two-person conversations with incremental polling and read receipts."""
from datetime import datetime, timedelta
from functools import wraps
import re
from io import BytesIO
import unicodedata
import secrets
from flask import Blueprint, g, request, jsonify, render_template, abort, make_response, send_file, url_for
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from app import db
from app.auth import login_required, ROLES
from app.models import User, ChatThread, ChatMessage, LivePresence, ChatAttachment, ChatReaction, ChatChange, ChatContact, ChatBlock, ChatState, UserAvatar, ChatGroup, ChatGroupMember

chat = Blueprint('chat', __name__)


@chat.errorhandler(HTTPException)
def api_error(error):
    if request.path.startswith('/chat/api/'):
        messages = {403: 'Bạn không có quyền thực hiện thao tác này.', 404: 'Tin nhắn hoặc cuộc trò chuyện không còn khả dụng.'}
        response = jsonify(error=messages.get(error.code, 'Không thể thực hiện thao tác. Vui lòng thử lại.'))
        response.status_code = error.code
        response.headers['Cache-Control'] = 'no-store'
        return response
    return error


def api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get('user'):
            return jsonify(error='Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'), 401
        response = view(*args, **kwargs)
        response = make_response(response)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return wrapped


def thread_for_user(thread_id):
    thread = db.session.get(ChatThread, thread_id)
    if not thread: abort(404)
    if thread.group:
        member = db.session.get(ChatGroupMember, (thread.id, g.user.id))
        if not member or not member.active: abort(404)
        # A deleted account must not leave its surviving group without an owner.
        if not any(row.active and row.owner for row in thread.group_members):
            candidates = sorted((row for row in thread.group_members if row.active and row.user.active), key=lambda row:row.user_id)
            if candidates:
                candidates[0].owner = True; db.session.commit()
    elif g.user.id not in (thread.low_id, thread.high_id): abort(404)
    return thread


def peer_for(thread):
    return thread.high_user if thread.low_id == g.user.id else thread.low_user


def blocked(peer_id):
    return bool(db.session.get(ChatBlock, (g.user.id, peer_id)) or db.session.get(ChatBlock, (peer_id, g.user.id)))


def friends(peer_id):
    return bool(db.session.get(ChatContact, (g.user.id, peer_id)))


def ensure_contacts(first, second):
    for owner, peer in ((first, second), (second, first)):
        if not db.session.get(ChatContact, (owner, peer)):
            try:
                with db.session.begin_nested():
                    db.session.add(ChatContact(owner_id=owner, peer_id=peer))
                    db.session.flush()
            except IntegrityError:
                pass


def cleared(thread):
    state = db.session.get(ChatState, (thread.id, g.user.id))
    cutoff = state.cleared_through if state else 0
    member = db.session.get(ChatGroupMember, (thread.id, g.user.id)) if thread.group else None
    return max(cutoff, member.joined_after if member else 0)


def can_send(peer):
    return bool(peer.active and not blocked(peer.id) and (g.user.role == 'admin' or friends(peer.id)))


def group_can_send(thread):
    member = db.session.get(ChatGroupMember, (thread.id, g.user.id))
    return bool(member and member.active and not any(blocked(row.user_id) for row in thread.group_members if row.active and row.user_id != g.user.id))


def require_sending(thread):
    if thread.group:
        if not group_can_send(thread): abort(403)
    elif not can_send(peer_for(thread)): abort(403)


def conversation_data(thread, online):
    if not thread.group:
        data = person(peer_for(thread), online); data['kind'] = 'direct'; return data
    own = db.session.get(ChatGroupMember, (thread.id, g.user.id))
    members = [row for row in thread.group_members if row.active]
    return dict(id=thread.id, kind='group', name=thread.group.name, role='Nhóm', active=True, avatar=None,
                online=False, can_send=group_can_send(thread), blocked_by_me=False, is_contact=True,
                member_count=len(members), owner=bool(own and own.owner))


def sender_name(message):
    user = db.session.get(User, message.sender_id)
    return user.member.name if user else 'Thành viên đã xóa'


def person(user, online_ids):
    is_blocked = blocked(user.id)
    return dict(id=user.id, name=user.member.name, role=ROLES.get(user.role, user.role),
                online=user.id in online_ids and not is_blocked, active=user.active,
                avatar=url_for('chat.avatar', user_id=user.id, v=user.avatar.version) if user.avatar else None,
                blocked_by_me=bool(db.session.get(ChatBlock, (g.user.id, user.id))),
                can_send=can_send(user), is_contact=friends(user.id))


def online_ids():
    return {row[0] for row in db.session.query(LivePresence.user_id).filter(
        LivePresence.last_seen >= datetime.utcnow()-timedelta(seconds=45),
        LivePresence.closed.is_(False), LivePresence.visible.is_(True)).distinct()}


def quote_data(message):
    return dict(id=message.id, sender_id=message.sender_id, sender_name=sender_name(message),
                body='Tin nhắn đã thu hồi' if message.deleted_at else (message.body[:200] or (message.attachment.filename if message.attachment else 'Tin nhắn')),
                deleted=bool(message.deleted_at))


def message_data(message):
    attachment = message.attachment if not message.deleted_at else None
    reply = db.session.get(ChatMessage, message.reply_id) if message.reply_id else None
    reactions = {}
    if not message.deleted_at:
        for reaction in message.reactions:
            group = reactions.setdefault(reaction.emoji, dict(emoji=reaction.emoji, count=0, mine=False))
            group['count'] += 1
            group['mine'] = group['mine'] or reaction.user_id == g.user.id
    return dict(id=message.id, sender_id=message.sender_id, sender_name=sender_name(message),
                read_count=sum(1 for row in message.thread.group_members if row.active and row.user_id != message.sender_id and row.last_read >= message.id) if message.thread.group else None,
                body='' if message.deleted_at else message.body,
                deleted=bool(message.deleted_at), edited_at=message.edited_at.isoformat()+'Z' if message.edited_at else None,
                reply=quote_data(reply) if reply and reply.thread_id == message.thread_id and reply.id > cleared(message.thread) and not message.deleted_at else None,
                reactions=list(reactions.values()), attachment=dict(filename=attachment.filename, size=attachment.size,
                    image=attachment.mimetype.startswith('image/'), url=url_for('chat.attachment', message_id=message.id)) if attachment else None,
                client_id=message.client_id, created_at=message.created_at.isoformat()+'Z')


def changed(message):
    db.session.add(ChatChange(thread_id=message.thread_id, message_id=message.id))


def message_for_user(message_id):
    message = db.session.get(ChatMessage, message_id)
    if not message:
        abort(404)
    thread = thread_for_user(message.thread_id)
    if message.id <= cleared(thread): abort(404)
    return message


def read_attachment(upload):
    if not upload or not upload.filename:
        return None
    name = re.split(r'[/\\]', upload.filename)[-1]
    name = ''.join(c for c in name if not unicodedata.category(c).startswith('C'))[:180] or 'tep-dinh-kem'
    extension = name.rsplit('.', 1)[-1].lower()
    if extension in ('jpg', 'jpeg', 'png', 'webp'):
        from app.covers import read_cover
        data = read_cover(upload)
        return dict(filename=name.rsplit('.', 1)[0]+'.jpg', mimetype='image/jpeg', data=data, size=len(data))
    data = upload.stream.read(10*1024*1024+1)
    if len(data) > 10*1024*1024:
        raise ValueError('Tệp đính kèm tối đa 10 MB; ảnh tối đa 5 MB.')
    if not data:
        raise ValueError('Tệp đính kèm đang trống.')
    if extension == 'pdf' and data.startswith(b'%PDF-'):
        mimetype = 'application/pdf'
    elif extension == 'txt':
        try:
            data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('Tệp TXT cần có định dạng UTF-8.') from None
        if b'\x00' in data:
            raise ValueError('Tệp văn bản không hợp lệ.')
        mimetype = 'text/plain'
    else:
        raise ValueError('Hỗ trợ ảnh JPG, PNG, WebP và tệp PDF, TXT.')
    return dict(filename=name, mimetype=mimetype, data=data, size=len(data))


@chat.get('/messenger')
@login_required

def page():
    return render_template('messenger.html')


@chat.get('/chat/api/overview')
@api

def overview():
    online = online_ids()
    threads = ChatThread.query.filter(or_(ChatThread.low_id == g.user.id, ChatThread.high_id == g.user.id, ChatThread.group_members.any(user_id=g.user.id, active=True))).order_by(ChatThread.updated_at.desc(), ChatThread.id.desc()).all()
    result = []
    for thread in threads:
        state = db.session.get(ChatState, (thread.id, g.user.id))
        if state and state.hidden: continue
        cutoff = cleared(thread)
        last = ChatMessage.query.filter(ChatMessage.thread_id == thread.id, ChatMessage.id > cutoff).order_by(ChatMessage.id.desc()).first()
        own_read = (db.session.get(ChatGroupMember,(thread.id,g.user.id)).last_read if thread.group else (thread.low_read if thread.low_id == g.user.id else thread.high_read))
        unread = ChatMessage.query.filter(ChatMessage.thread_id == thread.id, ChatMessage.sender_id != g.user.id, ChatMessage.id > max(own_read, cutoff)).count()
        result.append(dict(id=thread.id, peer=conversation_data(thread, online),
                           last=message_data(last) if last else None, unread=unread))
    contacts = User.query.filter(User.id != g.user.id, User.active.is_(True))
    if g.user.role != 'admin':
        contacts = contacts.join(ChatContact, ChatContact.peer_id == User.id).filter(ChatContact.owner_id == g.user.id)
    contacts = contacts.order_by(User.id).all()
    blocked_users = User.query.join(ChatBlock, ChatBlock.peer_id == User.id).filter(ChatBlock.owner_id == g.user.id).all()
    return jsonify(threads=result, contacts=[person(user, online) for user in contacts],
                   blocked=[person(user, online) for user in blocked_users], me=g.user.id, admin=g.user.role == 'admin')


@chat.post('/chat/api/threads')
@api

def start():
    peer_id = request.form.get('user_id', type=int)
    if g.user.role != 'admin' and peer_id != g.user.id and not friends(peer_id or -1):
        return jsonify(error='Hãy thêm bạn bằng đúng email đã đăng ký trước khi nhắn tin.'), 403
    peer = db.session.get(User, peer_id) if peer_id else None
    if not peer or not peer.active or peer.id == g.user.id:
        return jsonify(error='Không thể bắt đầu cuộc trò chuyện với tài khoản này.'), 400
    if blocked(peer.id):
        return jsonify(error='Không thể nhắn tin với tài khoản này. Kiểm tra danh sách chặn.'), 403
    if g.user.role != 'admin' and not friends(peer.id):
        return jsonify(error='Hãy thêm bạn bằng đúng email đã đăng ký trước khi nhắn tin.'), 403
    low, high = sorted([g.user.id, peer.id])
    thread = ChatThread.query.filter_by(low_id=low, high_id=high).first()
    if not thread:
        thread = ChatThread(low_id=low, high_id=high)
        db.session.add(thread)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            thread = ChatThread.query.filter_by(low_id=low, high_id=high).one()
    if g.user.role == 'admin': ensure_contacts(g.user.id, peer.id)
    state = db.session.get(ChatState, (thread.id, g.user.id))
    if state: state.hidden = False
    db.session.commit()
    return jsonify(id=thread.id)


@chat.get('/chat/api/threads/<int:thread_id>')
@api

def messages(thread_id):
    thread = thread_for_user(thread_id)
    after = max(0, request.args.get('after', 0, type=int) or 0)
    before = max(0, request.args.get('before', 0, type=int) or 0)
    cursor = max(0, request.args.get('changes', 0, type=int) or 0)
    events = ChatChange.query.filter(ChatChange.thread_id == thread.id, ChatChange.id > cursor).order_by(ChatChange.id).limit(200).all()
    next_cursor = events[-1].id if events else cursor
    updates = {event.message_id for event in events}
    around = request.args.get('around', type=int)
    cutoff = cleared(thread)
    query = ChatMessage.query.filter(ChatMessage.thread_id == thread.id, ChatMessage.id > cutoff)
    if around:
        target = db.session.get(ChatMessage, around)
        if not target or target.thread_id != thread.id or target.id <= cutoff: abort(404)
        rows = list(reversed(query.filter(ChatMessage.id < around).order_by(ChatMessage.id.desc()).limit(25).all()))
        rows += query.filter(ChatMessage.id >= around).order_by(ChatMessage.id).limit(26).all()
    elif before:
        query = query.filter(ChatMessage.id < before)
    elif after:
        query = query.filter(ChatMessage.id > after)
    if around:
        pass
    elif after and not before:
        rows = query.order_by(ChatMessage.id).limit(100).all()
    else:
        rows = list(reversed(query.order_by(ChatMessage.id.desc()).limit(50).all()))
    typing_names = []
    if thread.group:
        typing_names = [row.user.member.name for row in thread.group_members if row.active and row.user_id != g.user.id and not blocked(row.user_id) and row.typing_at and row.typing_at > datetime.utcnow()-timedelta(seconds=6)]
        peer_typing = bool(typing_names); peer_read = 0
    else:
        peer_typing = thread.high_typing if thread.low_id == g.user.id else thread.low_typing
        peer_read = thread.high_read if thread.low_id == g.user.id else thread.low_read
    updated = ChatMessage.query.filter(ChatMessage.thread_id == thread.id, ChatMessage.id.in_(updates), ChatMessage.id > cutoff).all() if updates else []
    return jsonify(changes=next_cursor, updates=[message_data(row) for row in updated], messages=[message_data(row) for row in rows], peer=conversation_data(thread, online_ids()),
                   peer_read=peer_read, group_reads=[{'user_id':row.user_id,'last_read':row.last_read} for row in thread.group_members if row.active and row.user_id!=g.user.id] if thread.group else [], typing_names=typing_names, typing=bool(typing_names) if thread.group else bool(not blocked(peer_for(thread).id) and peer_typing and peer_typing > datetime.utcnow()-timedelta(seconds=6)),
                   has_older=bool(rows and ChatMessage.query.filter(ChatMessage.thread_id == thread.id, ChatMessage.id < rows[0].id, ChatMessage.id > cutoff).first()))


@chat.post('/chat/api/threads/<int:thread_id>/send')
@api

def send(thread_id):
    thread = thread_for_user(thread_id)
    if not thread.group and not peer_for(thread).active:
        return jsonify(error='Tài khoản này hiện không thể nhận tin nhắn.'), 400
    require_sending(thread)
    if not thread.group and g.user.role == 'admin': ensure_contacts(g.user.id, peer_for(thread).id)
    body = request.form.get('body', '').strip()
    client_id = request.form.get('client_id', '')
    if (not body and not request.files.get('attachment')) or len(body) > 4000 or not re.fullmatch(r'[a-zA-Z0-9_-]{16,64}', client_id):
        return jsonify(error='Tin nhắn cần có nội dung và không quá 4.000 ký tự.'), 400
    existing = ChatMessage.query.filter_by(sender_id=g.user.id, client_id=client_id).first()
    if existing:
        if existing.thread_id != thread.id:
            return jsonify(error='Mã gửi tin đã được sử dụng.'), 409
        if existing.id <= cleared(thread):
            return jsonify(error='Tin nhắn này thuộc lịch sử đã xóa.'), 409
        return jsonify(message=message_data(existing))
    count = ChatMessage.query.filter(ChatMessage.sender_id == g.user.id, ChatMessage.created_at > datetime.utcnow()-timedelta(minutes=1)).count()
    if count >= 60:
        return jsonify(error='Bạn gửi tin quá nhanh. Vui lòng chờ một chút.'), 429
    reply_id = request.form.get('reply_id', type=int)
    reply = db.session.get(ChatMessage, reply_id) if reply_id else None
    if reply_id and (not reply or reply.thread_id != thread.id or reply.id <= cleared(thread) or reply.deleted_at):
        return jsonify(error='Không thể trả lời tin nhắn này.'), 400
    try:
        file_data = read_attachment(request.files.get('attachment'))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    message = ChatMessage(thread_id=thread.id, sender_id=g.user.id, body=body, client_id=client_id, reply_id=reply_id)
    if file_data:
        message.attachment = ChatAttachment(**file_data)
    db.session.add(message)
    # A new message can restore the recipient's conversation, with old history still cleared.
    for state in thread.states: state.hidden = False
    thread.updated_at = datetime.utcnow()
    if thread.group: db.session.get(ChatGroupMember, (thread.id,g.user.id)).typing_at = None
    else: setattr(thread, 'low_typing' if thread.low_id == g.user.id else 'high_typing', None)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        message = ChatMessage.query.filter_by(sender_id=g.user.id, client_id=client_id).first()
        if not message or message.thread_id != thread.id:
            return jsonify(error='Chưa gửi được tin nhắn. Vui lòng thử lại.'), 409
    return jsonify(message=message_data(message))


@chat.post('/chat/api/threads/<int:thread_id>/read')
@api

def read(thread_id):
    thread = thread_for_user(thread_id)
    message_id = request.form.get('message_id', type=int)
    message = db.session.get(ChatMessage, message_id) if message_id else None
    if not message or message.thread_id != thread.id:
        return jsonify(error='Tin nhắn không hợp lệ.'), 400
    if thread.group:
        ChatGroupMember.query.filter_by(thread_id=thread.id,user_id=g.user.id).update({'last_read':func.max(ChatGroupMember.last_read,message.id)},synchronize_session=False)
    else:
        field = 'low_read' if thread.low_id == g.user.id else 'high_read'
        ChatThread.query.filter_by(id=thread.id).update({field: func.max(getattr(ChatThread, field), message.id)}, synchronize_session=False)
    db.session.commit()
    return jsonify(ok=True)


@chat.post('/chat/api/threads/<int:thread_id>/typing')
@api

def typing(thread_id):
    thread = thread_for_user(thread_id)
    if request.form.get('typing') == '1': require_sending(thread)
    value = datetime.utcnow() if request.form.get('typing') == '1' else None
    if thread.group: db.session.get(ChatGroupMember,(thread.id,g.user.id)).typing_at = value
    else: setattr(thread, 'low_typing' if thread.low_id == g.user.id else 'high_typing', value)
    db.session.commit()
    return jsonify(ok=True)

@chat.get('/chat/api/unread')
@api
def unread():
    from sqlalchemy import case
    cursor = case((ChatThread.low_id == g.user.id, ChatThread.low_read), else_=ChatThread.high_read)
    count = db.session.query(func.count(ChatMessage.id)).join(ChatThread, ChatMessage.thread_id == ChatThread.id).outerjoin(
        ChatState, (ChatState.thread_id == ChatThread.id) & (ChatState.user_id == g.user.id)).filter(
        or_(ChatThread.low_id == g.user.id, ChatThread.high_id == g.user.id),
        ChatMessage.sender_id != g.user.id, ChatMessage.id > cursor,
        ChatMessage.id > func.coalesce(ChatState.cleared_through, 0),
        or_(ChatState.hidden.is_(False), ChatState.hidden.is_(None))).scalar()
    group_count = db.session.query(func.count(ChatMessage.id)).join(ChatGroupMember, ChatGroupMember.thread_id == ChatMessage.thread_id).outerjoin(
        ChatState,(ChatState.thread_id == ChatMessage.thread_id) & (ChatState.user_id == g.user.id)).filter(
        ChatGroupMember.user_id == g.user.id, ChatGroupMember.active.is_(True), ChatMessage.sender_id != g.user.id,
        ChatMessage.id > ChatGroupMember.last_read, ChatMessage.id > ChatGroupMember.joined_after,
        ChatMessage.id > func.coalesce(ChatState.cleared_through,0), or_(ChatState.hidden.is_(False),ChatState.hidden.is_(None))).scalar()
    return jsonify(unread=count+group_count)


@chat.get('/chat/api/attachments/<int:message_id>')
@api
def attachment(message_id):
    message = message_for_user(message_id)
    file = message.attachment
    if message.deleted_at or not file:
        abort(404)
    response = send_file(BytesIO(file.data), mimetype=file.mimetype, download_name=file.filename,
                         as_attachment=not file.mimetype.startswith('image/'))
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response


@chat.post('/chat/api/messages/<int:message_id>/edit')
@api
def edit(message_id):
    message = message_for_user(message_id)
    if message.sender_id != g.user.id:
        abort(403)
    require_sending(message.thread)
    if message.deleted_at or message.created_at < datetime.utcnow()-timedelta(minutes=15):
        return jsonify(error='Chỉ sửa được tin nhắn trong vòng 15 phút sau khi gửi.'), 400
    body = request.form.get('body', '').strip()
    if len(body) > 4000 or (not body and not message.attachment):
        return jsonify(error='Nội dung cần có từ 1 đến 4.000 ký tự.'), 400
    message.body = body
    message.edited_at = datetime.utcnow()
    changed(message)
    db.session.commit()
    return jsonify(message=message_data(message))


@chat.post('/chat/api/messages/<int:message_id>/recall')
@api
def recall(message_id):
    message = message_for_user(message_id)
    if message.sender_id != g.user.id:
        abort(403)
    if not message.deleted_at:
        message.body = ''
        message.deleted_at = datetime.utcnow()
        if message.attachment: db.session.delete(message.attachment)
        for reaction in list(message.reactions): db.session.delete(reaction)
        changed(message)
        db.session.commit()
    return jsonify(message=message_data(message))


@chat.post('/chat/api/messages/<int:message_id>/react')
@api
def react(message_id):
    message = message_for_user(message_id)
    require_sending(message.thread)
    if message.deleted_at:
        return jsonify(error='Tin nhắn đã được thu hồi.'), 400
    emoji = request.form.get('emoji', '')
    if emoji not in ('', '👍', '❤️', '😂', '😮', '😢', '🙏'):
        return jsonify(error='Cảm xúc không hợp lệ.'), 400
    reaction = db.session.get(ChatReaction, (message.id, g.user.id))
    if (reaction and reaction.emoji == emoji) or (not reaction and not emoji):
        return jsonify(message=message_data(message))
    if not emoji:
        if reaction: db.session.delete(reaction)
    elif reaction:
        reaction.emoji = emoji
    else:
        db.session.add(ChatReaction(message_id=message.id, user_id=g.user.id, emoji=emoji))
    changed(message)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error='Cảm xúc vừa thay đổi. Vui lòng thử lại.'), 409
    return jsonify(message=message_data(message))


@chat.get('/chat/api/threads/<int:thread_id>/search')
@api
def search(thread_id):
    thread = thread_for_user(thread_id)
    query = request.args.get('q', '').strip()[:100]
    before = request.args.get('before', type=int)
    if not query:
        return jsonify(messages=[], has_more=False)
    rows = ChatMessage.query.filter(ChatMessage.thread_id == thread_id, ChatMessage.id > cleared(thread), ChatMessage.deleted_at.is_(None),
                                   ChatMessage.body.contains(query, autoescape=True))
    if before: rows = rows.filter(ChatMessage.id < before)
    rows = rows.order_by(ChatMessage.id.desc()).limit(31).all()
    return jsonify(messages=[message_data(row) for row in rows[:30]], has_more=len(rows)>30)


@chat.post('/chat/api/contacts/add')
@api
def add_contact():
    email = request.form.get('email', '').strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 120:
        return jsonify(error='Nhập đầy đủ email đã đăng ký của người muốn thêm.'), 400
    peer = User.query.filter(func.lower(User.email) == email).first()
    if not peer:
        return jsonify(error='Email này chưa đăng ký tài khoản trong hệ thống.'), 404
    if peer.id == g.user.id:
        return jsonify(error='Bạn không thể thêm chính mình.'), 400
    if not peer.active or blocked(peer.id):
        return jsonify(error='Không thể thêm tài khoản này. Kiểm tra trạng thái hoặc danh sách chặn.'), 403
    ensure_contacts(g.user.id, peer.id)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return jsonify(peer=person(peer, online_ids()))


@chat.post('/chat/api/contacts/<int:peer_id>/block')
@api
def block_contact(peer_id):
    peer = db.session.get(User, peer_id)
    if not peer or peer_id == g.user.id: abort(404)
    known = friends(peer_id) or ChatThread.query.filter(or_(
        (ChatThread.low_id == g.user.id) & (ChatThread.high_id == peer_id),
        (ChatThread.high_id == g.user.id) & (ChatThread.low_id == peer_id))).first()
    if g.user.role != 'admin' and not known and not db.session.get(ChatBlock, (g.user.id, peer_id)): abort(404)
    row = db.session.get(ChatBlock, (g.user.id, peer_id))
    should_block = request.form.get('blocked') == '1'
    if should_block and not row: db.session.add(ChatBlock(owner_id=g.user.id, peer_id=peer_id))
    elif not should_block and row: db.session.delete(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return jsonify(ok=True)


@chat.post('/chat/api/threads/<int:thread_id>/remove-contact')
@api
def remove_contact(thread_id):
    thread = thread_for_user(thread_id)
    if thread.group: return jsonify(error='Dùng chức năng rời nhóm để ngừng tham gia.'),400
    peer = peer_for(thread)
    for owner, target in ((g.user.id, peer.id), (peer.id, g.user.id)):
        contact = db.session.get(ChatContact, (owner, target))
        if contact: db.session.delete(contact)
    state = db.session.get(ChatState, (thread.id, g.user.id))
    if not state:
        state = ChatState(thread_id=thread.id, user_id=g.user.id)
        db.session.add(state)
    state.cleared_through = db.session.query(func.max(ChatMessage.id)).filter_by(thread_id=thread.id).scalar() or 0
    state.hidden = True
    setattr(thread, 'low_read' if thread.low_id == g.user.id else 'high_read', state.cleared_through)
    db.session.commit()
    return jsonify(ok=True)


@chat.route('/profile/avatar', methods=['POST'])
@login_required
def update_avatar():
    from flask import flash, redirect
    from app.covers import read_cover
    if request.form.get('remove') == '1':
        if g.user.avatar: db.session.delete(g.user.avatar)
        db.session.commit()
        flash('Đã xóa ảnh đại diện.', 'success')
    else:
        try:
            data = read_cover(request.files.get('avatar'))
            if not data: raise ValueError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
            from PIL import Image, ImageOps
            with Image.open(BytesIO(data)) as image:
                image = ImageOps.fit(image, (256,256))
                output = BytesIO(); image.save(output, format='JPEG', quality=85)
            avatar = g.user.avatar or UserAvatar(user=g.user)
            avatar.data = output.getvalue(); avatar.version = secrets.token_hex(8)
            db.session.add(avatar); db.session.commit()
            flash('Đã cập nhật ảnh đại diện.', 'success')
        except ValueError as error:
            flash(str(error).replace('Ảnh bìa', 'Ảnh đại diện'), 'danger')
    return redirect(url_for('auth.profile'))


@chat.get('/chat/api/avatars/<int:user_id>')
@api
def avatar(user_id):
    user = db.session.get(User, user_id)
    if not user or not user.avatar: abort(404)
    known = user_id == g.user.id or g.user.role == 'admin' or friends(user_id) or ChatThread.query.filter(or_(
        (ChatThread.low_id == g.user.id) & (ChatThread.high_id == user_id),
        (ChatThread.high_id == g.user.id) & (ChatThread.low_id == user_id))).first()
    if not known:
        own_groups = db.session.query(ChatGroupMember.thread_id).filter_by(user_id=g.user.id,active=True)
        known = ChatGroupMember.query.filter(ChatGroupMember.user_id==user_id,ChatGroupMember.active.is_(True),ChatGroupMember.thread_id.in_(own_groups)).first()
    if not known: abort(404)
    response = send_file(BytesIO(user.avatar.data), mimetype='image/jpeg')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


from app import chat_groups  # Register group routes on the same authenticated blueprint.
