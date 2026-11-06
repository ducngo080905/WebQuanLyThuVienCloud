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
    assert client.post(f'/borrow/request/{book.id}').status_code==302
    # Admin clearing the phone is detected on the next poll, no page reload needed.
    user.member.phone='';db.session.commit()
    assert client.get('/live-updates').json['phone_required']


def test_announcements_targeting_permissions_and_read(live_app):
    admin,_=account(live_app,'admin@example.com','admin','0901234567')
    reader,user=account(live_app,'reader@example.com',phone='0901234567')
    other,_=account(live_app,'other@example.com',phone='0901234567')
    staff,_=account(live_app,'staff@example.com','librarian','0901234567')
    assert reader.get('/admin/announcements').status_code==403
    assert staff.post('/admin/announcements',data={}).status_code==403
    admin.post('/admin/announcements',data={'title':'Hello <script>','body':'Notice content','audience':'one','target_id':user.id})
    item=Announcement.query.one()
    assert len(reader.get('/live-updates').json['announcements'])==1
    assert not other.get('/live-updates').json['announcements']
    assert other.post(f'/announcements/{item.id}/read').status_code==404
    assert reader.post(f'/announcements/{item.id}/read').json['ok']
    assert not reader.get('/live-updates').json['announcements']
    assert 'Hello &lt;script&gt;' in reader.get('/inbox').text
    admin.post('/admin/announcements',data={'title':'Readers','body':'All readers','audience':'reader'})
    assert len(reader.get('/live-updates').json['announcements'])==1
    assert not staff.get('/live-updates').json['announcements']


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
    admin.post('/admin/announcements',data={'title':'Public notice','body':'Content','audience':'all'})
    item=Announcement.query.one()
    assert AnnouncementReceipt.query.filter_by(announcement_id=item.id,user_id=owner.id).first() is None
    assert admin.get('/live-updates').json=={'phone_required':False,'google_link_required':True,'announcements':[]}
    assert len(reader.get('/live-updates').json['announcements'])==1
    assert b'announcementToast' in reader.get('/').data
    assert b'announcementOverlay' not in reader.get('/').data
