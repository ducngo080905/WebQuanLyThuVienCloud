"""Live account presence only; no activity timeline or event recording."""
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from flask import Blueprint, abort, g, jsonify, redirect, request, session, url_for
from app import db
from app.models import User, LivePresence
from app.auth import login_required

activity = Blueprint('activity', __name__)


def device_name(agent):
    os_name = ('iPhone / iPad' if re.search(r'iphone|ipad',agent,re.I) else
               'Android' if 'Android' in agent else 'Windows' if 'Windows' in agent else
               'macOS' if 'Macintosh' in agent else 'Linux' if 'Linux' in agent else 'Thiết bị khác')
    browser = ('Edge' if 'Edg/' in agent else 'Opera' if 'OPR/' in agent else
               'Firefox' if 'Firefox/' in agent else 'Chrome' if 'Chrome/' in agent or 'CriOS/' in agent else
               'Safari' if 'Safari/' in agent else 'Trình duyệt khác')
    return f'{os_name} · {browser}'


def install_activity(app):
    @app.after_request
    def close_logged_out_sessions(response):
        if request.endpoint == 'auth.logout' and g.get('user') and not session.get('user_id'):
            key = g.get('activity_logout_session')
            if key:
                LivePresence.query.filter_by(user_id=g.user.id, session_key=key).update({'closed':True})
                db.session.commit()
        return response


@activity.post('/activity/heartbeat')
@login_required
def heartbeat():
    tab = request.form.get('tab_id', '')
    if not re.fullmatch(r'[a-f0-9]{32}', tab):
        abort(400)
    if 'presence_session' not in session:
        session['presence_session'] = secrets.token_hex(24)
    key = session['presence_session']
    identifier = hashlib.sha256((key+':'+tab).encode()).hexdigest()
    row = db.session.get(LivePresence, identifier)
    if not row:
        row = LivePresence(id=identifier, user_id=g.user.id, session_key=key)
        db.session.add(row)
    row.last_seen = datetime.utcnow()
    row.visible = request.form.get('visible') == '1'
    row.closed = request.form.get('closed') == '1'
    row.device = device_name(request.headers.get('User-Agent', ''))
    # Trust only the socket peer, never an arbitrary X-Forwarded-For header.
    row.ip = (request.remote_addr or 'Không xác định')[:45]
    db.session.commit()
    return '', 204


@activity.get('/admin/accounts/presence')
@login_required
def account_presence():
    if g.user.role != 'admin':
        abort(403)
    now = datetime.utcnow()
    cutoff = now-timedelta(seconds=45)
    users = User.query.all()
    presences = LivePresence.query.order_by(LivePresence.last_seen.desc()).all()
    grouped = {}
    for row in presences:
        grouped.setdefault(row.user_id, []).append(row)
    result = []
    for user in users:
        rows = grouped.get(user.id, [])
        live = [row for row in rows if not row.closed and row.last_seen >= cutoff] if user.active else []
        devices = []
        seen = set()
        for row in live or rows[:1]:
            identity = (row.device,row.ip)
            if identity not in seen:
                seen.add(identity)
                devices.append({'name':row.device,'ip':row.ip})
        result.append({'id':user.id,'online':bool(live),'viewing':any(row.visible for row in live),
                       'last_seen':rows[0].last_seen.isoformat()+'Z' if rows else None,
                       'devices':devices,'active':user.active})
    response = jsonify({'accounts':result, 'updated_at':now.isoformat()+'Z'})
    response.headers['Cache-Control'] = 'no-store'
    return response


@activity.get('/admin/activity')
@login_required
def dashboard():
    if g.user.role != 'admin':
        abort(403)
    return redirect(url_for('auth.accounts'))
