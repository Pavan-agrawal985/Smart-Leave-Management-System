from app.models import LeaveRequest, Organization, User


def run(app, *args):
    return app.test_cli_runner().invoke(args=list(args))


def seed(app, password="Demo@2026ab"):
    return run(app, "seed-demo", "--email", "me@gmail.com", "--password", password)


def test_seed_builds_a_lively_organization(flask_app, factory):
    result = seed(flask_app)
    assert result.exit_code == 0, result.output
    org = factory.get(Organization, name="Demo University")
    assert org.status == "active"
    assert factory.count(User, organization_id=org.id) == 8
    assert factory.count(LeaveRequest, organization_id=org.id) >= 8
    admin = factory.get(User, email="me+demo-asha@gmail.com")
    assert admin.role == "org_admin" and admin.email_verified is True
    assert admin.check_password("Demo@2026ab")


def test_demo_hierarchy(flask_app, factory):
    seed(flask_app)
    rahul = factory.get(User, email="me+demo-rahul@gmail.com")
    aman = factory.get(User, email="me+demo-aman@gmail.com")
    assert aman.manager_id == rahul.id
    assert rahul.manager_id == factory.get(User, email="me+demo-asha@gmail.com").id


def test_weak_password_and_bad_email_refused(flask_app, factory):
    weak = seed(flask_app, password="weak")
    assert weak.exit_code != 0 and "8 to 16" in weak.output
    bad = run(flask_app, "seed-demo", "--email", "nope", "--password", "Demo@2026ab")
    assert bad.exit_code != 0
    assert factory.count(Organization) == 0


def test_seed_twice_is_refused(flask_app, factory):
    assert seed(flask_app).exit_code == 0
    again = seed(flask_app)
    assert again.exit_code != 0 and "already exists" in again.output
    assert factory.count(Organization) == 1


def test_delete_demo_removes_everything(flask_app, factory):
    seed(flask_app)
    result = run(flask_app, "delete-demo", "--yes")
    assert result.exit_code == 0, result.output
    assert factory.count(Organization) == 0
    assert factory.count(User) == 0
    assert factory.count(LeaveRequest) == 0


def test_delete_without_demo_is_a_clear_error(flask_app):
    result = run(flask_app, "delete-demo", "--yes")
    assert result.exit_code != 0 and "No demo organization" in result.output