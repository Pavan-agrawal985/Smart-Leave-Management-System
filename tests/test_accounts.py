import re
from datetime import datetime, timedelta

from app.models import User

PASSWORD = "Passw0rd!x"
NEW_PASSWORD = "Brand@2026x"


def reset_token(mail):
    return re.search(r"/reset-password/(\S+)", mail["body"]).group(1)


def ask_reset(client, email):
    return client.post("/forgot-password", data={"email": email}, follow_redirects=True)


def edit(admin, uid, **data):
    return admin.post(f"/admin/employees/{uid}/edit", data=data, follow_redirects=True)


# ---------------------------------------------------------- forgot password

def test_login_page_links_to_forgot_password(client):
    assert b"/forgot-password" in client.get("/login").data


def test_reset_email_is_sent_and_hides_whether_account_exists(client, world, outbox):
    r = ask_reset(client, "emp@alpha.io")
    assert b"If this email is registered" in r.data
    assert [m["to"] for m in outbox] == ["emp@alpha.io"]
    assert outbox[0]["subject"] == "Reset your LeaveOk password"
    outbox.clear()
    r = ask_reset(client, "ghost@nowhere.io")
    assert b"If this email is registered" in r.data        # same answer for unknown emails
    assert outbox == []


def test_reset_email_is_throttled(client, factory, world, outbox):
    ask_reset(client, "emp@alpha.io")
    ask_reset(client, "emp@alpha.io")
    assert len(outbox) == 1
    factory.update(User, world.a_emp, reset_sent_at=datetime.utcnow() - timedelta(minutes=11))
    ask_reset(client, "emp@alpha.io")
    assert len(outbox) == 2


def test_reset_changes_the_password_and_works_only_once(client, world, outbox):
    ask_reset(client, "emp@alpha.io")
    token = reset_token(outbox[0])
    assert client.get(f"/reset-password/{token}").status_code == 200

    weak = client.post(f"/reset-password/{token}", data={"password": "weak1234", "confirm": "weak1234"})
    assert b"Password needs" in weak.data
    mismatch = client.post(f"/reset-password/{token}", data={"password": NEW_PASSWORD, "confirm": "Other@2026x"})
    assert b"do not match" in mismatch.data

    ok = client.post(f"/reset-password/{token}",
                     data={"password": NEW_PASSWORD, "confirm": NEW_PASSWORD}, follow_redirects=True)
    assert b"Password changed" in ok.data

    assert client.post("/login", data={"email": "emp@alpha.io", "password": NEW_PASSWORD}).status_code == 302
    client.get("/logout")
    old = client.post("/login", data={"email": "emp@alpha.io", "password": PASSWORD})
    assert b"Invalid email or password." in old.data

    again = client.get(f"/reset-password/{token}", follow_redirects=True)     # link already used
    assert b"invalid or expired" in again.data


def test_reset_clears_lock_and_confirms_email(client, factory, world, outbox):
    factory.update(User, world.a_emp, failed_logins=3, email_verified=False,
                   locked_until=datetime.utcnow() + timedelta(minutes=10))
    ask_reset(client, "emp@alpha.io")
    client.post(f"/reset-password/{reset_token(outbox[0])}",
                data={"password": NEW_PASSWORD, "confirm": NEW_PASSWORD})
    user = factory.get(User, id=world.a_emp)
    assert user.locked_until is None and user.failed_logins == 0 and user.email_verified is True


def test_bad_or_tampered_reset_links(client, world, outbox):
    ask_reset(client, "emp@alpha.io")
    token = reset_token(outbox[0])
    for bad in ("garbage", token + "x"):
        r = client.get(f"/reset-password/{bad}", follow_redirects=True)
        assert b"invalid or expired" in r.data


def test_deactivated_user_gets_no_reset_email(client, factory, world, outbox):
    factory.update(User, world.a_emp, is_active=False)
    ask_reset(client, "emp@alpha.io")
    assert outbox == []


