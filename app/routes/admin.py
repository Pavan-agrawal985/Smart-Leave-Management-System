from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User, LeaveType, LeaveRequest, Holiday, Organization
from app.services.validation import check_email, check_password
from app.services.email_service import send_invite_email, can_send_invite
bp = Blueprint("admin", __name__, url_prefix="/admin")


def org_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role != "org_admin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- employees
@bp.route("/employees", methods=["GET", "POST"])
@login_required
@org_admin_required
def employees():
    org_id = current_user.organization_id

    if request.method == "POST":
        name = " ".join(request.form.get("name", "").split())
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "employee")
        manager_id = request.form.get("manager_id", "")

        if role not in ("employee", "manager"):
            role = "employee"

        manager = None
        if manager_id.isdigit():
            manager = User.query.filter_by(
                id=int(manager_id), organization_id=org_id, is_active=True
            ).first()
            if manager and manager.role not in ("org_admin", "manager"):
                manager = None

        email, email_error = check_email(email)

        if email_error:
            flash(email_error)
        elif len(name) > 100:
            flash("Name is too long.")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.")
        else:
            user = User(
                organization_id=org_id,
                name=name or email.split("@")[0],
                email=email,
                role=role,
                manager_id=manager.id if manager else None,
                email_verified=False,
                invite_pending=True,
            )
            user.set_unusable_password()
            db.session.add(user)
            db.session.commit()
            org = db.session.get(Organization, org_id)
            if send_invite_email(user, org.name):
                flash(f"Invitation sent to {email}. They set their own details and password.", "ok")
            else:
                flash("Person added, but the invitation email could not be sent. Use 'Resend invite' in the list.", "ok")
            return redirect(url_for("admin.employees"))

    users = User.query.filter_by(organization_id=org_id).order_by(User.name).all()
    managers = [u for u in users if u.role in ("org_admin", "manager") and u.is_active]
    by_id = {u.id: u for u in users}
    return render_template("admin/employees.html", users=users, managers=managers, by_id=by_id)


@bp.route("/employees/<int:user_id>/resend-invite", methods=["POST"])
@login_required
@org_admin_required
def resend_invite(user_id):
    user = User.query.filter_by(
        id=user_id, organization_id=current_user.organization_id
    ).first_or_404()
    org = db.session.get(Organization, current_user.organization_id)

    if not user.invite_pending:
        flash("This person has already joined.")
    elif not can_send_invite(user):
        flash("An invitation was sent recently. Please wait 10 minutes before sending another.")
    else:
        send_invite_email(user, org.name)
        flash(f"Invitation sent again to {user.email}.", "ok")
    return redirect(url_for("admin.employees"))

def would_create_loop(user_id, new_manager_id):
    """True if making new_manager_id the boss of user_id would create a reporting loop."""
    seen = set()
    current = new_manager_id
    while current is not None and current not in seen:
        if current == user_id:
            return True
        seen.add(current)
        boss = db.session.get(User, current)
        current = boss.manager_id if boss else None
    return False


def move_reports_up(user):
    """The people reporting to `user` now report to `user`'s own manager."""
    for report in User.query.filter_by(manager_id=user.id).all():
        report.manager_id = user.manager_id


@bp.route("/employees/<int:user_id>/edit", methods=["POST"])
@login_required
@org_admin_required
def edit_employee(user_id):
    org_id = current_user.organization_id
    user = User.query.filter_by(id=user_id, organization_id=org_id).first_or_404()

    if user.role == "org_admin":
        flash("Admin accounts cannot be changed here.")
        return redirect(url_for("admin.employees"))

    role = request.form.get("role", user.role)
    if role not in ("employee", "manager"):
        role = user.role

    manager = None
    manager_id = request.form.get("manager_id", "")
    if manager_id.isdigit():
        manager = User.query.filter_by(
            id=int(manager_id), organization_id=org_id, is_active=True
        ).first()
        if manager and manager.role not in ("org_admin", "manager"):
            manager = None

    if manager and would_create_loop(user.id, manager.id):
        flash("That would make a reporting loop. Choose a different manager.")
        return redirect(url_for("admin.employees"))

    if user.role == "manager" and role == "employee":
        move_reports_up(user)   # an employee cannot approve, so hand the team upwards

    user.role = role
    user.manager_id = manager.id if manager else None
    db.session.commit()
    flash("Employee updated.", "ok")
    return redirect(url_for("admin.employees"))


@bp.route("/employees/<int:user_id>/status/<action>", methods=["POST"])
@login_required
@org_admin_required
def employee_status(user_id, action):
    if action not in ("deactivate", "reactivate"):
        abort(404)
    user = User.query.filter_by(
        id=user_id, organization_id=current_user.organization_id
    ).first_or_404()

    if user.role == "org_admin":
        flash("Admin accounts cannot be deactivated here.")
    elif action == "deactivate":
        move_reports_up(user)
        user.is_active = False
        db.session.commit()
        flash(f"{user.name} was deactivated.", "ok")
    else:
        user.is_active = True
        db.session.commit()
        flash(f"{user.name} was reactivated.", "ok")
    return redirect(url_for("admin.employees"))


# -------------------------------------------------------------- leave types

def valid_quota(text):
    return text.isdigit() and 0 <= int(text) <= 365


@bp.route("/leave-types", methods=["GET", "POST"])
@login_required
@org_admin_required
def leave_types():
    org_id = current_user.organization_id

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        quota = request.form.get("yearly_quota", "")
        carry = request.form.get("carry_forward") == "on"

        if not name:
            flash("Name is required.")
        elif not valid_quota(quota):
            flash("Days per year must be a number between 0 and 365.")
        elif LeaveType.query.filter_by(organization_id=org_id, name=name).first():
            flash("This leave type already exists.")
        else:
            db.session.add(
                LeaveType(
                    organization_id=org_id,
                    name=name,
                    yearly_quota=int(quota),
                    carry_forward=carry,
                )
            )
            db.session.commit()
            flash("Leave type added.", "ok")
        return redirect(url_for("admin.leave_types"))

    types = (
        LeaveType.query.filter_by(organization_id=org_id)
        .order_by(LeaveType.name)
        .all()
    )
    return render_template("admin/leave_types.html", types=types)


@bp.route("/leave-types/<int:type_id>/edit", methods=["POST"])
@login_required
@org_admin_required
def edit_leave_type(type_id):
    lt = LeaveType.query.filter_by(
        id=type_id, organization_id=current_user.organization_id
    ).first_or_404()

    name = request.form.get("name", "").strip()
    quota = request.form.get("yearly_quota", "")
    carry = request.form.get("carry_forward") == "on"

    clash = LeaveType.query.filter(
        LeaveType.organization_id == current_user.organization_id,
        LeaveType.name == name,
        LeaveType.id != lt.id,
    ).first()

    if not name:
        flash("Name is required.")
    elif not valid_quota(quota):
        flash("Days per year must be a number between 0 and 365.")
    elif clash:
        flash("Another leave type already has this name.")
    else:
        lt.name = name
        lt.yearly_quota = int(quota)
        lt.carry_forward = carry
        db.session.commit()
        flash("Leave type updated.", "ok")
    return redirect(url_for("admin.leave_types"))


@bp.route("/leave-types/<int:type_id>/delete", methods=["POST"])
@login_required
@org_admin_required
def delete_leave_type(type_id):
    lt = LeaveType.query.filter_by(
        id=type_id, organization_id=current_user.organization_id
    ).first_or_404()

    if LeaveRequest.query.filter_by(leave_type_id=lt.id).first():
        flash("Cannot delete: leave requests already use this type. Set its days to 0 instead.")
    else:
        db.session.delete(lt)
        db.session.commit()
        flash("Leave type deleted.", "ok")
    return redirect(url_for("admin.leave_types"))


# ----------------------------------------------------------------- holidays

DAYS = [(0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri"), (5, "Sat"), (6, "Sun")]


@bp.route("/holidays", methods=["GET", "POST"])
@login_required
@org_admin_required
def holidays():
    org_id = current_user.organization_id

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        try:
            day = datetime.strptime(request.form.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            day = None

        if not name or not day:
            flash("Holiday name and a valid date are required.")
        elif Holiday.query.filter_by(organization_id=org_id, holiday_date=day).first():
            flash("A holiday already exists on this date.")
        else:
            db.session.add(Holiday(organization_id=org_id, name=name, holiday_date=day))
            db.session.commit()
            flash("Holiday added.", "ok")
        return redirect(url_for("admin.holidays"))

    org = db.session.get(Organization, org_id)
    weekend = {int(x) for x in (org.weekend_days or "").split(",") if x.strip() != ""}
    items = Holiday.query.filter_by(organization_id=org_id).order_by(Holiday.holiday_date).all()
    return render_template("admin/holidays.html", holidays=items, days=DAYS, weekend=weekend)


@bp.route("/holidays/weekend", methods=["POST"])
@login_required
@org_admin_required
def set_weekend():
    chosen = sorted({int(x) for x in request.form.getlist("weekend") if x.isdigit() and 0 <= int(x) <= 6})
    org = db.session.get(Organization, current_user.organization_id)
    org.weekend_days = ",".join(str(x) for x in chosen)
    db.session.commit()
    flash("Weekly offs saved.", "ok")
    return redirect(url_for("admin.holidays"))


@bp.route("/holidays/<int:holiday_id>/delete", methods=["POST"])
@login_required
@org_admin_required
def delete_holiday(holiday_id):
    h = Holiday.query.filter_by(
        id=holiday_id, organization_id=current_user.organization_id
    ).first_or_404()
    db.session.delete(h)
    db.session.commit()
    flash("Holiday deleted.", "ok")
    return redirect(url_for("admin.holidays"))