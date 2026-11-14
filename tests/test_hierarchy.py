from datetime import date

import pytest
from app.extensions import db
from app.models import LeaveRequest, User
from app.services.leave_service import approver_for, pending_for


def apply(browser, type_id, start="2026-11-09", end="2026-11-09"):
    return browser.post("/leave/apply", data={
        "leave_type_id": type_id, "from_date": start, "to_date": end, "reason": "Personal",
    }, follow_redirects=True)


def request_by(factory, org_id, user_id, status="pending"):
    return factory.request(org_id, user_id, factory.leave_type(org_id),
                           date(2026, 11, 9), date(2026, 11, 9), 1, status)


def edit(admin, uid, **data):
    return admin.post(f"/admin/employees/{uid}/edit", data=data, follow_redirects=True)


def second_manager(factory, world):
    return factory.user(world.a, "mgr2@alpha.io", "Other Manager", "manager", world.a_admin)


# ------------------------------------------------------ administrators take no leave

def test_admins_take_no_leave(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    for url in ("/leave/apply", "/leave/my"):
        r = admin.get(url)
        assert r.status_code == 302 and "/dashboard" in r.headers["Location"]
    r = apply(admin, factory.leave_type(world.a))
    assert b"Administrators do not take leave" in r.data
    assert factory.count(LeaveRequest, user_id=world.a_admin) == 0
    nav = admin.get("/dashboard").data
    assert b"/leave/apply" not in nav and b"/leave/my" not in nav and b"/leave/approvals" in nav


def test_admin_dashboard_is_an_overview(login_as, world):
    html = login_as("admin@alpha.io").get("/dashboard").data
    assert b"Managers" in html and b"Employees" in html
    assert b"days left" not in html and b"/leave/apply" not in html


# ------------------------------------------------------------- who approves whom

def test_employee_leave_goes_to_the_employees_manager_only(login_as, factory, world, outbox):
    second_manager(factory, world)
    r = apply(login_as("emp@alpha.io"), factory.leave_type(world.a))
    assert b"submitted" in r.data
    assert [m["to"] for m in outbox] == ["mgr@alpha.io"]
    assert b"Zelda Employee" in login_as("mgr@alpha.io").get("/leave/approvals").data
    assert b"Zelda Employee" not in login_as("mgr2@alpha.io").get("/leave/approvals").data
    assert b"Zelda Employee" not in login_as("admin@alpha.io").get("/leave/approvals").data


def test_manager_leave_goes_to_the_admin(login_as, factory, world, outbox):
    r = apply(login_as("mgr@alpha.io"), factory.leave_type(world.a))
    assert b"submitted" in r.data
    assert [m["to"] for m in outbox] == ["admin@alpha.io"]
    admin = login_as("admin@alpha.io")
    assert b"Maya Manager" in admin.get("/leave/approvals").data
    rid = factory.get(LeaveRequest, user_id=world.a_mgr).id
    assert admin.post(f"/leave/{rid}/approve").status_code == 302
    assert factory.get(LeaveRequest, id=rid).status == "approved"
    assert any(m["to"] == "mgr@alpha.io" and "approved" in m["subject"] for m in outbox)


def test_who_may_decide_what(login_as, factory, world):
    second_manager(factory, world)
    emp_req = request_by(factory, world.a, world.a_emp)
    mgr_req = request_by(factory, world.a, world.a_mgr)
    refused = [
        (emp_req, "admin@alpha.io"), (emp_req, "mgr2@alpha.io"), (emp_req, "emp@alpha.io"),
        (mgr_req, "mgr@alpha.io"), (mgr_req, "mgr2@alpha.io"), (mgr_req, "emp@alpha.io"),
    ]
    for rid, email in refused:
        assert login_as(email).post(f"/leave/{rid}/approve").status_code == 403, (rid, email)
    assert login_as("admin@beta.io").post(f"/leave/{emp_req}/approve").status_code == 404
    assert login_as("mgr@alpha.io").post(f"/leave/{emp_req}/approve").status_code == 302
    assert login_as("admin@alpha.io").post(f"/leave/{mgr_req}/approve").status_code == 302


def test_each_approver_sees_only_their_own_queue(flask_app, factory, world):
    mgr2 = second_manager(factory, world)
    emp_req = request_by(factory, world.a, world.a_emp)
    mgr_req = request_by(factory, world.a, world.a_mgr)
    with flask_app.app_context():
        ids = lambda uid: [r.id for r in pending_for(db.session.get(User, uid))]
        assert ids(world.a_mgr) == [emp_req]
        assert ids(world.a_admin) == [mgr_req]
        assert ids(mgr2) == [] and ids(world.a_emp) == [] and ids(world.b_admin) == []


def test_approver_for(flask_app, factory, world):
    with flask_app.app_context():
        get = lambda uid: db.session.get(User, uid)
        assert approver_for(get(world.a_emp)).id == world.a_mgr
        assert approver_for(get(world.a_mgr)).id == world.a_admin
        assert approver_for(get(world.a_admin)) is None
    factory.update(User, world.a_mgr, is_active=False)
    with flask_app.app_context():
        assert approver_for(db.session.get(User, world.a_emp)) is None


def test_employee_without_a_manager_cannot_apply(login_as, factory, world):
    solo_id = factory.user(world.a, "solo@alpha.io", "Solo Person")
    solo = login_as("solo@alpha.io")
    for r in (solo.get("/leave/apply", follow_redirects=True), apply(solo, factory.leave_type(world.a))):
        assert b"do not have a manager" in r.data
    assert factory.count(LeaveRequest, user_id=solo_id) == 0


def test_employee_whose_manager_is_inactive_cannot_apply(login_as, factory, world):
    factory.update(User, world.a_mgr, is_active=False)
    r = apply(login_as("emp@alpha.io"), factory.leave_type(world.a))
    assert b"do not have a manager" in r.data


def test_unverified_manager_is_not_emailed_but_still_gets_the_request(login_as, factory, world, outbox):
    factory.update(User, world.a_mgr, email_verified=False)
    r = apply(login_as("emp@alpha.io"), factory.leave_type(world.a))
    assert b"submitted" in r.data and outbox == []
    factory.update(User, world.a_mgr, email_verified=True)
    assert b"Zelda Employee" in login_as("mgr@alpha.io").get("/leave/approvals").data


# ------------------------------------------------------------- controlling people

def test_employee_becomes_a_manager_under_the_admin(login_as, factory, world):
    r = edit(login_as("admin@alpha.io"), world.a_emp, role="manager", manager_id="")
    assert b"Employee updated." in r.data
    user = factory.get(User, id=world.a_emp)
    assert (user.role, user.manager_id) == ("manager", world.a_admin)


def test_manager_with_a_team_cannot_become_an_employee(login_as, factory, world):
    mgr2 = second_manager(factory, world)
    admin = login_as("admin@alpha.io")
    r = edit(admin, world.a_mgr, role="employee", manager_id=str(mgr2))
    assert b"still has employees" in r.data
    assert factory.get(User, id=world.a_mgr).role == "manager"
    edit(admin, world.a_emp, role="employee", manager_id=str(mgr2))          # move the team first
    assert b"Employee updated." in edit(admin, world.a_mgr, role="employee", manager_id=str(mgr2)).data
    user = factory.get(User, id=world.a_mgr)
    assert (user.role, user.manager_id) == ("employee", mgr2)


@pytest.mark.parametrize("manager", ["", "ADMIN", "EMPLOYEE", "OTHER_ORG", "SELF"])
def test_an_employee_needs_a_real_manager(login_as, factory, world, manager):
    other = factory.user(world.a, "other@alpha.io", "Other Emp", "employee", world.a_mgr)
    value = {"ADMIN": str(world.a_admin), "EMPLOYEE": str(other),
             "OTHER_ORG": str(world.b_admin), "SELF": str(world.a_emp)}.get(manager, manager)
    r = edit(login_as("admin@alpha.io"), world.a_emp, role="employee", manager_id=value)
    assert b"Choose a manager for this employee." in r.data
    assert factory.get(User, id=world.a_emp).manager_id == world.a_mgr


def test_unknown_roles_are_ignored(login_as, factory, world):
    edit(login_as("admin@alpha.io"), world.a_emp, role="org_admin", manager_id=str(world.a_mgr))
    assert factory.get(User, id=world.a_emp).role == "employee"


def test_the_admin_account_is_protected(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    assert b"Admin accounts cannot be changed here." in edit(
        admin, world.a_admin, role="employee", manager_id=str(world.a_mgr)).data
    r = admin.post(f"/admin/employees/{world.a_admin}/status/deactivate", follow_redirects=True)
    assert b"cannot be deactivated" in r.data
    user = factory.get(User, id=world.a_admin)
    assert user.role == "org_admin" and user.is_active is True


def test_deactivating_managers(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    r = admin.post(f"/admin/employees/{world.a_mgr}/status/deactivate", follow_redirects=True)
    assert b"still has employees" in r.data and factory.get(User, id=world.a_mgr).is_active is True
    lone = factory.user(world.a, "lone@alpha.io", "Lone Manager", "manager", world.a_admin)
    r = admin.post(f"/admin/employees/{lone}/status/deactivate", follow_redirects=True)
    assert b"was deactivated" in r.data and factory.get(User, id=lone).is_active is False
    admin.post(f"/admin/employees/{lone}/status/reactivate")
    assert factory.get(User, id=lone).is_active is True


def test_deactivated_employee_is_logged_out_and_blocked(client, login_as, factory, world):
    emp = login_as("emp@alpha.io")
    admin = login_as("admin@alpha.io")
    assert b"was deactivated" in admin.post(
        f"/admin/employees/{world.a_emp}/status/deactivate", follow_redirects=True).data
    after = emp.get("/dashboard")                                  # the open session ends
    assert after.status_code == 302 and "/login" in after.headers["Location"]
    blocked = client.post("/login", data={"email": "emp@alpha.io", "password": "Passw0rd!x"})
    assert b"deactivated" in blocked.data
    admin.post(f"/admin/employees/{world.a_emp}/status/reactivate")
    login_as("emp@alpha.io")                                       # works again


def test_other_org_and_non_admins_cannot_manage_people(login_as, factory, world):
    beta = login_as("admin@beta.io")
    assert beta.post(f"/admin/employees/{world.a_emp}/edit", data={"role": "manager"}).status_code == 404
    assert beta.post(f"/admin/employees/{world.a_emp}/status/deactivate").status_code == 404
    for email in ("emp@alpha.io", "mgr@alpha.io"):
        browser = login_as(email)
        assert browser.post(f"/admin/employees/{world.a_mgr}/status/deactivate").status_code == 403
        assert browser.post(f"/admin/employees/{world.a_mgr}/edit", data={"role": "employee"}).status_code == 403
    user = factory.get(User, id=world.a_mgr)
    assert user.role == "manager" and user.is_active is True


def test_unknown_status_action_is_404(login_as, world):
    r = login_as("admin@alpha.io").post(f"/admin/employees/{world.a_emp}/status/delete")
    assert r.status_code == 404