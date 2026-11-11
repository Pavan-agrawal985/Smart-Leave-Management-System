from datetime import date

import pytest
from app.models import Organization, LeaveRequest, User

OWNER = "owner@acme.io"
STRONG = "Strong@2026x"


@pytest.fixture()
def owner_setup(factory):
    hq = factory.org("Owner HQ")
    factory.user(hq, OWNER, "Olivia Owner", "org_admin")
    pending_org = factory.org("Pending School", "school", status="pending")
    factory.user(pending_org, "head@pending.io", "Hari Head", "org_admin")
    return hq, pending_org


def test_owner_approves_and_org_can_log_in(login_as, factory, owner_setup, outbox):
    hq, pending_org = owner_setup
    r = login_as(OWNER).post(f"/owner/organizations/{pending_org}/approve", follow_redirects=True)
    assert b"Pending School is now active." in r.data
    assert factory.get(Organization, id=pending_org).status == "active"
    assert any(m["to"] == "head@pending.io" and "approved" in m["subject"] for m in outbox)
    login_as("head@pending.io")                                # works now


def test_owner_rejects_org(client, login_as, factory, owner_setup):
    hq, pending_org = owner_setup
    login_as(OWNER).post(f"/owner/organizations/{pending_org}/reject")
    assert factory.get(Organization, id=pending_org).status == "rejected"
    r = client.post("/login", data={"email": "head@pending.io", "password": "Passw0rd!x"})
    assert b"not approved" in r.data


def test_owner_list_and_guards(login_as, owner_setup):
    hq, pending_org = owner_setup
    owner = login_as(OWNER)
    page = owner.get("/owner/organizations")
    assert page.status_code == 200 and b"Pending School" in page.data
    assert b"/owner/organizations" in owner.get("/dashboard").data           # menu link
    assert b"You cannot change your own organization." in owner.post(
        f"/owner/organizations/{hq}/reject", follow_redirects=True).data
    assert owner.post(f"/owner/organizations/{pending_org}/delete").status_code == 404
    assert owner.post("/owner/organizations/9999/approve").status_code == 404


def test_full_journey(client, login_as, factory, outbox, token_in, owner_setup):
    # 1. A school signs up.
    r = client.post("/register", data={
        "org_name": "Green Valley School", "org_type": "school", "name": "Priya Principal",
        "email": "principal@gv.in", "password": STRONG})
    assert r.status_code == 302
    school = factory.get(Organization, name="Green Valley School").id
    principal_id = factory.get(User, email="principal@gv.in").id

    # 2. She verifies her email, but cannot enter until the owner approves.
    client.get("/verify/" + token_in(outbox[-1]))
    r = client.post("/login", data={"email": "principal@gv.in", "password": STRONG})
    assert b"waiting for approval" in r.data

    # 3. The owner approves the school.
    login_as(OWNER).post(f"/owner/organizations/{school}/approve")
    assert any(m["to"] == "principal@gv.in" and "approved" in m["subject"] for m in outbox)

    # 4. The principal adds a teacher; the teacher verifies the email.
    principal = login_as("principal@gv.in", STRONG)
    principal.post("/admin/employees", data={
        "name": "Tara Teacher", "email": "tara@gv.in", "password": "Teach@2026x",
        "role": "employee", "manager_id": str(principal_id)})
    tara_mail = [m for m in outbox if m["to"] == "tara@gv.in"][-1]
    client.get("/verify/" + token_in(tara_mail))

    # 5. The teacher applies for two days (school week: only Sunday is off).
    tara = login_as("tara@gv.in", "Teach@2026x")
    t = factory.leave_type(school, "Casual Leave")
    r = tara.post("/leave/apply", data={"leave_type_id": t, "from_date": "2026-11-09",
                                        "to_date": "2026-11-10", "reason": "Wedding"}, follow_redirects=True)
    assert b"2 working day(s)" in r.data
    assert any(m["to"] == "principal@gv.in" and "waiting" in m["subject"] for m in outbox)

    # 6. The principal approves; the teacher sees it and is notified.
    rid = factory.get(LeaveRequest, user_id=factory.get(User, email="tara@gv.in").id).id
    assert principal.post(f"/leave/{rid}/approve").status_code == 302
    assert b"approved" in tara.get("/leave/my").data
    assert any(m["to"] == "tara@gv.in" and "approved" in m["subject"] for m in outbox)