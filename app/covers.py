from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_COVER_BYTES = 5 * 1024 * 1024


def read_cover(upload):
    if not upload or not upload.filename:
        return None
    content = upload.stream.read(MAX_COVER_BYTES + 1)
    if len(content) > MAX_COVER_BYTES:
        raise ValueError('Ảnh bìa tối đa 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP.')
                if image.width * image.height > 20_000_000:
                    raise ValueError('Ảnh quá lớn. Vui lòng chọn ảnh dưới 20 triệu điểm ảnh.')
                image.load()
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1200,1600))
                if image.mode in ('RGBA','LA') or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    output_image = Image.new('RGB', rgba.size, 'white')
                    output_image.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    output_image = image.convert('RGB')
                output = BytesIO()
                output_image.save(output,format='JPEG',quality=85,optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Tệp ảnh không hợp lệ hoặc bị hỏng. Chọn ảnh JPG, PNG hoặc WebP khác.') from None
