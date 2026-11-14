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
    from app.services.leave_service import approver_for
    approver = approver_for(req.user)
    if approver and approver.email_verified:
        return [approver]
    return []

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



def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="reset-password")


def can_send_reset(user):
    if not user.reset_sent_at:
        return True
    return datetime.utcnow() - user.reset_sent_at >= RESEND_WAIT


def send_reset_email(user):
    user.reset_sent_at = datetime.utcnow()
    db.session.commit()
    # The token carries a fingerprint of the current password, so it works only once.
    token = _reset_serializer().dumps({"id": user.id, "fp": user.password_hash[-12:]})
    link = url_for("auth.reset_password", token=token, _external=True)
    return _send(
        user.email,
        "Reset your LeaveOk password",
        f"Hi {user.name},\n\nClick this link to choose a new password (valid for 1 hour):\n{link}\n\n"
        "If you did not ask for this, ignore this email. Your password stays the same.",
    )


def read_reset_token(token):
    try:
        data = _reset_serializer().loads(token, max_age=3600)
    except BadSignature:  # also covers expired links
        return None
    user = db.session.get(User, data.get("id"))
    if user and user.password_hash[-12:] == data.get("fp"):
        return user
    return None
INVITE_DAYS = 7


def _invite_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="invite")


def can_send_invite(user):
    return can_send_verification(user)


def send_invite_email(user, org_name):
    user.verification_sent_at = datetime.utcnow()
    db.session.commit()
    safe_org = " ".join(str(org_name).split())[:80]          # one clean line, safe in an email subject
    # The token carries a fingerprint of the current password, so it stops working once they join.
    token = _invite_serializer().dumps({"id": user.id, "fp": user.password_hash[-12:]})
    link = url_for("auth.accept_invite", token=token, _external=True)
    return _send(
        user.email,
        f"You are invited to join {safe_org} on LeaveOk",
        f"Hello,\n\nYou have been invited to join {safe_org} on LeaveOk.\n\n"
        f"Click this link to enter your details and choose a password (valid for {INVITE_DAYS} days):\n{link}\n\n"
        "If you did not expect this invitation, you can ignore this email.",
    )


def read_invite_token(token):
    try:
        data = _invite_serializer().loads(token, max_age=60 * 60 * 24 * INVITE_DAYS)
    except BadSignature:  # also covers expired links
        return None
    user = db.session.get(User, data.get("id"))
    if (
        user
        and user.invite_pending
        and user.is_active
        and user.password_hash[-12:] == data.get("fp")
    ):
        return user
    return None