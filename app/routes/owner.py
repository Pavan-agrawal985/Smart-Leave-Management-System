import os
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Organization, User

bp = Blueprint("owner", __name__, url_prefix="/owner")


def owner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        owner = os.environ.get("OWNER_EMAIL", "").strip().lower()
        if not owner or current_user.email.lower() != owner:
            abort(404)
        return f(*args, **kwargs)
    return wrapper


@bp.route("/organizations")
@login_required
@owner_required
def organizations():
    orgs = Organization.query.order_by(Organization.created_at.desc()).all()
    admins = {}
    for u in User.query.filter_by(role="org_admin").all():
        admins.setdefault(u.organization_id, u)
    return render_template("owner/organizations.html", orgs=orgs, admins=admins)


@bp.route("/organizations/<int:org_id>/<action>", methods=["POST"])
@login_required
@owner_required
def decide(org_id, action):
    if action not in ("suspend", "reactivate"):
        abort(404)
    org = db.session.get(Organization, org_id)
    if org is None:
        abort(404)
    if org.id == current_user.organization_id:
        flash("You cannot change your own organization.")
        return redirect(url_for("owner.organizations"))

    org.status = "suspended" if action == "suspend" else "active"
    db.session.commit()
    flash(f"{org.name} is now {org.status}.", "ok")
    return redirect(url_for("owner.organizations"))