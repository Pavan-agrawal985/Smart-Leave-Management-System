from flask import Blueprint, abort, render_template

bp = Blueprint("pages", __name__)

PAGES = {
    "features": {
        "title": "Features - LeaveOk leave management",
        "description": "See what LeaveOk offers: private workspaces, configurable leave rules, a clear approval chain, a team calendar, reports and CSV export.",
        "h1": "LeaveOk features",
        "intro": "LeaveOk gives every organization a private workspace to set up leave rules, invite people and approve leave without spreadsheets.",
        "sections": [
            {"h": "A private workspace for every organization",
             "p": "Each organization has its own people, leave types, holidays and reports. One organization can never see another organization's data."},
            {"h": "Leave rules you control",
             "bullets": ["Leave types with yearly quotas", "Weekly offs and holidays you choose",
                         "Working-day counting, so weekends and holidays are never deducted",
                         "Checks for overlapping requests and for enough balance"]},
            {"h": "A clear approval chain",
             "p": "Employees apply to their manager. Managers apply to the administrator. The administrator takes no leave. Nobody approves their own request, and every decision is final."},
            {"h": "Invite your team in minutes",
             "p": "The administrator invites managers and employees by email. Each person opens a one-time link, enters their details and chooses their own password."},
            {"h": "Team calendar",
             "p": "See who is away and when, with holidays and weekly offs highlighted, so you can plan cover."},
            {"h": "Reports and CSV export",
             "p": "Filter by year, status, leave type and person. Managers see their own team. The CSV export opens cleanly in Excel."},
            {"h": "Private and secure",
             "bullets": ["Passwords are stored as secure hashes", "Email verification before the first login",
                         "Login lockout after repeated wrong passwords",
                         "Notification emails never contain names, dates or reasons"]},
            {"h": "Works on every device",
             "p": "LeaveOk adapts to phones, tablets and laptops, and includes a dark mode."},
        ],
    },
    "leave-management-for-banks": {
        "title": "Leave management software for banks - LeaveOk",
        "description": "Leave management software for banks. Ready-made privilege, sick and casual leave, clear approvals, a team calendar and reports for your staff.",
        "h1": "Leave management software for banks",
        "intro": "Banks run on clear rules and clear records. LeaveOk gives your bank a private leave workspace with privilege, sick and casual leave ready on day one.",
        "sections": [
            {"h": "A ready-made bank starter",
             "bullets": ["Privilege Leave: 30 days a year", "Sick Leave: 12 days a year", "Casual Leave: 12 days a year",
                         "Sunday as the weekly off"],
             "p": "Change any of it later: quotas, weekly offs and your own list of holidays."},
            {"h": "Approvals that follow your structure",
             "p": "Managers approve the leave of the employees who report to them. One administrator approves the managers. Nobody can approve their own leave."},
            {"h": "Records you can rely on",
             "p": "Every request is kept with its status. Filter reports by year, leave type or person, and export a CSV for your own records."},
            {"h": "Private by design",
             "p": "Your bank's data is kept separate from every other organization. Notification emails say only that something needs attention, so no personal details travel by email."},
            {"h": "Get started",
             "p": "Create your organization, choose Bank as the starting template, then invite your managers and employees."},
        ],
    },
    "leave-management-for-corporate-offices": {
        "title": "Leave management software for corporate offices - LeaveOk",
        "description": "Leave management software for corporate offices. Annual, sick and casual leave, simple approvals, a team calendar and reports in minutes.",
        "h1": "Leave management software for corporate offices",
        "intro": "Stop tracking leave in spreadsheets and chat messages. LeaveOk gives your office one place to request, approve and plan leave.",
        "sections": [
            {"h": "A ready-made office starter",
             "bullets": ["Annual Leave: 24 days a year", "Sick Leave: 12 days a year", "Casual Leave: 8 days a year",
                         "Saturday and Sunday as weekly offs"],
             "p": "Adjust the quotas, weekly offs and holidays to match your own policy."},
            {"h": "Simple approvals",
             "p": "Employees apply and their manager decides. Managers apply and the administrator decides. Everyone is told the outcome by email."},
            {"h": "Plan cover with the team calendar",
             "p": "See who is away, which days are holidays and where your team is thin, all in one monthly view."},
            {"h": "Reports for HR",
             "p": "Filter by year, status, leave type or person, and download a CSV that opens in Excel."},
            {"h": "Easy onboarding",
             "p": "Invite managers and employees by email. Each person joins through a link and sets their own password, so nobody has to share a password."},
            {"h": "Get started",
             "p": "Create your organization, choose Corporate office as the starting template, then invite your team."},
        ],
    },
    "faq": {
        "title": "FAQ - LeaveOk leave management",
        "description": "Answers to common questions about LeaveOk: who it is for, how people join, who approves leave, how data stays private and how to get started.",
        "h1": "Frequently asked questions",
        "intro": "Quick answers about how LeaveOk works.",
        "sections": [
            {"h": "Who is LeaveOk for?",
             "p": "Banks, corporate offices and other organizations that want a simple way to manage employee leave."},
            {"h": "How do employees get an account?",
             "p": "The administrator invites them by email. They open the link, enter their details and choose their own password."},
            {"h": "Who approves leave?",
             "p": "An employee's manager approves their leave. The administrator approves the managers' leave. The administrator takes no leave."},
            {"h": "Can another organization see our data?",
             "p": "No. Each organization's data is kept completely separate, and this is covered by automated tests."},
            {"h": "What do notification emails contain?",
             "p": "They only say that a request is waiting or has been decided. They never contain names, dates or reasons."},
            {"h": "Can we change leave types and holidays?",
             "p": "Yes. The administrator can edit leave types, yearly quotas, holidays and weekly offs at any time."},
            {"h": "Does it work on a phone?",
             "p": "Yes. LeaveOk works on phones, tablets and laptops."},
            {"h": "How do we start?",
             "p": "Create your organization, verify your email, then invite your managers and employees."},
        ],
    },
}


def show(slug):
    page = PAGES.get(slug)
    if page is None:
        abort(404)
    return render_template("page.html", page=page, current=slug, pages=PAGES)


for _slug in PAGES:
    bp.add_url_rule(f"/{_slug}", endpoint="show", view_func=show, defaults={"slug": _slug})