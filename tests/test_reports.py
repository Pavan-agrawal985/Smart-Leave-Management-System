import csv
import io
from datetime import date

import pytest
from app.extensions import db
from app.models import User
from app.services.report_service import report_rows, summarize

HEADER = ["Employee", "Email", "Leave type", "From", "To",
          "Working days", "Status", "Reason", "Applied on"]


def seed(factory, world):
    casual = factory.leave_type(world.a, "Casual Leave")
    sick = factory.leave_type(world.a, "Sick Leave")
    factory.request(world.a, world.a_emp, casual, date(2026, 11, 9), date(2026, 11, 10), 2, "approved")
    factory.request(world.a, world.a_emp, sick, date(2026, 11, 16), date(2026, 11, 16), 1, "pending")
    factory.request(world.a, world.a_admin, casual, date(2026, 12, 1), date(2026, 12, 1), 1, "rejected")
    factory.request(world.a, world.a_emp, casual, date(2025, 3, 3), date(2025, 3, 3), 1, "approved")
    return casual, sick


def parse(response):
    return list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))


# ------------------------------------------------------------------ access

@pytest.mark.parametrize("url", ["/reports/", "/reports/export.csv"])
def test_reports_need_login(client, url):
    r = client.get(url)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


@pytest.mark.parametrize("url", ["/reports/", "/reports/export.csv"])
def test_employees_cannot_open_reports(login_as, world, url):
    assert login_as("emp@alpha.io").get(url).status_code == 403


def test_menu_link_only_for_admin_and_manager(login_as, world):
    assert b"/reports/" in login_as("admin@alpha.io").get("/dashboard").data
    assert b"/reports/" in login_as("mgr@alpha.io").get("/dashboard").data
    assert b"/reports/" not in login_as("emp@alpha.io").get("/dashboard").data


# ----------------------------------------------------------------- scoping

def test_admin_sees_everyone_for_the_chosen_year(login_as, factory, world):
    seed(factory, world)
    data = login_as("admin@alpha.io").get("/reports/?year=2026").data
    assert b"Zelda Employee" in data and b"Alice Alpha" in data
    assert b"03 Mar 2025" not in data                       # other year


def test_manager_sees_only_the_team(login_as, factory, world):
    seed(factory, world)
    data = login_as("mgr@alpha.io").get("/reports/?year=2026").data
    assert b"Zelda Employee" in data
    assert b"Alice Alpha" not in data                       # the admin is not on this team


def test_other_organization_sees_nothing(login_as, factory, world):
    seed(factory, world)
    beta = login_as("admin@beta.io")
    page = beta.get("/reports/?year=2026").data
    assert b"Zelda" not in page and b"Alice Alpha" not in page
    rows = parse(beta.get("/reports/export.csv?year=2026"))
    assert rows == [HEADER]


# ----------------------------------------------------------------- filters

def test_filters_change_the_csv(login_as, factory, world):
    casual, sick = seed(factory, world)
    admin = login_as("admin@alpha.io")
    assert len(parse(admin.get("/reports/export.csv?year=2026"))) == 4            # header + 3
    assert len(parse(admin.get("/reports/export.csv?year=2025"))) == 2
    assert len(parse(admin.get("/reports/export.csv?year=2026&status=approved"))) == 2
    assert len(parse(admin.get(f"/reports/export.csv?year=2026&type={sick}"))) == 2
    assert len(parse(admin.get(f"/reports/export.csv?year=2026&person={world.a_admin}"))) == 2


@pytest.mark.parametrize("query", [
    "year=abc", "year=99999", "year=-5", "status=hacker", "type=zz", "person=-1", "type=99999",
])
def test_bad_filters_do_not_crash(login_as, factory, world, query):
    seed(factory, world)
    admin = login_as("admin@alpha.io")
    assert admin.get(f"/reports/?{query}").status_code == 200
    assert admin.get(f"/reports/export.csv?{query}").status_code == 200


# --------------------------------------------------------------------- CSV

def test_csv_download_format(login_as, factory, world):
    seed(factory, world)
    r = login_as("admin@alpha.io").get("/reports/export.csv?year=2026&status=approved")
    assert r.mimetype == "text/csv"
    assert "leave-report-2026.csv" in r.headers["Content-Disposition"]
    assert r.data.startswith("\ufeff".encode("utf-8"))
    rows = parse(r)
    assert rows[0] == HEADER
    assert rows[1][:7] == ["Zelda Employee", "emp@alpha.io", "Casual Leave",
                           "2026-11-09", "2026-11-10", "2", "approved"]


def test_csv_blocks_spreadsheet_formulas(login_as, factory, world):
    evil = factory.user(world.a, "evil@alpha.io", "=HYPERLINK(\"http://x\")", "employee", world.a_mgr)
    factory.request(world.a, evil, factory.leave_type(world.a), date(2026, 11, 9), date(2026, 11, 9), 1)
    rows = parse(login_as("admin@alpha.io").get("/reports/export.csv?year=2026"))
    assert rows[1][0].startswith("'=")


# ----------------------------------------------------------------- summary

def test_summary_totals(flask_app, factory, world):
    seed(factory, world)
    with flask_app.app_context():
        viewer = db.session.get(User, world.a_admin)
        summary = {s["name"]: s for s in summarize(report_rows(viewer, 2026))}
    assert summary["Zelda Employee"] == {"name": "Zelda Employee", "approved": 2, "pending": 1, "rejected": 0}
    assert summary["Alice Alpha"]["rejected"] == 1