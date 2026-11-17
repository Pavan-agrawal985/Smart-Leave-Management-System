from datetime import date, timedelta

import bcrypt
import click

from app.extensions import db
from app.models import Department, Holiday, LeaveRequest, LeaveType, Organization, User
from app.services.leave_service import weekend_set, working_days
from app.services.org_templates import seed_leave_types
from app.services.validation import check_password, owner_password_error

DEMO_ORG = "Demo Corporation"

PEOPLE = [  # (tag, name, role, reports to)
    ("asha", "Anita Verma", "org_admin", None),
    ("rahul", "Rohit Mehta", "manager", "asha"),
    ("neha", "Neha Kapoor", "manager", "asha"),
    ("aman", "Aman Singh", "employee", "rahul"),
    ("ritu", "Ritu Sharma", "employee", "rahul"),
    ("sana", "Sana Khan", "employee", "rahul"),
    ("karan", "Karan Joshi", "employee", "neha"),
    ("pooja", "Pooja Nair", "employee", "neha"),
]

# (person, leave type, days from today, length in days, status)
PLAN = [
    ("aman", "Casual Leave", -21, 2, "approved"),
    ("aman", "Sick Leave", 6, 1, "pending"),
    ("ritu", "Annual Leave", 12, 5, "approved"),
    ("ritu", "Casual Leave", -35, 1, "approved"),
    ("sana", "Casual Leave", 3, 2, "pending"),
    ("sana", "Sick Leave", -10, 3, "approved"),
    ("karan", "Casual Leave", 8, 2, "approved"),
    ("karan", "Annual Leave", -28, 2, "rejected"),
    ("pooja", "Annual Leave", 15, 4, "pending"),
    ("pooja", "Casual Leave", -14, 1, "approved"),
    ("rahul", "Casual Leave", 18, 2, "approved"),
]

REASONS = {
    "Casual Leave": "Family function",
    "Sick Leave": "Doctor's advice",
    "Annual Leave": "Planned trip",
}


def _plus(email, tag):
    local, domain = email.split("@", 1)
    return f"{local.split('+', 1)[0]}+{tag}@{domain}"


def _next_working_day(day, weekend):
    while day.weekday() in weekend:
        day += timedelta(days=1)
    return day


def register_commands(app):
    @app.cli.command("seed-demo")
    @click.option("--email", required=True, help="Your real Gmail. Demo users become yourname+demo-tag@gmail.com")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def seed_demo(email, password):
        """Create 'Demo Corporation' with people, holidays and leave requests."""
        if "@" not in email:
            raise click.ClickException("Give a real email address.")
        error = check_password(password)
        if error:
            raise click.ClickException(error)
        if Organization.query.filter_by(name=DEMO_ORG).first():
            raise click.ClickException("Demo Corporation already exists. Run 'flask delete-demo' first.")
        wanted = [_plus(email, f"demo-{p[0]}") for p in PEOPLE]
        if User.query.filter(User.email.in_(wanted)).first():
            raise click.ClickException("One of the demo emails is already registered.")

        today = date.today()
        org = Organization(name=DEMO_ORG, org_type="corporate", status="active")
        db.session.add(org)
        db.session.flush()
        seed_leave_types(org)
        weekend = weekend_set(org)

        for offset, name in ((9, "Founders Day"), (24, "Winter Break Day")):
            db.session.add(Holiday(
                organization_id=org.id, name=name,
                holiday_date=_next_working_day(today + timedelta(days=offset), weekend),
            ))
        db.session.flush()

        users = {}
        for tag, name, role, boss in PEOPLE:
            user = User(
                organization_id=org.id, name=name, email=_plus(email, f"demo-{tag}"),
                role=role, manager_id=users[boss].id if boss else None, email_verified=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            users[tag] = user

        types = {t.name: t for t in LeaveType.query.filter_by(organization_id=org.id)}
        made = 0
        for tag, type_name, offset, length, status in PLAN:
            start = _next_working_day(today + timedelta(days=offset), weekend)
            end = start + timedelta(days=length - 1)
            days = working_days(org, start, end)
            if days == 0:
                continue
            db.session.add(LeaveRequest(
                organization_id=org.id, user_id=users[tag].id,
                leave_type_id=types[type_name].id, from_date=start, to_date=end,
                days=days, reason=REASONS[type_name], status=status,
            ))
            made += 1
        db.session.commit()

        click.echo(f"Created {DEMO_ORG}: {len(users)} people, {made} leave requests.")
        click.echo(f"Administrator login: {_plus(email, 'demo-asha')}")
        click.echo(f"Manager login:       {_plus(email, 'demo-rahul')}")
        click.echo(f"Employee login:      {_plus(email, 'demo-aman')}")
        click.echo("Password: the one you just typed. Keep it private.")

    @app.cli.command("delete-demo")
    @click.confirmation_option(prompt="Delete Demo Corporation and ALL its data?")
    def delete_demo():
        """Remove the demo organization completely."""
        org = Organization.query.filter_by(name=DEMO_ORG).first()
        if not org:
            raise click.ClickException("No demo organization found.")
        org_id = org.id
        User.query.filter_by(organization_id=org_id).update({"manager_id": None})
        for model in (LeaveRequest, Holiday, LeaveType, User, Department):
            model.query.filter_by(organization_id=org_id).delete()
        db.session.delete(org)
        db.session.commit()
        click.echo("Demo Corporation deleted.")

    @app.cli.command("owner-hash")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def owner_hash(password):
        """Print the value to store as OWNER_PASSWORD_HASH."""
        error = owner_password_error(password)
        if error:
            raise click.ClickException(error)
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        click.echo("Copy the line below into your settings as OWNER_PASSWORD_HASH:")
        click.echo(hashed)