"""Release detection and persistent server-enforced maintenance mode."""
import hashlib
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for
from app import db
from app.models import LibrarySetting

operations=Blueprint('operations',__name__)


def maintenance_enabled():
    # A scalar SELECT avoids ORM identity-map staleness across workers/requests.
    return db.session.query(LibrarySetting.value).filter_by(key='maintenance_enabled').scalar()==1


VIETNAM_TIME = timezone(timedelta(hours=7))
END_KEY = 'maintenance_end_minute'
DEADLINE_KEY = 'maintenance_deadline'


def maintenance_end():
    if not g.get('maintenance_enabled'):
        return None
    settings = dict(db.session.query(LibrarySetting.key, LibrarySetting.value)
                    .filter(LibrarySetting.key.in_((END_KEY, DEADLINE_KEY))).all())
    timestamp = settings.get(DEADLINE_KEY, settings.get(END_KEY, 0) * 60)
    return datetime.fromtimestamp(timestamp, VIETNAM_TIME) if timestamp else None


def write_setting(key, value):
    row = db.session.get(LibrarySetting, key)
    if row is None:
        db.session.add(LibrarySetting(key=key, value=value))
    else:
        row.value = value


def maintenance_response():
    if request.method!='GET' or request.path.startswith('/api/') or request.accept_mimetypes.best=='application/json':
        response=jsonify(error='Thư viện đang bảo trì. Vui lòng quay lại sau.',maintenance=True)
        response.status_code=503
    else:
        response=current_app.make_response((render_template('maintenance.html'),503))
    response.headers['Cache-Control']='no-store'
    response.headers['Retry-After']='60'
    response.headers['X-Library-Maintenance']='1'
    return response


def maintenance_gate():
    if request.endpoint in ('static','main.health'):return None
    enabled=maintenance_enabled();g.maintenance_enabled=enabled
    if not enabled or (g.get('user') and g.user.role=='admin'):return None
    if request.endpoint in ('operations.status','operations.page','auth.login','auth.logout','google_auth.sign_in'):return None
    return maintenance_response()


def install_operations(app):
    digest=hashlib.sha256()
    root=Path(app.root_path)
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix in ('.py','.html','.css','.js','.woff2'):
            digest.update(str(path.relative_to(root)).encode());digest.update(path.read_bytes())
    app.config.setdefault('APP_VERSION',os.environ.get('APP_VERSION') or digest.hexdigest()[:16])
    @app.context_processor
    def operations_context():
        end = maintenance_end()
        return {
                'maintenance_end_label':end.strftime('%H:%M · %d/%m/%Y') if end else '',
                'app_version':app.config['APP_VERSION'],'maintenance_active':bool(g.get('maintenance_enabled',False))}


@operations.get('/system/status')
def status():
    end = maintenance_end()
    response=jsonify(remaining_seconds=max(0, int(end.timestamp()) - int(time.time())) if end else None,
                     expected_end=end.strftime('%H:%M · %d/%m/%Y') if end else '',maintenance=bool(g.get('maintenance_enabled')),admin=bool(g.get('user') and g.user.role=='admin'),version=current_app.config['APP_VERSION'])
    response.headers['Cache-Control']='no-store'
    return response


@operations.get('/maintenance')
def page():
    if g.get('maintenance_enabled') or (g.get('user') and g.user.role=='admin' and request.args.get('preview')=='1'):
        return maintenance_response()
    return redirect(url_for('auth.library_home'))


@operations.post('/admin/maintenance')
def toggle():
    if not g.get('user') or g.user.role!='admin':abort(403)
    value=request.form.get('enabled')
    if value not in ('0','1'):abort(400)
    editing = request.form.get('update_schedule') == '1'
    if editing:
        if not g.get('maintenance_enabled'):
            abort(409)
        value = '1'
    deadline = 0
    duration = request.form.get('duration_hours', '').strip()
    raw_end = request.form.get('expected_end', '').strip()
    if value == '1' and (duration or raw_end):
        try:
            if duration:
                hours = float(duration.replace(',', '.'))
                if not 1 / 3600 <= hours <= 720:
                    raise ValueError
                deadline = int(time.time()) + round(hours * 3600)
            else:
                end = datetime.strptime(raw_end, '%Y-%m-%dT%H:%M').replace(tzinfo=VIETNAM_TIME)
                if end <= datetime.now(VIETNAM_TIME):
                    raise ValueError
                deadline = int(end.timestamp())
        except (ValueError, OverflowError, OSError):
            message = 'Nhập số giờ bảo trì lớn hơn 0 và tối đa 720 giờ.' if duration else 'Thời điểm mở lại dự kiến phải nằm trong tương lai.'
            if request.accept_mimetypes.best == 'application/json':
                return jsonify(error=message), 400
            flash(message, 'danger')
            return redirect(url_for('main.index'), code=303)
    if not editing:
        write_setting('maintenance_enabled', int(value))
    write_setting(DEADLINE_KEY, deadline)
    db.session.commit()
    if request.accept_mimetypes.best=='application/json':return jsonify(ok=True,maintenance=value=='1')
    return redirect(url_for('main.index'),code=303)
