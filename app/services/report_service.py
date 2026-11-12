import csv
import io
from sqlalchemy import func
from app.models import LeaveRequest
from app.services.calendar_service import team_user_ids

HEADER = [
    "Employee", "Email", "Leave type", "From", "To",
    "Working days", "Status", "Reason", "Applied on",
]


def report_rows(viewer, year, status=None, type_id=None, person_id=None):
    ids = team_user_ids(viewer)
    q = LeaveRequest.query.filter(
        LeaveRequest.organization_id == viewer.organization_id,
        LeaveRequest.user_id.in_(ids),
        func.extract("year", LeaveRequest.from_date) == year,
    )
    if status in ("pending", "approved", "rejected"):
        q = q.filter(LeaveRequest.status == status)
    if type_id:
        q = q.filter(LeaveRequest.leave_type_id == type_id)
    if person_id:
        q = q.filter(LeaveRequest.user_id == person_id)
    return q.order_by(LeaveRequest.from_date.desc()).all()


def summarize(rows):
    people = {}
    for r in rows:
        entry = people.setdefault(
            r.user_id, {"name": r.user.name, "approved": 0, "pending": 0, "rejected": 0}
        )
        if r.status == "approved":
            entry["approved"] += r.days
        elif r.status == "pending":
            entry["pending"] += r.days
        else:
            entry["rejected"] += 1
    return sorted(people.values(), key=lambda e: e["name"].lower())


def _safe(value):
    """Stops spreadsheet formula injection: a cell starting with = + - @ would run as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for r in rows:
        writer.writerow([
            _safe(x) for x in (
                r.user.name,
                r.user.email,
                r.leave_type.name,
                r.from_date.isoformat(),
                r.to_date.isoformat(),
                r.days,
                r.status,
                r.reason,
                r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
            )
        ])
    return "\ufeff" + buffer.getvalue()   # the marker helps Excel read names correctly