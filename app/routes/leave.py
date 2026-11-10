from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import LeaveType, LeaveRequest, Organization
from app.services.leave_service import (
    working_days, used_days, has_overlap, can_approve, pending_for,
)

bp = Blueprint("leave", __name__, url_prefix="/leave")


@bp.route("/apply", methods=["GET", "POST"])
@login_required
def apply():
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
                    db.session.add(
                        LeaveRequest(
                            organization_id=current_user.organization_id,
                            user_id=current_user.id,
                            leave_type_id=leave_type.id,
                            from_date=from_date,
                            to_date=to_date,
                            days=days,
                            reason=reason,
                        )
                    )
                    db.session.commit()
                    flash(f"Leave request submitted ({days} working day(s)).", "ok")
                    return redirect(url_for("leave.my"))

    return render_template("leave/apply.html", types=types)


@bp.route("/my")
@login_required
def my():
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
    flash(f"Request {req.status}.", "ok")
    return redirect(url_for("leave.approvals"))