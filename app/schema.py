"""Small, additive upgrades for existing SQLite installations; never rebuild user tables."""
from datetime import datetime
from pathlib import Path
import sqlite3
from sqlalchemy import inspect, text
from app import db


def upgrade_schema(app):
    if db.engine.dialect.name != 'sqlite':
        return
    additions = {
        'sample_pages': [('mimetype', "VARCHAR(30) NOT NULL DEFAULT 'image/jpeg'"),
                         ('page_count', 'INTEGER NOT NULL DEFAULT 1')],
        'password_resets': [('account_guard', "VARCHAR(64) NOT NULL DEFAULT ''")],
        'mail_records': [('dispatch_key', 'VARCHAR(100)')],
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
