"""Group membership and ownership; chat transport stays shared with direct messages."""
from datetime import datetime
from flask import g, request, jsonify, abort
from app import db
from app.models import User, ChatThread, ChatMessage, ChatGroup, ChatGroupMember, ChatBlock
from app.chat import chat, api, thread_for_user, friends, conversation_data, online_ids


def group_for_user(thread_id, owner=False):
    thread = thread_for_user(thread_id)
    if not thread.group: abort(404)
    membership = db.session.get(ChatGroupMember,(thread.id,g.user.id))
    if owner and not membership.owner: abort(403)
    return thread, membership


def eligible(user_id, existing_ids):
    if g.user.role != 'admin' and not friends(user_id):
        return None
    user = db.session.get(User,user_id)
    if not user or not user.active: return None
    for other in existing_ids:
        if db.session.get(ChatBlock,(user_id,other)) or db.session.get(ChatBlock,(other,user_id)):
            return None
    return user


@chat.post('/chat/api/groups')
@api
def create_group():
    name = request.form.get('name','').strip()
    try: ids = sorted({int(value) for value in request.form.get('member_ids','').split(',')})
    except ValueError: ids = []
    if not name or len(name)>80 or not 1<=len(ids)<=49 or g.user.id in ids or any(value<1 for value in ids):
        return jsonify(error='Nhập tên nhóm (tối đa 80 ký tự) và chọn từ 1 đến 49 người khác.'),400
    included = [g.user.id]
    for user_id in ids:
        if not eligible(user_id,included):
            return jsonify(error='Chỉ mời bạn bè đang hoạt động và không có quan hệ chặn trong nhóm. Admin có thể chọn toàn bộ tài khoản.'),403
        included.append(user_id)
    thread=ChatThread(low_id=None,high_id=None)
    thread.group=ChatGroup(name=name)
    db.session.add(thread);db.session.flush()
    db.session.add_all([ChatGroupMember(thread_id=thread.id,user_id=user_id,owner=user_id==g.user.id) for user_id in included])
    db.session.commit()
    return jsonify(id=thread.id,peer=conversation_data(thread,online_ids()))


@chat.get('/chat/api/threads/<int:thread_id>/group')
@api
def group_details(thread_id):
    thread, membership=group_for_user(thread_id)
    members=[]
    for row in sorted(thread.group_members,key=lambda row:(not row.owner,row.user_id)):
        if not row.active: continue
        user=row.user
        members.append(dict(id=user.id,name=user.member.name,owner=row.owner,active=user.active,
                            avatar=('/chat/api/avatars/'+str(user.id)+'?v='+user.avatar.version) if user.avatar else None))
    return jsonify(id=thread.id,name=thread.group.name,owner=membership.owner,members=members)


@chat.post('/chat/api/threads/<int:thread_id>/group')
@api
def manage_group(thread_id):
    action=request.form.get('action','')
    thread, membership=group_for_user(thread_id,owner=action!='leave')
    if action=='rename':
        name=request.form.get('name','').strip()
        if not name or len(name)>80: return jsonify(error='Tên nhóm cần có từ 1 đến 80 ký tự.'),400
        thread.group.name=name
    elif action=='add':
        target_id=request.form.get('user_id',type=int)
        active=[row.user_id for row in thread.group_members if row.active]
        if not target_id or target_id in active or len(active)>=50:
            return jsonify(error='Tài khoản đã có trong nhóm hoặc nhóm đã đủ 50 người.'),400
        if not eligible(target_id,active): return jsonify(error='Không thể thêm tài khoản này. Cần là bạn bè đang hoạt động và không chặn thành viên nào trong nhóm.'),403
        target=db.session.get(ChatGroupMember,(thread.id,target_id))
        cutoff=db.session.query(db.func.max(ChatMessage.id)).filter_by(thread_id=thread.id).scalar() or 0
        if target:
            target.active=True;target.owner=False;target.joined_after=cutoff;target.last_read=cutoff;target.typing_at=None
        else:
            db.session.add(ChatGroupMember(thread_id=thread.id,user_id=target_id,joined_after=cutoff,last_read=cutoff))
    elif action in ('remove','transfer'):
        target_id=request.form.get('user_id',type=int)
        target=db.session.get(ChatGroupMember,(thread.id,target_id)) if target_id else None
        if not target or not target.active or target_id==g.user.id:
            return jsonify(error='Chọn thành viên khác đang ở trong nhóm.'),400
        if action=='transfer':
            if not target.user.active: return jsonify(error='Không thể chuyển quyền cho tài khoản đang khóa.'),400
            changed = ChatGroupMember.query.filter_by(thread_id=thread.id,user_id=g.user.id,active=True,owner=True).update({'owner':False},synchronize_session=False)
            if not changed:
                db.session.rollback(); return jsonify(error='Quyền trưởng nhóm vừa thay đổi. Vui lòng mở lại thông tin nhóm.'),403
            db.session.expire(membership);target.owner=True
        else:
            target.active=False;target.owner=False;target.typing_at=None
    elif action=='leave':
        others=[row for row in thread.group_members if row.active and row.user_id!=g.user.id]
        if membership.owner and others:
            return jsonify(error='Hãy chuyển quyền trưởng nhóm cho thành viên khác trước khi rời nhóm.'),400
        membership.active=False;membership.owner=False;membership.typing_at=None
    else:
        return jsonify(error='Thao tác không hợp lệ.'),400
    thread.updated_at=datetime.utcnow();db.session.commit()
    return jsonify(ok=True,left=action=='leave')
