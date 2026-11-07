"""Linux production entrypoint: gunicorn -c gunicorn.conf.py run:app."""
import os
bind = os.environ.get('BIND', '0.0.0.0:5000')
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
worker_class = 'gthread'
threads = int(os.environ.get('WEB_THREADS', '4'))
timeout = 60
graceful_timeout = 45
keepalive = 5
preload_app = True
accesslog = '-'
errorlog = '-'
