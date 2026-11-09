from datetime import datetime
from app.extensions import db


class LeaveType(db.Model):
    __tablename__ = "leave_types"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = db.Column(db.String(60), nullable=False)
    yearly_quota = db.Column(db.Integer, default=12)
    carry_forward = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint("organization_id", "name"),)


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    leave_type_id = db.Column(
        db.Integer, db.ForeignKey("leave_types.id"), nullable=False
    )
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending", index=True)  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    leave_type = db.relationship("LeaveType")