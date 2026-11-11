from datetime import date

import pytest
from app.models import LeaveRequest, User


def apply(client, type_id, start, end, reason="Family function"):
    return client.post("/leave/apply", data={
        "leave_type_id": type_id, "from_date": start, "to_date": end, "reason": reason,
    }, follow_redirects=True)


def pending(factory, world, start=date(2026, 11, 9), end=date(2026, 11, 13), days=5):
    return factory.request(world.a, world.a_emp, factory.leave_type(world.a), start, end, days)


# ---------- applying ----------

def test_apply_creates_request_and_emails_manager_without_private_details(login_as, factory, world, outbox):
    emp = login_as("emp@alpha.io")
    r = apply(emp, factory.leave_type(world.a), "2026-11-09", "2026-11-13")
    assert b"5 working day(s)" in r.data
    req = factory.get(LeaveRequest, user_id=world.a_emp)
    assert (req.days, req.status) == (5, "pending")
    mails = [m for m in outbox if m["to"] == "mgr@alpha.io"]
    assert len(mails) == 1
    assert "Zelda" not in mails[0]["body"] and "Family function" not in mails[0]["body"]


def test_employee_without_manager_notifies_admin(login_as, factory, world, outbox):
    factory.user(world.a, "solo@alpha.io", "Solo Person")
    apply(login_as("solo@alpha.io"), factory.leave_type(world.a), "2026-11-09", "2026-11-09")
    assert [m["to"] for m in outbox] == ["admin@alpha.io"]


def test_unverified_manager_is_not_emailed(login_as, factory, world, outbox):
    factory.update(User, world.a_mgr, email_verified=False)
    apply(login_as("emp@alpha.io"), factory.leave_type(world.a), "2026-11-09", "2026-11-09")
    assert [m["to"] for m in outbox] == ["admin@alpha.io"]


def test_weekends_and_holidays_do_not_cost_leave(login_as, factory, world):
    factory.holiday(world.a, date(2026, 11, 16))
    r = apply(login_as("emp@alpha.io"), factory.leave_type(world.a), "2026-11-13", "2026-11-17")
    assert b"2 working day(s)" in r.data                      # Fri + Tue only


def test_cannot_exceed_balance(login_as, factory, world):
    emp = login_as("emp@alpha.io")
    t = factory.leave_type(world.a, "Casual Leave")           # 8 days a year
    assert b"submitted" in apply(emp, t, "2026-11-09", "2026-11-13").data        # 5 days
    r = apply(emp, t, "2026-11-16", "2026-11-19")                                 # 4 days, 3 left
    assert b"Not enough balance. You have 3 day(s) left for Casual Leave." in r.data
    assert factory.count(LeaveRequest, user_id=world.a_emp) == 1


@pytest.mark.parametrize("start,end,message", [
    ("2026-11-13", "2026-11-09", b"End date cannot be before start date."),
    ("2026-01-01", "2027-06-01", b"cannot be longer than one year"),
    ("2026-11-14", "2026-11-15", b"weekly offs or holidays"),
    ("", "2026-11-15", b"Please fill all fields correctly."),
    ("not-a-date", "2026-11-15", b"Please fill all fields correctly."),
])
def test_apply_validation(login_as, factory, world, start, end, message):
    r = apply(login_as("emp@alpha.io"), factory.leave_type(world.a), start, end)
    assert message in r.data
    assert factory.count(LeaveRequest) == 0


def test_invalid_leave_types_rejected(login_as, factory, world):
    emp = login_as("emp@alpha.io")
    other_org_type = factory.leave_type(world.b)
    assert b"Invalid leave type." in apply(emp, other_org_type, "2026-11-09", "2026-11-09").data
    assert b"Please fill all fields correctly." in apply(emp, "abc", "2026-11-09", "2026-11-09").data


def test_overlapping_request_blocked_but_rejected_ones_do_not_block(login_as, factory, world):
    emp = login_as("emp@alpha.io")
    t = factory.leave_type(world.a)
    factory.request(world.a, world.a_emp, t, date(2026, 12, 7), date(2026, 12, 8), 2, "rejected")
    assert b"submitted" in apply(emp, t, "2026-12-07", "2026-12-08").data
    assert b"submitted" in apply(emp, t, "2026-11-09", "2026-11-10").data
    r = apply(emp, t, "2026-11-10", "2026-11-11")
    assert b"You already have a leave request in these dates." in r.data


# ---------- approving ----------

def test_manager_approves_and_employee_is_told(login_as, factory, world, outbox):
    rid = pending(factory, world)
    mgr = login_as("mgr@alpha.io")
    page = mgr.get("/leave/approvals")
    assert page.status_code == 200 and b"Zelda Employee" in page.data
    r = mgr.post(f"/leave/{rid}/approve", follow_redirects=True)
    assert b"Request approved." in r.data
    assert factory.get(LeaveRequest, id=rid).status == "approved"
    mail = [m for m in outbox if m["to"] == "emp@alpha.io"][0]
    assert mail["subject"] == "Your leave request was approved"
    assert "2026" not in mail["body"]                         # no dates in email
    assert b"<b>3</b>" in login_as("emp@alpha.io").get("/dashboard").data   # 8 - 5 days left


def test_rejecting_gives_the_days_back(login_as, factory, world):
    rid = pending(factory, world)
    login_as("mgr@alpha.io").post(f"/leave/{rid}/reject")
    assert factory.get(LeaveRequest, id=rid).status == "rejected"
    assert b"<b>8</b>" in login_as("emp@alpha.io").get("/dashboard").data


def test_admin_can_also_decide(login_as, factory, world):
    rid = pending(factory, world)
    assert login_as("admin@alpha.io").post(f"/leave/{rid}/approve").status_code == 302
    assert factory.get(LeaveRequest, id=rid).status == "approved"


def test_nobody_else_can_decide(login_as, factory, world):
    factory.user(world.a, "mgr2@alpha.io", "Other Manager", "manager", world.a_admin)
    rid = pending(factory, world)
    for email in ("emp@alpha.io", "mgr2@alpha.io"):
        assert login_as(email).post(f"/leave/{rid}/approve").status_code == 403
    assert factory.get(LeaveRequest, id=rid).status == "pending"


def test_cannot_approve_own_request(login_as, factory, world):
    own = factory.request(world.a, world.a_admin, factory.leave_type(world.a),
                          date(2026, 11, 9), date(2026, 11, 9), 1)
    assert login_as("admin@alpha.io").post(f"/leave/{own}/approve").status_code == 403


def test_decision_is_final_and_actions_are_checked(login_as, factory, world):
    rid = pending(factory, world)
    mgr = login_as("mgr@alpha.io")
    assert mgr.post(f"/leave/{rid}/approve").status_code == 302
    assert mgr.post(f"/leave/{rid}/reject").status_code == 403     # already decided
    assert mgr.post(f"/leave/{rid}/delete").status_code == 404     # unknown action


def test_employee_cannot_open_approvals(login_as, world):
    assert login_as("emp@alpha.io").get("/leave/approvals").status_code == 403


# ---------- my leaves, dashboard, calendar ----------

def test_my_leaves_and_dashboard(login_as, factory, world):
    pending(factory, world)
    emp = login_as("emp@alpha.io")
    assert b"pending" in emp.get("/leave/my").data
    dash = emp.get("/dashboard").data
    assert b"Casual Leave" in dash and b"Zelda Employee" in dash


def test_calendar_shows_team_and_holidays_only(login_as, factory, world):
    factory.holiday(world.a, date(2026, 11, 16), "Diwali Break")
    t = factory.leave_type(world.a)
    other = factory.user(world.a, "other@alpha.io", "Orson Outsider", "employee", world.a_admin)
    mate = factory.user(world.a, "mate@alpha.io", "Tina Teammate", "employee", world.a_mgr)
    factory.request(world.a, world.a_emp, t, date(2026, 11, 9), date(2026, 11, 9), 1, "approved")
    factory.request(world.a, mate, t, date(2026, 11, 10), date(2026, 11, 10), 1, "pending")
    factory.request(world.a, other, t, date(2026, 11, 11), date(2026, 11, 11), 1, "approved")
    factory.request(world.a, mate, t, date(2026, 11, 12), date(2026, 11, 12), 1, "rejected")

    emp_view = login_as("emp@alpha.io").get("/leave/calendar?month=2026-11").data
    assert b"Zelda Employee" in emp_view and b"Tina Teammate" in emp_view
    assert b"Orson Outsider" not in emp_view                   # different manager's team
    assert b"Diwali Break" in emp_view

    admin_view = login_as("admin@alpha.io").get("/leave/calendar?month=2026-11").data
    assert b"Orson Outsider" in admin_view and b"Zelda Employee" in admin_view


@pytest.mark.parametrize("month", ["garbage", "2026-13", ""])
def test_calendar_survives_bad_month(login_as, world, month):
    assert login_as("emp@alpha.io").get(f"/leave/calendar?month={month}").status_code == 200