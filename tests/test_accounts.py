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


# ------------------------------------------------------ people management

def test_admin_changes_role_and_manager(login_as, factory, world):
    r = edit(login_as("admin@alpha.io"), world.a_emp, role="manager", manager_id=str(world.a_admin))
    assert b"Employee updated." in r.data
    user = factory.get(User, id=world.a_emp)
    assert (user.role, user.manager_id) == ("manager", world.a_admin)


def test_unknown_role_is_ignored(login_as, factory, world):
    edit(login_as("admin@alpha.io"), world.a_emp, role="org_admin", manager_id="")
    assert factory.get(User, id=world.a_emp).role == "employee"


def test_admin_accounts_cannot_be_edited_or_deactivated(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    assert b"Admin accounts cannot be changed here." in edit(admin, world.a_admin, role="employee").data
    r = admin.post(f"/admin/employees/{world.a_admin}/status/deactivate", follow_redirects=True)
    assert b"cannot be deactivated" in r.data
    assert factory.get(User, id=world.a_admin).is_active is True


def test_no_reporting_loops(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    edit(admin, world.a_emp, role="manager", manager_id=str(world.a_mgr))     # Zelda reports to Maya
    r = edit(admin, world.a_mgr, role="manager", manager_id=str(world.a_emp))  # Maya -> Zelda: a loop
    assert b"reporting loop" in r.data
    assert factory.get(User, id=world.a_mgr).manager_id == world.a_admin
    r = edit(admin, world.a_mgr, role="manager", manager_id=str(world.a_mgr))  # own manager
    assert b"reporting loop" in r.data


def test_demoting_a_manager_moves_the_team_up(login_as, factory, world):
    edit(login_as("admin@alpha.io"), world.a_mgr, role="employee", manager_id=str(world.a_admin))
    assert factory.get(User, id=world.a_emp).manager_id == world.a_admin


def test_deactivate_blocks_login_logs_out_and_can_be_undone(client, login_as, factory, world):
    emp = login_as("emp@alpha.io")
    admin = login_as("admin@alpha.io")
    r = admin.post(f"/admin/employees/{world.a_emp}/status/deactivate", follow_redirects=True)
    assert b"was deactivated" in r.data

    after = emp.get("/dashboard")                      # the open session is ended
    assert after.status_code == 302 and "/login" in after.headers["Location"]
    blocked = client.post("/login", data={"email": "emp@alpha.io", "password": PASSWORD})
    assert b"deactivated" in blocked.data

    admin.post(f"/admin/employees/{world.a_emp}/status/reactivate")
    login_as("emp@alpha.io")                           # works again


def test_deactivating_a_manager_moves_the_team_up(login_as, factory, world):
    login_as("admin@alpha.io").post(f"/admin/employees/{world.a_mgr}/status/deactivate")
    assert factory.get(User, id=world.a_emp).manager_id == world.a_admin


def test_other_org_and_non_admins_cannot_manage_people(login_as, factory, world):
    beta = login_as("admin@beta.io")
    assert beta.post(f"/admin/employees/{world.a_emp}/edit", data={"role": "manager"}).status_code == 404
    assert beta.post(f"/admin/employees/{world.a_emp}/status/deactivate").status_code == 404
    emp = login_as("emp@alpha.io")
    assert emp.post(f"/admin/employees/{world.a_mgr}/status/deactivate").status_code == 403
    assert emp.post(f"/admin/employees/{world.a_mgr}/edit", data={"role": "employee"}).status_code == 403
    user = factory.get(User, id=world.a_mgr)
    assert user.role == "manager" and user.is_active is True


def test_unknown_status_action_is_404(login_as, world):
    r = login_as("admin@alpha.io").post(f"/admin/employees/{world.a_emp}/status/delete")
    assert r.status_code == 404