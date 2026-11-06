import pytest
from app import create_app, db
from app.models import User, Member, ChatThread, ChatMessage, ChatAttachment, ChatGroupMember, ChatGroup
from tests.test_chat import chat_app, user


def make_group(client, name, *people):
    for person in people: client.post('/chat/api/contacts/add',data={'email':person.email})
    return client.post('/chat/api/groups',data={'name':name,'member_ids':','.join(str(person.id) for person in people)})


def test_group_privacy_shared_chat_and_read_receipts(chat_app):
    a,alice=user(chat_app,'alice');b,bob=user(chat_app,'bob');c,carol=user(chat_app,'carol'); outsider,admin=user(chat_app,'admin','admin')
    response=make_group(a,'Book club',bob,carol)
    assert response.status_code==200
    thread=response.json['id']
    assert response.json['peer']['member_count']==3
    assert b.get('/chat/api/overview').json['threads'][0]['peer']['kind']=='group'
    assert outsider.get(f'/chat/api/threads/{thread}').status_code==404
    assert outsider.get(f'/chat/api/threads/{thread}/group').status_code==404
    assert outsider.post(f'/chat/api/threads/{thread}/send',data={'body':'no','client_id':'outsider_nonce11'}).status_code==404
    from io import BytesIO
    message=a.post(f'/chat/api/threads/{thread}/send',data={'body':'A reading plan','client_id':'group_file_nonce1','attachment':(BytesIO(b'read me'),'plan.txt')}).json['message']
    assert message['sender_name']=='alice'
    assert b.get('/chat/api/unread').json['unread']==1 and c.get('/chat/api/unread').json['unread']==1
    assert outsider.get(message['attachment']['url']).status_code==404
    assert b.get(message['attachment']['url']).status_code==200
    b.post(f'/chat/api/threads/{thread}/read',data={'message_id':message['id']})
    result=a.get(f'/chat/api/threads/{thread}').json
    assert result['messages'][0]['read_count']==1 and result['group_reads'][0]['last_read']==message['id']
    assert b.get('/chat/api/unread').json['unread']==0
    assert b.post(f'/chat/api/threads/{thread}/typing',data={'typing':'1'}).json['ok']
    assert a.get(f'/chat/api/threads/{thread}').json['typing_names']==['bob']
    reply=c.post(f'/chat/api/threads/{thread}/send',data={'body':'Agreed','client_id':'group_reply_nonce','reply_id':message['id']}).json['message']
    assert reply['reply']['sender_name']=='alice'
    assert b.post(f'/chat/api/messages/{message["id"]}/edit',data={'body':'No'}).status_code==403
    assert b.post(f'/chat/api/messages/{message["id"]}/react',data={'emoji':'❤️'}).status_code==200
    assert b.get(f'/chat/api/threads/{thread}/search?q=reading').json['messages'][0]['id']==message['id']
    assert b.post(f'/chat/api/threads/{thread}/remove-contact',data={}).status_code==400
    # Multiple groups with the same participants coexist with direct chats.
    second=make_group(a,'Another club',bob,carol)
    assert second.status_code==200 and second.json['id']!=thread
    assert a.post('/chat/api/threads',data={'user_id':bob.id}).status_code==200


def test_group_management_owner_permissions_join_cutoff_leave_and_transfer(chat_app):
    a,alice=user(chat_app,'alice');b,bob=user(chat_app,'bob');c,carol=user(chat_app,'carol');d,dana=user(chat_app,'dana')
    thread=make_group(a,'Group',bob,carol).json['id']
    original=a.post(f'/chat/api/threads/{thread}/send',data={'body':'Before joining','client_id':'before_join_nonce'}).json['message']['id']
    assert b.post(f'/chat/api/threads/{thread}/group',data={'action':'rename','name':'No'}).status_code==403
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'leave'}).status_code==400
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'add','user_id':dana.id}).status_code==403
    a.post('/chat/api/contacts/add',data={'email':dana.email})
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'add','user_id':dana.id}).json['ok']
    assert d.get(f'/chat/api/threads/{thread}').json['messages']==[]
    assert not d.get(f'/chat/api/threads/{thread}/search?q=Before').json['messages']
    assert d.post(f'/chat/api/messages/{original}/react',data={'emoji':'👍'}).status_code==404
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'remove','user_id':dana.id}).json['ok']
    assert d.get(f'/chat/api/threads/{thread}').status_code==404
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'rename','name':'New group name'}).json['ok']
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'transfer','user_id':bob.id}).json['ok']
    assert b.get(f'/chat/api/threads/{thread}/group').json['owner']
    assert a.post(f'/chat/api/threads/{thread}/group',data={'action':'leave'}).json['left']
    assert a.get(f'/chat/api/threads/{thread}').status_code==404
    assert b.post(f'/chat/api/threads/{thread}/group',data={'action':'remove','user_id':carol.id}).json['ok']
    assert b.post(f'/chat/api/threads/{thread}/group',data={'action':'leave'}).json['left']
    assert b.get('/chat/api/overview').json['threads']==[]


def test_group_creation_privacy_blocking_and_deleted_owner(chat_app):
    a,alice=user(chat_app,'alice');b,bob=user(chat_app,'bob');c,carol=user(chat_app,'carol');d,dana=user(chat_app,'dana')
    assert a.post('/chat/api/groups',data={'name':'Group','member_ids':f'{bob.id},{carol.id}'}).status_code==403
    assert make_group(a,'',bob,carol).status_code==400
    assert make_group(a,'Only two',bob).status_code==200
    assert a.post('/chat/api/groups',data={'name':'Empty','member_ids':''}).status_code==400
    b.post('/chat/api/contacts/add',data={'email':carol.email})
    b.post(f'/chat/api/contacts/{carol.id}/block',data={'blocked':'1'})
    assert make_group(a,'Blocked',bob,carol).status_code==403
    b.post(f'/chat/api/contacts/{carol.id}/block',data={'blocked':'0'})
    thread=make_group(a,'Survives deletion',bob,carol).json['id']
    message=a.post(f'/chat/api/threads/{thread}/send',data={'body':'Owner message','client_id':'deleted_owner_msg'}).json['message']['id']
    b.post(f'/chat/api/contacts/{carol.id}/block',data={'blocked':'1'})
    assert b.post(f'/chat/api/threads/{thread}/send',data={'body':'Blocked bypass','client_id':'blocked_group_no'}).status_code==403
    assert c.post(f'/chat/api/threads/{thread}/send',data={'body':'Blocked bypass','client_id':'blocked_group_no'}).status_code==403
    b.post(f'/chat/api/contacts/{carol.id}/block',data={'blocked':'0'})
    db.session.delete(alice);db.session.commit()
    info=b.get(f'/chat/api/threads/{thread}/group').json
    assert info['owner'] and len(info['members'])==2
    assert b.get(f'/chat/api/threads/{thread}').json['messages'][0]['sender_name']=='Thành viên đã xóa'
    assert db.session.get(ChatThread,thread) is not None


def test_group_thread_schema_upgrade_keeps_direct_history_and_files(tmp_path):
    import sqlite3
    database=tmp_path/'legacy-chat.db'
    config={'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+database.as_posix(),'SECRET_KEY':'migration','WTF_CSRF_ENABLED':False}
    app=create_app(config)
    with app.app_context():
        a,alice=user(app,'alice');b,bob=user(app,'bob')
        a.post('/chat/api/contacts/add',data={'email':bob.email})
        thread=a.post('/chat/api/threads',data={'user_id':bob.id}).json['id']
        message=ChatMessage(thread_id=thread,sender_id=alice.id,body='History survives',client_id='migration_message')
        message.attachment=ChatAttachment(filename='old.txt',mimetype='text/plain',size=4,data=b'file')
        db.session.add(message);db.session.commit();message_id=message.id
        db.session.remove();db.engine.dispose()
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE old_threads (id INTEGER PRIMARY KEY,low_id INTEGER NOT NULL,high_id INTEGER NOT NULL,low_read INTEGER NOT NULL,high_read INTEGER NOT NULL,low_typing DATETIME,high_typing DATETIME,updated_at DATETIME NOT NULL,UNIQUE(low_id,high_id),CHECK(low_id<high_id))')
        connection.execute('INSERT INTO old_threads SELECT * FROM chat_threads')
        connection.execute('DROP TABLE chat_threads')
        connection.execute('ALTER TABLE old_threads RENAME TO chat_threads')
    upgraded=create_app(config)
    with upgraded.app_context():
        row=db.session.get(ChatMessage,message_id)
        assert row.body=='History survives' and row.attachment.data==b'file' and row.thread.id==thread
        first=ChatThread(group=ChatGroup(name='Group 1'))
        second=ChatThread(group=ChatGroup(name='Group 2'))
        db.session.add_all([first,second]);db.session.commit()
        assert first.id!=second.id and db.session.get(ChatThread,thread).low_id is not None
        db.session.remove();db.engine.dispose()
    assert list(tmp_path.glob('schema-backup-groups-*.db'))


def test_deleted_group_sender_cannot_become_a_reused_account(chat_app):
    a,alice=user(chat_app,'alice');b,bob=user(chat_app,'bob');owner,old_owner=user(chat_app,'oldowner')
    thread=make_group(owner,'Keep history',alice,bob).json['id']
    original=owner.post(f'/chat/api/threads/{thread}/send',data={'body':'Original author','client_id':'old_owner_unique'}).json['message']['id']
    old_id=old_owner.id;db.session.delete(old_owner);db.session.commit()
    newcomer,new_user=user(chat_app,'newowner')
    assert new_user.id==old_id
    assert a.get(f'/chat/api/threads/{thread}').json['messages'][0]['sender_name']=='Thành viên đã xóa'
    assert db.session.get(ChatMessage,original).sender_id<0
    assert newcomer.get(f'/chat/api/threads/{thread}').status_code==404
