import gzip
import re
from datetime import datetime
from contextlib import contextmanager
import pytest
from sqlalchemy import event
from flask import url_for
from app import create_app, db
from app.auth import account_guard
from app.models import User, Member, Book, Issue


@pytest.fixture
def performance_app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                      'SECRET_KEY': 'performance-tests', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        member = Member(name='Admin', email='perf@example.com', member_id='PERF')
        user = User(email=member.email, password_hash='test-only-not-a-password', role='admin', member=member)
        db.session.add(user); db.session.commit()
        client = app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = user.id
            session['account_guard'] = account_guard(user)
        db.session.remove()
        yield app, client
        db.session.remove(); db.drop_all()


@contextmanager
def queries():
    statements = []
    def track(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(db.engine, 'before_cursor_execute', track)
    try:
        yield statements
    finally:
        event.remove(db.engine, 'before_cursor_execute', track)


def test_public_assets_skip_auth_database_and_use_fingerprints(performance_app):
    app, client = performance_app
    with app.test_request_context():
        asset = url_for('static', filename='library.css')
    with queries() as statements:
        response = client.get(asset)
    assert not statements
    assert response.status_code == 200
    assert 'immutable' in response.headers['Cache-Control']
    assert response.cache_control.max_age == 31536000
    assert 'Set-Cookie' not in response.headers
    assert client.get('/static/missing.css').status_code == 404
    assert 'immutable' not in client.get('/static/missing.css').headers.get('Cache-Control', '')


def test_catalog_queries_do_not_grow_per_book(performance_app):
    app, client = performance_app
    def measure():
        db.session.remove()
        with queries() as statements:
            response = client.get('/catalog')
        assert response.status_code == 200
        assert not any('FROM issues' in sql and 'count(' not in sql.lower() and 'WHERE' not in sql for sql in statements)
        return len(statements)
    base = measure()
    db.session.add_all([Book(title=f'Volume {i}', author='Author', isbn=f'volume-{i}', quantity=1, available=1) for i in range(100)])
    db.session.commit()
    assert measure() <= base + 1


def test_gzip_keeps_html_private_and_preserves_content(performance_app):
    app, client = performance_app
    plain = client.get('/accounts')
    compressed = client.get('/accounts', headers={'Accept-Encoding': 'gzip'})
    assert compressed.headers['Content-Encoding'] == 'gzip'
    assert compressed.headers['Cache-Control'] == 'no-store'
    assert 'Accept-Encoding' in compressed.headers['Vary']
    assert gzip.decompress(compressed.data) == plain.data
    assert len(compressed.data) < len(plain.data) // 2
    rejected = client.get('/accounts', headers={'Accept-Encoding':'gzip;q=0, identity;q=1'})
    assert 'Content-Encoding' not in rejected.headers


def test_fonts_are_local_and_content_addressed(performance_app):
    app, client = performance_app
    page = client.get('/catalog').text
    assert 'fonts.googleapis.com' not in page
    assert 'fonts/fonts.css?rev=' in page
    font_css = client.get('/static/fonts/fonts.css').text
    for filename in set(re.findall(r'url\(([^)]+)\)', font_css)):
        response = client.get('/static/fonts/' + filename)
        assert response.status_code == 200
        assert 'immutable' in response.headers['Cache-Control']


def test_statistics_use_sql_counts_and_keep_overdue_correct(performance_app):
    app, client = performance_app
    book = Book(title='Statistics Book', author='Author', isbn='stats', quantity=2, available=1)
    member = Member(name='Reader',email='stats@example.com',member_id='STATS')
    db.session.add_all([Issue(book=book,member=member,status='issued',due_date=datetime(2020,1,1)),
                        Issue(book=book,member=member,status='returned',due_date=datetime(2020,1,1))])
    db.session.commit();db.session.remove()
    with app.test_request_context('/admin'):
        from flask import g
        from app.routes import interface_stats
        g.user = None
        with queries() as statements:
            stats = interface_stats()['ui_stats']
        assert len(statements) == 1
        assert stats == dict(total=2,active=1,returned=1,overdue=1,borrowers=1,overdue_members=1,active_percent=50)


def test_missing_setting_is_read_once_per_request(performance_app):
    app, client = performance_app
    from app.features import setting
    with app.test_request_context('/profile'):
        with queries() as statements:
            for _ in range(25):
                assert setting('missing-rate', 12) == 12
        assert len(statements) == 1


def test_rendered_static_asset_urls_retain_valid_cache_versions(performance_app):
    from html import unescape
    app, client = performance_app
    page=client.get('/').text
    for url in set(re.findall(r'(?:href|src)="(/static/[^"]+)"',page)):
        response=client.get(unescape(url))
        assert response.status_code==200
        assert 'immutable' in response.headers['Cache-Control'],url
