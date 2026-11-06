from flask import Flask
import os
import secrets
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app(config=None):
    app = Flask(__name__)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    secret_path = Path(app.instance_path) / 'session-secret'
    if not secret_path.exists():
        try:
            with secret_path.open('x') as secret_file:
                secret_file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secret_path.read_text()
    app.config.update(SESSION_COOKIE_NAME='library_session', SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
                      WTF_CSRF_ENABLED=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
    app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID',
        '396585905684-36hsg5h1qha05teg5jgprvir546d8b40.apps.googleusercontent.com')

    if config:
        app.config.update(config)

    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    from app.auth import auth, install_auth
    app.register_blueprint(auth)
    install_auth(app)
    from app.google_login import google_auth, google_context
    app.register_blueprint(google_auth)
    app.context_processor(google_context)
    from app.activity import activity, install_activity
    app.register_blueprint(activity)
    install_activity(app)
    from app.features import features, install_features
    app.register_blueprint(features)
    install_features(app)

    @app.errorhandler(413)
    def upload_too_large(error):
        from flask import flash, redirect, url_for
        flash('Tệp tải lên quá lớn. Tổng tệp tối đa 32 MB; ảnh tối đa 5 MB, PDF đọc thử tối đa 10 MB.', 'danger')
        return redirect(url_for('main.books'), code=303)

    with app.app_context():
        db.create_all()
        from app.schema import upgrade_schema
        upgrade_schema(app)
        from app.models import User
        if not User.query.filter_by(role='admin').first():
            setup_path = Path(app.instance_path) / 'setup-token'
            if not setup_path.exists():
                setup_path.write_text(secrets.token_urlsafe(32))
            app.config['SETUP_TOKEN'] = setup_path.read_text().strip()

    return app
