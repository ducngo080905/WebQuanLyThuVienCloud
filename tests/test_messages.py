import pytest
from app import create_app,db
from app.models import User,Member,Announcement,AnnouncementReceipt,Book

@pytest.fixture
def live_app():
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:',
                    'SECRET_KEY':'live-tests','WTF_CSRF_ENABLED':False})
    with app.app_context():
        yield app
        db.session.remove();db.drop_all()


def account(app,email,role='reader',phone=''):
    member=Member(name=role,email=email,member_id=email,phone=phone)
    user=User(email=email,role=role,member=member);user.set_password('password123')
    db.session.add(user);db.session.commit()
    client=app.test_client();client.post('/login',data={'email':email,'password':'password123'})
    return client,user


def test_required_phone_detected_live_and_validated(live_app):
    client,user=account(live_app,'reader@example.com')
    assert client.get('/live-updates').json['phone_required']
    assert 'live_updates.js' in client.get('/').text
    book=Book(title='Book',author='A',isbn='PHONE',quantity=1,available=1);db.session.add(book);db.session.commit()
    assert client.post(f'/borrow/request/{book.id}').status_code==428
    assert client.post('/profile/required-phone',data={'phone':'abc'}).status_code==400
    assert client.post('/profile/required-phone',data={'phone':'090 123 4567'}).json['ok']
    assert user.member.phone=='0901234567'
    assert not client.get('/live-updates').json['phone_required']
    assert client.post(f'/borrow/request/{book.id}').status_code==303
    # Admin clearing the phone is detected on the next poll, no page reload needed.
    user.member.phone='';db.session.commit()
    assert client.get('/live-updates').json['phone_required']


def test_announcement_publish_edit_expire_and_delete(live_app):
    admin,_=account(live_app,'admin@example.com','admin','0901234567')
    reader,_=account(live_app,'reader@example.com',phone='0901234567')
    url='/admin/announcements'
    assert reader.get(url).status_code==403
    assert reader.post(url,data={'body':'Denied','color':'#123456'}).status_code==403
    assert admin.post(url,data={'body':'Hello <script>','color':'#123456'}).status_code==303
    item_id=Announcement.query.one().id
    assert reader.get('/live-updates').json['announcements'][0]['color']=='#123456'
    edit_page=admin.get(f'{url}?edit={item_id}')
    assert edit_page.status_code==200
    compose, editor = edit_page.text.split('<dialog id="noticeEdit"', 1)
    assert 'Hello &lt;script&gt;' not in compose
    assert 'Hello &lt;script&gt;' in editor
    admin.post(url,data={'edit':item_id,'body':'Edited','color':'#654321','expiry_date':'2000-01-01','expiry_time':'07:00'})
    assert not reader.get('/live-updates').json['announcements']
    assert 'Đã tự tắt' in admin.get(url).text
    admin.post(url,data={'edit':item_id,'body':'Edited','color':'#654321'})
    notice=reader.get('/live-updates').json['announcements'][0]
    assert notice['body']=='Edited' and notice['color']=='#654321'
    endpoint=f'{url}/{item_id}/delete'
    assert reader.post(endpoint).status_code==403
    assert admin.post(endpoint).status_code==303
    assert not reader.get('/live-updates').json['announcements']


def test_live_csrf_and_anonymous_access(live_app):
    guest=live_app.test_client()
    assert guest.get('/live-updates').status_code==302
    client,user=account(live_app,'reader@example.com')
    live_app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/profile/required-phone',data={'phone':'0901234567'}).status_code==303
    assert user.member.phone==''
    client.get('/')
    with client.session_transaction() as sess: csrf=sess['csrf_token']
    assert client.post('/profile/required-phone',data={'phone':'0901234567','csrf_token':csrf}).json['ok']

def test_admin_does_not_receive_live_notifications_or_phone_prompt(live_app):
    admin,owner=account(live_app,'admin@example.com','admin')
    reader,user=account(live_app,'reader@example.com',phone='0901234567')
    admin.post('/admin/announcements',data={'body':'Content','color':'#123456'})
    item=Announcement.query.one()
    assert AnnouncementReceipt.query.filter_by(announcement_id=item.id,user_id=owner.id).first() is None
    assert admin.get('/live-updates').json=={'phone_required':False,'google_link_required':True,'announcements':[]}
    assert len(reader.get('/live-updates').json['announcements'])==1
    assert b'noticeTicker' in reader.get('/').data
    assert b'announcementOverlay' not in reader.get('/').data


def test_read_all_is_private_and_csrf_protected(live_app):
    reader,user=account(live_app,'bulk@example.com',phone='0901234567')
    other,peer=account(live_app,'bulk-other@example.com',phone='0901234567')
    item=Announcement(title='Announcement',body='Body',audience='all',sender_id=user.id)
    db.session.add(item);db.session.flush()
    db.session.add_all([AnnouncementReceipt(announcement_id=item.id,user_id=user.id),AnnouncementReceipt(announcement_id=item.id,user_id=peer.id)])
    db.session.commit()
    live_app.config['WTF_CSRF_ENABLED']=True
    assert reader.post('/inbox/read-all').status_code==303
    assert db.session.get(AnnouncementReceipt,(item.id,user.id)).read_at is None
    reader.get('/')
    with reader.session_transaction() as session: token=session['csrf_token']
    assert reader.post('/inbox/read-all',data={'csrf_token':token}).json['ok']
    db.session.expire_all()
    assert db.session.get(AnnouncementReceipt,(item.id,user.id)).read_at is not None
    assert db.session.get(AnnouncementReceipt,(item.id,peer.id)).read_at is None
    assert live_app.test_client().post('/inbox/read-all').status_code==303


def test_reader_navigation_and_ticker(live_app):
    guest=live_app.test_client()
    page=guest.get('/catalog').text
    assert 'Menu đăng nhập' in page and 'reader-account-menu' in page
    reader,user=account(live_app,'nav@example.com',phone='0901234567')
    page=reader.get('/').text
    assert 'Menu tài khoản' in page and 'reader_navigation.js' in page
    nav=page.split('<nav class="reader-nav"',1)[1].split('</nav>',1)[0]
    assert 'Sách của tôi' not in nav and 'Tin từ quản trị' not in nav and 'Thông báo' not in nav and 'Hồ sơ' not in nav
    menu=page.split('class="reader-account-menu"',1)[1].split('</details>',1)[0]
    assert '/my-books' in menu and '/profile' in menu and 'method="post"' in menu and 'csrf_token' in menu
    assert '/notifications' not in menu
    assert page.index('id="noticeTicker"') < page.index('class="reader-header reader-navbar"')
    for path in ('/notifications?tab=loans', '/inbox'):
        response=reader.get(path)
        assert response.status_code==302 and response.location=='/'
