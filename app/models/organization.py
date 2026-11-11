from datetime import datetime
from app.extensions import db


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    org_type = db.Column(db.String(30), default="custom")  # school, college, corporate, bank, custom
    weekend_days = db.Column(
        db.String(20), nullable=False, default="5,6", server_default="5,6"
    )  # 0=Mon ... 6=Sun
    status = db.Column(
        db.String(20), nullable=False, default="pending", server_default="active"
    )  # pending, active, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)


class Holiday(db.Model):
    __tablename__ = "holidays"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    holiday_date = db.Column(db.Date, nullable=False)

    __table_args__ = (db.UniqueConstraint("organization_id", "holiday_date"),)