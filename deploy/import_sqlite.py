"""Copy a local SQLite snapshot into an empty PostgreSQL database."""
import argparse
import os
from pathlib import Path
import sys
import ssl

from sqlalchemy import Integer, create_engine, inspect, select, text
from sqlalchemy.engine import URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.database import database_uri
from app import models  # Register the tables used by both engines.


def import_database(source_path, destination_uri, apply=False):
    source_path = Path(source_path).resolve(strict=True)
    source = create_engine(URL.create('sqlite', database='file:' + source_path.as_posix(),
                                     query={'mode': 'ro', 'uri': 'true'}))
    uri = database_uri(destination_uri)
    options = {'connect_timeout': 10}
    if uri.startswith('postgresql+pg8000:'):
        options = {'timeout': 30, 'ssl_context': ssl.create_default_context()}
    destination = create_engine(uri, connect_args=options)
    if destination.dialect.name != 'postgresql':
        raise ValueError('The destination must be PostgreSQL.')
    counts = {}
    try:
        with source.connect() as reader, destination.connect() as writer:
            reader.exec_driver_sql('BEGIN')
            transaction = writer.begin()
            try:
                writer.execute(text('SELECT pg_advisory_xact_lock(715730219)'))
                db.metadata.create_all(bind=writer)
                tables = db.metadata.sorted_tables
                for table in tables:
                    if writer.execute(select(table).limit(1)).first() is not None:
                        raise ValueError('Destination contains data. Import requires an empty database.')
                available = set(inspect(reader).get_table_names())
                for table in tables:
                    if table.name not in available:
                        continue
                    rows = reader.execute(select(table).order_by(*table.primary_key.columns))
                    counts[table.name] = 0
                    while batch := rows.fetchmany(100):
                        writer.execute(table.insert().values([dict(row._mapping) for row in batch]))
                        counts[table.name] += len(batch)
                    for column in table.primary_key.columns:
                        if not apply or len(table.primary_key.columns) != 1 or not isinstance(column.type, Integer):
                            continue
                        sequence = writer.execute(text('SELECT pg_get_serial_sequence(:table, :column)'),
                                                  {'table': table.name, 'column': column.name}).scalar()
                        if sequence:
                            maximum = writer.execute(select(db.func.max(column))).scalar()
                            writer.execute(text('SELECT setval(CAST(:sequence AS regclass), :value, :used)'),
                                           {'sequence': sequence, 'value': maximum or 1, 'used': maximum is not None})
                if apply:
                    transaction.commit()
                else:
                    transaction.rollback()
            except Exception:
                transaction.rollback()
                raise
            finally:
                reader.rollback()
    finally:
        source.dispose()
        destination.dispose()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--apply', action='store_true', help='Commit the import. Omit to validate and roll back.')
    args = parser.parse_args()
    destination = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if not destination:
        parser.error('Set DATABASE_URL or POSTGRES_URL in the environment.')
    try:
        counts = import_database(args.source, destination, args.apply)
    except Exception:
        # Connection exceptions can contain credentials or user rows. Do not echo them.
        print('Import failed. The destination transaction was rolled back. Check connectivity, schema and source integrity.', file=sys.stderr)
        return 1
    print('Import committed.' if args.apply else 'Validation succeeded. Changes rolled back.')
    for name, count in counts.items():
        print(f'{name} {count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
