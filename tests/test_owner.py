from datetime import date

import bcrypt
import pytest
from app.models import LeaveRequest, Organization, User
from app.services.owner_stats import org_rows, platform_stats
from app.services.validation import owner_password_error


# ------------------------------------------------------------------- login

def test_login_page_is_public(client):
    r = client.get("/owner/login")
    assert r.status_code == 200
    assert b'name="email"' in r.data and b'name="password"' in r.data


def test_owner_logs_in_with_the_set_password(client, owner_credentials):
    r = client.post("/owner/login", data={
        "email": owner_credentials.email.upper(), "password": owner_credentials.password})
    assert r.status_code == 302 and "/owner/organizations" in r.headers["Location"]
    assert client.get("/owner/organizations").status_code == 200


@pytest.mark.parametrize("email,password", [
    ("owner@acme.io", "Wrong#Pass2026x"),
    ("someone@else.io", "Owner#Pass2026x"),
    ("admin@alpha.io", "Passw0rd!x"),          # a normal user's login does not work here
    ("owner@acme.io", ""),
    ("owner@acme.io", "A" * 100),
    ("", ""),
])
def test_wrong_owner_credentials(client, world, email, password):
    r = client.post("/owner/login", data={"email": email, "password": password})
    assert r.status_code == 200 and b"Invalid owner email or password." in r.data
    assert client.get("/owner/organizations").status_code == 302


def test_owner_login_not_set_up(client, monkeypatch):
    monkeypatch.delenv("OWNER_PASSWORD_HASH")
    r = client.post("/owner/login", data={"email": "owner@acme.io", "password": "Owner#Pass2026x"})
    assert b"not set up" in r.data


def test_owner_login_needs_csrf_token(csrf_app):
    r = csrf_app.test_client().post("/owner/login", data={"email": "owner@acme.io", "password": "x"})
    assert r.status_code == 400


def test_logout_ends_the_session(owner_client):
    assert owner_client.get("/owner/organizations").status_code == 200
    owner_client.get("/owner/logout")
    r = owner_client.get("/owner/organizations")
    assert r.status_code == 302 and "/owner/login" in r.headers["Location"]


def test_owner_session_expires(owner_client):
    with owner_client.session_transaction() as s:
        s["owner_at"] = 0
    r = owner_client.get("/owner/organizations")
    assert r.status_code == 302 and "/owner/login" in r.headers["Location"]


def test_logged_in_owner_skips_the_login_page(owner_client):
    r = owner_client.get("/owner/login")
    assert r.status_code == 302 and "/owner/organizations" in r.headers["Location"]


def test_normal_users_cannot_open_owner_pages(login_as, world):
    for email in ("admin@alpha.io", "mgr@alpha.io", "emp@alpha.io"):
        r = login_as(email).get("/owner/organizations")
        assert r.status_code == 302 and "/owner/login" in r.headers["Location"]


# ------------------------------------------------------------------ screen

def test_owner_sees_organizations_not_employee_data(owner_client, factory, world):
    factory.request(world.a, world.a_emp, factory.leave_type(world.a),
                    date(2026, 11, 9), date(2026, 11, 9), 1)
    page = owner_client.get("/owner/organizations").data
    assert b"Alpha Corp" in page and b"Beta Bank" in page
    assert b"admin@alpha.io" in page and b"Alice Alpha" in page
    assert b"Zelda" not in page and b"emp@alpha.io" not in page and b"Maya" not in page


def test_menus_differ(owner_client, login_as, world):
    owner_page = owner_client.get("/owner/organizations").data
    assert b"/owner/logout" in owner_page and b"/leave/apply" not in owner_page
    user_page = login_as("admin@alpha.io").get("/dashboard").data
    assert b"/owner/" not in user_page


def test_platform_stats(flask_app, factory, world):
    t = factory.leave_type(world.a)
    factory.request(world.a, world.a_emp, t, date(2026, 11, 9), date(2026, 11, 9), 1, "pending")
    factory.request(world.a, world.a_emp, t, date(2026, 11, 10), date(2026, 11, 10), 1, "approved")
    factory.org("Gamma", status="suspended")
    with flask_app.app_context():
        s = platform_stats()
    assert (s["organizations"], s["active"], s["suspended"]) == (3, 2, 1)
    assert (s["people"], s["requests"], s["pending"], s["new_week"]) == (4, 2, 1, 3)


def test_org_rows(flask_app, factory, world):
    factory.request(world.a, world.a_emp, factory.leave_type(world.a),
                    date(2026, 11, 9), date(2026, 11, 9), 1)
    with flask_app.app_context():
        rows = {r["org"].name: r for r in org_rows()}
    alpha, beta = rows["Alpha Corp"], rows["Beta Bank"]
    assert (alpha["people"], alpha["requests"]) == (3, 1)
    assert alpha["admin_email"] == "admin@alpha.io" and alpha["last_activity"] is not None
    assert (beta["people"], beta["requests"]) == (1, 0) and beta["last_activity"] is None

    factory.update(User, world.a_emp, is_active=False)           # deactivated people are not counted
    with flask_app.app_context():
        assert {r["org"].name: r for r in org_rows()}["Alpha Corp"]["people"] == 2


# ------------------------------------------------------------ suspend, reactivate

def test_owner_can_suspend_and_reactivate(client, owner_client, login_as, factory, world):
    r = owner_client.post(f"/owner/organizations/{world.a}/suspend", follow_redirects=True)
    assert b"Alpha Corp is now suspended." in r.data
    assert factory.get(Organization, id=world.a).status == "suspended"
    blocked = client.post("/login", data={"email": "admin@alpha.io", "password": "Passw0rd!x"})
    assert b"suspended" in blocked.data

    owner_client.post(f"/owner/organizations/{world.a}/reactivate")
    assert factory.get(Organization, id=world.a).status == "active"
    login_as("admin@alpha.io")


def test_owner_action_guards(owner_client, client, world):
    assert owner_client.post(f"/owner/organizations/{world.a}/delete").status_code == 404
    assert owner_client.post(f"/owner/organizations/{world.a}/approve").status_code == 404
    assert owner_client.post("/owner/organizations/9999/suspend").status_code == 404
    r = client.post(f"/owner/organizations/{world.a}/suspend")        # not logged in as owner
    assert r.status_code == 302 and "/owner/login" in r.headers["Location"]


# ----------------------------------------------------------- password and command

@pytest.mark.parametrize("pw,word", [
    ("Short#1aA", "12 to 72"),
    ("Aa1#" * 20, "12 to 72"),
    ("Owner #Pass2026x", "spaces"),
    ("OWNER#PASS2026X", "lowercase"),
    ("owner#pass2026x", "uppercase"),
    ("Owner#PassWordxx", "number"),
    ("OwnerPass2026xx", "special symbol"),
])
def test_owner_password_rules(pw, word):
    assert word in owner_password_error(pw)


def test_owner_password_rules_accept_a_strong_one():
    assert owner_password_error("Owner#Pass2026x") is None


def test_owner_hash_command(flask_app):
    runner = flask_app.test_cli_runner()
    ok = runner.invoke(args=["owner-hash", "--password", "Owner#Pass2026x"])
    assert ok.exit_code == 0
    hashed = [line for line in ok.output.splitlines() if line.startswith("$2")][0]
    assert bcrypt.checkpw(b"Owner#Pass2026x", hashed.encode("utf-8"))
    weak = runner.invoke(args=["owner-hash", "--password", "weak"])
    assert weak.exit_code != 0 and "12 to 72" in weak.output