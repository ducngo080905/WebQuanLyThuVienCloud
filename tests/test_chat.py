import pytest
from app import create_app, db
from app.models import User, Member, ChatMessage, ChatThread

@pytest.fixture
def chat_app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'SECRET_KEY': 'chat-test', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


def user(app, label, role='reader'):
    member = Member(name=label, email=label+'@example.com', member_id=label, phone='0901234567')
    account = User(member=member, email=member.email, role=role)
    account.set_password('password123')
    db.session.add(account); db.session.commit()
    client = app.test_client()
    client.post('/login', data={'email': account.email, 'password': 'password123'})
    return client, account


def start_chat(client, peer):
    client.post('/chat/api/contacts/add', data={'email':peer.email})
    return client.post('/chat/api/threads', data={'user_id':peer.id})


def send(client, thread, body='Hello', nonce='0123456789abcdef'):
    return client.post(f'/chat/api/threads/{thread}/send', data={'body': body, 'client_id': nonce})


def test_chat_private_delivery_read_and_duplicate_send(chat_app):
    a, alice = user(chat_app, 'alice')
    b, bob = user(chat_app, 'bob', 'admin')
    c, carol = user(chat_app, 'carol')
    thread = start_chat(a, bob).json['id']
    assert start_chat(b, alice).json['id'] == thread
    assert ChatThread.query.count() == 1
    message = send(a, thread, '<script>hello</script>\nSecond line').json['message']
    assert send(a, thread).json['message']['id'] == message['id']
    assert ChatMessage.query.count() == 1
    assert b.get('/chat/api/overview').json['threads'][0]['unread'] == 1
    assert b.get('/chat/api/unread').json['unread'] == 1
    assert b.get(f'/chat/api/threads/{thread}').json['messages'][0]['body'] == '<script>hello</script>\nSecond line'
    assert c.get(f'/chat/api/threads/{thread}').status_code == 404
    assert send(c, thread).status_code == 404
    assert c.post(f'/chat/api/threads/{thread}/read', data={'message_id':message['id']}).status_code == 404
    assert c.post(f'/chat/api/threads/{thread}/typing', data={'typing':'1'}).status_code == 404
    assert b.post(f'/chat/api/threads/{thread}/read', data={'message_id':message['id']}).json['ok']
    assert b.get('/chat/api/unread').json['unread'] == 0
    assert a.get(f'/chat/api/threads/{thread}').json['peer_read'] == message['id']
    reply = send(a, thread, 'Next', 'next_message_nonce').json['message']['id']
    b.post(f'/chat/api/threads/{thread}/read', data={'message_id':reply})
    b.post(f'/chat/api/threads/{thread}/read', data={'message_id':message['id']})
    assert a.get(f'/chat/api/threads/{thread}').json['peer_read'] == reply
    assert b.post(f'/chat/api/threads/{thread}/typing', data={'typing':'1'}).json['ok']
    assert a.get(f'/chat/api/threads/{thread}').json['typing']
    overview = a.get('/chat/api/overview').json
    assert 'email' not in overview['contacts'][0] and 'phone' not in overview['contacts'][0]
    assert 'messenger.js' in a.get('/messenger').text
    assert 'messenger.css' in a.get('/messenger').text


def test_chat_validation_pagination_and_deletion(chat_app):
    a, alice = user(chat_app, 'alice')
    b, bob = user(chat_app, 'bob')
    c, carol = user(chat_app, 'carol')
    assert start_chat(a, alice).status_code == 400
    assert a.post('/chat/api/threads', data={'user_id': 999999}).status_code == 403
    thread = start_chat(a, bob).json['id']
    other = start_chat(a, carol).json['id']
    assert send(a, thread, '').status_code == 400
    assert send(a, thread, 'a'*4001).status_code == 400
    for index in range(55):
        assert send(a, thread, str(index), f'{index:016d}').status_code == 200
    latest = b.get(f'/chat/api/threads/{thread}').json
    assert len(latest['messages']) == 50 and latest['has_older']
    oldest = latest['messages'][0]['id']
    earlier = b.get(f'/chat/api/threads/{thread}?before={oldest}').json
    assert len(earlier['messages']) == 5 and not earlier['has_older']
    last = latest['messages'][-1]['id']
    assert not b.get(f'/chat/api/threads/{thread}?after={last}').json['messages']
    assert send(a, other, nonce=f'{0:016d}').status_code == 409
    assert b.post(f'/chat/api/threads/{other}/read',data={'message_id':last}).status_code == 404
    own_other = send(c, other, nonce='other_thread_nonce').json['message']['id']
    assert a.post(f'/chat/api/threads/{thread}/read',data={'message_id':own_other}).status_code == 400
    for index in range(55, 60):
        assert send(a, thread, str(index), f'{index:016d}').status_code == 200
    assert send(a, thread, 'Too fast', 'rate_limit_nonce').status_code == 429
    bob.active = False; db.session.commit()
    assert send(a, thread, nonce='inactive_peer_nonce').status_code == 400
    assert start_chat(a, bob).status_code == 400
    db.session.delete(bob); db.session.commit()
    assert db.session.get(ChatThread,thread) is None
    assert ChatMessage.query.filter_by(thread_id=thread).count() == 0
    assert db.session.get(ChatThread,other) is not None


def test_chat_csrf_and_login_required(chat_app):
    guest = chat_app.test_client()
    assert guest.get('/messenger').status_code == 302
    assert guest.get('/chat/api/overview').status_code == 401
    a, alice = user(chat_app, 'alice')
    b, bob = user(chat_app, 'bob')
    chat_app.config['WTF_CSRF_ENABLED'] = True
    assert start_chat(a, bob).status_code == 303
    assert ChatThread.query.count() == 0
    a.get('/messenger')
    with a.session_transaction() as sess: token = sess['csrf_token']
    assert a.post('/chat/api/contacts/add',data={'email':bob.email,'csrf_token':token}).status_code == 200
    assert a.post('/chat/api/threads',data={'user_id':bob.id,'csrf_token':token}).status_code == 200


def test_chat_replies_reactions_edits_recall_sync_and_search(chat_app):
    from datetime import datetime, timedelta
    a, alice = user(chat_app, 'alice')
    b, bob = user(chat_app, 'bob')
    c, carol = user(chat_app, 'carol')
    thread = start_chat(a, bob).json['id']
    other = start_chat(c, alice).json['id']
    original = send(a, thread, 'Library meeting', 'original_message').json['message']['id']
    foreign = send(c, other, 'Private', 'private_message_nonce').json['message']['id']
    assert b.post(f'/chat/api/threads/{thread}/send', data={'body':'wrong reply','client_id':'bad_reply_nonce1','reply_id':foreign}).status_code == 400
    reply = b.post(f'/chat/api/threads/{thread}/send', data={'body':'Okay','client_id':'valid_reply_nonce','reply_id':original}).json['message']
    assert reply['reply']['body'] == 'Library meeting'
    assert b.post(f'/chat/api/messages/{original}/edit', data={'body':'Changed'}).status_code == 403
    assert b.post(f'/chat/api/messages/{original}/recall', data={}).status_code == 403
    assert c.post(f'/chat/api/messages/{original}/react', data={'emoji':'👍'}).status_code == 404
    edited = a.post(f'/chat/api/messages/{original}/edit', data={'body':'Library update'}).json['message']
    assert edited['edited_at'] and edited['body'] == 'Library update'
    assert b.get(f'/chat/api/threads/{thread}/search?q=update').json['messages'][0]['id'] == original
    assert c.get(f'/chat/api/threads/{thread}/search?q=update').status_code == 404
    assert c.get(f'/chat/api/threads/{thread}?around={original}').status_code == 404
    assert a.get(f'/chat/api/threads/{thread}?around={foreign}').status_code == 404
    assert a.post(f'/chat/api/messages/{original}/react',data={'emoji':'invalid'}).status_code == 400
    for client in (a,b):
        assert client.post(f'/chat/api/messages/{original}/react',data={'emoji':'❤️'}).status_code == 200
    data = b.get(f'/chat/api/threads/{thread}').json
    item = next(row for row in data['messages'] if row['id']==original)
    assert item['reactions'] == [{'emoji':'❤️','count':2,'mine':True}]
    assert next(row for row in data['messages'] if row['id']==reply['id'])['reply']['body'] == 'Library update'
    cursor = data['changes']
    a.post(f'/chat/api/messages/{original}/react',data={'emoji':''})
    updates = b.get(f'/chat/api/threads/{thread}?after={reply["id"]}&changes={cursor}').json
    assert updates['messages'] == [] and updates['updates'][0]['reactions'][0]['count']==1
    recalled = a.post(f'/chat/api/messages/{original}/recall', data={}).json['message']
    assert recalled['deleted'] and recalled['body']=='' and recalled['reactions']==[]
    assert not b.get(f'/chat/api/threads/{thread}/search?q=update').json['messages']
    quoted = next(row for row in b.get(f'/chat/api/threads/{thread}').json['messages'] if row['id']==reply['id'])['reply']
    assert quoted['deleted'] and quoted['body']=='Tin nhắn đã thu hồi'
    assert a.post(f'/chat/api/messages/{original}/edit', data={'body':'No'}).status_code == 400
    assert b.post(f'/chat/api/messages/{original}/react', data={'emoji':'👍'}).status_code == 400
    old = db.session.get(ChatMessage,reply['id']); old.created_at=datetime.utcnow()-timedelta(minutes=16);db.session.commit()
    assert b.post(f'/chat/api/messages/{old.id}/edit',data={'body':'Too late'}).status_code==400


def test_chat_private_attachments_validation_and_recall(chat_app):
    from io import BytesIO
    from PIL import Image
    from app.models import ChatAttachment
    a, alice = user(chat_app, 'alice')
    b, bob = user(chat_app, 'bob')
    c, carol = user(chat_app, 'carol')
    thread = start_chat(a, bob).json['id']
    def upload(data, name, nonce):
        return a.post(f'/chat/api/threads/{thread}/send',data={'client_id':nonce,'attachment':(BytesIO(data),name)})
    assert upload(b'<html>hello</html>', 'page.html','bad_html_nonce111').status_code==400
    assert upload(b'not a picture', 'book.png','bad_image_nonce11').status_code==400
    assert upload(b'not a PDF', 'book.pdf','bad_pdf_nonce1111').status_code==400
    assert upload(b'\xff\x00', 'text.txt','bad_text_nonce111').status_code==400
    assert upload(b'a'*(10*1024*1024+1),'large.txt','large_file_nonce1').status_code==400
    pdf=upload(b'%PDF-1.4\n%%EOF', '../../document.pdf','valid_pdf_nonce1').json['message']
    assert pdf['attachment']['filename']=='document.pdf' and not pdf['attachment']['image']
    file_url=pdf['attachment']['url']
    response=b.get(file_url)
    assert response.status_code==200 and 'attachment' in response.headers['Content-Disposition']
    assert response.headers['Cache-Control']=='no-store'
    assert c.get(file_url).status_code==404
    image=BytesIO();Image.new('RGB',(20,20),'red').save(image,format='PNG')
    picture=upload(image.getvalue(),'ảnh.png','valid_image_nonce').json['message']
    assert picture['attachment']['image'] and b.get(picture['attachment']['url']).mimetype=='image/jpeg'
    a.post(f'/chat/api/messages/{pdf["id"]}/recall',data={})
    assert b.get(file_url).status_code==404
    assert db.session.get(ChatAttachment,pdf['id']) is None
    assert b.get(picture['attachment']['url']).status_code==200


def test_chat_additive_upgrade_preserves_old_messages(tmp_path):
    import sqlite3
    database=tmp_path/'old-chat.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL, sender_id INTEGER NOT NULL, body TEXT NOT NULL, client_id VARCHAR(64) NOT NULL, created_at DATETIME NOT NULL)')
        connection.execute("INSERT INTO chat_messages VALUES(1,1,1,'Existing history','existing_nonce11','2026-11-06 10:00:00')")
    app=create_app({'TESTING':True,'SECRET_KEY':'test','SQLALCHEMY_DATABASE_URI':'sqlite:///'+database.as_posix()})
    with app.app_context():
        row=db.session.get(ChatMessage,1)
        assert row.body=='Existing history' and row.reply_id is None and row.deleted_at is None
        db.session.remove();db.engine.dispose()
    assert list(tmp_path.glob('schema-backup-*.db'))


def test_chat_email_contacts_and_admin_directory_privacy(chat_app):
    a, alice = user(chat_app, 'alice')
    b, bob = user(chat_app, 'bob')
    staff, librarian = user(chat_app, 'staff', 'librarian')
    admin, owner = user(chat_app, 'admin', 'admin')
    assert a.get('/chat/api/overview').json['contacts'] == []
    assert staff.get('/chat/api/overview').json['contacts'] == []
    directory = admin.get('/chat/api/overview').json['contacts']
    assert {p['id'] for p in directory} == {alice.id,bob.id,librarian.id}
    assert a.post('/chat/api/threads',data={'user_id':bob.id}).status_code == 403
    assert a.post('/chat/api/contacts/add',data={'email':'bob'}).status_code == 400
    missing = a.post('/chat/api/contacts/add',data={'email':'notregistered@example.com'})
    assert missing.status_code==404 and 'chưa đăng ký' in missing.json['error']
    assert a.post('/chat/api/contacts/add',data={'email':'BOB@EXAMPLE.COM'}).json['peer']['id']==bob.id
    assert [p['id'] for p in a.get('/chat/api/overview').json['contacts']]==[bob.id]
    assert [p['id'] for p in b.get('/chat/api/overview').json['contacts']]==[alice.id]
    assert a.post('/chat/api/threads',data={'user_id':bob.id}).status_code==200
    thread=admin.post('/chat/api/threads',data={'user_id':librarian.id}).json['id']
    assert send(staff,thread,nonce='reply_to_admin_nonce').status_code==200


def test_chat_blocking_is_enforced_both_directions(chat_app):
    a, alice=user(chat_app,'alice')
    b, bob=user(chat_app,'bob','admin')
    c, carol=user(chat_app,'carol')
    thread=start_chat(a,bob).json['id']
    message=send(a,thread,nonce='before_block_nonce').json['message']['id']
    assert c.post(f'/chat/api/contacts/{alice.id}/block',data={'blocked':'1'}).status_code==404
    assert a.post(f'/chat/api/contacts/{bob.id}/block',data={'blocked':'1'}).json['ok']
    for client in (a,b):
        assert send(client,thread,nonce='blocked_send_nonce').status_code==403
        assert client.post(f'/chat/api/threads/{thread}/typing',data={'typing':'1'}).status_code==403
        assert client.post(f'/chat/api/messages/{message}/react',data={'emoji':'👍'}).status_code==403
    assert a.post(f'/chat/api/messages/{message}/edit',data={'body':'bypass block'}).status_code==403
    assert b.post('/chat/api/threads',data={'user_id':alice.id}).status_code==403
    assert b.post('/chat/api/contacts/add',data={'email':alice.email}).status_code==403
    assert a.get('/chat/api/overview').json['blocked'][0]['id']==bob.id
    peer=b.get(f'/chat/api/threads/{thread}').json['peer']
    assert not peer['can_send'] and not peer['online']
    assert a.post(f'/chat/api/contacts/{bob.id}/block',data={'blocked':'0'}).json['ok']
    assert send(b,thread,nonce='after_unblock_nonce').status_code==200


def test_chat_removing_contact_clears_only_own_history(chat_app):
    from io import BytesIO
    a, alice=user(chat_app,'alice')
    b, bob=user(chat_app,'bob')
    thread=start_chat(a,bob).json['id']
    message=b.post(f'/chat/api/threads/{thread}/send',data={'body':'Old private text','client_id':'old_file_message','attachment':(BytesIO(b'old content'),'history.txt')}).json['message']
    assert a.get('/chat/api/unread').json['unread']==1
    assert a.post(f'/chat/api/threads/{thread}/remove-contact',data={}).json['ok']
    assert a.get('/chat/api/overview').json['threads']==[]
    assert a.get('/chat/api/overview').json['contacts']==[]
    assert a.get('/chat/api/unread').json['unread']==0
    assert a.get(f'/chat/api/threads/{thread}').json['messages']==[]
    assert not a.get(f'/chat/api/threads/{thread}/search?q=Old').json['messages']
    assert a.get(message['attachment']['url']).status_code==404
    assert b.get(message['attachment']['url']).status_code==200
    assert b.get(f'/chat/api/threads/{thread}').json['messages'][0]['body']=='Old private text'
    assert send(a,thread,nonce='removed_sender_nonce').status_code==403
    assert send(b,thread,nonce='removed_peer_nonce1').status_code==403
    assert a.post('/chat/api/threads',data={'user_id':bob.id}).status_code==403
    assert db.session.get(User,bob.id) is not None
    a.post('/chat/api/contacts/add',data={'email':bob.email})
    restored=a.post('/chat/api/threads',data={'user_id':bob.id}).json['id']
    assert restored==thread and not a.get(f'/chat/api/threads/{thread}').json['messages']
    assert send(b,thread,'New message','new_after_add_nonce').status_code==200
    assert len(a.get(f'/chat/api/threads/{thread}').json['messages'])==1


def test_user_avatar_upload_visibility_and_delete(chat_app):
    from io import BytesIO
    from PIL import Image
    from app.models import UserAvatar
    a, alice=user(chat_app,'alice')
    b, bob=user(chat_app,'bob')
    admin, owner=user(chat_app,'admin','admin')
    picture=BytesIO();Image.new('RGB',(40,60),'green').save(picture,format='PNG')
    assert a.post('/profile/avatar',data={'avatar':(BytesIO(b'bad'),'bad.png')}).status_code==302
    assert db.session.get(UserAvatar,alice.id) is None
    assert a.post('/profile/avatar',data={'avatar':(BytesIO(picture.getvalue()),'me.png')}).status_code==302
    avatar=db.session.get(UserAvatar,alice.id)
    assert avatar is not None
    url=f'/chat/api/avatars/{alice.id}'
    response=a.get(url)
    assert response.status_code==200 and response.mimetype=='image/jpeg'
    with Image.open(BytesIO(response.data)) as image: assert image.size==(256,256)
    assert b.get(url).status_code==404 and admin.get(url).status_code==200
    a.post('/chat/api/contacts/add',data={'email':bob.email})
    assert b.get(url).status_code==200
    assert b.get('/chat/api/overview').json['contacts'][0]['avatar']
    assert 'profileAvatar' in a.get('/profile').text
    a.post('/profile/avatar',data={'remove':'1'})
    assert a.get(url).status_code==404


def test_floating_chat_role_visibility_and_clean_embed(chat_app):
    reader, account = user(chat_app, 'reader')
    staff, _ = user(chat_app, 'staff', 'librarian')
    admin, _ = user(chat_app, 'admin', 'admin')
    for client in (reader, staff):
        page = client.get('/profile').text
        assert 'id="chatWidgetLauncher"' in page and 'chat_widget.css' in page
        assert '<iframe id="chatWidgetFrame"' in page and 'data-src="/messenger?embed=1"' in page
        assert '<iframe id="chatWidgetFrame" title="Trò chuyện thư viện" allow="camera' in page
    assert 'id="chatWidgetLauncher"' not in admin.get('/admin').text
    assert 'id="chatWidgetLauncher"' not in chat_app.test_client().get('/').text
    assert 'id="chatWidgetLauncher"' not in reader.get('/messenger').text
    with reader.session_transaction() as sess: sess['_flashes'] = [('success', 'Preserve parent notification')]
    frame = reader.get('/messenger?embed=1')
    assert frame.status_code == 200 and 'chat-embed' in frame.text
    assert 'messenger_embed.css' in frame.text and 'id="messenger"' in frame.text
    assert 'reader-header' not in frame.text and 'class="sidebar"' not in frame.text
    assert 'id="chatWidgetLauncher"' not in frame.text and 'live_updates.js' not in frame.text
    assert 'presence.js' not in frame.text and 'Preserve parent notification' not in frame.text
    assert 'Preserve parent notification' in reader.get('/profile').text
    assert chat_app.test_client().get('/messenger?embed=1').status_code == 302
