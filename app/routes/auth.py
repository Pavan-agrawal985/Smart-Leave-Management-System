from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import Organization, User
from app.services.org_templates import seed_leave_types
from app.services.validation import check_email, check_password
from app.services.email_service import send_verification_email, read_verification_token

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

        email, email_error = check_email(email)
        if email_error:
            flash(email_error)
            return render_template("auth/register.html")
        password_error = check_password(password)
        if password_error:
            flash(password_error)
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return render_template("auth/register.html")

        org = Organization(name=org_name, org_type=org_type)
        db.session.add(org)
        db.session.flush()  # gives org an id before we save the user
        seed_leave_types(org)

        user = User(
            organization_id=org.id,
            name=name,
            email=email,
            role="org_admin",
            email_verified=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if send_verification_email(user):
            flash(f"Account created. We sent a verification link to {email}. Click it, then log in.", "ok")
        else:
            flash("Account created, but the verification email could not be sent. Try to log in and press 'Resend verification email'.", "ok")
        return redirect(url_for("auth.login"))

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
            if not user.email_verified:
                flash("Please verify your email first. Check your inbox and spam folder.")
                return render_template("auth/login.html", unverified_email=user.email)
            login_user(user)
            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.")

    return render_template("auth/login.html")


@bp.route("/verify/<token>")
def verify_email(token):
    user = read_verification_token(token)
    if not user:
        flash("This verification link is invalid or expired. Log in and press 'Resend verification email'.")
        return redirect(url_for("auth.login"))
    if not user.email_verified:
        user.email_verified = True
        db.session.commit()
    flash("Email verified. You can log in now.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user and not user.email_verified:
        send_verification_email(user)
    flash("If this account needs verification, a new link was sent. Check your inbox and spam.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))