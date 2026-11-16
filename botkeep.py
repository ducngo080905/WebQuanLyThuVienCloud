"""Botkeep Python profile entrypoint: python botkeep.py (Linux)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def configure():
    # Botkeep can store panel Environment values in a managed .env file.
    # Actual runtime environment variables take precedence over that file.
    load_dotenv(ROOT / '.env', override=False)
    value = os.environ.get('SERVER_PORT', '')
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise RuntimeError('Set SERVER_PORT to the assigned port shown in Botkeep Network.')
    if not os.environ.get('SECRET_KEY'):
        raise RuntimeError('Set a stable SECRET_KEY in Botkeep Environment before starting.')
    if not (os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')):
        raise RuntimeError('Set the existing Neon DATABASE_URL in Botkeep Environment before starting.')
    os.environ['BIND'] = f'0.0.0.0:{int(value)}'
    os.environ.setdefault('WEB_CONCURRENCY', '1')
    os.environ.setdefault('WEB_THREADS', '2')
    os.environ.setdefault('COOKIE_SECURE', '1')


def main():
    configure()
    os.chdir(ROOT)
    # Import only when starting: Gunicorn runs on the Linux hosting runtime.
    from gunicorn.app.wsgiapp import WSGIApplication
    WSGIApplication(prog='gunicorn').run()


if __name__ == '__main__':
    import sys
    sys.argv = [sys.argv[0], '-c', str(ROOT / 'gunicorn.conf.py'), 'run:app']
    main()
