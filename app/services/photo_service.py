import io
import os
import secrets
from urllib.parse import unquote

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 25_000_000
SIZE = 400
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS * 4          # our own 25 million pixel check runs first


class PhotoError(Exception):
    """A problem the person can fix. The message is safe to show them."""


def parse_cloudinary_url(value):
    """Reads cloudinary://API_KEY:API_SECRET@CLOUD_NAME. Returns (cloud, key, secret) or None."""
    value = (value or "").strip().strip("\"'").strip()
    if value.upper().startswith("CLOUDINARY_URL="):
        value = value.split("=", 1)[1].strip().strip("\"'").strip()
    if not value.startswith("cloudinary://"):
        return None
    rest = value[len("cloudinary://"):]
    if "@" not in rest:
        return None
    credentials, cloud = rest.rsplit("@", 1)
    if ":" not in credentials:
        return None
    key, secret = credentials.split(":", 1)
    key, secret = unquote(key), unquote(secret)
    cloud = cloud.split("/")[0].split("?")[0]
    if not (key and secret and cloud) or any(ch in key + secret + cloud for ch in "<> "):
        return None                                           # empty parts or an unfilled placeholder
    return cloud, key, secret


def storage_ready():
    return parse_cloudinary_url(os.environ.get("CLOUDINARY_URL", "")) is not None


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

    cloud, key, secret = parse_cloudinary_url(os.environ["CLOUDINARY_URL"])
    cloudinary.config(cloud_name=cloud, api_key=key, api_secret=secret, secure=True)


def upload_photo(data):
    """Stores the photo online. Returns (web address, storage id)."""
    if not storage_ready():
        print("Photo storage setting is missing or malformed (CLOUDINARY_URL).")
        raise PhotoError("Photo storage is not set up correctly. Please ask your administrator.")
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
    except Exception as exc:
        # The real reason goes to the server log (never shown to the user, never includes secrets).
        print(f"Photo upload failed: {type(exc).__name__}: {str(exc)[:300]}")
        raise PhotoError("The photo could not be uploaded right now. Please try again.")


def delete_photo(public_id):
    if not public_id or not storage_ready():
        return
    try:
        _configure()
        import cloudinary.uploader

        cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception as exc:
        print(f"Photo delete failed: {type(exc).__name__}: {str(exc)[:300]}")   # an old file left behind must never break the page