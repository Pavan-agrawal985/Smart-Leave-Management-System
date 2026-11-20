import re
from datetime import date, datetime

PHONE_RE = re.compile(r"^[0-9+()\-\s]{7,20}$")
FIELDS = ("name", "job_title", "department", "employee_code", "phone", "location", "joined_on", "about")
COMPLETENESS_FIELDS = ("photo_url", "job_title", "department", "phone", "location", "joined_on", "about")


def avatar_src(user, size=96):
    """The photo address, resized by the image service for this display size."""
    url = getattr(user, "photo_url", None)
    if not url:
        return None
    if "res.cloudinary.com" in url and "/upload/" in url:
        return url.replace("/upload/", f"/upload/c_fill,w_{size},h_{size},g_face,f_auto,q_auto/", 1)
    return url


def initials(name):
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def avatar_hue(user):
    return (getattr(user, "id", 0) or 0) * 47 % 360


def completeness(user):
    filled = sum(1 for field in COMPLETENESS_FIELDS if getattr(user, field, None))
    return round(filled * 100 / len(COMPLETENESS_FIELDS))


def shown_values(user, form=None):
    """What to show in the edit form: the saved values, or what was just typed."""
    if form is not None:
        return {key: form.get(key, "") for key in FIELDS}
    return {
        "name": user.name or "",
        "job_title": user.job_title or "",
        "department": user.department or "",
        "employee_code": user.employee_code or "",
        "phone": user.phone or "",
        "location": user.location or "",
        "joined_on": user.joined_on.isoformat() if user.joined_on else "",
        "about": user.about or "",
    }


def clean_profile(form):
    """Returns (values, error). The error is None when everything is fine."""

    def one_line(key, limit, label):
        value = " ".join(form.get(key, "").split())
        if len(value) > limit:
            raise ValueError(f"{label} is too long.")
        return value

    try:
        name = one_line("name", 100, "Name")
        if not name:
            raise ValueError("Please enter your name.")
        values = {
            "name": name,
            "job_title": one_line("job_title", 100, "Job title") or None,
            "department": one_line("department", 100, "Department") or None,
            "employee_code": one_line("employee_code", 40, "Employee ID") or None,
            "location": one_line("location", 100, "Location") or None,
        }

        phone = " ".join(form.get("phone", "").split())
        if phone and not PHONE_RE.match(phone):
            raise ValueError("Phone number can have digits, spaces, + - and brackets only (7 to 20 characters).")
        values["phone"] = phone or None

        joined = form.get("joined_on", "").strip()
        if joined:
            try:
                day = datetime.strptime(joined, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Please enter a valid date of joining.")
            if day > date.today() or day < date(1950, 1, 1):
                raise ValueError("Date of joining must be between 1950 and today.")
            values["joined_on"] = day
        else:
            values["joined_on"] = None

        about = form.get("about", "").replace("\r\n", "\n").strip()
        if len(about) > 500:
            raise ValueError("About is too long (500 characters at most).")
        values["about"] = about or None
    except ValueError as exc:
        return None, str(exc)
    return values, None


def can_view_profile(viewer, target):
    if viewer.organization_id != target.organization_id:
        return False
    if viewer.id == target.id or viewer.role == "org_admin":
        return True
    if target.role == "org_admin":
        return True                                           # everyone can see their administrator
    if target.id == viewer.manager_id:
        return True                                           # your own manager
    if target.manager_id == viewer.id:
        return True                                           # people who report to you
    return viewer.manager_id is not None and viewer.manager_id == target.manager_id   # teammates


def can_see_contact(viewer, target):
    return (
        viewer.id == target.id
        or viewer.role == "org_admin"
        or target.manager_id == viewer.id
    )