import io
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.extensions import db
from app.models import User
from app.services.photo_service import PhotoError, process_image
from app.services.profile_service import avatar_src, completeness, initials

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def image_bytes(size=(800, 600), color="red", fmt="PNG", mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, fmt)
    return buf.getvalue()


def upload(browser, data, name="me.png"):
    return browser.post("/profile/photo", data={"photo": (io.BytesIO(data), name)},
                        content_type="multipart/form-data", follow_redirects=True)


def save_profile(browser, **over):
    data = {"name": "Zelda Employee", "job_title": "", "department": "", "employee_code": "",
            "phone": "", "location": "", "joined_on": "", "about": ""}
    data.update(over)
    return browser.post("/profile", data=data, follow_redirects=True)


# ------------------------------------------------------------------ access

@pytest.mark.parametrize("url", ["/profile", "/people/1"])
def test_pages_need_login(client, url):
    r = client.get(url)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


@pytest.mark.parametrize("url", ["/profile", "/profile/photo", "/profile/photo/remove", "/profile/password"])
def test_actions_need_login(client, url):
    r = client.post(url)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_the_owner_has_no_profile(owner_client):
    r = owner_client.get("/profile")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_profile_forms_need_a_csrf_token(csrf_app):
    browser = csrf_app.test_client()
    for url in ("/profile", "/profile/photo", "/profile/password"):
        assert browser.post(url, data={"name": "x"}).status_code == 400


# ----------------------------------------------------------------- details

def test_details_are_saved_and_tidied(login_as, factory, world):
    emp = login_as("emp@alpha.io")
    r = save_profile(
        emp, name="  Zelda   Z  Employee ", job_title="Relationship Officer", department="Retail Banking",
        employee_code="EMP-204", phone="+91 98765 43210", location="Delhi",
        joined_on="2023-04-17", about="Line one\nLine two")
    assert b"Profile saved." in r.data
    user = factory.get(User, id=world.a_emp)
    assert user.name == "Zelda Z Employee"
    assert (user.job_title, user.department, user.employee_code) == ("Relationship Officer", "Retail Banking", "EMP-204")
    assert (user.phone, user.location) == ("+91 98765 43210", "Delhi")
    assert user.joined_on == date(2023, 4, 17) and user.about == "Line one\nLine two"
    page = emp.get("/profile").data
    assert b"Relationship Officer" in page and b"EMP-204" in page


def test_empty_optional_fields_are_stored_as_nothing(login_as, factory, world):
    save_profile(login_as("emp@alpha.io"), job_title="Officer")
    save_profile(login_as("emp@alpha.io"), job_title="   ")
    user = factory.get(User, id=world.a_emp)
    assert user.job_title is None and user.phone is None and user.joined_on is None


@pytest.mark.parametrize("over,message", [
    ({"name": ""}, b"Please enter your name."),
    ({"name": "x" * 101}, b"Name is too long."),
    ({"job_title": "x" * 101}, b"Job title is too long."),
    ({"department": "x" * 101}, b"Department is too long."),
    ({"employee_code": "x" * 41}, b"Employee ID is too long."),
    ({"location": "x" * 101}, b"Location is too long."),
    ({"phone": "call me"}, b"Phone number"),
    ({"phone": "123"}, b"Phone number"),
    ({"joined_on": "not-a-date"}, b"valid date of joining"),
    ({"joined_on": "2999-01-01"}, b"between 1950 and today"),
    ({"joined_on": "1900-01-01"}, b"between 1950 and today"),
    ({"about": "x" * 501}, b"About is too long"),
])
def test_profile_rules(login_as, factory, world, over, message):
    r = save_profile(login_as("emp@alpha.io"), **{"job_title": "Original", **over})
    assert message in r.data
    user = factory.get(User, id=world.a_emp)
    assert user.name == "Zelda Employee" and user.job_title is None       # nothing was saved


def test_about_text_cannot_run_scripts(login_as, factory, world):
    save_profile(login_as("emp@alpha.io"), about="<script>alert(1)</script>")
    page = login_as("admin@alpha.io").get(f"/people/{world.a_emp}").data
    assert b"&lt;script&gt;" in page and b"<script>alert(1)" not in page


# ------------------------------------------------------------------- photos

def test_photo_is_processed_and_stored_online(login_as, factory, world, photos):
    emp = login_as("emp@alpha.io")
    before = sorted(p.name for p in STATIC.iterdir())
    r = upload(emp, image_bytes((1200, 800)))
    assert b"Photo updated." in r.data
    stored = Image.open(io.BytesIO(photos.uploaded[0]))
    assert stored.format == "JPEG" and stored.size == (400, 400)
    assert len(photos.uploaded[0]) < 100_000
    user = factory.get(User, id=world.a_emp)
    assert user.photo_url.startswith("https://") and user.photo_public_id == "leaveok/avatars/fake1"
    assert sorted(p.name for p in STATIC.iterdir()) == before             # nothing saved in the project folder


def test_replacing_a_photo_deletes_the_old_one(login_as, factory, world, photos):
    emp = login_as("emp@alpha.io")
    upload(emp, image_bytes())
    upload(emp, image_bytes(color="blue"))
    assert photos.deleted == ["leaveok/avatars/fake1"]
    assert factory.get(User, id=world.a_emp).photo_public_id == "leaveok/avatars/fake2"


def test_removing_a_photo(login_as, factory, world, photos):
    emp = login_as("emp@alpha.io")
    upload(emp, image_bytes())
    r = emp.post("/profile/photo/remove", follow_redirects=True)
    assert b"Photo removed." in r.data and photos.deleted == ["leaveok/avatars/fake1"]
    user = factory.get(User, id=world.a_emp)
    assert user.photo_url is None and user.photo_public_id is None


@pytest.mark.parametrize("data,name,message", [
    (b"", "empty.png", b"choose a photo"),
    (b"not an image at all", "fake.png", b"not a valid image"),
    (image_bytes(fmt="GIF"), "a.gif", b"JPG, PNG or WebP"),
    (image_bytes(fmt="BMP"), "a.bmp", b"JPG, PNG or WebP"),
    (b"x" * (4 * 1024 * 1024 + 1), "big.jpg", b"too large"),
])
def test_bad_photos_are_refused(login_as, factory, world, photos, data, name, message):
    r = upload(login_as("emp@alpha.io"), data, name)
    assert message in r.data
    assert photos.uploaded == [] and factory.get(User, id=world.a_emp).photo_url is None


def test_no_file_chosen(login_as, world):
    r = login_as("emp@alpha.io").post("/profile/photo", data={}, follow_redirects=True)
    assert b"Please choose a photo." in r.data


def test_storage_failure_is_explained(login_as, factory, world, photos):
    photos.fail = True
    r = upload(login_as("emp@alpha.io"), image_bytes())
    assert b"could not be uploaded" in r.data
    assert factory.get(User, id=world.a_emp).photo_url is None


def test_huge_files_are_stopped_with_a_friendly_message(login_as, world):
    big = b"x" * (5 * 1024 * 1024 + 10)
    r = upload(login_as("emp@alpha.io"), big, "huge.jpg")
    assert b"too large" in r.data


def test_processing_removes_hidden_metadata_and_whitens_transparency():
    img = Image.new("RGB", (300, 300), "green")
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert b"SecretCamera" in buf.getvalue()
    out = Image.open(io.BytesIO(process_image(buf.getvalue())))
    assert len(out.getexif()) == 0

    transparent = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    buf = io.BytesIO()
    transparent.save(buf, "PNG")
    corner = Image.open(io.BytesIO(process_image(buf.getvalue()))).getpixel((2, 2))
    assert min(corner) > 240                                              # white, not black


def test_photos_with_too_many_pixels_are_refused():
    with pytest.raises(PhotoError, match="too many pixels"):
        process_image(image_bytes((6000, 5000), "white", mode="L"))

def test_photo_form_shrinks_big_photos_in_the_browser(login_as, world):
    page = login_as("emp@alpha.io").get("/profile").data
    assert b'id="photo-form"' in page and b"up to 10 MB" in page
    assert b"createImageBitmap" in page and b"toBlob" in page

# ------------------------------------------------------------------- avatars

def test_initials_avatar_until_a_photo_exists(login_as, world):
    emp = login_as("emp@alpha.io")
    page = emp.get("/dashboard").data
    assert b'class="avatar initials' in page and b">ZE<" in page
    upload(emp, image_bytes())
    page = emp.get("/dashboard").data
    assert b'<img class="avatar"' in page and b"c_fill,w_52,h_52,g_face,f_auto,q_auto" in page


@pytest.mark.parametrize("name,expected", [
    ("Zelda Employee", "ZE"), ("Madonna", "M"), ("   ", "?"), ("dr. asha verma", "DV"),
])
def test_initials(name, expected):
    assert initials(name) == expected


def test_avatar_addresses():
    cloud = SimpleNamespace(photo_url="https://res.cloudinary.com/demo/image/upload/v1/a.jpg")
    assert "/upload/c_fill,w_96,h_96,g_face,f_auto,q_auto/v1/a.jpg" in avatar_src(cloud, 96)
    assert avatar_src(SimpleNamespace(photo_url=None)) is None
    other = SimpleNamespace(photo_url="https://example.com/me.jpg")
    assert avatar_src(other) == "https://example.com/me.jpg"


# ------------------------------------------------------------ viewing profiles

def test_who_can_view_whose_profile(login_as, factory, world):
    mgr2 = factory.user(world.a, "mgr2@alpha.io", "Other Manager", "manager", world.a_admin)
    emp2 = factory.user(world.a, "emp2@alpha.io", "Tara Teammate", "employee", world.a_mgr)
    stranger = factory.user(world.a, "str@alpha.io", "Sam Stranger", "employee", mgr2)
    everyone = {world.a_admin, world.a_mgr, world.a_emp, mgr2, emp2, stranger}
    allowed = {
        "emp@alpha.io": {world.a_emp, world.a_mgr, world.a_admin, emp2},
        "mgr@alpha.io": {world.a_mgr, world.a_emp, emp2, world.a_admin, mgr2},
        "admin@alpha.io": everyone,
    }
    for email, ids in allowed.items():
        browser = login_as(email)
        for uid in everyone:
            expected = 200 if uid in ids else 403
            assert browser.get(f"/people/{uid}").status_code == expected, (email, uid)


def test_other_organizations_are_invisible(login_as, world):
    assert login_as("admin@beta.io").get(f"/people/{world.a_emp}").status_code == 404
    assert login_as("admin@alpha.io").get(f"/people/{world.b_admin}").status_code == 404
    assert login_as("admin@alpha.io").get("/people/99999").status_code == 404


def test_contact_details_are_shown_only_to_the_right_people(login_as, factory, world):
    factory.user(world.a, "emp2@alpha.io", "Tara Teammate", "employee", world.a_mgr)
    factory.update(User, world.a_emp, phone="+91 98765 43210", employee_code="EMP-204",
                   job_title="Relationship Officer", about="Hello team")
    for email, sees in (("emp@alpha.io", True), ("mgr@alpha.io", True),
                        ("admin@alpha.io", True), ("emp2@alpha.io", False)):
        page = login_as(email).get(f"/people/{world.a_emp}").data
        assert (b"98765 43210" in page) is sees, email
        assert (b"EMP-204" in page) is sees, email
        assert (b"emp@alpha.io" in page) is sees, email
        assert b"Relationship Officer" in page and b"Hello team" in page      # the public card


def test_people_and_approvals_pages_link_to_profiles(login_as, factory, world):
    admin = login_as("admin@alpha.io")
    assert f'href="/people/{world.a_emp}"'.encode() in admin.get("/admin/employees").data
    factory.request(world.a, world.a_emp, factory.leave_type(world.a),
                    date(2026, 11, 9), date(2026, 11, 9), 1)
    approvals = login_as("mgr@alpha.io").get("/leave/approvals").data
    assert f'href="/people/{world.a_emp}"'.encode() in approvals


# ---------------------------------------------------------------- completeness

def test_completeness_and_the_dashboard_nudge(flask_app, factory, world, login_as):
    with flask_app.app_context():
        assert completeness(db.session.get(User, world.a_emp)) == 0
    assert b"Your profile is 0% complete" in login_as("emp@alpha.io").get("/dashboard").data
    factory.update(User, world.a_emp, job_title="x", department="y", phone="1234567", location="z",
                   joined_on=date(2020, 1, 1), about="a",
                   photo_url="https://res.cloudinary.com/demo/image/upload/v1/a.jpg")
    with flask_app.app_context():
        assert completeness(db.session.get(User, world.a_emp)) == 100
    assert b"complete." not in login_as("emp@alpha.io").get("/dashboard").data


# ------------------------------------------------------------------- password

def change(browser, current, new, confirm=None):
    return browser.post("/profile/password", follow_redirects=True, data={
        "current_password": current, "new_password": new, "confirm_password": confirm or new})


def test_password_change(client, login_as, world):
    emp = login_as("emp@alpha.io")
    assert b"current password is not correct" in change(emp, "Wrong@2026x", "Brand@2026x").data
    assert b"Password needs" in change(emp, "Passw0rd!x", "weak1234").data
    assert b"do not match" in change(emp, "Passw0rd!x", "Brand@2026x", "Other@2026x").data
    assert b"different from your current" in change(emp, "Passw0rd!x", "Passw0rd!x").data
    assert b"Password changed." in change(emp, "Passw0rd!x", "Brand@2026x").data
    old = client.post("/login", data={"email": "emp@alpha.io", "password": "Passw0rd!x"})
    assert b"Invalid email or password." in old.data
    assert client.post("/login", data={"email": "emp@alpha.io", "password": "Brand@2026x"}).status_code == 302