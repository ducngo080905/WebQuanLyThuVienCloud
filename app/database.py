"""Database configuration shared by local SQLite and hosted PostgreSQL."""
import os

from sqlalchemy.engine import make_url


def database_uri(value):
    url = make_url(value)
    if url.drivername in ('postgres', 'postgresql'):
        url = url.set(drivername='postgresql+psycopg')
    return url.render_as_string(hide_password=False)


def configure_database(app):
    configured = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', database_uri(configured) if configured else 'sqlite:///library.db')
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri(uri)
    if make_url(app.config['SQLALCHEMY_DATABASE_URI']).get_backend_name() == 'postgresql':
        if not os.environ.get('SECRET_KEY') and not app.config.get('TESTING'):
            raise RuntimeError('Set a stable SECRET_KEY environment variable before using hosted PostgreSQL.')
        app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
            'pool_pre_ping': True,
            'pool_size': 2,
            'max_overflow': 1,
            'connect_args': {'connect_timeout': 10},
        })
