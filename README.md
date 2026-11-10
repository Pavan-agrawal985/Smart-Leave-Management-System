# LeaveOk

A multi-organization leave management system. Each organization (school, college, corporate office, bank, or any other institution) signs up, gets its own private workspace, and manages employee leave with its own people and rules.

## Features

- **Multi-organization (multi-tenant):** every record belongs to an organization, and one organization can never see another's data
- **Organization sign-up** with ready-made leave types for School, College, Corporate and Bank
- **Roles:** Organization Admin, Manager, Employee
- **Employee management:** the admin adds people and sets who reports to whom
- **Apply for leave** with overlap check and balance check
- **Approve or reject:** managers handle their own team, admins handle everyone
- **Leave balance** per leave type for the current year
- **Security:** bcrypt password hashing, CSRF protection, secrets kept in `.env`, parameterized queries through SQLAlchemy

## Tech stack

| Part | Tool |
|---|---|
| Backend | Flask |
| Database | Postgres (Neon) with SQLAlchemy and Flask-Migrate |
| Login | Flask-Login, bcrypt |
| Forms and security | Flask-WTF (CSRF) |
| Frontend | Jinja templates, plain CSS |

## Project structure

```
LeaveOk/
├── run.py                  # starts the app
├── config.py               # reads settings from .env
├── requirements.txt
├── migrations/             # database change history
└── app/
    ├── __init__.py         # creates the Flask app
    ├── extensions.py       # db, login, csrf, migrate
    ├── models/             # database tables
    ├── routes/             # pages (auth, main, leave, admin)
    ├── services/           # business rules (balances, approvals, templates)
    ├── templates/          # HTML pages
    └── static/             # CSS
```

## Run it locally

**1. Clone and enter the project**

```bash
git clone https://github.com/Pavan-agrawal985/Smart-Leave-Management-System.git
cd Smart-Leave-Management-System
```

**2. Create a virtual environment and install packages**

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
python -m pip install -r requirements.txt
```

**3. Create a free Postgres database** at [neon.com](https://neon.com) and copy its connection string.

**4. Create a `.env` file** in the project root

```
SECRET_KEY=any-long-random-text
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/neondb?sslmode=require
FLASK_APP=run.py
```

**5. Create the tables and start the app**

```bash
flask db upgrade
python run.py
```

Open http://127.0.0.1:5000 and sign up your first organization.

## How to use

1. **Sign up** an organization. You become its admin, and default leave types are created for your organization type.
2. **Employees** page: add managers and employees, and set who they report to.
3. Employees **apply** for leave. Their manager or the admin **approves or rejects** it.
4. The **dashboard** shows each person's balance for every leave type.

## Current limits

- Leave days are counted as calendar days (weekends and holidays are not excluded yet)
- Approval is single-step (the reporting manager or an admin)
- Leave types are created from templates and cannot be edited from the screen yet

## Roadmap

- [ ] Edit leave types and quotas from the admin screen
- [ ] Holiday calendar and weekend exclusion
- [ ] Multi-step approval chains per leave type
- [ ] Email notifications
- [ ] Team leave calendar and CSV reports
- [ ] Automated tests for data isolation between organizations
- [ ] Live deployment (VPS + Nginx + Gunicorn + Cloudflare) with CI/CD


## Live demo

https://smart-leave-management-system-lemon.vercel.app/

Hosted on Vercel with a Neon Postgres database. Pushing to `main` redeploys automatically.