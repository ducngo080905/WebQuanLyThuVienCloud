"""Account profile pictures, independent of messaging."""
from io import BytesIO
import secrets
from flask import Blueprint, abort, g, send_file, request, url_for
from app import db
from app.auth import login_required
from app.models import User, UserAvatar

avatars = Blueprint('avatars', __name__)


@avatars.route('/profile/avatar', methods=['POST'])
@login_required
def update_avatar():
    from flask import flash, redirect
    from app.covers import read_cover
    if request.form.get('remove') == '1':
        if g.user.avatar: db.session.delete(g.user.avatar)
        db.session.commit()
        flash('Đã xóa ảnh đại diện.', 'success')
    else:
        try:
            data = read_cover(request.files.get('avatar'))
            if not data: raise ValueError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
            from PIL import Image, ImageOps
            with Image.open(BytesIO(data)) as image:
                image = ImageOps.fit(image, (256,256))
                output = BytesIO(); image.save(output, format='JPEG', quality=85)
            avatar = g.user.avatar or UserAvatar(user=g.user)
            avatar.data = output.getvalue(); avatar.version = secrets.token_hex(8)
            db.session.add(avatar); db.session.commit()
            flash('Đã cập nhật ảnh đại diện.', 'success')
        except ValueError as error:
            flash(str(error).replace('Ảnh bìa', 'Ảnh đại diện'), 'danger')
    return redirect(url_for('auth.profile'))


@avatars.get('/profile/avatars/<int:user_id>')
@login_required
def avatar(user_id):
    if user_id != g.user.id and g.user.role != 'admin':
        abort(404)
    user = db.session.get(User, user_id)
    if not user or not user.avatar:
        abort(404)
    response = send_file(BytesIO(user.avatar.data), mimetype='image/jpeg')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response
