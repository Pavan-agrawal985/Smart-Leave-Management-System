import re
from datetime import datetime, timedelta

import pytest
from app.models import Organization, User


def post(client, url, **data):
    return client.post(url, data=data, follow_redirects=True)


def invite(admin, **over):
    data = {"name": "New Hire", "email": "hire@alpha.io", "role": "employee"}
    data.update(over)
    return post(admin, "/admin/employees", **data)


def last_invite(outbox, to):
    return [m for m in outbox if m["to"] == to and "/invite/" in m["body"]][-1]


def token_of(mail):
    return re.search(r"/invite/(\S+)", mail["body"]).group(1)


def test_admin_invites_an_employee(login_as, factory, world, outbox):
    r = invite(login_as("admin@alpha.io"), manager_id=str(world.a_mgr))
    assert b"Invitation sent to hire@alpha.io" in r.data
    user = factory.get(User, email="hire@alpha.io")
    assert (user.name, user.role, user.manager_id) == ("New Hire", "employee", world.a_mgr)
    assert user.invite_pending is True and user.email_verified is False
    mail = last_invite(outbox, "hire@alpha.io")
    assert "Alpha Corp" in mail["subject"]
    assert "New Hire" not in mail["body"]


def test_employees_page_shows_the_invited_status(login_as, world):
    admin = login_as("admin@alpha.io")
    invite(admin)
    page = admin.get("/admin/employees").data
    assert b"invited" in page and b"Resend invite" in page and b"hire@alpha.io" in page


def test_invited_person_cannot_log_in_yet(client, login_as, world):
    invite(login_as("admin@alpha.io"))
    r = client.post("/login", data={"email": "hire@alpha.io", "password": "Anything@2026"})
    assert b"Invalid email or password." in r.data


def test_employee_joins_with_their_own_details(client, login_as, factory, world, outbox):
    invite(login_as("admin@alpha.io"), name="", email="tara@alpha.io", manager_id=str(world.a_mgr))
    token = token_of(last_invite(outbox, "tara@alpha.io"))

    page = client.get(f"/invite/{token}")
    assert page.status_code == 200
    assert b"Join Alpha Corp" in page.data and b"tara@alpha.io" in page.data

    for data, message in [
        ({"name": "", "password": "Teach@2026x", "confirm": "Teach@2026x"}, b"Please enter your name."),
        ({"name": "Tara", "password": "weak1234", "confirm": "weak1234"}, b"Password needs"),
        ({"name": "Tara", "password": "Teach@2026x", "confirm": "Other@2026x"}, b"do not match"),
    ]:
        assert message in client.post(f"/invite/{token}", data=data).data
    assert factory.get(User, email="tara@alpha.io").invite_pending is True

    ok = client.post(f"/invite/{token}", follow_redirects=True,
                     data={"name": "Tara Teacher", "password": "Teach@2026x", "confirm": "Teach@2026x"})
    assert b"Your account is ready" in ok.data
    user = factory.get(User, email="tara@alpha.io")
    assert (user.name, user.invite_pending, user.email_verified, user.manager_id) == (
        "Tara Teacher", False, True, world.a_mgr)
    login_as("tara@alpha.io", "Teach@2026x")                    # can log in

    again = client.get(f"/invite/{token}", follow_redirects=True)   # the link works only once
    assert b"invalid or expired" in again.data


def test_dead_invitations_are_refused(client, login_as, factory, world, outbox):
    invite(login_as("admin@alpha.io"))
    token = token_of(last_invite(outbox, "hire@alpha.io"))
    uid = factory.get(User, email="hire@alpha.io").id
    for bad in ("garbage", token + "x"):
        assert b"invalid or expired" in client.get(f"/invite/{bad}", follow_redirects=True).data
    factory.update(User, uid, is_active=False)
    assert b"invalid or expired" in client.get(f"/invite/{token}", follow_redirects=True).data
    factory.update(User, uid, is_active=True)
    factory.update(Organization, world.a, status="suspended")
    assert b"invalid or expired" in client.get(f"/invite/{token}", follow_redirects=True).data


def test_resend_invite_is_throttled(login_as, factory, world, outbox):
    admin = login_as("admin@alpha.io")
    invite(admin)
    uid = factory.get(User, email="hire@alpha.io").id
    sent = len(outbox)
    r = admin.post(f"/admin/employees/{uid}/resend-invite", follow_redirects=True)
    assert b"wait 10 minutes" in r.data and len(outbox) == sent
    factory.update(User, uid, verification_sent_at=datetime.utcnow() - timedelta(minutes=11))
    r = admin.post(f"/admin/employees/{uid}/resend-invite", follow_redirects=True)
    assert b"Invitation sent again" in r.data and len(outbox) == sent + 1
    joined = admin.post(f"/admin/employees/{world.a_emp}/resend-invite", follow_redirects=True)
    assert b"already joined" in joined.data


def test_forgot_password_for_an_invited_person_resends_the_invitation(client, login_as, factory, world, outbox):
    invite(login_as("admin@alpha.io"))
    uid = factory.get(User, email="hire@alpha.io").id
    factory.update(User, uid, verification_sent_at=datetime.utcnow() - timedelta(minutes=11))
    outbox.clear()
    client.post("/forgot-password", data={"email": "hire@alpha.io"})
    assert len(outbox) == 1 and "/invite/" in outbox[0]["body"] and "reset-password" not in outbox[0]["body"]


@pytest.mark.parametrize("over,message", [
    ({"email": "nope"}, b"Invalid email"),
    ({"email": "emp@alpha.io"}, b"Email already registered."),
    ({"name": "x" * 101}, b"Name is too long."),
])
def test_invitation_rules(login_as, factory, world, outbox, over, message):
    before = factory.count(User)
    assert message in invite(login_as("admin@alpha.io"), **over).data
    assert factory.count(User) == before
    assert outbox == []


def test_roles_and_managers_are_checked(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    invite(admin, email="x1@alpha.io", role="org_admin")
    invite(admin, email="x2@alpha.io", role="manager")
    invite(admin, email="x3@alpha.io", manager_id=str(world.b_admin))     # a manager from another organization
    invite(admin, email="x4@alpha.io", manager_id=str(world.a_emp))       # an employee cannot be a manager
    assert factory.get(User, email="x1@alpha.io").role == "employee"
    assert factory.get(User, email="x2@alpha.io").role == "manager"
    assert factory.get(User, email="x3@alpha.io").manager_id is None
    assert factory.get(User, email="x4@alpha.io").manager_id is None


def test_only_the_org_admin_can_invite_or_resend(login_as, factory, world):
    assert login_as("emp@alpha.io").post("/admin/employees", data={"email": "z@alpha.io"}).status_code == 403
    invite(login_as("admin@alpha.io"))
    uid = factory.get(User, email="hire@alpha.io").id
    assert login_as("admin@beta.io").post(f"/admin/employees/{uid}/resend-invite").status_code == 404
    assert login_as("mgr@alpha.io").post(f"/admin/employees/{uid}/resend-invite").status_code == 403