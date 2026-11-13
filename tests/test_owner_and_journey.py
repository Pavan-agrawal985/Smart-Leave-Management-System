import re

import pytest
from app.models import Organization, User, LeaveRequest

OWNER = "owner@acme.io"
STRONG = "Strong@2026x"


@pytest.fixture()
def owner_setup(factory):
    hq = factory.org("Owner HQ")
    factory.user(hq, OWNER, "Olivia Owner", "org_admin")
    school = factory.org("Green School", "school")
    factory.user(school, "head@school.io", "Hari Head", "org_admin")
    return hq, school


def test_owner_can_suspend_and_reactivate(client, login_as, factory, owner_setup):
    hq, school = owner_setup
    owner = login_as(OWNER)
    r = owner.post(f"/owner/organizations/{school}/suspend", follow_redirects=True)
    assert b"Green School is now suspended." in r.data
    assert factory.get(Organization, id=school).status == "suspended"
    blocked = client.post("/login", data={"email": "head@school.io", "password": "Passw0rd!x"})
    assert b"suspended" in blocked.data
    owner.post(f"/owner/organizations/{school}/reactivate")
    assert factory.get(Organization, id=school).status == "active"
    login_as("head@school.io")                                  # works again


def test_owner_list_and_guards(login_as, owner_setup):
    hq, school = owner_setup
    owner = login_as(OWNER)
    page = owner.get("/owner/organizations")
    assert page.status_code == 200 and b"Green School" in page.data
    assert b"/owner/organizations" in owner.get("/dashboard").data           # menu link
    assert b"You cannot change your own organization." in owner.post(
        f"/owner/organizations/{hq}/suspend", follow_redirects=True).data
    assert owner.post(f"/owner/organizations/{school}/delete").status_code == 404
    assert owner.post(f"/owner/organizations/{school}/approve").status_code == 404   # old route is gone
    assert owner.post("/owner/organizations/9999/suspend").status_code == 404


def test_full_journey(client, login_as, factory, outbox, token_in):
    # 1. Anyone creates an organization. No approval step.
    r = client.post("/register", data={
        "org_name": "Green Valley School", "org_type": "school", "name": "Priya Principal",
        "email": "principal@gv.in", "password": STRONG})
    assert r.status_code == 302
    school = factory.get(Organization, name="Green Valley School")
    assert school.status == "active"
    school_id = school.id
    principal_id = factory.get(User, email="principal@gv.in").id

    # 2. She verifies her email and logs in right away.
    client.get("/verify/" + token_in(outbox[-1]))
    principal = login_as("principal@gv.in", STRONG)

    # 3. She invites a teacher. There is no password field, the teacher chooses their own.
    principal.post("/admin/employees", data={
        "name": "Tara T", "email": "tara@gv.in", "role": "employee", "manager_id": str(principal_id)})
    invite = [m for m in outbox if m["to"] == "tara@gv.in"][-1]
    assert "Green Valley School" in invite["subject"]
    token = re.search(r"/invite/(\S+)", invite["body"]).group(1)

    # 4. The teacher joins through the link and sets their details and password.
    joined = client.post(f"/invite/{token}", data={
        "name": "Tara Teacher", "password": "Teach@2026x", "confirm": "Teach@2026x"})
    assert joined.status_code == 302
    tara = login_as("tara@gv.in", "Teach@2026x")

    # 5. The teacher applies for two days (school week: only Sunday is off).
    t = factory.leave_type(school_id, "Casual Leave")
    r = tara.post("/leave/apply", data={"leave_type_id": t, "from_date": "2026-11-09",
                                        "to_date": "2026-11-10", "reason": "Wedding"}, follow_redirects=True)
    assert b"2 working day(s)" in r.data
    assert any(m["to"] == "principal@gv.in" and "waiting" in m["subject"] for m in outbox)

    # 6. The principal approves; the teacher sees it and is notified.
    rid = factory.get(LeaveRequest, user_id=factory.get(User, email="tara@gv.in").id).id
    assert principal.post(f"/leave/{rid}/approve").status_code == 302
    assert b"approved" in tara.get("/leave/my").data
    assert any(m["to"] == "tara@gv.in" and "approved" in m["subject"] for m in outbox)

    # 7. The admin sees the person's details.
    page = principal.get("/admin/employees").data
    assert b"Tara Teacher" in page and b"tara@gv.in" in page