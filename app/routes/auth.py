from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import Organization, User

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        org_name = request.form.get("org_name", "").strip()
        org_type = request.form.get("org_type", "custom")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not (org_name and name and email and password):
            flash("All fields are required.")
            return render_template("auth/register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return render_template("auth/register.html")

        org = Organization(name=org_name, org_type=org_type)
        db.session.add(org)
        db.session.flush()  # gives org an id before we save the user

        user = User(organization_id=org.id, name=name, email=email, role="org_admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))