import re

from app.models import Organization, User, LeaveRequest

STRONG = "Strong@2026x"


def join(client, outbox, email, name, password):
    mail = [m for m in outbox if m["to"] == email and "/invite/" in m["body"]][-1]
    token = re.search(r"/invite/(\S+)", mail["body"]).group(1)
    r = client.post(f"/invite/{token}", data={"name": name, "password": password, "confirm": password})
    assert r.status_code == 302


def test_full_journey(client, login_as, factory, outbox, token_in):
    # 1. Anyone creates an organization. No approval step.
    r = client.post("/register", data={
        "org_name": "Green Valley School", "org_type": "school", "name": "Priya Principal",
        "email": "principal@gv.in", "password": STRONG})
    assert r.status_code == 302
    school = factory.get(Organization, name="Green Valley School")
    assert school.status == "active"
    school_id = school.id

    # 2. She verifies her email and logs in right away.
    client.get("/verify/" + token_in(outbox[-1]))
    principal = login_as("principal@gv.in", STRONG)

    # 3. She invites a manager, who joins and sets her own password.
    principal.post("/admin/employees", data={"name": "Mia M", "email": "mia@gv.in", "role": "manager"})
    join(client, outbox, "mia@gv.in", "Mia Manager", "Mia@2026xyz")
    mia_id = factory.get(User, email="mia@gv.in").id

    # 4. She invites a teacher under that manager.
    principal.post("/admin/employees", data={
        "name": "Tara T", "email": "tara@gv.in", "role": "employee", "manager_id": str(mia_id)})
    join(client, outbox, "tara@gv.in", "Tara Teacher", "Teach@2026x")

    mia = login_as("mia@gv.in", "Mia@2026xyz")
    tara = login_as("tara@gv.in", "Teach@2026x")
    t = factory.leave_type(school_id, "Casual Leave")

    # 5. The teacher applies. Only her manager is told and can decide.
    r = tara.post("/leave/apply", data={"leave_type_id": t, "from_date": "2026-11-09",
                                        "to_date": "2026-11-10", "reason": "Wedding"}, follow_redirects=True)
    assert b"2 working day(s)" in r.data
    assert [m["to"] for m in outbox if "waiting" in m["subject"]] == ["mia@gv.in"]
    assert b"Tara Teacher" not in principal.get("/leave/approvals").data
    rid = factory.get(LeaveRequest, user_id=factory.get(User, email="tara@gv.in").id).id
    assert principal.post(f"/leave/{rid}/approve").status_code == 403       # the administrator does not approve employees
    assert mia.post(f"/leave/{rid}/approve").status_code == 302
    assert b"approved" in tara.get("/leave/my").data
    assert any(m["to"] == "tara@gv.in" and "approved" in m["subject"] for m in outbox)

    # 6. The manager applies. Only the administrator decides.
    mia.post("/leave/apply", data={"leave_type_id": t, "from_date": "2026-11-12", "to_date": "2026-11-12"})
    assert any(m["to"] == "principal@gv.in" and "waiting" in m["subject"] for m in outbox)
    assert b"Mia Manager" in principal.get("/leave/approvals").data
    mia_req = factory.get(LeaveRequest, user_id=mia_id).id
    assert principal.post(f"/leave/{mia_req}/approve").status_code == 302
    assert any(m["to"] == "mia@gv.in" and "approved" in m["subject"] for m in outbox)

    # 7. The administrator takes no leave, and sees everyone's details.
    assert principal.get("/leave/apply").status_code == 302
    page = principal.get("/admin/employees").data
    assert b"Tara Teacher" in page and b"Mia Manager" in page