from datetime import date, timedelta
import hashlib
from io import BytesIO

import pytest
from app import create_app, db
from app.models import Book, Member, User


@pytest.fixture
def mobile_app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                      'SECRET_KEY': 'mobile-test-only', 'WTF_CSRF_ENABLED': True})
    with app.app_context():
        for role in ('reader', 'admin', 'librarian'):
            email = f'{role}@example.com'
            member = Member(name=role, email=email, member_id=role, phone='0901234567')
            user = User(email=email, role=role, member=member)
            user.set_password('mobile-test-password')
            db.session.add(user)
        db.session.add(Book(title='Sách mẫu', author='Tác giả', isbn='MOBILE-TEST', quantity=2, available=2))
        db.session.commit()
        yield app
        db.session.remove()


def login(app, role):
    client = app.test_client()
    session_info = client.get('/api/mobile/session').json
    assert session_info['user'] is None
    response = client.post('/api/mobile/login', data={'csrf_token': session_info['csrf_token'],
                           'email': f'{role}@example.com', 'password': 'mobile-test-password'})
    assert response.status_code == 200
    assert response.json['user']['role'] == role
    return client, response.json['csrf_token']


def test_mobile_and_web_share_stock_requests_and_returns(mobile_app):
    reader, reader_token = login(mobile_app, 'reader')
    admin, admin_token = login(mobile_app, 'admin')
    book = Book.query.one()
    assert reader.post(f'/api/mobile/borrow/{book.id}', data={'csrf_token': 'bad'}).status_code == 403
    assert reader.post(f'/api/mobile/borrow/{book.id}', data={'csrf_token': reader_token}).json['ok']
    assert 'Sách mẫu' in admin.get('/admin/borrow-requests').text
    pending = admin.get('/api/mobile/library').json['requests'][0]
    assert reader.post(f"/api/mobile/requests/{pending['id']}", data={'csrf_token': reader_token}).status_code == 403
    response = admin.post(f"/admin/borrow-requests/{pending['id']}/review",
                          data={'action': 'approve', 'csrf_token': admin_token,
                                'due_date': (date.today()+timedelta(days=14)).isoformat()})
    assert response.status_code == 302
    reader_state = reader.get('/api/mobile/library').json
    assert reader_state['books'][0]['available'] == 1
    issue = reader_state['loans'][0]
    assert issue['status'] == 'issued'
    for _ in range(2):
        response = admin.post(f"/api/mobile/returns/{issue['id']}",
                              data={'csrf_token': admin_token, 'return_date': date.today().isoformat()})
        assert response.json['ok']
    assert admin.get('/api/books').json[0]['available'] == 2
    assert reader.get('/api/mobile/library').json['loans'][0]['status'] == 'returned'


def test_mobile_role_boundaries_notices_and_maintenance(mobile_app):
    reader, reader_token = login(mobile_app, 'reader')
    admin, admin_token = login(mobile_app, 'admin')
    librarian, librarian_token = login(mobile_app, 'librarian')
    assert mobile_app.test_client().get('/api/mobile/library').status_code == 401
    for client, token in ((reader, reader_token), (librarian, librarian_token)):
        assert client.post('/api/mobile/notices', data={'csrf_token': token}).status_code == 403
    assert admin.post('/api/mobile/notices', data={'body': 'Mobile notice', 'color': '#2346B4',
                                                   'csrf_token': admin_token}).json['ok']
    assert reader.get('/live-updates').json['announcements'][0]['body'] == 'Mobile notice'
    assert admin.post('/admin/maintenance', data={'enabled': '1', 'csrf_token': admin_token}).status_code == 303
    locked = reader.get('/api/mobile/library')
    assert locked.status_code == 503 and locked.json['maintenance']
    assert admin.get('/api/mobile/library').status_code == 200
    assert reader.post('/api/mobile/logout', data={'csrf_token': reader_token}).json['ok']
    assert reader.get('/api/mobile/session').json['user'] is None


def test_mobile_edits_are_visible_on_web_and_web_edits_are_visible_in_mobile(mobile_app):
    admin, token = login(mobile_app, 'admin')
    result = admin.post('/api/mobile/books', data={
        'csrf_token': token, 'title': 'Sách từ Android', 'author': 'Tác giả',
        'isbn': 'ANDROID-BOOK', 'quantity': '3', 'description': 'Giới thiệu từ Android',
    })
    assert result.json['ok']
    book = Book.query.filter_by(isbn='ANDROID-BOOK').one()
    assert 'Giới thiệu từ Android' in admin.get(f'/book/{book.id}').text
    result = admin.post(f'/admin/books/{book.id}/edit', data={
        'csrf_token': token, 'title': 'Sách sửa từ web', 'author': 'Tác giả',
        'isbn': 'ANDROID-BOOK', 'quantity': '4',
    })
    assert result.status_code == 303
    row = next(item for item in admin.get('/api/mobile/library').json['books'] if item['id'] == book.id)
    assert row['title'] == 'Sách sửa từ web' and row['available'] == 4


def test_mobile_book_upload_preserves_metadata_and_sample_order(mobile_app):
    from PIL import Image

    admin, token = login(mobile_app, 'admin')
    image = BytesIO()
    Image.new('RGB', (160, 200), 'white').save(image, 'PNG')
    png = image.getvalue()
    result = admin.post('/api/mobile/books', data={
        'csrf_token': token, 'title': 'Sách có ảnh', 'author': 'Tác giả', 'isbn': 'MOBILE-MEDIA',
        'quantity': '3', 'publisher': 'Nhà xuất bản', 'shelf': 'A2', 'year': '2025', 'pages': '150',
        'cover': (BytesIO(png), 'cover.png'),
        'samples': [(BytesIO(png), 'first.png'), (BytesIO(png), 'second.png')],
    })
    assert result.json['ok']
    book = Book.query.filter_by(isbn='MOBILE-MEDIA').one()
    assert book.cover and [page.position for page in book.sample_pages] == [1, 2]
    assert (book.info.publisher, book.info.shelf, book.info.year, book.info.pages) == ('Nhà xuất bản', 'A2', 2025, 150)


def test_mobile_admin_permissions_and_notice_edit(mobile_app):
    reader, _ = login(mobile_app, 'reader')
    librarian, librarian_token = login(mobile_app, 'librarian')
    admin, token = login(mobile_app, 'admin')
    assert reader.get('/api/mobile/reports').status_code == 403
    assert librarian.get('/api/mobile/reports').json['loans'] == []
    assert librarian.post('/api/mobile/reports', data={'fine_per_day': 5000, 'csrf_token': librarian_token}).status_code == 403
    assert admin.post('/api/mobile/reports', data={'fine_per_day': 5000, 'csrf_token': token}).json['ok']
    assert librarian.get('/api/mobile/reports').json['rate'] == 5000
    assert librarian.get('/api/mobile/recoveries').status_code == 403
    assert admin.get('/api/mobile/recoveries').json == {'items': []}

    fields = {'body': 'Original', 'color': '#2457D6', 'csrf_token': token}
    assert admin.post('/api/mobile/notices', data=fields).json['ok']
    notice = admin.get('/api/mobile/library').json['sent'][0]
    fields.update(edit=notice['id'], body='Updated', expires_at='2090-01-01T12:30')
    assert admin.post('/api/mobile/notices', data=fields).json['ok']
    saved, = admin.get('/api/mobile/library').json['sent']
    assert (saved['id'], saved['body'], saved['expires_at']) == (notice['id'], 'Updated', fields['expires_at'])


@pytest.mark.parametrize('mode', ['login', 'register'])
def test_mobile_browser_auth_requires_proof_confirmation_and_one_time_exchange(mobile_app, monkeypatch, mode):
    app_client = mobile_app.test_client()
    browser = mobile_app.test_client()
    token = app_client.get('/api/mobile/session').json['csrf_token']
    proof = 'ab' * 32
    started = app_client.post('/api/mobile/connect', data={
        'csrf_token': token, 'mode': mode, 'proof_hash': hashlib.sha256(proof.encode()).hexdigest(),
    }).json
    exchange = {'csrf_token': token, 'id': started['id'], 'proof': proof}
    assert app_client.post('/api/mobile/connect/exchange', data=exchange).status_code == 202
    assert app_client.post('/api/mobile/connect/exchange', data=dict(exchange, proof='cd' * 32)).status_code == 410
    assert browser.get(started['path'], follow_redirects=True).status_code == 200
    with browser.session_transaction() as browser_session:
        csrf = browser_session['csrf_token']
        nonce = browser_session['google_nonce']
    if mode == 'login':
        monkeypatch.setattr('app.google_login.verify_credential', lambda *_: {
            'nonce': nonce, 'sub': 'android-google', 'email': 'android-google@gmail.com', 'email_verified': True,
        })
        response = browser.post('/auth/google', data={'csrf_token': csrf, 'credential': 'verified-test'})
    else:
        monkeypatch.setattr('app.google_login.registration_google_claims',
                            lambda _: {'email': 'android-register@gmail.com', 'subject': 'android-register'})
        response = browser.post('/register', data={'csrf_token': csrf, 'google_credential': 'verified-test',
                                'name': 'Độc giả Android', 'password': 'android-secret', 'confirm_password': 'android-secret'})
    assert response.location == '/api/mobile/connect/confirm'
    assert app_client.post('/api/mobile/connect/exchange', data=exchange).status_code == 202
    assert browser.get(response.location).status_code == 200
    with browser.session_transaction() as browser_session:
        csrf = browser_session['csrf_token']
    assert browser.post(response.location, data={'csrf_token': csrf, 'action': 'confirm'}).status_code == 200
    authorized = app_client.post('/api/mobile/connect/exchange', data=exchange)
    assert authorized.status_code == 200 and authorized.json['user']['role'] == 'reader'
    assert app_client.get('/api/mobile/library').status_code == 200
    assert app_client.post('/api/mobile/connect/exchange', data=dict(exchange, csrf_token=authorized.json['csrf_token'])).status_code == 410
