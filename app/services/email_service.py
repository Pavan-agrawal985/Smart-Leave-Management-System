import os
import smtplib
from email.message import EmailMessage
from flask import url_for, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature
from app.extensions import db
from app.models import User


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


def send_verification_email(user):
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


def _dates(req):
    return f"{req.from_date.strftime('%d %b %Y')} to {req.to_date.strftime('%d %b %Y')}"


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
            f"Leave request from {req.user.name}",
            f"{req.user.name} applied for {req.days} working day(s) of "
            f"{req.leave_type.name} ({_dates(req)}).\n"
            f"Reason: {req.reason or '-'}\n\n"
            "Log in to LeaveOk to approve or reject.",
        )


def notify_decision(req):
    if not req.user.email_verified:
        return
    _send(
        req.user.email,
        f"Your leave request was {req.status}",
        f"Your {req.leave_type.name} request ({_dates(req)}, "
        f"{req.days} working day(s)) was {req.status}.",
    )