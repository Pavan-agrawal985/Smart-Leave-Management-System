from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User

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