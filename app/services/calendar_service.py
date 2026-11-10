import calendar
from datetime import timedelta
from sqlalchemy import or_
from app.models import User, LeaveRequest, Holiday


def team_user_ids(user):
    base = User.query.filter(User.organization_id == user.organization_id)
    if user.role == "org_admin":
        q = base
    elif user.role == "manager":
        q = base.filter(or_(User.manager_id == user.id, User.id == user.id))
    elif user.manager_id:
        q = base.filter(User.manager_id == user.manager_id)
    else:
        q = base.filter(User.id == user.id)
    return [u.id for u in q.all()]


def month_data(user, org, year, month):
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    first, last = weeks[0][0], weeks[-1][-1]
    ids = team_user_ids(user)

    leaves = LeaveRequest.query.filter(
        LeaveRequest.user_id.in_(ids),
        LeaveRequest.status.in_(["pending", "approved"]),
        LeaveRequest.from_date <= last,
        LeaveRequest.to_date >= first,
    ).all()

    holidays = {
        h.holiday_date: h.name
        for h in Holiday.query.filter(
            Holiday.organization_id == org.id,
            Holiday.holiday_date >= first,
            Holiday.holiday_date <= last,
        )
    }
    weekend = {int(x) for x in (org.weekend_days or "").split(",") if x.strip() != ""}

    by_day = {}
    for r in leaves:
        d = max(r.from_date, first)
        end = min(r.to_date, last)
        while d <= end:
            by_day.setdefault(d, []).append((r.user.name, r.status))
            d += timedelta(days=1)

    return {"weeks": weeks, "by_day": by_day, "holidays": holidays, "weekend": weekend}