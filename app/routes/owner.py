import hmac
import os
import time
from functools import wraps

import bcrypt
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, session, url_for,
)
from app.extensions import db
from app.models import Organization
from app.services.owner_stats import org_rows, platform_stats

bp = Blueprint("owner", __name__, url_prefix="/owner")

SESSION_HOURS = 8


def owner_configured():
    return bool(
        os.environ.get("OWNER_EMAIL", "").strip()
        and os.environ.get("OWNER_PASSWORD_HASH", "").strip()
    )


def check_owner(email, password):
    expected = os.environ.get("OWNER_EMAIL", "").strip().lower()
    hashed = os.environ.get("OWNER_PASSWORD_HASH", "").strip()
    if not (expected and hashed):
        return False
    email_ok = hmac.compare_digest(email.strip().lower().encode("utf-8"), expected.encode("utf-8"))
    try:                                   # always check the password, so timing reveals nothing
        password_ok = bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        password_ok = False
    return email_ok and password_ok


def owner_logged_in():
    if not session.get("owner"):
        return False
    if time.time() - session.get("owner_at", 0) > SESSION_HOURS * 3600:
        session.pop("owner", None)
        session.pop("owner_at", None)
        return False
    return True


def owner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not owner_logged_in():
            return redirect(url_for("owner.login"))
        return f(*args, **kwargs)
    return wrapper


@bp.route("/")
@owner_required
def home():
    return redirect(url_for("owner.organizations"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if owner_logged_in():
        return redirect(url_for("owner.organizations"))

    if request.method == "POST":
        if not owner_configured():
            flash("Owner login is not set up on this server.")
        elif check_owner(request.form.get("email", ""), request.form.get("password", "")):
            session["owner"] = True
            session["owner_at"] = time.time()
            return redirect(url_for("owner.organizations"))
        else:
            time.sleep(current_app.config.get("OWNER_FAIL_DELAY", 1.0))
            flash("Invalid owner email or password.")

    return render_template("owner/login.html")


@bp.route("/logout")
def logout():
    session.pop("owner", None)
    session.pop("owner_at", None)
    return redirect(url_for("owner.login"))


@bp.route("/organizations")
@owner_required
def organizations():
    return render_template("owner/organizations.html", stats=platform_stats(), rows=org_rows())


@bp.route("/organizations/<int:org_id>/<action>", methods=["POST"])
@owner_required
def decide(org_id, action):
    if action not in ("suspend", "reactivate"):
        abort(404)
    org = db.session.get(Organization, org_id)
    if org is None:
        abort(404)
    org.status = "suspended" if action == "suspend" else "active"
    db.session.commit()
    flash(f"{org.name} is now {org.status}.", "ok")
    return redirect(url_for("owner.organizations"))