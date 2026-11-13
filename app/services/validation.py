import re
from email_validator import validate_email, EmailNotValidError


def check_email(raw):
    """Returns (clean_email, error). Checks format AND that the domain can receive mail."""
    try:
        result = validate_email((raw or "").strip(), check_deliverability=True)
        return result.normalized.lower(), None
    except EmailNotValidError as exc:
        return None, f"Invalid email: {exc}"


def check_password(pw):
    """Returns an error message, or None if the password is strong enough."""
    pw = pw or ""
    if not 8 <= len(pw) <= 16:
        return "Password must be 8 to 16 characters long."
    if " " in pw:
        return "Password cannot contain spaces."
    if not re.search(r"[a-z]", pw):
        return "Password needs at least one lowercase letter."
    if not re.search(r"[A-Z]", pw):
        return "Password needs at least one uppercase letter."
    if not re.search(r"[0-9]", pw):
        return "Password needs at least one number."
    if not re.search(r"[^A-Za-z0-9]", pw):
        return "Password needs at least one special symbol, like @ # $ % !"
    return None

def owner_password_error(pw):
    """The owner account is more powerful, so its password rules are stricter."""
    pw = pw or ""
    if not 12 <= len(pw) <= 72 or len(pw.encode("utf-8")) > 72:
        return "The owner password must be 12 to 72 characters long."
    if " " in pw:
        return "The owner password cannot contain spaces."
    if not re.search(r"[a-z]", pw):
        return "The owner password needs a lowercase letter."
    if not re.search(r"[A-Z]", pw):
        return "The owner password needs an uppercase letter."
    if not re.search(r"[0-9]", pw):
        return "The owner password needs a number."
    if not re.search(r"[^A-Za-z0-9]", pw):
        return "The owner password needs a special symbol."
    return None