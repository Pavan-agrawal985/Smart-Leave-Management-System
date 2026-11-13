from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import LeaveRequest, Organization, User


def platform_stats():
    week_ago = datetime.utcnow() - timedelta(days=7)
    return {
        "organizations": Organization.query.count(),
        "active": Organization.query.filter_by(status="active").count(),
        "suspended": Organization.query.filter(Organization.status != "active").count(),
        "people": User.query.filter_by(is_active=True).count(),
        "requests": LeaveRequest.query.count(),
        "pending": LeaveRequest.query.filter_by(status="pending").count(),
        "new_week": Organization.query.filter(Organization.created_at >= week_ago).count(),
    }


def org_rows():
    """One row per organization. Organization-level facts only, never employee details."""
    people = dict(
        db.session.query(User.organization_id, func.count(User.id))
        .filter(User.is_active.is_(True))
        .group_by(User.organization_id)
        .all()
    )
    requests = dict(
        db.session.query(LeaveRequest.organization_id, func.count(LeaveRequest.id))
        .group_by(LeaveRequest.organization_id)
        .all()
    )
    last = dict(
        db.session.query(LeaveRequest.organization_id, func.max(LeaveRequest.created_at))
        .group_by(LeaveRequest.organization_id)
        .all()
    )
    admins = {}
    for user in User.query.filter_by(role="org_admin").order_by(User.id).all():
        admins.setdefault(user.organization_id, user)

    rows = []
    for org in Organization.query.order_by(Organization.created_at.desc()).all():
        admin = admins.get(org.id)
        rows.append({
            "org": org,
            "admin_name": admin.name if admin else "-",
            "admin_email": admin.email if admin else "-",
            "people": people.get(org.id, 0),
            "requests": requests.get(org.id, 0),
            "last_activity": last.get(org.id),
        })
    return rows