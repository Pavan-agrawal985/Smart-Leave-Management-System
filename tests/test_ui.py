import pytest

PUBLIC = ["/", "/login", "/register", "/forgot-password"]



def check_shell(html):
    assert b'<html lang="en">' in html
    assert b'name="viewport"' in html and b"width=device-width" in html
    assert b'rel="icon"' in html
    assert b'name="theme-color"' in html
    assert b'id="nav-toggle"' in html and b'id="theme-toggle"' in html
    assert b"logo.svg" in html
    assert b"Skip to content" in html


@pytest.mark.parametrize("url", PUBLIC)
def test_public_pages_have_the_responsive_shell(client, url):
    r = client.get(url)
    assert r.status_code == 200
    check_shell(r.data)


ADMIN_PAGES = ["/dashboard", "/leave/calendar", "/leave/approvals", "/reports/",
               "/admin/employees", "/admin/leave-types", "/admin/holidays"]
EMPLOYEE_PAGES = ["/dashboard", "/leave/apply", "/leave/my", "/leave/calendar"]


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_admin_pages_have_the_responsive_shell(login_as, world, url):
    r = login_as("admin@alpha.io").get(url)
    assert r.status_code == 200
    check_shell(r.data)


@pytest.mark.parametrize("url", EMPLOYEE_PAGES)
def test_employee_pages_have_the_responsive_shell(login_as, world, url):
    r = login_as("emp@alpha.io").get(url)
    assert r.status_code == 200
    check_shell(r.data)

def test_owner_pages_have_the_shell(owner_client, client, world):
    for page in (owner_client.get("/owner/organizations"), client.get("/owner/login")):
        assert page.status_code == 200
        check_shell(page.data)

@pytest.mark.parametrize("path,kind", [("logo.svg", "svg"), ("favicon.svg", "svg"), ("style.css", "css")])
def test_static_assets_are_served(client, path, kind):
    r = client.get("/static/" + path)
    assert r.status_code == 200
    assert kind in r.mimetype


def test_css_has_mobile_rules_and_dark_mode(client):
    css = client.get("/static/style.css").data
    assert b"@media (max-width" in css
    assert b'[data-theme="dark"]' in css


def test_landing_has_its_sections(client):
    html = client.get("/").data
    for text in (b"Create your organization", b"How it works", b"Schools", b"Login", b"Sample view"):
        assert text in html


def test_dashboard_shows_balance_tiles(login_as, world):
    html = login_as("emp@alpha.io").get("/dashboard").data
    assert b'class="tile"' in html and b"days left" in html