from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models import User, LeaveType, LeaveRequest, Holiday, Organization

bp = Blueprint("admin", __name__, url_prefix="/admin")


def org_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role != "org_admin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper


@bp.route("/employees", methods=["GET", "POST"])
@login_required
@org_admin_required
def employees():
    org_id = current_user.organization_id

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "employee")
        manager_id = request.form.get("manager_id", "")

        if role not in ("employee", "manager"):
            role = "employee"

        manager = None
        if manager_id.isdigit():
            manager = User.query.filter_by(id=int(manager_id), organization_id=org_id).first()

        if not (name and email and password):
            flash("Name, email and password are required.")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.")
        else:
            user = User(
                organization_id=org_id,
                name=name,
                email=email,
                role=role,
                manager_id=manager.id if manager else None,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Employee added.", "ok")
            return redirect(url_for("admin.employees"))

    users = User.query.filter_by(organization_id=org_id).order_by(User.name).all()
    managers = [u for u in users if u.role in ("org_admin", "manager")]
    by_id = {u.id: u for u in users}
    return render_template("admin/employees.html", users=users, managers=managers, by_id=by_id)


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