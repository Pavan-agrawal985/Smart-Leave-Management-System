import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import Organization, User
from app.services.org_templates import seed_leave_types
from app.services.validation import check_email, check_password
from app.services.email_service import (
    send_verification_email, read_verification_token, can_send_verification,
    send_reset_email, read_reset_token, can_send_reset,
)

bp = Blueprint("auth", __name__)

MAX_FAILS = 5
LOCK_MINUTES = 15


def _is_owner_email(email):
    owner = os.environ.get("OWNER_EMAIL", "").strip().lower()
    return bool(owner) and email == owner


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

        is_owner = _is_owner_email(email)
        org = Organization(
            name=org_name,
            org_type=org_type,
            status="active" if is_owner else "pending",
        )
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

        send_verification_email(user)
        if is_owner:
            flash(f"Account created. Check {email} for the verification link, then log in.", "ok")
        else:
            flash(
                f"Account created. Click the verification link sent to {email}. "
                "The LeaveOk team will then review and approve your organization.",
                "ok",
            )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        now = datetime.utcnow()

        user = User.query.filter_by(email=email).first()

        if user and user.locked_until and user.locked_until > now:
            flash(f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes.")
            return render_template("auth/login.html")

        if user and user.check_password(password):
            if user.failed_logins or user.locked_until:
                user.failed_logins = 0
                user.locked_until = None
                db.session.commit()

            if not user.is_active:
                flash("This account is deactivated. Please contact your administrator.")
                return render_template("auth/login.html")

            if not user.email_verified:
                flash("Please verify your email first. Check your inbox and spam folder.")
                return render_template("auth/login.html", unverified_email=user.email)

            org = db.session.get(Organization, user.organization_id)
            if org.status == "pending":
                flash("Your organization is waiting for approval by the LeaveOk team. You will get an email when it is approved.")
                return render_template("auth/login.html")
            if org.status != "active":
                flash("Your organization request was not approved.")
                return render_template("auth/login.html")

            login_user(user)
            return redirect(url_for("main.dashboard"))

        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILS:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            db.session.commit()

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
    if user and not user.email_verified and can_send_verification(user):
        send_verification_email(user)
    flash(
        "If this account needs verification, a link was sent. "
        "You can request one every 10 minutes. Check your inbox and spam.",
        "ok",
    )
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and can_send_reset(user):
            send_reset_email(user)
        flash(
            "If this email is registered, a reset link was sent. "
            "You can request one every 10 minutes. Check your inbox and spam.",
            "ok",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = read_reset_token(token)
    if not user:
        flash("This reset link is invalid or expired. Please request a new one.")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        error = check_password(password)
        if error:
            flash(error)
        elif password != confirm:
            flash("The two passwords do not match.")
        else:
            user.set_password(password)
            user.failed_logins = 0
            user.locked_until = None
            user.email_verified = True  # the link reached their inbox, so the address is real
            db.session.commit()
            flash("Password changed. You can log in now.", "ok")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset.html", token=token)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))