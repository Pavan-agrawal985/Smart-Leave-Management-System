import io
import os
import secrets
from urllib.parse import unquote, urlparse

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 25_000_000
SIZE = 400
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS*4


class PhotoError(Exception):
    """A problem the person can fix. The message is safe to show them."""


def storage_ready():
    return bool(os.environ.get("CLOUDINARY_URL", "").strip())


def process_image(raw):
    """Checks the file is a real photo, crops it square, shrinks it and removes hidden metadata."""
    if not raw:
        raise PhotoError("Please choose a photo.")
    if len(raw) > MAX_BYTES:
        raise PhotoError("The photo is too large. Please use one under 4 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise PhotoError("Please upload a JPG, PNG or WebP photo.")
            if source.width * source.height > MAX_PIXELS:
                raise PhotoError("The photo has too many pixels. Please use a smaller one.")
            image = ImageOps.exif_transpose(source)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
    except PhotoError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise PhotoError("That file is not a valid image.")

    image = ImageOps.fit(image, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.4))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85, optimize=True)      # re-encoding also drops EXIF data such as GPS
    return out.getvalue()


def _configure():
    import cloudinary

    parsed = urlparse(os.environ["CLOUDINARY_URL"].strip())
    cloudinary.config(
        cloud_name=parsed.hostname,
        api_key=unquote(parsed.username or ""),
        api_secret=unquote(parsed.password or ""),
        secure=True,
    )


def upload_photo(data):
    """Stores the photo online. Returns (web address, storage id)."""
    if not storage_ready():
        raise PhotoError("Photo storage is not set up yet. Please ask your administrator.")
    try:
        _configure()
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            data,
            public_id=secrets.token_urlsafe(18),             # random, so addresses cannot be guessed
            folder="leaveok/avatars",
            resource_type="image",
            overwrite=False,
            unique_filename=False,
        )
        return result["secure_url"], result["public_id"]
    except Exception:
        raise PhotoError("The photo could not be uploaded right now. Please try again.")


def delete_photo(public_id):
    if not public_id or not storage_ready():
        return
    try:
        _configure()
        import cloudinary.uploader

        cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception:
        pass                                                  # an old file left behind must never break the page