import pytest
from app import create_app, db
from app.models import Book, Member, Issue, User
from datetime import datetime, timedelta


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret'
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    with app.app_context():
        admin_member = Member(name='Admin', email='admin@example.com', member_id='ADMIN')
        db.session.add(admin_member)
        db.session.flush()
        admin = User(email=admin_member.email, member_id=admin_member.id, role='admin')
        admin.set_password('test-password')
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = admin_id
    return client


@pytest.fixture
def sample_book(app):
    with app.app_context():
        book = Book(title='Test Book', author='Test Author',
                    isbn='123-456', genre='Fiction', quantity=3, available=3)
        db.session.add(book)
        db.session.commit()
        return book.id


@pytest.fixture
def sample_member(app):
    with app.app_context():
        member = Member(name='Test User', email='test@example.com',
                        phone='9999999999', member_id='MEM99999')
        db.session.add(member)
        db.session.commit()
        return member.id


# ─── Health & Dashboard ───────────────────────────────────────────────────────

def test_health_endpoint(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'healthy'


def test_dashboard_loads(client):
    resp = client.get('/admin')
    assert resp.status_code == 200
    assert 'Tổng quan'.encode() in resp.data


def test_dashboard_loads_with_active_issue(client, sample_book, sample_member):
    client.post('/issues/add', data={
        'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': str(sample_book),
        'member_id': str(sample_member)
    })

    resp = client.get('/admin')
    assert resp.status_code == 200
    assert 'Đang mượn'.encode() in resp.data


# ─── Books ────────────────────────────────────────────────────────────────────

def test_books_page(client):
    resp = client.get('/books')
    assert resp.status_code == 200


def test_add_book(client):
    resp = client.post('/books/add', data={
        'title': 'Clean Code',
        'author': 'Robert Martin',
        'isbn': '978-0132350884',
        'genre': 'Technology',
        'quantity': '2'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Clean Code' in resp.data


def test_add_book_duplicate_isbn(client, app):
    """Duplicate ISBN should not create a second book (DB enforces uniqueness)."""
    data = dict(title='Book A', author='Author', isbn='DUP-001', genre='', quantity='1')
    client.post('/books/add', data=data, follow_redirects=True)
    try:
        client.post('/books/add', data=data, follow_redirects=True)
    except Exception:
        pass  # IntegrityError is the expected behaviour
    with app.app_context():
        count = Book.query.filter_by(isbn='DUP-001').count()
        assert count == 1  # only one book should exist


def test_api_books(client, sample_book):
    resp = client.get('/api/books')
    assert resp.status_code == 200
    books = resp.get_json()
    assert len(books) >= 1
    assert books[0]['title'] == 'Test Book'


def test_delete_book(client, app, sample_book):
    resp = client.post(f'/books/delete/{sample_book}', follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Book.query.get(sample_book) is None


@pytest.mark.parametrize('returned', [False, True])
def test_delete_book_with_loans(client, app, sample_book, sample_member, returned):
    with app.app_context():
        other = Book(title='Other Book', author='Author', isbn='OTHER-ISBN', quantity=2, available=2)
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    for book_id in (sample_book, sample_book, other_id):
        client.post('/issues/add', data={
            'book_id': book_id, 'member_id': sample_member,
            'issue_date': '2026-10-01', 'due_date': '2026-11-15'
        })
    with app.app_context():
        issue_ids = [issue.id for issue in Issue.query.filter_by(book_id=sample_book).all()]
    if returned:
        for issue_id in issue_ids:
            client.post(f'/issues/return/{issue_id}', data={'return_date': '2026-10-30'})

    response = client.post(f'/books/delete/{sample_book}', follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == '/books'
    assert 'Đã xóa sách.'.encode() in response.data
    with app.app_context():
        assert db.session.get(Book, sample_book) is None
        assert all(db.session.get(Issue, issue_id) is None for issue_id in issue_ids)
        assert Issue.query.one().book_id == other_id
        assert db.session.get(Book, other_id).available == 1
        assert db.session.get(Member, sample_member) is not None
    assert [book['id'] for book in client.get('/api/books').get_json()] == [other_id]
    for path in ('/', '/issues', '/members', '/api/issues'):
        assert client.get(path,follow_redirects=True).status_code == 200


# ─── Members ─────────────────────────────────────────────────────────────────

def test_members_page(client):
    resp = client.get('/members',follow_redirects=True)
    assert resp.status_code == 200


def test_add_member(client):
    resp = client.post('/members/add', data={
        'name': 'Priya Sharma',
        'email': 'priya@example.com',
        'phone': '9876543210'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Priya Sharma' in resp.data


def test_api_members(client, sample_member):
    resp = client.get('/api/members')
    assert resp.status_code == 200
    members = resp.get_json()
    assert any(m['name'] == 'Test User' for m in members)


def test_delete_member_without_issues(client, app, sample_member):
    resp = client.post(f'/members/delete/{sample_member}', follow_redirects=True)

    assert resp.status_code == 200
    assert 'Đã xóa thành viên.'.encode() in resp.data
    with app.app_context():
        assert db.session.get(Member, sample_member) is None


@pytest.mark.parametrize('returned', [False, True])
def test_delete_member_with_issue_removes_history_and_restores_stock(
        client, app, sample_book, sample_member, returned):
    client.post('/issues/add', data={
        'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': str(sample_book), 'member_id': str(sample_member)
    })
    with app.app_context():
        issue_id = Issue.query.one().id
    if returned:
        client.post(f'/issues/return/{issue_id}', data={'return_date': '2026-10-30'})

    resp = client.post(f'/members/delete/{sample_member}', follow_redirects=True)

    assert resp.status_code == 200
    assert resp.request.path == '/accounts'
    assert 'Đã xóa thành viên.'.encode() in resp.data
    with app.app_context():
        assert db.session.get(Member, sample_member) is None
        assert db.session.get(Issue, issue_id) is None
        assert db.session.get(Book, sample_book).available == 3
    assert all(m['id'] != sample_member for m in client.get('/api/members').get_json())
    assert client.get('/api/issues').get_json() == []
    assert client.get('/issues').status_code == 200
    assert client.get('/').status_code == 200


def test_edit_member(client, app, sample_member, sample_book):
    client.post('/issues/add', data={'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': sample_book, 'member_id': sample_member})
    page = client.get(f'/members/edit/{sample_member}',follow_redirects=True)
    assert page.status_code == 200
    assert b'Test User' in page.data
    response = client.post(f'/members/edit/{sample_member}', data={
        'name': 'Updated User', 'email': 'updated@example.com', 'phone': '0123456789'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Updated User' in response.data
    with app.app_context():
        member = db.session.get(Member, sample_member)
        assert (member.name, member.email, member.phone) == (
            'Updated User', 'updated@example.com', '0123456789')
        assert member.member_id == 'MEM99999'
        assert Issue.query.one().member_id == sample_member


@pytest.mark.parametrize('name,email', [('', 'new@example.com'), ('User', 'invalid'), ('User', 'other@example.com')])
def test_edit_member_rejects_invalid_or_duplicate_email(client, app, sample_member, name, email):
    with app.app_context():
        db.session.add(Member(name='Other', email='other@example.com', member_id='MEMOTHER'))
        db.session.commit()
    response = client.post(f'/members/edit/{sample_member}', data={
        'name': name, 'email': email, 'phone': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        member = db.session.get(Member, sample_member)
        assert member.name == 'Test User'
        assert member.email == 'test@example.com'


def test_delete_member_keeps_other_members_issues(client, app, sample_member, sample_book):
    with app.app_context():
        other = Member(name='Other', email='other@example.com', member_id='MEMOTHER')
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    for member_id in (sample_member, sample_member, other_id):
        client.post('/issues/add', data={'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': sample_book, 'member_id': member_id})
    response = client.post(f'/members/delete/{sample_member}', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Issue.query.one().member_id == other_id
        assert db.session.get(Member, other_id) is not None
        assert db.session.get(Book, sample_book).available == 2


# ─── Issues ──────────────────────────────────────────────────────────────────

def test_issues_page(client):
    resp = client.get('/issues')
    assert resp.status_code == 200


def test_issue_book(client, app, sample_book, sample_member):
    resp = client.post('/issues/add', data={
        'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': str(sample_book),
        'member_id': str(sample_member)
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        issue = Issue.query.first()
        assert issue is not None
        assert issue.status == 'issued'
        assert issue.issue_date == datetime(2026, 10, 1)
        assert issue.due_date == datetime(2026, 11, 15)
        book = Book.query.get(sample_book)
        assert book.available == 2   # was 3, now 2


def test_return_book(client, app, sample_book, sample_member):
    client.post('/issues/add', data={
        'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': str(sample_book),
        'member_id': str(sample_member)
    })
    with app.app_context():
        issue = Issue.query.first()
        issue_id = issue.id

    resp = client.post(f'/issues/return/{issue_id}', data={'return_date': '2026-10-30'}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        issue = Issue.query.get(issue_id)
        assert issue.status == 'returned'
        assert issue.return_date == datetime(2026, 10, 30)
        book = Book.query.get(sample_book)
        assert book.available == 3   # restored


def test_api_issues(client, app, sample_book, sample_member):
    client.post('/issues/add', data={
        'issue_date': '2026-10-01', 'due_date': '2026-11-15', 'book_id': str(sample_book),
        'member_id': str(sample_member)
    })
    resp = client.get('/api/issues')
    assert resp.status_code == 200
    issues = resp.get_json()
    assert len(issues) == 1


@pytest.mark.parametrize('issue_date,due_date', [
    ('', '2026-11-15'), ('2026-10-01', ''),
    ('invalid', '2026-11-15'), ('2026-10-01', '2026-09-30'),
    ('2026-02-30', '2026-11-15')
])
def test_invalid_loan_dates_do_not_change_stock(client, app, sample_book, sample_member, issue_date, due_date):
    response = client.post('/issues/add', data={
        'book_id': sample_book, 'member_id': sample_member,
        'issue_date': issue_date, 'due_date': due_date
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Issue.query.count() == 0
        assert db.session.get(Book, sample_book).available == 3


def test_return_dates_and_repeated_return(client, app, sample_book, sample_member):
    client.post('/issues/add', data={
        'book_id': sample_book, 'member_id': sample_member,
        'issue_date': '2026-10-01', 'due_date': '2026-10-01'
    })
    with app.app_context():
        issue_id = Issue.query.one().id
    for return_date in ('', 'invalid', '2026-09-30'):
        response = client.post(f'/issues/return/{issue_id}', data={'return_date': return_date}, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            assert db.session.get(Issue, issue_id).status == 'issued'
            assert db.session.get(Book, sample_book).available == 2
    for _ in range(2):
        client.post(f'/issues/return/{issue_id}', data={'return_date': '2026-10-01'})
    with app.app_context():
        assert db.session.get(Issue, issue_id).return_date == datetime(2026, 10, 1)
        assert db.session.get(Book, sample_book).available == 3

def test_book_cover_upload_replace_public_and_remove(client,app):
    from io import BytesIO
    from PIL import Image
    from app.models import BookCover
    def picture(color):
        output=BytesIO();Image.new('RGB',(60,90),color).save(output,format='PNG');output.seek(0);return output
    response=client.post('/books/add',data={'title':'Illustrated Book','author':'Author','isbn':'COVER-1',
               'quantity':'2','cover':(picture('red'),'cover.png')},follow_redirects=True)
    assert response.status_code==200
    with app.app_context():
        book=Book.query.filter_by(isbn='COVER-1').one();book_id=book.id
        version=book.cover.version
    guest=app.test_client()
    image=guest.get(f'/covers/{book_id}')
    assert image.status_code==200 and image.mimetype=='image/jpeg'
    assert image.headers['X-Content-Type-Options']=='nosniff'
    assert f'/covers/{book_id}'.encode() in guest.get('/catalog').data
    client.post(f'/books/{book_id}/cover',data={'cover':(picture('blue'),'new.png')})
    with app.app_context():
        assert db.session.get(BookCover,book_id).version!=version
    assert guest.get(f'/covers/{book_id}').data != image.data
    client.post(f'/books/{book_id}/cover',data={'remove_cover':'1'})
    assert guest.get(f'/covers/{book_id}').status_code==404


def test_book_cover_invalid_file_does_not_create_book(client,app):
    from io import BytesIO
    for content in (b'<svg onload="alert(1)"></svg>',b'x'*(5*1024*1024+1)):
        response=client.post('/books/add',data={'title':'Bad Cover','author':'Author','isbn':'BAD-COVER',
                  'quantity':'1','cover':(BytesIO(content),'fake.jpg')},follow_redirects=True)
        assert response.status_code==200
    with app.app_context():
        assert Book.query.filter_by(isbn='BAD-COVER').count()==0


def test_book_cover_deleted_with_book_and_staff_only(client,app,sample_book):
    from app.models import BookCover
    with app.app_context():
        db.session.add(BookCover(book_id=sample_book,data=b'test-image',version='1'));db.session.commit()
    assert app.test_client().post(f'/books/{sample_book}/cover',data={'remove_cover':'1'}).status_code==302
    client.post(f'/books/delete/{sample_book}')
    with app.app_context():
        assert db.session.get(BookCover,sample_book) is None

def test_dashboard_counts_accounts_not_retained_member_profiles(client,app):
    import re
    with app.app_context():
        member=Member(name='Reader',email='countreader@example.com',member_id='COUNT-READER')
        db.session.add(member);db.session.flush()
        user=User(email=member.email,member_id=member.id,role='reader',password_hash='')
        db.session.add_all([user,
            Member(name='Archived',email='archived-99@deleted.invalid',member_id='ARCHIVED'),
            Member(name='No login',email='legacy@example.com',member_id='LEGACY')])
        db.session.commit()
        assert Member.query.count()==4
    html=client.get('/admin').text
    card=html.split('id="account-stat"',1)[1].split('icon-bg',1)[0]
    assert re.search(r'class="value">\s*2\s*</div>',card)
    assert '1 quản trị · 1 người dùng' in card
