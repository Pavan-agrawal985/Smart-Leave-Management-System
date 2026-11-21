import pytest
from app.services.photo_service import parse_cloudinary_url, storage_ready


@pytest.mark.parametrize("value,expected", [
    ("cloudinary://123456789012345:secretKEY-_1@mycloud", ("mycloud", "123456789012345", "secretKEY-_1")),
    ('"cloudinary://123456:abc@MyCloud"', ("MyCloud", "123456", "abc")),                 # quotes and capital letters kept
    ("CLOUDINARY_URL=cloudinary://123456:abc@mycloud", ("mycloud", "123456", "abc")),    # the name pasted in too
    ("  cloudinary://123456:abc%40d@mycloud  ", ("mycloud", "123456", "abc@d")),
])
def test_cloudinary_setting_is_read_forgivingly(value, expected):
    assert parse_cloudinary_url(value) == expected


@pytest.mark.parametrize("value", [
    "", "mycloud", "https://example.com",
    "cloudinary://<your_api_key>:<your_api_secret>@mycloud",      # placeholders left in
    "cloudinary://123456@mycloud", "cloudinary://123456:abc@", "cloudinary://:abc@mycloud",
])
def test_broken_cloudinary_settings_are_rejected(value):
    assert parse_cloudinary_url(value) is None


def test_storage_ready_follows_the_setting(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    assert storage_ready() is False
    monkeypatch.setenv("CLOUDINARY_URL", "garbage")
    assert storage_ready() is False
    monkeypatch.setenv("CLOUDINARY_URL", "cloudinary://123456:abc@mycloud")
    assert storage_ready() is True