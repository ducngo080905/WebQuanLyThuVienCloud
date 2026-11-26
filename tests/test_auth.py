import pytest
from app import create_app, db
from app.models import User, Member, Book, Issue
from datetime import datetime

@pytest.fixture
def auth_app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                      'SECRET_KEY': 'test-auth', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


def legacy_account(client, email='reader@example.com', **extra):
    """Seed a pre-Google password account to retain migration/legacy coverage."""
    from app.auth import create_account
    from sqlalchemy.exc import IntegrityError
    try:
        create_account(extra.get('name','Reader'),email.lower(),'secret123',extra.get('phone','0901234567'))
    except (ValueError,IntegrityError):
        db.session.rollback()
    return client.post('/login',data={'email':email,'password':'secret123'},follow_redirects=True)



def test_legacy_reader_login_logout_permissions(auth_app):
    c = auth_app.test_client()
    assert c.get('/members').status_code == 302
    assert c.get('/api/members').status_code == 401
    assert legacy_account(c).status_code == 200
    user = User.query.one()
    assert user.role == 'reader' and user.password_hash != 'secret123'
    assert c.get('/books').headers['Location'].endswith('/catalog')
    assert c.get('/catalog').status_code == 200
    assert c.get('/admin').status_code == 403
    assert c.get('/profile').status_code == 200
    for path in ['/members', '/issues', '/accounts', '/api/members', '/api/issues']:
        assert c.get(path).status_code == 403
    assert c.post('/books/add', data={}).status_code == 403
    c.post('/logout')
    assert c.get('/my-books').status_code == 302
    response = c.post('/login', data={'email':user.email,'password':'secret123'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')
    assert c.get('/my-books').status_code == 200


def test_reader_only_sees_own_loans(auth_app):
    c = auth_app.test_client()
    legacy_account(c)
    user = User.query.one()
    other = Member(name='Other', email='other@example.com', member_id='OTHER')
    book1 = Book(title='Private Other Book', author='A', isbn='1', quantity=1, available=0)
    book2 = Book(title='Own Book', author='A', isbn='2', quantity=1, available=0)
    db.session.add_all([other, book1, book2]); db.session.flush()
    db.session.add_all([Issue(member_id=other.id, book_id=book1.id, due_date=datetime(2020,1,1)),
                        Issue(member_id=user.member_id, book_id=book2.id, due_date=datetime(2020,1,1))])
    db.session.commit()
    page = c.get('/my-books').data
    assert b'Own Book' in page and b'Private Other Book' not in page
    assert 'Quá hạn'.encode() in page


def test_setup_admin_accounts_and_lock(auth_app):
    c = auth_app.test_client()
    assert c.get('/setup').status_code == 403
    data = dict(token=auth_app.config['SETUP_TOKEN'], name='Admin', email='admin@example.com',
                password='secret123', confirm_password='secret123')
    assert c.post('/setup', data=data).status_code == 302
    assert c.get('/setup', query_string={'token':data['token']}).status_code == 404
    admin = User.query.one()
    c.post('/accounts', data={'user_id':admin.id, 'role':'reader', 'active':'0'})
    assert admin.role == 'admin' and admin.active
    c.post('/accounts', data={'action':'create','name':'Staff','email':'staff@example.com',
                              'password':'secret123','role':'librarian'})
    staff = User.query.filter_by(role='librarian').one()
    staff_client = auth_app.test_client()
    staff_client.post('/login', data={'email':staff.email,'password':'secret123'})
    assert staff_client.get('/members').status_code == 302
    assert staff_client.get('/accounts').status_code == 403
    c.post('/accounts', data={'user_id':staff.id,'role':'librarian','active':'0'})
    assert staff_client.get('/members').status_code == 302


def test_duplicate_email_and_profile_password(auth_app):
    c=auth_app.test_client();legacy_account(c)
    user=User.query.one()
    c.post('/profile',data={'name':'New Name','phone':'123','password':'newsecret',
                           'confirm_password':'newsecret','current_password':'wrong'})
    assert user.check_password('secret123')
    c.post('/profile',data={'name':'New Name','phone':'123','password':'newsecret',
                           'confirm_password':'newsecret','current_password':'secret123'})
    assert user.check_password('newsecret') and user.member.name=='New Name'
    c.post('/logout');legacy_account(c,email='READER@example.com')
    assert User.query.count()==1


def test_csrf_enforced(auth_app,monkeypatch):
    auth_app.config['WTF_CSRF_ENABLED']=True
    c=auth_app.test_client()
    assert c.post('/register',data={}).status_code==303
    assert User.query.count() == 0
    c.get('/register')
    with c.session_transaction() as session:
        token=session['csrf_token']
    with c.session_transaction() as sess: nonce=sess['google_nonce']
    monkeypatch.setattr('app.google_login.verify_credential',lambda token,audience:dict(sub='csrf-google',email='csrf@gmail.com',email_verified=True,nonce=nonce))
    response=c.post('/register',data={'name':'Reader','email':'csrf@gmail.com','google_credential':'verified-token','password':'secret123',
                                    'confirm_password':'secret123','csrf_token':token})
    assert response.status_code==302
    assert c.post('/logout',data={'csrf_token':'wrong'}).status_code==303
    assert c.get('/my-books').status_code == 200


def test_stale_login_tab_after_registration(auth_app,monkeypatch):
    auth_app.config['WTF_CSRF_ENABLED'] = True
    c = auth_app.test_client()
    c.get('/login')
    with c.session_transaction() as sess:
        old_token = sess['csrf_token']
        nonce = sess['google_nonce']
    monkeypatch.setattr('app.google_login.verify_credential',lambda token,audience:dict(sub='tabs-google',email='tabs@gmail.com',email_verified=True,nonce=nonce))
    response = c.post('/register', data={'name':'Reader','email':'tabs@gmail.com','google_credential':'verified-token',
                        'password':'secret123','confirm_password':'secret123','csrf_token':old_token})
    assert response.headers['Location'].endswith('/')
    response = c.post('/login', data={'email':'tabs@gmail.com','password':'secret123','csrf_token':old_token})
    assert response.status_code == 303 and response.headers['Location'].endswith('/')
    assert c.get('/admin').status_code == 403
    assert c.get('/').status_code == 200


def test_admin_landing_and_guest_catalog(auth_app):
    c = auth_app.test_client()
    assert c.get('/').status_code == 200
    assert c.get('/catalog').status_code == 200
    c.post('/setup', data={'token':auth_app.config['SETUP_TOKEN'],'name':'Admin',
             'email':'admin@example.com','password':'secret123','confirm_password':'secret123'})
    c.post('/logout')
    response = c.post('/login', data={'email':'admin@example.com','password':'secret123'})
    assert response.headers['Location'].endswith('/admin')
    page = c.get('/admin')
    assert page.status_code == 200
    title = page.data.decode().split('<title>')[1].split('</title>')[0]
    assert '<div' not in title

def test_reader_request_approval_stock_and_return(auth_app):
    from app.models import BorrowRequest
    c=auth_app.test_client();legacy_account(c)
    reader=User.query.one()
    book=Book(title='Request Book',author='Author',isbn='REQ-1',quantity=1,available=1)
    staff_member=Member(name='Staff',email='staff@example.com',member_id='STAFF')
    db.session.add_all([book,staff_member]);db.session.flush()
    staff=User(email=staff_member.email,role='librarian',member_id=staff_member.id)
    staff.set_password('secret123');db.session.add(staff);db.session.commit()
    assert 'Mượn nhanh' in c.get('/catalog').text
    # Older pending requests remain reviewable after switching the reader UI.
    db.session.add(BorrowRequest(book_id=book.id,member_id=reader.member_id))
    db.session.commit()
    item=BorrowRequest.query.one()
    assert book.available==1 and item.member_id==reader.member_id
    assert c.post(f'/admin/borrow-requests/{item.id}/review',data={'action':'approve','due_date':'2099-01-01'}).status_code==403
    librarian=auth_app.test_client();librarian.post('/login',data={'email':staff.email,'password':'secret123'})
    assert librarian.get('/admin/borrow-requests').status_code==200
    for _ in range(2):
        librarian.post(f'/admin/borrow-requests/{item.id}/review',data={'action':'approve','due_date':'2099-01-01'})
    db.session.expire_all()
    assert BorrowRequest.query.one().status=='approved'
    assert Issue.query.count()==1 and book.available==0
    issue=Issue.query.one()
    librarian.post(f'/issues/return/{issue.id}',data={'return_date':datetime.now().date().isoformat()})
    assert book.available==1


def test_request_ownership_cancel_reject_and_unavailable(auth_app):
    from app.models import BorrowRequest
    c=auth_app.test_client();legacy_account(c)
    owner=User.query.one()
    book=Book(title='Only Copy',author='Author',isbn='REQ-2',quantity=1,available=1)
    db.session.add(book);db.session.commit()
    db.session.add(BorrowRequest(book_id=book.id,member_id=owner.member_id));db.session.commit()
    item=BorrowRequest.query.one()
    other=auth_app.test_client();legacy_account(other,email='other@example.com')
    assert b'Only Copy' not in other.get('/my-books').data
    assert other.post(f'/borrow/requests/{item.id}/cancel').status_code==403
    c.post(f'/borrow/requests/{item.id}/cancel')
    db.session.expire_all();assert item.status=='cancelled' and book.available==1
    db.session.add(BorrowRequest(book_id=book.id,member_id=owner.member_id));db.session.commit()
    pending=BorrowRequest.query.filter_by(status='pending').one()
    owner.role='admin';db.session.commit()
    book.available=0;db.session.commit()
    c.post(f'/admin/borrow-requests/{pending.id}/review',data={'action':'approve','due_date':'2099-01-01'})
    db.session.expire_all();assert pending.status=='pending' and Issue.query.count()==0
    c.post(f'/admin/borrow-requests/{pending.id}/review',data={'action':'reject'})
    db.session.expire_all();assert pending.status=='rejected' and book.available==0
    other.post(f'/borrow/request/{book.id}')
    assert BorrowRequest.query.filter_by(status='pending').count()==0


def test_request_csrf_and_invalid_due_date(auth_app):
    from app.models import BorrowRequest
    c=auth_app.test_client();legacy_account(c)
    user=User.query.one()
    book=Book(title='Safe Book',author='Author',isbn='REQ-3',quantity=1,available=1)
    db.session.add(book);db.session.commit()
    auth_app.config['WTF_CSRF_ENABLED']=True
    assert c.post(f'/borrow/request/{book.id}').status_code==303
    assert BorrowRequest.query.count()==0
    c.get('/catalog')
    with c.session_transaction() as sess: token=sess['csrf_token']
    db.session.add(BorrowRequest(book_id=book.id,member_id=user.member_id));db.session.commit()
    item=BorrowRequest.query.one()
    user.role='admin';db.session.commit()
    c.post(f'/admin/borrow-requests/{item.id}/review',data={'csrf_token':token,'action':'approve','due_date':'2000-01-01'})
    db.session.expire_all();assert item.status=='pending' and book.available==1 and Issue.query.count()==0

def google_submit(client, monkeypatch, email='googleuser@gmail.com', subject='google-sub-1', **changes):
    client.get('/login')
    with client.session_transaction() as sess:
        nonce=sess['google_nonce']
    claims=dict(sub=subject,email=email,email_verified=True,nonce=nonce,name='Google Reader')
    claims.update(changes)
    monkeypatch.setattr('app.google_login.verify_credential', lambda token, audience: claims)
    return client.post('/auth/google',data={'credential':'signed-google-token'})


def test_google_new_reader_and_returning_login(auth_app,monkeypatch):
    from app.models import GoogleIdentity
    c=auth_app.test_client()
    assert google_submit(c,monkeypatch).headers['Location'].endswith('/')
    user=User.query.one()
    assert user.role=='reader' and not user.password_hash
    assert not user.check_password('')
    assert GoogleIdentity.query.one().subject=='google-sub-1'
    assert c.get('/my-books').status_code==200
    c.post('/logout')
    google_submit(c,monkeypatch)
    assert User.query.count()==1
    assert c.get('/admin').status_code==403
    user.active=False;db.session.commit()
    c.post('/logout');google_submit(c,monkeypatch)
    assert c.get('/my-books').status_code==302


def test_google_existing_email_requires_explicit_link(auth_app,monkeypatch):
    from app.models import GoogleIdentity
    c=auth_app.test_client();legacy_account(c,email='reader@gmail.com')
    user=User.query.one();c.post('/logout')
    google_submit(c,monkeypatch,email=user.email)
    assert GoogleIdentity.query.count()==0 and c.get('/my-books').status_code==302
    c.post('/login',data={'email':user.email,'password':'secret123'})
    c.get('/profile')
    with c.session_transaction() as sess: nonce=sess['google_nonce']
    monkeypatch.setattr('app.google_login.verify_credential',lambda token,audience:dict(sub='linked-admin',email=user.email,email_verified=True,nonce=nonce))
    for password,count in [('wrong',0),('secret123',1)]:
        c.post('/auth/google',data={'credential':'valid','intent':'link','link_password':password})
        assert GoogleIdentity.query.count()==count
    user.role='admin';db.session.commit();c.post('/logout')
    response=google_submit(c,monkeypatch,email=user.email,subject='linked-admin')
    assert response.headers['Location'].endswith('/admin')


@pytest.mark.parametrize('changes',[{'nonce':'wrong'},{'email_verified':False},{'sub':''}])
def test_google_rejects_bad_claims(auth_app,monkeypatch,changes):
    c=auth_app.test_client();google_submit(c,monkeypatch,**changes)
    assert User.query.count()==0
    assert c.get('/my-books').status_code==302


def test_google_rejects_invalid_signature_and_missing_csrf(auth_app,monkeypatch):
    c=auth_app.test_client();c.get('/login')
    def invalid(*args): raise ValueError('invalid signature')
    monkeypatch.setattr('app.google_login.verify_credential',invalid)
    assert c.post('/auth/google',data={'credential':'invalid'}).status_code==303
    assert User.query.count()==0
    auth_app.config['WTF_CSRF_ENABLED']=True
    assert c.post('/auth/google',data={'credential':'invalid'}).status_code==303
    assert User.query.count()==0


def test_google_verifier_passes_configured_audience(auth_app,monkeypatch):
    from app.google_login import verify_credential
    def verify(token, transport, audience, clock_skew_in_seconds):
        assert clock_skew_in_seconds == 30
        assert token=='test-credential' and audience==auth_app.config['GOOGLE_CLIENT_ID']
        return {'sub':'verified'}
    monkeypatch.setattr('google.oauth2.id_token.verify_oauth2_token',verify)
    assert verify_credential('test-credential',auth_app.config['GOOGLE_CLIENT_ID'])['sub']=='verified'


def test_live_presence_admin_only_and_no_journal(auth_app):
    from app.models import LivePresence, ActivityEvent
    reader=auth_app.test_client();legacy_account(reader)
    user=User.query.one()
    assert reader.get('/admin/accounts/presence').status_code==403
    tab='a'*32
    reader.post('/activity/heartbeat',data={'tab_id':tab,'visible':'1'},
                headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0) Chrome/130.0',
                         'X-Forwarded-For':'203.0.113.99'})
    row=LivePresence.query.one()
    assert row.device=='Windows · Chrome' and row.ip=='127.0.0.1'
    assert ActivityEvent.query.count()==0
    admin=auth_app.test_client()
    admin.post('/setup',data={'token':auth_app.config['SETUP_TOKEN'],'name':'Admin','email':'adminpresence@example.com','password':'secret123','confirm_password':'secret123'})
    def state():
        return next(a for a in admin.get('/admin/accounts/presence').json['accounts'] if a['id']==user.id)
    assert state()['online'] and state()['viewing']
    assert 'account_presence.js' in admin.get('/accounts').text
    assert 'Hoạt động tài khoản' not in admin.get('/accounts').text
    assert admin.get('/admin/activity').status_code==302
    # Hiding one tab must not mark another visible tab as hidden.
    reader.post('/activity/heartbeat',data={'tab_id':'b'*32,'visible':'0'})
    assert state()['viewing']
    reader.post('/activity/heartbeat',data={'tab_id':tab,'visible':'0'})
    assert state()['online'] and not state()['viewing']
    reader.post('/activity/heartbeat',data={'tab_id':tab,'closed':'1'})
    assert state()['online']
    reader.post('/logout')
    assert not state()['online']
    assert ActivityEvent.query.count()==0


def test_presence_timeout_csrf_and_multiple_sessions(auth_app):
    from app.models import LivePresence
    from datetime import timedelta
    first=auth_app.test_client();legacy_account(first)
    user=User.query.one()
    first.post('/activity/heartbeat',data={'tab_id':'1'*32,'visible':'1'})
    second=auth_app.test_client();second.post('/login',data={'email':user.email,'password':'secret123'})
    second.post('/activity/heartbeat',data={'tab_id':'2'*32,'visible':'1'})
    first.post('/logout')
    assert LivePresence.query.filter_by(closed=False).count()==1
    user.role='admin';db.session.commit()
    row=LivePresence.query.filter_by(closed=False).one()
    row.last_seen=datetime.utcnow()-timedelta(seconds=46);db.session.commit()
    account=second.get('/admin/accounts/presence').json['accounts'][0]
    assert not account['online']
    auth_app.config['WTF_CSRF_ENABLED']=True
    before=row.last_seen
    assert second.post('/activity/heartbeat',data={'tab_id':'2'*32,'visible':'1'}).status_code==303
    db.session.expire_all();assert row.last_seen==before

def setup_deletion_admin(app):
    admin=app.test_client()
    admin.post('/setup',data={'token':app.config['SETUP_TOKEN'],'name':'Admin','email':'deleteadmin@example.com','password':'secret123','confirm_password':'secret123'})
    return admin


def test_delete_account_allows_fresh_registration_preserves_loans(auth_app):
    from app.models import BorrowRequest
    admin=setup_deletion_admin(auth_app)
    reader=auth_app.test_client();legacy_account(reader,email='reader@gmail.com')
    user=User.query.filter_by(email='reader@gmail.com').one();old_id=user.id;member_id=user.member_id
    book=Book(title='Old loan',author='A',isbn='DELETE-1',quantity=1,available=0)
    db.session.add(book);db.session.flush()
    db.session.add(Issue(book_id=book.id,member_id=member_id,due_date=datetime(2099,1,1)))
    db.session.add(BorrowRequest(book_id=book.id,member_id=member_id));db.session.commit()
    assert reader.post(f'/accounts/{old_id}/delete',data={'mode':'delete'}).status_code==403
    assert admin.post(f'/accounts/{old_id}/delete',data={'mode':'delete'}).status_code==302
    assert db.session.get(User,old_id) is None and Issue.query.count()==1 and book.available==0
    assert BorrowRequest.query.one().status=='cancelled'
    new=auth_app.test_client();legacy_account(new,email='reader@gmail.com')
    new_user=User.query.filter_by(email='reader@gmail.com').one()
    assert new_user.member_id!=member_id
    assert b'Old loan' not in new.get('/my-books').data
    assert reader.get('/my-books').status_code==302


def test_delete_block_google_and_password_and_unblock(auth_app,monkeypatch):
    from app.models import RegistrationBlock,GoogleIdentity
    admin=setup_deletion_admin(auth_app)
    reader=auth_app.test_client();google_submit(reader,monkeypatch,email='r.eader@gmail.com',subject='blocked-sub')
    user=User.query.filter_by(email='r.eader@gmail.com').one()
    admin.post(f'/accounts/{user.id}/delete',data={'mode':'block'})
    block=RegistrationBlock.query.one()
    assert block.email=='reader@gmail.com' and block.google_subject=='blocked-sub'
    assert GoogleIdentity.query.count()==0
    retry=auth_app.test_client();legacy_account(retry,email='reader+alias@gmail.com')
    assert User.query.count()==1
    google_submit(retry,monkeypatch,email='changed@gmail.com',subject='blocked-sub')
    assert User.query.count()==1
    admin.post(f'/accounts/registration-blocks/{block.id}/remove')
    legacy_account(retry,email='r.eader@gmail.com')
    assert User.query.count()==2


def test_admin_delete_protection_and_transfer(auth_app):
    admin=setup_deletion_admin(auth_app)
    source=User.query.filter_by(role='admin').one()
    response=admin.post(f'/accounts/{source.id}/delete',data={'mode':'block'},follow_redirects=True)
    assert 'chuyển tài khoản khác làm quản trị'.encode() in response.data
    assert db.session.get(User,source.id) is not None
    reader=auth_app.test_client();legacy_account(reader,email='newadmin@gmail.com')
    target=User.query.filter_by(email='newadmin@gmail.com').one()
    admin.post(f'/accounts/{source.id}/transfer-admin',data={'target_id':target.id})
    assert source.role=='librarian' and target.role=='admin'
    assert admin.get('/accounts').status_code==403
    assert reader.post(f'/accounts/{source.id}/delete',data={'mode':'delete'}).status_code==302
    assert db.session.get(User,source.id) is None

def test_accounts_groups_and_full_editor(auth_app):
    admin=setup_deletion_admin(auth_app)
    reader=auth_app.test_client();legacy_account(reader,email='editable@example.com')
    user=User.query.filter_by(email='editable@example.com').one()
    original_member_id=user.member_id
    assert reader.get(f'/accounts/{user.id}/edit').status_code==403
    page=admin.get('/accounts')
    assert b'id="admin-accounts"' in page.data and b'id="user-accounts"' in page.data
    assert admin.get('/members').headers['Location'].endswith('/accounts')
    response=admin.post(f'/accounts/{user.id}/edit',data={'name':'Edited Reader','email':'edited@example.com',
        'phone':'0900000000','member_code':'EDIT-MEMBER','joined_at':'2020-01-02','role':'librarian','active':'1',
        'password':'newpassword123','confirm_password':'newpassword123'},follow_redirects=True)
    assert response.status_code==200 and b'Edited Reader' in response.data
    assert user.email==user.member.email=='edited@example.com'
    assert user.member.member_id=='EDIT-MEMBER' and user.member.phone=='0900000000'
    assert user.member.joined_at==datetime(2020,1,2) and user.role=='librarian'
    assert user.member_id==original_member_id and user.check_password('newpassword123')
    assert user.password_change_required
    assert reader.get('/my-books').status_code==302


def test_account_edit_self_guard_duplicate_and_google_unlink(auth_app):
    from app.models import GoogleIdentity
    admin=setup_deletion_admin(auth_app)
    owner=User.query.filter_by(role='admin').one()
    base={'name':'Admin','email':owner.email,'phone':'','member_code':owner.member.member_id,
          'joined_at':owner.member.joined_at.strftime('%Y-%m-%d'),'role':'reader','active':'0'}
    admin.post(f'/accounts/{owner.id}/edit',data=base)
    assert owner.active and owner.role=='admin'
    reader=auth_app.test_client();legacy_account(reader,email='linked@example.com')
    user=User.query.filter_by(email='linked@example.com').one()
    db.session.add(GoogleIdentity(user_id=user.id,subject='edit-linked-sub'));db.session.commit()
    data={'name':'Reader','email':'newlinked@example.com','phone':'','member_code':user.member.member_id,
          'joined_at':user.member.joined_at.strftime('%Y-%m-%d'),'role':'reader','active':'1'}
    admin.post(f'/accounts/{user.id}/edit',data=data)
    assert user.email=='linked@example.com'
    data['unlink_google']='1';admin.post(f'/accounts/{user.id}/edit',data=data)
    assert user.email=='newlinked@example.com' and not user.google_identity
    data['email']=owner.email;admin.post(f'/accounts/{user.id}/edit',data=data)
    assert user.email=='newlinked@example.com'
