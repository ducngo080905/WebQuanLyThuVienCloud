from sqlalchemy import literal
from sqlalchemy.dialects import postgresql
import pytest

from app import create_app
from app.catalog import fold, library_fold
from app.database import database_uri


@pytest.mark.parametrize('prefix', ['postgres', 'postgresql', 'postgresql+psycopg'])
def test_postgres_urls_select_psycopg(prefix):
    uri = database_uri(f'{prefix}://test:password@localhost/library?sslmode=require')
    assert uri == 'postgresql+psycopg://test:password@localhost/library?sslmode=require'


def test_database_url_is_used_and_explicit_test_config_wins(monkeypatch, tmp_path):
    uri = 'sqlite:///' + (tmp_path / 'persistent.db').as_posix()
    monkeypatch.setenv('DATABASE_URL', uri)
    application = create_app({'TESTING': True, 'SECRET_KEY': 'test-only'})
    assert application.config['SQLALCHEMY_DATABASE_URI'] == uri
    assert application.test_client().get('/catalog').status_code == 200
    isolated = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    assert isolated.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'


def test_postgres_requires_stable_session_secret(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test:password@localhost/library')
    monkeypatch.delenv('SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError, match='stable SECRET_KEY'):
        create_app()


def test_vietnamese_catalog_search_has_postgres_implementation():
    statement = library_fold(literal('Đặng Ánh'))
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert 'regexp_replace(translate(lower(' in sql
    assert 'library_fold(' not in sql
    assert fold('Đặng Ánh') == 'dang anh'
