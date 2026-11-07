"""Small, additive upgrades for existing SQLite installations; never rebuild user tables."""
from datetime import datetime
from pathlib import Path
import sqlite3
from sqlalchemy import inspect, text
from app import db


def upgrade_schema(app):
    if db.engine.dialect.name != 'sqlite':
        return
    upgrade_chat_threads()
    additions = {
        'chat_messages': [('reply_id', 'INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL'),
                          ('edited_at', 'DATETIME'), ('deleted_at', 'DATETIME')],
        'sample_pages': [('mimetype', "VARCHAR(30) NOT NULL DEFAULT 'image/jpeg'"),
                         ('page_count', 'INTEGER NOT NULL DEFAULT 1')],
        'password_resets': [('account_guard', "VARCHAR(64) NOT NULL DEFAULT ''")],
        'mail_records': [('dispatch_key', 'VARCHAR(100)')],
        'announcements': [('color', "VARCHAR(7) NOT NULL DEFAULT '#1b3885'"),
                          ('expires_at', 'DATETIME')],
        'renewal_requests': [('requested_days', 'INTEGER NOT NULL DEFAULT 7'),
                             ('approved_days', 'INTEGER')],
    }
    inspector=inspect(db.engine)
    changes=[]
    for table,columns in additions.items():
        if not inspector.has_table(table): continue
        existing={column['name'] for column in inspector.get_columns(table)}
        changes.extend((table,name,declaration) for name,declaration in columns if name not in existing)
    if not changes: return
    database=db.engine.url.database
    if database and database!=':memory:':
        backup=Path(database).parent/('schema-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
        with sqlite3.connect(database) as source,sqlite3.connect(backup) as target:
            source.backup(target)
    with db.engine.begin() as connection:
        for table,name,declaration in changes:
            connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {declaration}'))
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_dispatch_key ON mail_records(dispatch_key)'))


def upgrade_chat_threads():
    """Allow group threads with no direct-message pair, preserving every existing ID."""
    inspector = inspect(db.engine)
    if not inspector.has_table('chat_threads'):
        return
    columns = {column['name']: column for column in inspector.get_columns('chat_threads')}
    if columns['low_id']['nullable'] and columns['high_id']['nullable']:
        return
    database = db.engine.url.database
    if database and database != ':memory:':
        backup = Path(database).parent/('schema-backup-groups-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
        with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
    from sqlalchemy import MetaData
    from sqlalchemy.schema import CreateTable, CreateIndex
    from app.models import ChatThread, User
    metadata = MetaData()
    User.__table__.to_metadata(metadata)
    replacement = ChatThread.__table__.to_metadata(metadata, name='chat_threads_group_upgrade')
    names = ', '.join('"'+column.name+'"' for column in ChatThread.__table__.columns)
    with db.engine.connect() as connection:
        foreign_keys = connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
        connection.commit()
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        connection.commit()
        try:
            with connection.begin():
                connection.exec_driver_sql('BEGIN IMMEDIATE')
                connection.execute(CreateTable(replacement))
                connection.exec_driver_sql(f'INSERT INTO chat_threads_group_upgrade ({names}) SELECT {names} FROM chat_threads')
                connection.exec_driver_sql('DROP TABLE chat_threads')
                connection.exec_driver_sql('ALTER TABLE chat_threads_group_upgrade RENAME TO chat_threads')
                for index in ChatThread.__table__.indexes:
                    connection.execute(CreateIndex(index))
        finally:
            connection.exec_driver_sql('PRAGMA foreign_keys='+str(int(foreign_keys)))
            connection.commit()
