"""Public asset caching and transport compression; never cache account HTML."""
import gzip
import hashlib
from pathlib import Path
from flask import request


def install_performance(app):
    root = Path(app.static_folder)
    versions = {str(path.relative_to(root)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()[:12]
                for path in root.rglob('*') if path.is_file()}

    @app.url_defaults
    def version_asset(endpoint, values):
        if endpoint == 'static' and values.get('filename') in versions:
            values['rev'] = versions[values['filename']]

    @app.after_request
    def optimize_response(response):
        if request.endpoint == 'static':
            # Only fingerprinted, public static files get long caching. No user media.
            filename = request.view_args.get('filename')
            fingerprinted = versions.get(filename) and (request.args.get('rev') == versions[filename] or (filename.endswith('.woff2') and versions[filename] in filename))
            if response.status_code in (200, 304) and fingerprinted:
                response.cache_control.public = True
                response.cache_control.max_age = 31536000
                response.cache_control.immutable = True
            return response
        if response.status_code != 200 or response.is_streamed or response.direct_passthrough:
            return response
        if response.mimetype not in ('text/html', 'application/json', 'text/css', 'text/javascript', 'application/javascript'):
            return response
        response.vary.add('Accept-Encoding')
        if request.accept_encodings['gzip'] <= 0 or response.headers.get('Content-Encoding') or response.headers.get('Content-Range'):
            return response
        content = response.get_data()
        if len(content) < 2048:
            return response
        compressed = gzip.compress(content, compresslevel=5, mtime=0)
        if len(compressed) < len(content):
            response.set_data(compressed)
            response.headers['Content-Encoding'] = 'gzip'
        return response
