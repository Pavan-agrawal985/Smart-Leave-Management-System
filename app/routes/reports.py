from datetime import date
from flask import Blueprint, Response, abort, render_template, request
from flask_login import login_required, current_user
from app.models import LeaveType, User
from app.services.calendar_service import team_user_ids
from app.services.report_service import report_rows, summarize, to_csv

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _allowed():
    if current_user.role not in ("org_admin", "manager"):
        abort(403)


def _filters():
    year = request.args.get("year", type=int) or date.today().year
    year = min(max(year, 2000), 2100)
    status = request.args.get("status", "")
    if status not in ("pending", "approved", "rejected"):
        status = ""
    type_id = request.args.get("type", type=int)
    person_id = request.args.get("person", type=int)
    return year, status, type_id, person_id


@bp.route("/")
@login_required
def index():
    _allowed()
    year, status, type_id, person_id = _filters()
    rows = report_rows(current_user, year, status, type_id, person_id)
    people = (
        User.query.filter(User.id.in_(team_user_ids(current_user)))
        .order_by(User.name)
        .all()
    )
    types = (
        LeaveType.query.filter_by(organization_id=current_user.organization_id)
        .order_by(LeaveType.name)
        .all()
    )
    return render_template(
        "reports/index.html",
        rows=rows, summary=summarize(rows), people=people, types=types,
        year=year, status=status, type_id=type_id, person_id=person_id,
    )


@bp.route("/export.csv")
@login_required
def export():
    _allowed()
    year, status, type_id, person_id = _filters()
    rows = report_rows(current_user, year, status, type_id, person_id)
    return Response(
        to_csv(rows),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leave-report-{year}.csv"},
    )