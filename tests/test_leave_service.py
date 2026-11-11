from datetime import date

from app.extensions import db
from app.models import Organization, User, LeaveRequest
from app.services.leave_service import (
    working_days, get_balances, has_overlap, can_approve, pending_for,
)

# Nov 2026: 9 = Monday ... 13 = Friday, 14 = Saturday, 15 = Sunday, 16 = Monday
WEEK_MON, WEEK_FRI = date(2026, 11, 9), date(2026, 11, 13)
FRI, SAT, SUN, MON, TUE = (date(2026, 11, n) for n in (13, 14, 15, 16, 17))


def days(app, org_id, start, end):
    with app.app_context():
        return working_days(db.session.get(Organization, org_id), start, end)


def test_weekends_are_skipped(flask_app, world):
    assert days(flask_app, world.a, WEEK_MON, WEEK_FRI) == 5
    assert days(flask_app, world.a, FRI, TUE) == 3          # Fri, Mon, Tue
    assert days(flask_app, world.a, SAT, SUN) == 0
    assert days(flask_app, world.a, FRI, FRI) == 1


def test_holidays_are_skipped(flask_app, factory, world):
    factory.holiday(world.a, MON)
    assert days(flask_app, world.a, FRI, TUE) == 2


def test_holiday_on_a_weekend_is_not_counted_twice(flask_app, factory, world):
    factory.holiday(world.a, SAT)
    assert days(flask_app, world.a, FRI, TUE) == 3


def test_holiday_of_another_org_is_ignored(flask_app, factory, world):
    factory.holiday(world.b, MON)
    assert days(flask_app, world.a, FRI, TUE) == 3


def test_custom_weekly_offs(flask_app, factory, world):
    factory.update(Organization, world.a, weekend_days="6")   # only Sunday off
    assert days(flask_app, world.a, FRI, TUE) == 4
    factory.update(Organization, world.a, weekend_days="")    # no weekly off
    assert days(flask_app, world.a, FRI, TUE) == 5


def test_balances_count_pending_and_approved_only(flask_app, factory, world):
    t = factory.leave_type(world.a, "Casual Leave")           # 8 days a year
    factory.request(world.a, world.a_emp, t, date(2026, 11, 9), date(2026, 11, 10), 2, "pending")
    factory.request(world.a, world.a_emp, t, date(2026, 11, 11), date(2026, 11, 11), 1, "approved")
    factory.request(world.a, world.a_emp, t, date(2026, 11, 12), date(2026, 11, 13), 2, "rejected")
    factory.request(world.a, world.a_emp, t, date(2025, 3, 3), date(2025, 3, 4), 2, "approved")
    with flask_app.app_context():
        user = db.session.get(User, world.a_emp)
        row = next(r for r in get_balances(user, 2026) if r["type"].name == "Casual Leave")
        assert (row["quota"], row["used"], row["left"]) == (8, 3, 5)


def test_overlap_detection(flask_app, factory, world):
    t = factory.leave_type(world.a)
    factory.request(world.a, world.a_emp, t, date(2026, 11, 9), date(2026, 11, 11), 3, "pending")
    factory.request(world.a, world.a_emp, t, date(2026, 12, 1), date(2026, 12, 3), 3, "rejected")
    with flask_app.app_context():
        assert has_overlap(world.a_emp, date(2026, 11, 11), date(2026, 11, 12)) is True
        assert has_overlap(world.a_emp, date(2026, 11, 12), date(2026, 11, 13)) is False
        assert has_overlap(world.a_emp, date(2026, 12, 2), date(2026, 12, 2)) is False   # rejected


def test_who_can_approve(flask_app, factory, world):
    mgr2 = factory.user(world.a, "mgr2@alpha.io", "Other Manager", "manager", world.a_admin)
    t = factory.leave_type(world.a)
    rid = factory.request(world.a, world.a_emp, t, date(2026, 11, 9), date(2026, 11, 9), 1)
    done = factory.request(world.a, world.a_emp, t, date(2026, 11, 10), date(2026, 11, 10), 1, "approved")
    with flask_app.app_context():
        req = db.session.get(LeaveRequest, rid)
        get = lambda uid: db.session.get(User, uid)
        assert can_approve(get(world.a_mgr), req) is True        # the employee's manager
        assert can_approve(get(world.a_admin), req) is True      # org admin
        assert can_approve(get(world.a_emp), req) is False       # self
        assert can_approve(get(mgr2), req) is False              # another team's manager
        assert can_approve(get(world.b_admin), req) is False     # other organization
        assert can_approve(get(world.a_mgr), db.session.get(LeaveRequest, done)) is False  # not pending


def test_pending_lists(flask_app, factory, world):
    mgr2 = factory.user(world.a, "mgr2@alpha.io", "Other Manager", "manager", world.a_admin)
    t = factory.leave_type(world.a)
    rid = factory.request(world.a, world.a_emp, t, date(2026, 11, 9), date(2026, 11, 9), 1)
    factory.request(world.a, world.a_admin, t, date(2026, 11, 10), date(2026, 11, 10), 1)
    with flask_app.app_context():
        ids = lambda uid: [r.id for r in pending_for(db.session.get(User, uid))]
        assert ids(world.a_mgr) == [rid]
        assert ids(world.a_admin) == [rid]       # his own request is not listed
        assert ids(mgr2) == []
        assert ids(world.b_admin) == []