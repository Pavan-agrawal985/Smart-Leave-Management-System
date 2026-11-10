from datetime import date, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models import LeaveType, LeaveRequest, User, Holiday


def weekend_set(org):
    return {int(x) for x in (org.weekend_days or "").split(",") if x.strip() != ""}


def working_days(org, from_date, to_date):
    weekend = weekend_set(org)
    holidays = {
        h.holiday_date
        for h in Holiday.query.filter(
            Holiday.organization_id == org.id,
            Holiday.holiday_date >= from_date,
            Holiday.holiday_date <= to_date,
        )
    }
    total = 0
    day = from_date
    while day <= to_date:
        if day.weekday() not in weekend and day not in holidays:
            total += 1
        day += timedelta(days=1)
    return total


def used_days(user_id, leave_type_id, year):
    total = (
        db.session.query(func.coalesce(func.sum(LeaveRequest.days), 0))
        .filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.leave_type_id == leave_type_id,
            LeaveRequest.status.in_(["pending", "approved"]),
            func.extract("year", LeaveRequest.from_date) == year,
        )
        .scalar()
    )
    return int(total)


def get_balances(user, year=None):
    year = year or date.today().year
    types = (
        LeaveType.query.filter_by(organization_id=user.organization_id)
        .order_by(LeaveType.name)
        .all()
    )
    rows = []
    for t in types:
        used = used_days(user.id, t.id, year)
        rows.append({"type": t, "quota": t.yearly_quota, "used": used, "left": t.yearly_quota - used})
    return rows


def has_overlap(user_id, from_date, to_date):
    return (
        LeaveRequest.query.filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.from_date <= to_date,
            LeaveRequest.to_date >= from_date,
        ).first()
        is not None
    )


def can_approve(approver, req):
    if req.organization_id != approver.organization_id:
        return False
    if req.status != "pending":
        return False
    if req.user_id == approver.id:
        return False
    if approver.role == "org_admin":
        return True
    return req.user.manager_id == approver.id


def pending_for(approver):
    q = LeaveRequest.query.filter(
        LeaveRequest.organization_id == approver.organization_id,
        LeaveRequest.status == "pending",
        LeaveRequest.user_id != approver.id,
    )
    if approver.role != "org_admin":
        q = q.join(User, LeaveRequest.user_id == User.id).filter(User.manager_id == approver.id)
    return q.order_by(LeaveRequest.created_at.desc()).all()