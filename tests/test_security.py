from datetime import date

import pytest
from app.models import Holiday, LeaveRequest, LeaveType, User, Organization

GET_PAGES = ["/dashboard", "/leave/apply", "/leave/my", "/leave/approvals", "/leave/calendar",
             "/admin/employees", "/admin/leave-types", "/admin/holidays", "/owner/organizations"]
POST_ACTIONS = ["/leave/1/approve", "/admin/leave-types/1/edit", "/admin/leave-types/1/delete",
                "/admin/holidays/1/delete", "/admin/holidays/weekend", "/owner/organizations/1/approve"]


@pytest.mark.parametrize("url", GET_PAGES)
def test_pages_need_login(client, url):
    r = client.get(url)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


@pytest.mark.parametrize("url", POST_ACTIONS)
def test_actions_need_login(client, url):
    r = client.post(url)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


@pytest.mark.parametrize("url", ["/admin/employees", "/admin/leave-types", "/admin/holidays"])
def test_only_org_admin_opens_admin_pages(login_as, world, url):
    for email in ("emp@alpha.io", "mgr@alpha.io"):
        assert login_as(email).get(url).status_code == 403
    assert login_as("admin@alpha.io").get(url).status_code == 200


def test_employee_cannot_use_admin_actions(login_as, world):
    emp = login_as("emp@alpha.io")
    assert emp.post("/admin/leave-types", data={"name": "Free Leave", "yearly_quota": "99"}).status_code == 403
    assert emp.post("/admin/employees", data={"name": "X"}).status_code == 403


def test_owner_pages_hidden_from_everyone_else(login_as, world):
    for email in ("emp@alpha.io", "admin@alpha.io"):
        assert login_as(email).get("/owner/organizations").status_code == 404


def test_menu_matches_role(login_as, factory, world):
    emp = login_as("emp@alpha.io").get("/dashboard").data
    assert b"/admin/employees" not in emp and b"/leave/approvals" not in emp
    mgr = login_as("mgr@alpha.io").get("/dashboard").data
    assert b"/leave/approvals" in mgr and b"/admin/employees" not in mgr
    admin = login_as("admin@alpha.io").get("/dashboard").data
    assert all(link in admin for link in (b"/admin/employees", b"/admin/leave-types", b"/admin/holidays"))
    assert b"/owner/organizations" not in admin


# ---------- tenant isolation: organization B must never touch organization A ----------

def a_request(factory, world):
    return factory.request(world.a, world.a_emp, factory.leave_type(world.a),
                           date(2026, 11, 9), date(2026, 11, 9), 1)


def test_other_org_admin_cannot_decide_requests(login_as, factory, world):
    rid = a_request(factory, world)
    assert login_as("admin@beta.io").post(f"/leave/{rid}/approve").status_code == 404
    assert factory.get(LeaveRequest, id=rid).status == "pending"


def test_other_org_admin_cannot_edit_or_delete_leave_types(login_as, factory, world):
    lt = factory.leave_type(world.a, "Sick Leave")
    b_admin = login_as("admin@beta.io")
    assert b_admin.post(f"/admin/leave-types/{lt}/edit", data={"name": "Hacked", "yearly_quota": "1"}).status_code == 404
    assert b_admin.post(f"/admin/leave-types/{lt}/delete").status_code == 404
    assert factory.get(LeaveType, id=lt).name == "Sick Leave"


def test_other_org_admin_cannot_delete_holidays(login_as, factory, world):
    hid = factory.holiday(world.a, date(2026, 11, 16), "Alpha Day")
    assert login_as("admin@beta.io").post(f"/admin/holidays/{hid}/delete").status_code == 404
    assert factory.get(Holiday, id=hid) is not None


def test_other_org_data_never_appears_on_pages(login_as, factory, world):
    a_request(factory, world)
    factory.holiday(world.a, date(2026, 11, 16), "Alpha Day")
    b_admin = login_as("admin@beta.io")
    pages = ["/admin/employees", "/admin/holidays", "/leave/approvals",
             "/leave/calendar?month=2026-11", "/dashboard", "/leave/my"]
    for url in pages:
        data = b_admin.get(url).data
        for secret in (b"Zelda", b"emp@alpha.io", b"Maya Manager", b"Alpha Day", b"Alpha Corp"):
            assert secret not in data, f"{secret!r} leaked on {url}"


def test_same_holiday_date_allowed_in_two_orgs(login_as, factory, world):
    factory.holiday(world.a, date(2026, 11, 16))
    r = login_as("admin@beta.io").post("/admin/holidays", data={"name": "Beta Day", "date": "2026-11-16"}, follow_redirects=True)
    assert b"Holiday added." in r.data


def test_members_of_a_suspended_org_are_logged_out(login_as, factory, world):
    emp = login_as("emp@alpha.io")
    assert emp.get("/dashboard").status_code == 200
    factory.update(Organization, world.a, status="rejected")
    r = emp.get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


# ---------- CSRF ----------

def test_forms_without_csrf_token_are_refused(csrf_app):
    browser = csrf_app.test_client()
    assert b'name="csrf_token"' in browser.get("/login").data
    assert browser.post("/login", data={"email": "a@b.io", "password": "x"}).status_code == 400
    assert browser.post("/register", data={"email": "a@b.io"}).status_code == 400