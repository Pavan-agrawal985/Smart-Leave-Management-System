from flask import Blueprint, Response, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Organization
from app.services.leave_service import get_balances, pending_for

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@bp.route("/robots.txt")
def robots():
    text = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /owner/\n"
        "Disallow: /leave/\n"
        "Disallow: /dashboard\n"
        f"Sitemap: {url_for('main.sitemap', _external=True)}\n"
    )
    return Response(text, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    pages = [
        url_for("main.index", _external=True),
        url_for("auth.login", _external=True),
        url_for("auth.register", _external=True),
    ]
    urls = "".join(f"<url><loc>{p}</loc></url>" for p in pages)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(xml, mimetype="application/xml")


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