import bcrypt
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="employee")  # org_admin, manager, employee
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, plain):
        self.password_hash = bcrypt.hashpw(
            plain.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, plain):
        return bcrypt.checkpw(plain.encode("utf-8"), self.password_hash.encode("utf-8"))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))