import bcrypt
import os
import re
from types import SimpleNamespace

import pytest

# SAFETY: tests always use a throwaway in-memory SQLite database,
# never your real Neon database. This is set BEFORE the app is imported.
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite://"

from config import Config  # noqa: E402
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Organization, User, LeaveType, LeaveRequest, Holiday  # noqa: E402
from app.services.org_templates import seed_leave_types  # noqa: E402

PASSWORD = "Passw0rd!x"
OWNER_EMAIL = "owner@acme.io"
OWNER_PASSWORD = "Owner#Pass2026x"
OWNER_HASH = bcrypt.hashpw(OWNER_PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("utf-8")


@pytest.fixture(autouse=True)
def fast_passwords(monkeypatch):
    """Cheap hashing in tests only. The real app keeps the normal, slow setting."""
    real_gensalt = bcrypt.gensalt
    monkeypatch.setattr(bcrypt, "gensalt", lambda *a, **k: real_gensalt(rounds=4))

class SqliteTestConfig(Config):
    OWNER_FAIL_DELAY = 0
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class CsrfOnConfig(SqliteTestConfig):
    WTF_CSRF_ENABLED = True


def _build(config):
    application = create_app(config)
    assert application.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")
    with application.app_context():
        db.create_all()
    return application


def _teardown(application):
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def flask_app():
    application = _build(SqliteTestConfig)
    yield application
    _teardown(application)


@pytest.fixture()
def csrf_app():
    application = _build(CsrfOnConfig)
    yield application
    _teardown(application)


_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")


def fake_check_email(raw):
    """Syntax-only email check, so tests never need internet or DNS."""
    raw = (raw or "").strip()
    if not _EMAIL_RE.fullmatch(raw):
        return None, "Invalid email: not a valid address."
    return raw.lower(), None


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Captures every email instead of sending it."""
    sent = []

    def fake_send(to_email, subject, body):
        sent.append({"to": to_email, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("app.services.email_service._send", fake_send)
    monkeypatch.setattr("app.routes.auth.check_email", fake_check_email)
    monkeypatch.setattr("app.routes.admin.check_email", fake_check_email)
    monkeypatch.setenv("OWNER_PASSWORD_HASH", OWNER_HASH)
    return sent


@pytest.fixture()
def token_in():
    def _token(mail):
        return re.search(r"/verify/(\S+)", mail["body"]).group(1)
    return _token


class Factory:
    """Creates test data directly in the database."""

    def __init__(self, app):
        self.app = app

    def org(self, name="Alpha Corp", org_type="corporate", status="active"):
        with self.app.app_context():
            org = Organization(name=name, org_type=org_type, status=status)
            db.session.add(org)
            db.session.flush()
            seed_leave_types(org)
            db.session.commit()
            return org.id

    def user(self, org_id, email, name=None, role="employee",
             manager_id=None, verified=True, password=PASSWORD):
        with self.app.app_context():
            user = User(
                organization_id=org_id,
                name=name or email.split("@")[0],
                email=email,
                role=role,
                manager_id=manager_id,
                email_verified=verified,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return user.id

    def leave_type(self, org_id, name="Casual Leave"):
        with self.app.app_context():
            return LeaveType.query.filter_by(organization_id=org_id, name=name).first().id

    def holiday(self, org_id, day, name="Test Holiday"):
        with self.app.app_context():
            holiday = Holiday(organization_id=org_id, name=name, holiday_date=day)
            db.session.add(holiday)
            db.session.commit()
            return holiday.id

    def request(self, org_id, user_id, type_id, start, end, days, status="pending"):
        with self.app.app_context():
            req = LeaveRequest(
                organization_id=org_id, user_id=user_id, leave_type_id=type_id,
                from_date=start, to_date=end, days=days, reason="test", status=status,
            )
            db.session.add(req)
            db.session.commit()
            return req.id

    def get(self, model, **filters):
        with self.app.app_context():
            return model.query.filter_by(**filters).first()

    def count(self, model, **filters):
        with self.app.app_context():
            return model.query.filter_by(**filters).count()

    def update(self, model, row_id, **values):
        with self.app.app_context():
            row = db.session.get(model, row_id)
            for key, value in values.items():
                setattr(row, key, value)
            db.session.commit()


@pytest.fixture()
def factory(flask_app):
    return Factory(flask_app)


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture()
def login_as(flask_app):
    def _login(email, password=PASSWORD):
        browser = flask_app.test_client()
        response = browser.post("/login", data={"email": email, "password": password})
        assert response.status_code == 302, f"login failed for {email}"
        return browser
    return _login


@pytest.fixture()
def world(factory):
    """Org A (corporate): admin, manager, employee.  Org B (bank): admin."""
    a = factory.org("Alpha Corp", "corporate")
    a_admin = factory.user(a, "admin@alpha.io", "Alice Alpha", "org_admin")
    a_mgr = factory.user(a, "mgr@alpha.io", "Maya Manager", "manager", a_admin)
    a_emp = factory.user(a, "emp@alpha.io", "Zelda Employee", "employee", a_mgr)
    b = factory.org("Beta Bank", "bank")
    b_admin = factory.user(b, "admin@beta.io", "Bob Beta", "org_admin")
    return SimpleNamespace(a=a, a_admin=a_admin, a_mgr=a_mgr, a_emp=a_emp,
                           b=b, b_admin=b_admin)

@pytest.fixture()
def owner_credentials():
    return SimpleNamespace(email=OWNER_EMAIL, password=OWNER_PASSWORD)


@pytest.fixture()
def owner_client(flask_app):
    browser = flask_app.test_client()
    r = browser.post("/owner/login", data={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert r.status_code == 302, "owner login failed"
    return browser

@pytest.fixture(autouse=True)
def owner_env(monkeypatch):
    """Tests always use the test owner login, never the real one from .env."""
    monkeypatch.setenv("OWNER_EMAIL", OWNER_EMAIL)
    monkeypatch.setenv("OWNER_PASSWORD_HASH", OWNER_HASH)