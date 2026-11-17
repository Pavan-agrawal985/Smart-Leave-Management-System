import pytest
from app.models import LeaveType, Organization

STRONG = "Strong@2026x"


def signup(client, org_type, email="t@example.io"):
    return client.post("/register", data={
        "org_name": "Type Test Org", "org_type": org_type,
        "name": "Tess Tester", "email": email, "password": STRONG})


def test_sign_up_offers_only_bank_corporate_and_other(client):
    html = client.get("/register").data
    for value in (b'value="bank"', b'value="corporate"', b'value="custom"'):
        assert value in html
    for gone in (b'value="school"', b'value="college"', b"School", b"College"):
        assert gone not in html


@pytest.mark.parametrize("org_type,leave_types,weekend", [
    ("corporate", {"Annual Leave", "Sick Leave", "Casual Leave"}, "5,6"),
    ("bank", {"Privilege Leave", "Sick Leave", "Casual Leave"}, "6"),
    ("custom", {"Casual Leave", "Sick Leave"}, "5,6"),
])
def test_each_type_gets_its_starter_rules(client, factory, org_type, leave_types, weekend):
    assert signup(client, org_type).status_code == 302
    org = factory.get(Organization, name="Type Test Org")
    assert (org.org_type, org.weekend_days) == (org_type, weekend)
    with factory.app.app_context():
        names = {t.name for t in LeaveType.query.filter_by(organization_id=org.id)}
    assert names == leave_types


@pytest.mark.parametrize("old_type", ["school", "college", "hacker", ""])
def test_old_or_unknown_types_become_other(client, factory, old_type):
    signup(client, old_type)
    org = factory.get(Organization, name="Type Test Org")
    assert org.org_type == "custom" and org.weekend_days == "5,6"


@pytest.mark.parametrize("url", ["/", "/register", "/login", "/forgot-password"])
def test_public_pages_do_not_mention_schools_or_colleges(client, url):
    html = client.get(url).data.lower()
    assert b"school" not in html and b"college" not in html