import calendar
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import LeaveType, LeaveRequest, Organization
from app.services.leave_service import (
    working_days, used_days, has_overlap, can_approve, pending_for, approver_for,
)
from app.services.email_service import notify_new_request, notify_decision
from app.services.calendar_service import month_data

bp = Blueprint("leave", __name__, url_prefix="/leave")


def _admins_take_no_leave():
    if current_user.role == "org_admin":
        flash("Administrators do not take leave here. You approve leave for your managers.")
        return redirect(url_for("main.dashboard"))
    return None


@bp.route("/apply", methods=["GET", "POST"])
@login_required
def apply():
    blocked = _admins_take_no_leave()
    if blocked:
        return blocked
    if approver_for(current_user) is None:
        flash("You do not have a manager yet, so you cannot apply for leave. Please ask your administrator.")
        return redirect(url_for("main.dashboard"))

    types = (
        LeaveType.query.filter_by(organization_id=current_user.organization_id)
        .order_by(LeaveType.name)
        .all()
    )

    if request.method == "POST":
        try:
            type_id = int(request.form.get("leave_type_id", ""))
            from_date = datetime.strptime(request.form.get("from_date", ""), "%Y-%m-%d").date()
            to_date = datetime.strptime(request.form.get("to_date", ""), "%Y-%m-%d").date()
        except ValueError:
            flash("Please fill all fields correctly.")
            return render_template("leave/apply.html", types=types)

        reason = request.form.get("reason", "").strip()
        leave_type = LeaveType.query.filter_by(
            id=type_id, organization_id=current_user.organization_id
        ).first()

        if not leave_type:
            flash("Invalid leave type.")
        elif to_date < from_date:
            flash("End date cannot be before start date.")
        elif (to_date - from_date).days > 365:
            flash("A leave request cannot be longer than one year.")
        elif has_overlap(current_user.id, from_date, to_date):
            flash("You already have a leave request in these dates.")
        else:
            org = db.session.get(Organization, current_user.organization_id)
            days = working_days(org, from_date, to_date)
            if days == 0:
                flash("These dates are all weekly offs or holidays, so no leave is needed.")
            else:
                left = leave_type.yearly_quota - used_days(
                    current_user.id, leave_type.id, from_date.year
                )
                if days > left:
                    flash(f"Not enough balance. You have {left} day(s) left for {leave_type.name}.")
                else:
                    new_req = LeaveRequest(
                        organization_id=current_user.organization_id,
                        user_id=current_user.id,
                        leave_type_id=leave_type.id,
                        from_date=from_date,
                        to_date=to_date,
                        days=days,
                        reason=reason,
                    )
                    db.session.add(new_req)
                    db.session.commit()
                    notify_new_request(new_req)
                    flash(f"Leave request submitted ({days} working day(s)).", "ok")
                    return redirect(url_for("leave.my"))

    return render_template("leave/apply.html", types=types)


@bp.route("/my")
@login_required
def my():
    blocked = _admins_take_no_leave()
    if blocked:
        return blocked
    requests_ = (
        LeaveRequest.query.filter_by(user_id=current_user.id)
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )
    return render_template("leave/my.html", requests=requests_)


@bp.route("/approvals")
@login_required
def approvals():
    if current_user.role not in ("org_admin", "manager"):
        abort(403)
    return render_template("leave/approvals.html", requests=pending_for(current_user))


@bp.route("/<int:req_id>/<action>", methods=["POST"])
@login_required
def decide(req_id, action):
    if action not in ("approve", "reject"):
        abort(404)
    req = LeaveRequest.query.filter_by(
        id=req_id, organization_id=current_user.organization_id
    ).first_or_404()
    if not can_approve(current_user, req):
        abort(403)
    req.status = "approved" if action == "approve" else "rejected"
    db.session.commit()
    notify_decision(req)
    flash(f"Request {req.status}.", "ok")
    return redirect(url_for("leave.approvals"))


@bp.route("/calendar")
@login_required
def team_calendar():
    today = date.today()
    try:
        year, month = (int(x) for x in request.args.get("month", "").split("-"))
        date(year, month, 1)
    except ValueError:
        year, month = today.year, today.month

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)

    org = db.session.get(Organization, current_user.organization_id)
    data = month_data(current_user, org, year, month)
    return render_template(
        "leave/calendar.html",
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        prev=f"{prev_y}-{prev_m:02d}",
        nxt=f"{next_y}-{next_m:02d}",
        today=today,
        **data,
    )