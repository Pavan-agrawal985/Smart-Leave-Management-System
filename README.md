# LeaveOk

A multi-organization leave management system. Schools, colleges, banks and offices each get a private workspace with their own people, leave types, holidays and approvals.

**Live:** https://YOUR-APP.vercel.app
**Demo video:** https://YOUR-VIDEO-LINK

![Dashboard](docs/screenshots/dashboard.png)

## What it does

- **Multi-tenant by design:** every record belongs to an organization, and one organization can never see another's data (covered by automated tests)
- **Onboarding:** pick School, College, Corporate or Bank and get sensible default leave types and weekly offs
- **Owner approval:** new organizations are reviewed before they can use the app
- **Leave rules:** configurable leave types and quotas, weekly offs, holidays, overlap and balance checks, weekends and holidays excluded from leave days
- **Approvals:** managers approve their own team, admins approve everyone, nobody approves their own request
- **Team calendar:** who is away and when, showing names and dates only
- **Reports:** filter by year, status, type and person, with a CSV export that is safe to open in Excel
- **People management:** change roles and managers, deactivate leavers, with reporting-loop protection

## Security

- Passwords hashed with bcrypt, 8 to 16 characters with upper, lower, number and symbol
- Email verification links and forgot-password links that expire and work once
- Login lockout after 5 wrong attempts, and throttled verification and reset emails
- CSRF protection on every form, role checks on every page, secrets only in environment variables
- Notification emails contain no names, dates or reasons

## Screenshots

| Apply | Approvals |
|---|---|
| ![Apply](docs/screenshots/apply.png) | ![Approvals](docs/screenshots/approvals.png) |

| Calendar | Reports |
|---|---|
| ![Calendar](docs/screenshots/calendar.png) | ![Reports](docs/screenshots/reports.png) |

## Tech stack

| Part | Tool |
|---|---|
| Backend | Flask, SQLAlchemy, Flask-Migrate |
| Database | PostgreSQL (Neon) |
| Auth and security | Flask-Login, bcrypt, Flask-WTF (CSRF) |
| Hosting | Vercel (serverless) |
| Tests and CI | pytest (150+ tests), GitHub Actions |

## Project structure

```
app/
  models/      database tables
  routes/      pages (auth, leave, admin, owner, reports)
  services/    business rules (balances, workflow, email, reports)
  templates/   HTML pages
tests/         automated test suite
migrations/    database change history
```

## Run it locally

```bash
git clone https://github.com/Pavan-agrawal985/Smart-Leave-Management-System.git
cd Smart-Leave-Management-System
python -m venv venv
venv\Scripts\activate            # Windows
python -m pip install -r requirements.txt
```

Create a free Postgres database at [neon.com](https://neon.com), then create a `.env` file:

```
SECRET_KEY=any-long-random-text
DATABASE_URL=postgresql://USER:PASSWORD@HOST/neondb?sslmode=require
OWNER_EMAIL=your-email@gmail.com
MAIL_USERNAME=sender@gmail.com
MAIL_PASSWORD=sixteenletterapppassword
FLASK_APP=run.py
```

```bash
flask db upgrade
python run.py
```

Sign up with the `OWNER_EMAIL` address to become the owner. Run the tests with `python -m pytest -q`.

## Roadmap

- [ ] Custom email domain and a transactional email service
- [ ] Multi-step approval chains per leave type
- [ ] Carry-forward of unused leave at year end
- [ ] Departments and department-level reports