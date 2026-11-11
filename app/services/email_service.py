import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from flask import url_for, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature
from app.extensions import db
from app.models import User

RESEND_WAIT = timedelta(minutes=10)


def _send(to_email, subject, body):
    username = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_PASSWORD")
    if not (username and password and to_email):
        return False

    msg = EmailMessage()
    msg["From"] = f"LeaveOk <{username}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    for method in ("ssl", "starttls"):
        try:
            if method == "ssl":
                server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
            else:
                server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
                server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as exc:  # email must never break the app
            print(f"Email via {method} failed:", repr(exc))
    return False


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="verify-email")


def can_send_verification(user):
    if not user.verification_sent_at:
        return True
    return datetime.utcnow() - user.verification_sent_at >= RESEND_WAIT


def send_verification_email(user):
    user.verification_sent_at = datetime.utcnow()
    db.session.commit()
    token = _serializer().dumps({"id": user.id, "email": user.email})
    link = url_for("auth.verify_email", token=token, _external=True)
    return _send(
        user.email,
        "Verify your LeaveOk email",
        f"Hi {user.name},\n\nClick this link to verify your email (valid for 2 days):\n{link}\n\n"
        "If you did not expect this email, you can ignore it.",
    )


def read_verification_token(token):
    try:
        data = _serializer().loads(token, max_age=60 * 60 * 24 * 2)
    except BadSignature:  # also covers expired links
        return None
    user = db.session.get(User, data.get("id"))
    if user and user.email == data.get("email"):
        return user
    return None


def approvers_for(req):
    employee = req.user
    if employee.manager_id:
        manager = db.session.get(User, employee.manager_id)
        if manager and manager.email_verified:
            return [manager]
    return User.query.filter(
        User.organization_id == req.organization_id,
        User.role == "org_admin",
        User.id != employee.id,
        User.email_verified.is_(True),
    ).all()


def notify_new_request(req):
    for approver in approvers_for(req):
        _send(
            approver.email,
            "A leave request is waiting for you",
            "A leave request is waiting for your approval.\n\n"
            "Log in to LeaveOk to view it.",
        )


def notify_decision(req):
    if not req.user.email_verified:
        return
    _send(
        req.user.email,
        f"Your leave request was {req.status}",
        "Log in to LeaveOk to see the details.",
    )


def notify_org_approved(org):
    admin = User.query.filter_by(organization_id=org.id, role="org_admin").first()
    if admin and admin.email_verified:
        _send(
            admin.email,
            "Your LeaveOk organization is approved",
            f"Good news, {org.name} is approved. You can log in to LeaveOk now.",
        )