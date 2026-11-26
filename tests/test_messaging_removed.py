"""Removing chat must not break account pictures or library announcements."""
from io import BytesIO

import pytest
from PIL import Image
from app import create_app, db
from app.auth import account_guard
from app.models import Member, User, UserAvatar


@pytest.fixture
def library():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                      'SECRET_KEY': 'removed-chat-tests', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        clients = {}
        users = {}
        for role in ('reader', 'admin', 'librarian'):
            member = Member(name=role, email=f'{role}@example.com', member_id=role,
                            phone='0901234567')
            user = User(member=member, email=member.email, role=role,
                        password_hash='test-only')
            db.session.add(user)
            db.session.flush()
            client = app.test_client()
            with client.session_transaction() as session:
                session['user_id'] = user.id
                session['account_guard'] = account_guard(user)
            clients[role], users[role] = client, user
        db.session.commit()
        yield app, clients, users
        db.session.remove()
        db.drop_all()


def test_chat_is_removed_for_all_roles(library):
    app, clients, _ = library
    assert 'chat' not in app.blueprints
    for client in (app.test_client(), *clients.values()):
        for path in ('/messenger', '/chat/api/overview', '/chat/api/unread',
                     '/chat/api/attachments/1', '/chat/api/avatars/1'):
            assert client.get(path).status_code == 404
        assert client.post('/chat/api/threads').status_code == 404
    for role, client in clients.items():
        for path in ('/profile', '/admin' if role == 'admin' else '/'):
            page = client.get(path)
            assert page.status_code == 200
            for obsolete in ('/messenger', '/chat/api/', 'chat_widget', 'chat_badge', 'messenger.js'):
                assert obsolete not in page.text
    assert clients['admin'].get('/admin/announcements').status_code == 200
    assert clients['reader'].get('/live-updates').status_code == 200


def test_profile_avatar_survives_without_chat(library):
    app, clients, users = library
    reader = clients['reader']
    assert reader.post('/profile/avatar', data={'avatar': (BytesIO(b'bad'), 'bad.png')}).status_code == 302
    assert db.session.get(UserAvatar, users['reader'].id) is None
    image = BytesIO()
    Image.new('RGB', (320, 180), 'blue').save(image, format='PNG')
    image.seek(0)
    assert reader.post('/profile/avatar', data={'avatar': (image, 'avatar.png')}).status_code == 302
    url = f"/profile/avatars/{users['reader'].id}"
    assert url in reader.get('/profile').text
    for client in (reader, clients['admin']):
        response = client.get(url)
        assert response.status_code == 200
        assert response.mimetype == 'image/jpeg'
        assert response.headers['Cache-Control'] == 'no-store'
        with Image.open(BytesIO(response.data)) as picture:
            assert picture.size == (256, 256)
    assert clients['librarian'].get(url).status_code == 404
    assert app.test_client().get(url).status_code == 302
    assert reader.post('/profile/avatar', data={'remove': '1'}).status_code == 302
    assert reader.get(url).status_code == 404
