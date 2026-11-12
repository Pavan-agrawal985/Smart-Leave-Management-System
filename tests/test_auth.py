from datetime import datetime, timedelta

import pytest
from app.models import Organization, User, LeaveType

PASSWORD = "Passw0rd!x"
STRONG = "Strong@2026x"


def signup(client, **over):
    data = {"org_name": "Green Valley School", "org_type": "school",
            "name": "Priya Principal", "email": "principal@gv.in", "password": STRONG}
    data.update(over)
    return client.post("/register", data=data)


def test_signup_creates_pending_org_and_unverified_admin(client, factory, outbox):
    r = signup(client, email="Principal@GV.in")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    org = factory.get(Organization, name="Green Valley School")
    assert org.status == "pending"
    assert org.weekend_days == "6"
    assert factory.count(LeaveType, organization_id=org.id) > 0
    user = factory.get(User, email="principal@gv.in")           # stored in lowercase
    assert user.role == "org_admin" and user.email_verified is False
    assert user.password_hash != STRONG and user.password_hash.startswith("$2")
    assert len(outbox) == 1 and outbox[0]["to"] == "principal@gv.in"


def test_owner_email_signup_is_active_immediately(client, factory):
    signup(client, email="owner@acme.io")
    assert factory.get(Organization, name="Green Valley School").status == "active"


@pytest.mark.parametrize("over,message", [
    ({"password": "ravi1234"}, b"Password needs"),
    ({"password": "Ab1@"}, b"8 to 16"),
    ({"email": "not-an-email"}, b"Invalid email"),
    ({"org_name": ""}, b"All fields are required."),
    ({"name": ""}, b"All fields are required."),
])
def test_signup_rules(client, factory, over, message):
    r = signup(client, **over)
    assert r.status_code == 200 and message in r.data
    assert factory.count(User) == 0 and factory.count(Organization) == 0


def test_duplicate_email_rejected(client, factory):
    signup(client)
    r = signup(client, org_name="Another School")
    assert b"Email already registered." in r.data
    assert factory.count(Organization) == 1


def test_login_blocked_until_email_verified(client, factory):
    org = factory.org(status="active")
    factory.user(org, "a@alpha.io", verified=False)
    r = client.post("/login", data={"email": "a@alpha.io", "password": PASSWORD})
    assert r.status_code == 200
    assert b"verify your email first" in r.data and b"Resend verification email" in r.data


def test_verification_link_verifies_email(client, factory, outbox, token_in):
    signup(client)
    r = client.get("/verify/" + token_in(outbox[-1]), follow_redirects=True)
    assert b"Email verified" in r.data
    assert factory.get(User, email="principal@gv.in").email_verified is True


def test_bad_and_tampered_links_do_nothing(client, factory, outbox, token_in):
    signup(client)
    token = token_in(outbox[-1])
    for bad in ("garbage", token + "x"):
        r = client.get("/verify/" + bad, follow_redirects=True)
        assert b"invalid or expired" in r.data
    assert factory.get(User, email="principal@gv.in").email_verified is False


def test_pending_org_cannot_log_in_even_after_verifying(client, factory, outbox, token_in):
    signup(client)
    client.get("/verify/" + token_in(outbox[-1]))
    r = client.post("/login", data={"email": "principal@gv.in", "password": STRONG})
    assert b"waiting for approval" in r.data


def test_rejected_org_cannot_log_in(client, factory):
    org = factory.org(status="rejected")
    factory.user(org, "a@alpha.io")
    r = client.post("/login", data={"email": "a@alpha.io", "password": PASSWORD})
    assert b"not approved" in r.data


def test_wrong_password_and_unknown_email(client, world):
    for email, pw in (("emp@alpha.io", "Wrong@2026x"), ("nobody@alpha.io", PASSWORD)):
        r = client.post("/login", data={"email": email, "password": pw})
        assert b"Invalid email or password." in r.data


def test_login_is_case_insensitive_and_logout_works(login_as, world):
    browser = login_as("EMP@ALPHA.IO")
    assert browser.get("/dashboard").status_code == 200
    browser.get("/logout")
    r = browser.get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_resend_is_throttled_to_one_per_ten_minutes(client, factory, outbox):
    signup(client)                                             # email 1
    client.post("/resend-verification", data={"email": "principal@gv.in"})
    assert len(outbox) == 1                                    # throttled
    user_id = factory.get(User, email="principal@gv.in").id
    factory.update(User, user_id, verification_sent_at=datetime.utcnow() - timedelta(minutes=11))
    client.post("/resend-verification", data={"email": "principal@gv.in"})
    assert len(outbox) == 2


def test_resend_does_not_reveal_which_emails_exist(client, outbox):
    r = client.post("/resend-verification", data={"email": "ghost@nowhere.io"}, follow_redirects=True)
    assert b"If this account needs verification" in r.data
    assert outbox == []

def wrong(client, times):
    for _ in range(times):
        client.post("/login", data={"email": "emp@alpha.io", "password": "Wrong@2026x"})


def test_account_locks_after_five_wrong_passwords(client, world):
    wrong(client, 5)
    r = client.post("/login", data={"email": "emp@alpha.io", "password": PASSWORD})
    assert b"Too many failed attempts" in r.data           # even the right password is refused


def test_lock_expires_and_success_resets_counter(client, factory, world):
    wrong(client, 5)
    factory.update(User, world.a_emp, locked_until=datetime.utcnow() - timedelta(minutes=1))
    ok = client.post("/login", data={"email": "emp@alpha.io", "password": PASSWORD})
    assert ok.status_code == 302                            # allowed again
    client.get("/logout")
    wrong(client, 4)                                        # counter started from zero
    assert client.post("/login", data={"email": "emp@alpha.io", "password": PASSWORD}).status_code == 302


def test_four_wrong_attempts_do_not_lock(client, world):
    wrong(client, 4)
    assert client.post("/login", data={"email": "emp@alpha.io", "password": PASSWORD}).status_code == 302