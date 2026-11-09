from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Organization
from app.services.leave_service import get_balances, pending_for

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    org = db.session.get(Organization, current_user.organization_id)
    balances = get_balances(current_user)
    pending_count = 0
    if current_user.role in ("org_admin", "manager"):
        pending_count = len(pending_for(current_user))
    return render_template(
        "dashboard.html", org=org, balances=balances, pending_count=pending_count
    )