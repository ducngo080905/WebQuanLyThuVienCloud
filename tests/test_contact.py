from app import create_app, db
from app.auth import account_guard
from app.models import User, Member, ContactRequest, ContactReply
import pytest


@pytest.fixture
def support():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                      'SECRET_KEY': 'contact-test', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        clients, users = {}, {}
        for role in ('reader', 'other', 'admin', 'librarian'):
            member = Member(name=role, email=f'{role}@example.com', member_id=role, phone='0901234567')
            user = User(member=member, email=member.email, password_hash='test', role='reader' if role=='other' else role)
            db.session.add(user)
            db.session.flush()
            client = app.test_client()
            with client.session_transaction() as session:
                session['user_id'] = user.id
                session['account_guard'] = account_guard(user)
            users[role], clients[role] = user, client
        db.session.commit()
        yield app, clients, users
        db.session.remove()
        db.drop_all()


def create(client, subject='Cần hỗ trợ mượn sách', body='Tôi cần hỗ trợ từ xa.'):
    response = client.post('/contact', data={'subject': subject, 'body': body})
    assert response.status_code == 303
    return response.headers['Location']


def test_reader_and_admin_exchange_and_close(support):
    app, clients, _ = support
    url = create(clients['reader'])
    item = ContactRequest.query.one()
    assert item.status == 'waiting'
    assert 'Tôi cần hỗ trợ từ xa.' in clients['admin'].get(url).text
    assert item.subject in clients['admin'].get('/admin/contact').text
    response = clients['admin'].post(url, data={'body': 'Bạn cho biết mã sách nhé.'}, follow_redirects=True)
    assert response.status_code == 200
    assert item.status == 'replied'
    assert 'Bạn cho biết mã sách nhé.' in clients['reader'].get(url).text
    assert 'Admin đã phản hồi' in clients['reader'].get('/contact').text
    clients['reader'].post(url, data={'body': 'Mã sách 123'})
    assert item.status == 'waiting'
    clients['admin'].post(url+'/status', data={'status': 'closed'})
    assert item.status == 'closed'
    before = ContactReply.query.count()
    clients['reader'].post(url, data={'body': 'Cannot send until reopened'})
    assert ContactReply.query.count() == before
    clients['reader'].post(url+'/status', data={'status': 'waiting'})
    clients['reader'].post(url, data={'body': 'Trao đổi thêm'})
    assert ContactReply.query.count() == before+1
    assert 'data-refresh="contactConversation"' in clients['reader'].get(url).text


def test_contact_privacy_roles_and_navigation(support):
    app, clients, _ = support
    url = create(clients['reader'], subject='Private subject')
    for role in ('other', 'librarian'):
        assert clients[role].get(url).status_code == 404
        assert clients[role].post(url, data={'body': 'intrusion'}).status_code == 404
        assert clients[role].post(url+'/status', data={'status': 'closed'}).status_code == 404
        assert clients[role].get('/admin/contact').status_code == 403
        assert 'Private subject' not in clients[role].get('/contact').text
    assert app.test_client().get('/contact').status_code == 302
    assert app.test_client().post(url, data={'body': 'anonymous'}).status_code == 302
    assert ContactReply.query.count() == 1
    assert 'Liên hệ admin' in clients['reader'].get('/').text
    assert 'Liên hệ độc giả' in clients['admin'].get('/admin').text
    assert clients['admin'].get('/contact').headers['Location'].endswith('/admin/contact')


def test_contact_validation_csrf_and_escaped_html(support):
    app, clients, _ = support
    reader = clients['reader']
    for subject, body in [('', 'body'), ('x'*161, 'body'), ('subject', ''), ('subject', 'x'*5001)]:
        assert reader.post('/contact', data={'subject':subject,'body':body}).status_code == 400
    assert ContactRequest.query.count() == 0
    url = create(reader, subject='<script>subject</script>', body='<img src=x onerror=alert(1)>')
    page = reader.get(url).text
    assert '&lt;script&gt;subject&lt;/script&gt;' in page
    assert '<img src=x onerror=' not in page
    count = ContactReply.query.count()
    reader.post(url, data={'body':'x'*5001})
    assert ContactReply.query.count() == count
    assert reader.post(url+'/status', data={'status':'invalid'}).status_code == 400
    app.config['WTF_CSRF_ENABLED'] = True
    for path, values in [('/contact', {'subject':'No CSRF','body':'body'}),
                         (url, {'body':'No CSRF'}), (url+'/status', {'status':'closed'})]:
        assert reader.post(path, data=values).status_code == 303
    assert ContactRequest.query.count() == 1
    assert ContactReply.query.count() == count
    with reader.session_transaction() as session:
        token = session['csrf_token']
    assert reader.post(url, data={'body':'With CSRF','csrf_token':token}).status_code == 303
    assert ContactReply.query.count() == count+1


def test_contact_pagination_filters_and_account_deletion(support):
    _, clients, users = support
    for i in range(17):
        db.session.add(ContactRequest(user_id=users['reader'].id, subject=f'Request {i}', status='closed' if i==0 else 'waiting'))
    db.session.commit()
    assert clients['reader'].get('/contact').text.count('class="contact-request"') == 15
    assert clients['reader'].get('/contact?page=2').text.count('class="contact-request"') == 2
    assert clients['admin'].get('/admin/contact?status=closed').text.count('class="contact-request"') == 1
    url = create(clients['reader'])
    clients['admin'].post(url, data={'body': 'Reply'})
    db.session.delete(users['admin'])
    db.session.commit()
    assert clients['reader'].get(url).status_code == 200
    db.session.delete(users['reader'])
    db.session.commit()
    assert ContactRequest.query.count() == ContactReply.query.count() == 0
