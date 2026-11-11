import pytest
from app.services.validation import check_email, check_password


@pytest.mark.parametrize("pw", ["Ravi@2026x", "Abcd@123", "Abcdefgh@1234567"])
def test_strong_passwords_pass(pw):
    assert check_password(pw) is None


@pytest.mark.parametrize("pw,word", [
    ("Ab1@", "8 to 16"),
    ("Abcdefgh@12345678", "8 to 16"),   # 17 characters
    ("", "8 to 16"),
    (None, "8 to 16"),
    ("Ravi @2026x", "spaces"),
    ("ravi@2026x", "uppercase"),
    ("RAVI@2026X", "lowercase"),
    ("Ravi@Passw", "number"),
    ("Ravi2026xyz", "special symbol"),
])
def test_weak_passwords_fail(pw, word):
    assert word in check_password(pw)


@pytest.mark.parametrize("raw", ["", "plainaddress", "user@", "@domain.com", "a b@c.com"])
def test_bad_email_syntax_rejected(raw):
    clean, error = check_email(raw)
    assert clean is None
    assert "Invalid email" in error