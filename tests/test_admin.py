import pytest
from app.models import Holiday, LeaveType, Organization, User


def post(client, url, **data):
    return client.post(url, data=data, follow_redirects=True)


# ---------- leave types ----------

def test_add_leave_type(login_as, factory, world):
    r = post(login_as("admin@alpha.io"), "/admin/leave-types",
             name="Study Leave", yearly_quota="5", carry_forward="on")
    assert b"Leave type added." in r.data
    lt = factory.get(LeaveType, organization_id=world.a, name="Study Leave")
    assert (lt.yearly_quota, lt.carry_forward) == (5, True)


@pytest.mark.parametrize("quota", ["abc", "-1", "400", "", "3.5"])
def test_bad_quota_rejected(login_as, factory, world, quota):
    before = factory.count(LeaveType, organization_id=world.a)
    r = post(login_as("admin@alpha.io"), "/admin/leave-types", name="Odd Leave", yearly_quota=quota)
    assert b"between 0 and 365" in r.data
    assert factory.count(LeaveType, organization_id=world.a) == before


def test_duplicate_and_empty_names_rejected(login_as, world):
    admin = login_as("admin@alpha.io")
    assert b"This leave type already exists." in post(admin, "/admin/leave-types", name="Casual Leave", yearly_quota="5").data
    assert b"Name is required." in post(admin, "/admin/leave-types", name="", yearly_quota="5").data


def test_edit_leave_type_changes_quota_and_checkbox(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    annual = factory.leave_type(world.a, "Annual Leave")      # starts with carry forward on
    r = post(admin, f"/admin/leave-types/{annual}/edit", name="Annual Leave", yearly_quota="30")
    assert b"Leave type updated." in r.data
    lt = factory.get(LeaveType, id=annual)
    assert (lt.yearly_quota, lt.carry_forward) == (30, False)  # box not ticked


def test_edit_cannot_reuse_another_name(login_as, factory, world):
    sick = factory.leave_type(world.a, "Sick Leave")
    r = post(login_as("admin@alpha.io"), f"/admin/leave-types/{sick}/edit", name="Casual Leave", yearly_quota="5")
    assert b"Another leave type already has this name." in r.data
    assert factory.get(LeaveType, id=sick).name == "Sick Leave"


def test_delete_unused_type_but_not_used_one(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    unused = factory.leave_type(world.a, "Sick Leave")
    used = factory.leave_type(world.a, "Casual Leave")
    from datetime import date
    factory.request(world.a, world.a_emp, used, date(2026, 11, 9), date(2026, 11, 9), 1)
    assert b"Leave type deleted." in admin.post(f"/admin/leave-types/{unused}/delete", follow_redirects=True).data
    assert factory.get(LeaveType, id=unused) is None
    assert b"Cannot delete" in admin.post(f"/admin/leave-types/{used}/delete", follow_redirects=True).data
    assert factory.get(LeaveType, id=used) is not None


# ---------- holidays and weekly offs ----------

def test_holidays_add_duplicate_invalid_delete(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    assert b"Holiday added." in post(admin, "/admin/holidays", name="Diwali", date="2026-11-08").data
    assert b"A holiday already exists on this date." in post(admin, "/admin/holidays", name="Again", date="2026-11-08").data
    assert b"valid date are required" in post(admin, "/admin/holidays", name="Bad", date="2026-13-45").data
    assert b"valid date are required" in post(admin, "/admin/holidays", name="", date="2026-11-09").data
    holiday = factory.get(Holiday, organization_id=world.a)
    assert b"Holiday deleted." in admin.post(f"/admin/holidays/{holiday.id}/delete", follow_redirects=True).data
    assert factory.count(Holiday, organization_id=world.a) == 0


@pytest.mark.parametrize("chosen,saved", [
    (["5", "6"], "5,6"),
    (["6", "0"], "0,6"),          # sorted
    (["9", "abc", "6"], "6"),     # invalid values ignored
    ([], ""),                     # no weekly off
])
def test_weekly_offs_saved(login_as, factory, world, chosen, saved):
    r = post(login_as("admin@alpha.io"), "/admin/holidays/weekend", weekend=chosen)
    assert b"Weekly offs saved." in r.data
    assert factory.get(Organization, id=world.a).weekend_days == saved


# ---------- employees ----------

def add_employee(admin, **over):
    data = {"name": "New Hire", "email": "hire@alpha.io", "password": "Hire@2026x", "role": "employee"}
    data.update(over)
    return post(admin, "/admin/employees", **data)


def test_add_employee_needs_verification(login_as, factory, world, outbox, token_in, client):
    r = add_employee(login_as("admin@alpha.io"), manager_id=str(world.a_mgr))
    assert b"Employee added" in r.data
    user = factory.get(User, email="hire@alpha.io")
    assert (user.role, user.manager_id, user.email_verified) == ("employee", world.a_mgr, False)
    mail = [m for m in outbox if m["to"] == "hire@alpha.io"][0]
    assert mail["subject"] == "Verify your LeaveOk email"

    r = client.post("/login", data={"email": "hire@alpha.io", "password": "Hire@2026x"})
    assert b"verify your email first" in r.data                # blocked until verified
    client.get("/verify/" + token_in(mail))
    assert client.post("/login", data={"email": "hire@alpha.io", "password": "Hire@2026x"}).status_code == 302


def test_admin_cannot_create_another_admin_through_the_form(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    add_employee(admin, email="x1@alpha.io", role="org_admin")
    add_employee(admin, email="x2@alpha.io", role="manager")
    assert factory.get(User, email="x1@alpha.io").role == "employee"
    assert factory.get(User, email="x2@alpha.io").role == "manager"


def test_manager_from_another_org_is_ignored(login_as, factory, world):
    add_employee(login_as("admin@alpha.io"), manager_id=str(world.b_admin))
    assert factory.get(User, email="hire@alpha.io").manager_id is None


@pytest.mark.parametrize("over,message", [
    ({"password": "hire1234"}, b"Password needs"),
    ({"email": "nope"}, b"Invalid email"),
    ({"email": "emp@alpha.io"}, b"Email already registered."),
    ({"name": ""}, b"Name, email and password are required."),
])
def test_employee_form_rules(login_as, factory, world, over, message):
    before = factory.count(User)
    assert message in add_employee(login_as("admin@alpha.io"), **over).data
    assert factory.count(User) == before