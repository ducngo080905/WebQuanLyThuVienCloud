from datetime import datetime
import pytest
from app import create_app,db
from app.auth import account_guard
from app.models import User,Member,Book,BorrowRequest,LibrarySetting,GoogleIdentity


@pytest.fixture
def operations_app():
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:',
                    'SECRET_KEY':'operations-test','WTF_CSRF_ENABLED':False,'APP_VERSION':'release-1'})
    with app.app_context():
        clients={};users={}
        for role in ('admin','reader','librarian'):
            member=Member(name=role,email=role+'@example.com',phone='0901234567',member_id=role)
            user=User(email=member.email,role=role,member=member,password_hash='test-not-a-login-password')
            db.session.add(user);db.session.flush()
            client=app.test_client()
            with client.session_transaction() as session:session['user_id']=user.id;session['account_guard']=account_guard(user)
            clients[role]=client;users[role]=user
        db.session.add(Book(title='Available book',author='Author',isbn='OPERATIONS',quantity=1,available=1));db.session.commit()
        yield app,clients,users
        db.session.remove();db.drop_all()


def test_only_admin_can_control_and_preview_maintenance(operations_app):
    app,clients,users=operations_app
    for client in (app.test_client(),clients['reader'],clients['librarian']):
        assert client.post('/admin/maintenance',data={'enabled':'1'}).status_code==403
    assert clients['admin'].post('/admin/maintenance',data={'enabled':'bad'}).status_code==400
    assert not clients['reader'].get('/system/status').json['maintenance']
    assert clients['admin'].get('/maintenance?preview=1').status_code==503
    assert not clients['reader'].get('/system/status').json['maintenance']
    assert 'maintenanceDialog' in clients['admin'].get('/admin').text
    assert 'maintenanceDialog' not in clients['librarian'].get('/issues').text


def test_server_blocks_pages_api_and_writes_but_admin_stays_online(operations_app):
    app,clients,users=operations_app
    clients['admin'].post('/admin/maintenance',data={'enabled':'1'})
    for client in (clients['reader'],clients['librarian'],app.test_client()):
        for path in ('/','/catalog','/my-books','/inbox','/register','/covers/1','/api/books'):
            response=client.get(path)
            assert response.status_code==503,path
            assert response.headers['X-Library-Maintenance']=='1'
            assert response.headers['Cache-Control']=='no-store'
        response=client.post('/borrow/request/1')
        assert response.status_code==503 and response.json['maintenance'] is True
        assert client.get('/system/status').json['maintenance'] is True
        assert client.get('/login').status_code in (200,303)
    assert BorrowRequest.query.count()==0
    assert clients['admin'].get('/admin').status_code==200
    assert clients['admin'].get('/system/status').json['admin'] is True
    assert app.test_client().get('/static/operations.css').status_code==200
    assert app.test_client().get('/health').status_code==200
    assert clients['reader'].post('/logout').status_code==302


def test_disable_restores_access_and_commands_are_idempotent(operations_app):
    app,clients,users=operations_app
    for _ in range(2):clients['admin'].post('/admin/maintenance',data={'enabled':'1'})
    assert LibrarySetting.query.filter_by(key='maintenance_enabled').one().value==1
    for _ in range(2):clients['admin'].post('/admin/maintenance',data={'enabled':'0'})
    assert clients['reader'].get('/catalog').status_code==200
    assert clients['reader'].get('/maintenance').status_code==302
    assert clients['reader'].get('/system/status').json['maintenance'] is False


def test_toggle_csrf_and_release_detection(operations_app):
    app,clients,users=operations_app
    app.config['WTF_CSRF_ENABLED']=True
    assert clients['admin'].post('/admin/maintenance',data={'enabled':'1'}).status_code==303
    assert LibrarySetting.query.filter_by(key='maintenance_enabled').first() is None
    clients['admin'].get('/admin')
    with clients['admin'].session_transaction() as session:token=session['csrf_token']
    response=clients['admin'].post('/admin/maintenance',data={'enabled':'1','csrf_token':token},headers={'Accept':'application/json'})
    assert response.json=={'ok':True,'maintenance':True}
    response=clients['reader'].get('/system/status')
    assert response.json['version']=='release-1' and response.headers['Cache-Control']=='no-store'
    app.config['APP_VERSION']='release-2'
    assert clients['reader'].get('/system/status').json['version']=='release-2'


def test_google_admin_login_allowed_but_new_account_creation_blocked(operations_app,monkeypatch):
    app,clients,users=operations_app
    db.session.add(GoogleIdentity(user_id=users['admin'].id,subject='existing-admin'));db.session.commit()
    clients['admin'].post('/admin/maintenance',data={'enabled':'1'})
    client=app.test_client();client.get('/login')
    with client.session_transaction() as session:nonce=session['google_nonce']
    monkeypatch.setattr('app.google_login.verify_credential',lambda *_:{'sub':'new-reader','email':'new-reader@gmail.com','email_verified':True,'nonce':nonce})
    assert client.post('/auth/google',data={'credential':'synthetic'}).status_code==503
    assert User.query.count()==3
    monkeypatch.setattr('app.google_login.verify_credential',lambda *_:{'sub':'existing-admin','email':users['admin'].email,'email_verified':True,'nonce':nonce})
    assert client.post('/auth/google',data={'credential':'synthetic'}).status_code==303
    assert client.get('/admin').status_code==200


def test_maintenance_estimate_can_be_changed_without_reopening(operations_app):
    from datetime import timedelta
    from app.operations import VIETNAM_TIME

    _, clients, _ = operations_app
    admin, reader = clients['admin'], clients['reader']
    end = datetime.now(VIETNAM_TIME) + timedelta(days=1)
    headers = {'Accept': 'application/json'}
    assert admin.post('/admin/maintenance', data={'enabled':'1', 'expected_end':'2020-01-01T08:00'}, headers=headers).status_code == 400
    assert reader.get('/system/status').json['maintenance'] is False
    assert admin.post('/admin/maintenance', data={'enabled':'1', 'expected_end':end.strftime('%Y-%m-%dT%H:%M')}).status_code == 303
    label = end.strftime('%H:%M · %d/%m/%Y')
    assert label in reader.get('/maintenance').text
    assert reader.get('/system/status').json['expected_end'] == label
    later = end + timedelta(hours=2)
    assert admin.post('/admin/maintenance', data={'enabled':'0', 'update_schedule':'1', 'expected_end':later.strftime('%Y-%m-%dT%H:%M')}).status_code == 303
    assert reader.get('/system/status').json['expected_end'] == later.strftime('%H:%M · %d/%m/%Y')
    assert reader.get('/catalog').status_code == 503
    admin.post('/admin/maintenance', data={'enabled':'0'})
    assert reader.get('/system/status').json['expected_end'] == ''


def test_maintenance_duration_accepts_decimal_hours(operations_app):
    _, clients, _ = operations_app
    admin, reader = clients['admin'], clients['reader']
    headers = {'Accept': 'application/json'}
    for invalid in ('0', '-2', 'nan', '721'):
        result = admin.post('/admin/maintenance', data={'enabled':'1', 'duration_hours':invalid}, headers=headers)
        assert result.status_code == 400
    assert reader.get('/system/status').json['maintenance'] is False
    admin.post('/admin/maintenance', data={'enabled':'1', 'duration_hours':'0,5'})
    status = reader.get('/system/status').json
    assert status['maintenance'] is True
    assert 1795 <= status['remaining_seconds'] <= 1800
    assert 'maintenanceCountdown' in reader.get('/maintenance').text
