from app.extensions import db
from app.models import LeaveType

TEMPLATES = {
    "school": [("Casual Leave", 12, False), ("Medical Leave", 10, False), ("Duty Leave", 10, False)],
    "college": [("Casual Leave", 12, False), ("Medical Leave", 10, False), ("Duty Leave", 15, False), ("Earned Leave", 15, True)],
    "corporate": [("Annual Leave", 24, True), ("Sick Leave", 12, False), ("Casual Leave", 8, False)],
    "bank": [("Privilege Leave", 30, True), ("Sick Leave", 12, False), ("Casual Leave", 12, False)],
    "custom": [("Casual Leave", 12, False), ("Sick Leave", 10, False)],
}


def seed_leave_types(org):
    for name, quota, carry in TEMPLATES.get(org.org_type, TEMPLATES["custom"]):
        db.session.add(
            LeaveType(organization_id=org.id, name=name, yearly_quota=quota, carry_forward=carry)
        )