# LeaveOk — Smart Leave Management System

A role-based leave management web app built with Flask and MySQL. Students can apply for leaves and track their status, while admins can manage all requests and users.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| Frontend | HTML5, CSS3, Vanilla JS |
| Database | MySQL |
| DB Driver | mysql-connector-python |
| Styling | Custom CSS — dark sidebar theme, no frameworks |
| Sessions | Flask server-side sessions |

---

## Project Structure

```
LeaveOk/
├── app.py                          # All Flask routes and logic
├── README.md
│
├── static/
│   └── style.css                   # Global stylesheet (shared across all pages)
│
└── templates/
    ├── home.html                   # Landing page
    ├── login.html                  # Login
    ├── register.html               # Register (Student / Faculty / Admin)
    │
    ├── user Dashboard/
    │   ├── user_dashboard.html     # Stats + quick actions
    │   ├── apply_leave.html        # Leave application form
    │   ├── leave_history.html      # All leave requests table
    │   ├── leave_status.html       # Status with faculty name & remarks
    │   └── user_profile.html       # Tabbed profile — info, password, account
    │
    └── admin Dashboard/
        ├── admin_dashboard.html    # System stats + recent leave requests
        ├── admin_leaves.html       # Full leave table with approve/reject
        └── admin_users.html        # All registered users
```

---

## Database Setup

Run this in your MySQL client:

```sql
CREATE DATABASE leave_system;
USE leave_system;

CREATE TABLE users (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100),
    email      VARCHAR(100) UNIQUE,
    password   VARCHAR(255),
    role       VARCHAR(50)  DEFAULT 'Student',
    phone      VARCHAR(20)  DEFAULT '',
    department VARCHAR(100) DEFAULT '',
    bio        TEXT         DEFAULT ''
);

CREATE TABLE leaves (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT,
    leave_type   VARCHAR(50),
    from_date    DATE,
    to_date      DATE,
    reason       TEXT,
    status       VARCHAR(20)  DEFAULT 'Pending',
    faculty_name VARCHAR(100),
    remarks      TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

> The `phone`, `department`, and `bio` columns are added automatically on first run if they don't exist.

---

## Installation

**1. Clone the repo**

```bash
git clone https://github.com/pawanstar123/Smart-Leave-Management-System.git
cd Smart-Leave-Management-System
```

**2. Install dependencies**

```bash
pip install flask mysql-connector-python
```

**3. Update DB credentials in `app.py`**

```python
db = mysql.connector.connect(
    host="localhost",
    user="your_username",
    password="your_password",
    database="leave_system",
    auth_plugin='mysql_native_password'
)
```

**4. Run**

```bash
python app.py
```

Then open `http://127.0.0.1:5000`

---

## Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Landing page |
| GET/POST | `/register` | Register new user |
| GET/POST | `/login` | Login |
| GET | `/logout` | Logout |
| GET | `/user/dashboard` | User dashboard with leave stats |
| GET/POST | `/user/apply_leave` | Submit a leave request |
| GET | `/user/leave_history` | View all personal leave requests |
| GET | `/user/leave_status` | View status with faculty name & remarks |
| GET/POST | `/user/profile` | View and edit profile, change password |
| GET | `/admin/dashboard` | Admin overview — stats + recent requests |
| GET | `/admin/users` | All registered users |
| GET | `/admin/leaves` | All leave requests with approve/reject |
| POST | `/admin/leave/<id>/approve` | Approve a leave |
| POST | `/admin/leave/<id>/reject` | Reject a leave |

---

## User Roles

| Role | Redirected To | Capabilities |
|------|--------------|--------------|
| Student | `/user/dashboard` | Apply leave, view history/status, manage profile |
| Faculty | `/faculty/dashboard` | _(in progress)_ |
| Admin | `/admin/dashboard` | View all users, approve/reject all leaves |

---

## Features

- Role-based login — auto-redirects to the correct dashboard
- User dashboard with live leave stats (Total / Approved / Pending / Rejected)
- Leave application form with type, date range, and reason
- Leave history and detailed status table with faculty remarks
- Professional profile page — tabbed layout with personal info, password change, and account details
- Admin can approve or reject any pending leave from the dashboard or leaves page
- Consistent dark-sidebar theme across all pages via a single shared CSS file

---

## Notes

- Passwords are stored in plain text — hashing with `bcrypt` is recommended before any production use
- The Faculty dashboard route exists in login redirect logic but the dashboard itself is not yet implemented

---

## Contributors

| Name | Role |
|------|------|
| Pavan Agrawal | Developer |
| Keshav Kumar Singh | Developer |
| Rohan Kumar | Developer |
| Himanshu Kasana | Developer |
| Vipin | Developer |

Department of Computer Science (CSE-A), Faculty of Technology, University of Delhi
