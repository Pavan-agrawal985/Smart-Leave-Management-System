# 🗓️ LeaveOk — Smart Leave Management System (SLMS)

> A secure, role-based web application that automates and simplifies the complete leave application and approval process for students, faculty, and employees — built as an academic project at the Faculty of Technology, University of Delhi.

---

## 📋 Table of Contents

- [Description](#description)
- [System Architecture](#system-architecture)
- [Features](#features)
- [User Roles & Access Levels](#user-roles--access-levels)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Security Design](#security-design)
- [Installation](#installation)
- [Usage](#usage)
- [Routes Reference](#routes-reference)
- [Screenshots](#screenshots)
- [Future Enhancements](#future-enhancements)
- [Contributors](#contributors)

---

## 📝 Description

The **Smart Leave Management System (SLMS)** is a full-stack web application designed to digitize and automate the complete leave management process within an educational institution or organization. It provides a secure, role-based platform where users can submit leave requests, track approvals, and manage their profiles — while administrators have full control over users and leave activity.

The system follows a **three-tier web architecture** (Presentation → Application → Data) and is built in compliance with the IEEE 830 SRS standard.

> Prepared by: Pavan Agrawal, Keshav Kumar Singh, Rohan Kumar, Himanshu Kasana, Vipin
> Department of Computer Science (CSE-A), Faculty of Technology, University of Delhi

---

## 🏗️ System Architecture

The SLMS follows a **three-tier architecture**:

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| Presentation Layer | HTML5, CSS3, JavaScript | User interfaces for all roles |
| Application Layer | Python (Flask) | Authentication, leave workflows, business logic |
| Data Layer | MySQL | Users, leave records, roles, reports |

Communication between layers uses **HTTPS / REST API** with **JSON** data exchange.

### Component Modules

- **Authentication Module** — Login, registration, session handling, RBAC
- **Leave Management Module** — Apply leave, approve/reject workflow, balance updates
- **Reporting & Analytics Module** — Department-wise stats, admin dashboards
- **Notification Service** — Alerts for approvals, rejections, and updates

---

## ✨ Features

### 👤 Employee / Student
- 🔐 Secure registration and login with role selection (Student / Faculty / Admin)
- 📊 Personal dashboard with live leave stats (Total / Approved / Pending / Rejected)
- 📝 Apply for leave — select type (Sick / Casual / Emergency / Other), date range, and reason
- 📁 Full leave history table sorted by latest
- � Detailed leave status view with faculty name and admin remarks
- 👤 Profile management — update name, email, phone, department, and bio
- 🔑 Change password with live match validation

### 🧑‍🏫 Manager / Teacher
- 📋 Dashboard with assigned users' leave requests
- ✅ Approve or reject leave requests with remarks
- 📊 View team/class leave reports

### 🛠️ Admin
- 📊 System-wide dashboard — total users, total leaves, pending, approved
- ✅ One-click approve or reject for any leave request
- 👥 View and manage all registered users
- 📋 Full leave request table with user, type, dates, reason, and status

---

## 👥 User Roles & Access Levels

As defined in the SRS (Section 2.3):

| User Class | Access Level | Key Capabilities |
|------------|-------------|-----------------|
| Employee / Student | Limited | Apply leave, view status & history, manage profile |
| Manager / Teacher | Medium | Review requests, approve/reject, add remarks |
| Admin | Full | Manage users, configure policies, monitor system |

---

## �️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| Frontend | HTML5, CSS3, JavaScript |
| Database | MySQL |
| DB Driver | mysql-connector-python |
| Styling | Custom CSS (dark sidebar theme, no frameworks) |
| Sessions | Flask server-side sessions |
| Dev Tools | Visual Studio Code, Git & GitHub |
| Protocol | HTTP/HTTPS |

---

## 📁 Project Structure

```
Smart-Leave-Management-System/
│
├── app.py                              # Main Flask application (all routes & logic)
├── requirements.txt                    # Python dependencies
├── README.md                           # Project documentation
│
├── static/
│   └── style.css                       # Global stylesheet
│
└── templates/
    ├── home.html                       # Landing page (Login / Register)
    ├── login.html                      # Login form
    ├── register.html                   # Registration (Student / Faculty / Admin)
    │
    ├── user Dashboard/
    │   ├── user_dashboard.html         # Stats cards + quick actions
    │   ├── apply_leave.html            # Leave application form
    │   ├── leave_history.html          # All leave requests table
    │   ├── leave_status.html           # Status with faculty name & remarks
    │   └── user_profile.html           # Tabbed profile + password change
    │
    └── admin Dashboard/
        ├── admin_dashboard.html        # System stats + recent leaves
        ├── admin_leaves.html           # Full leave management (approve/reject)
        └── admin_users.html            # All registered users list
```

---

## 🗄️ Database Schema

The system uses **MySQL** with the following tables (as defined in the Software Design Document, Section 7.3):

**1. Users Table**
```sql
CREATE TABLE users (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100),
    email      VARCHAR(100) UNIQUE,
    password   VARCHAR(255),
    role       VARCHAR(50)  DEFAULT 'Student',  -- Student / Faculty / Admin
    phone      VARCHAR(20)  DEFAULT '',
    department VARCHAR(100) DEFAULT '',
    bio        TEXT         DEFAULT ''
);
```

**2. Leave Requests Table**
```sql
CREATE TABLE leaves (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT,
    leave_type   VARCHAR(50),   -- Sick / Casual / Emergency / Other
    from_date    DATE,
    to_date      DATE,
    reason       TEXT,
    status       VARCHAR(20) DEFAULT 'Pending',  -- Pending / Approved / Rejected
    faculty_name VARCHAR(100),
    remarks      TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

> The app automatically adds `phone`, `department`, and `bio` columns to `users` on first run if they don't exist.

### Database Relationships

| Relationship | Type |
|-------------|------|
| Users → Leave Requests | One-to-Many (1:M) |
| Users → Leave Balance | One-to-One (1:1) |
| Leave Types → Leave Requests | One-to-Many (1:M) |

---

## � Security Design

As specified in the Software Design Document (Section 7.4):

- **Role-Based Access Control (RBAC)** — Strictly separates Employee, Manager, and Admin privileges
- **Session Management** — Flask server-side sessions with a secret key
- **HTTPS Communication** — All data transmission encrypted via TLS (production)
- **Input Validation** — Prevents SQL Injection and XSS attacks via parameterized queries
- **Password Security** — Passwords should be hashed using bcrypt or SHA-256 (recommended upgrade from current plain-text storage)
- **Unauthorized Access Prevention** — All routes check session before serving content

> ⚠️ Note: The current implementation stores passwords in plain text. Implementing `bcrypt` hashing is listed as a future enhancement and is strongly recommended before any production deployment.

---

## ⚙️ Installation

### Prerequisites

- Python 3.8+
- MySQL Server running locally
- pip

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/pawanstar123/Smart-Leave-Management-System.git
cd Smart-Leave-Management-System
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Set up the MySQL database**

Open your MySQL client and run:

```sql
CREATE DATABASE leave_system;
USE leave_system;

CREATE TABLE users (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100),
    email      VARCHAR(100) UNIQUE,
    password   VARCHAR(255),
    role       VARCHAR(50) DEFAULT 'Student',
    phone      VARCHAR(20) DEFAULT '',
    department VARCHAR(100) DEFAULT '',
    bio        TEXT DEFAULT ''
);

CREATE TABLE leaves (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT,
    leave_type   VARCHAR(50),
    from_date    DATE,
    to_date      DATE,
    reason       TEXT,
    status       VARCHAR(20) DEFAULT 'Pending',
    faculty_name VARCHAR(100),
    remarks      TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**4. Configure your database credentials**

Open `app.py` and update the connection block:

```python
db = mysql.connector.connect(
    host="localhost",
    user="your_mysql_username",
    password="your_mysql_password",
    database="leave_system",
    auth_plugin='mysql_native_password'
)
```

**5. Run the application**

```bash
python app.py
```

**6. Open in your browser**

```
http://127.0.0.1:5000
```

---

## 🚀 Usage

### As a User (Student / Faculty)
1. Go to `http://127.0.0.1:5000` and click **Register**
2. Fill in your name, email, password, and select your role
3. Log in — you'll be redirected to your personal dashboard
4. Use **Apply Leave** to submit a new request (type, dates, reason)
5. Track requests under **Leave History** and **Leave Status**
6. Update your profile or change your password under **Profile**

### As an Admin
1. Register with role set to **Admin** (or update `role` directly in the database)
2. Log in — you'll be redirected to the Admin Dashboard automatically
3. View system-wide stats on the dashboard
4. Go to **Leaves** to approve or reject pending requests
5. Go to **Users** to view all registered accounts

---

## 🔗 Routes Reference

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Home / landing page |
| GET/POST | `/register` | User registration |
| GET/POST | `/login` | User login |
| GET | `/logout` | Clear session and redirect |
| GET | `/user/dashboard` | User stats dashboard |
| GET/POST | `/user/apply_leave` | Submit a leave request |
| GET | `/user/leave_history` | View all personal leaves |
| GET | `/user/leave_status` | View status with faculty & remarks |
| GET/POST | `/user/profile` | View and edit profile |
| GET | `/admin/dashboard` | Admin overview |
| GET | `/admin/users` | All registered users |
| GET | `/admin/leaves` | All leave requests |
| POST | `/admin/leave/<id>/approve` | Approve a leave |
| POST | `/admin/leave/<id>/reject` | Reject a leave |

---

## 📸 Screenshots

> Screenshots will be added here.

| Page | Preview |
|------|---------|
| Home / Landing | _coming soon_ |
| User Dashboard | _coming soon_ |
| Apply Leave | _coming soon_ |
| Leave Status | _coming soon_ |
| User Profile | _coming soon_ |
| Admin Dashboard | _coming soon_ |
| Admin Leave Management | _coming soon_ |

---

## 🔮 Future Enhancements

As identified in the SRS (Section 1.4 & 5.4):

- [ ] Password hashing using bcrypt (security upgrade)
- [ ] Email / SMS notifications on leave approval or rejection
- [ ] Leave balance tracking per user
- [ ] PDF export of leave history and reports
- [ ] Calendar view for leave visualization
- [ ] Multi-level approval workflow (Student → Faculty → HOD → Admin)
- [ ] Department-wise leave statistics and analytics
- [ ] Mobile-responsive UI
- [ ] REST API support for mobile clients
- [ ] JWT-based authentication (upgrade from session-based)

---

## 👥 Contributors

| Name | Enrollment No. | Role |
|------|---------------|------|
| Pavan Agrawal | 24293916041 | Developer |
| Keshav Kumar Singh | 2429316058 | Developer |
| Rohan Kumar | 24293916025 | Developer |
| Himanshu Kasana | 24293916012 | Developer |
| Vipin | 24293916014 | Developer |

> Faculty of Technology, University of Delhi — Department of Computer Science (CSE-A)

---

## 📄 References

- IEEE Std 830-1998: IEEE Recommended Practice for Software Requirements Specifications
- Roger S. Pressman, *Software Engineering: A Practitioner's Approach*, McGraw-Hill
- Ian Sommerville, *Software Engineering*, Pearson Education

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<p align="center">Made with ❤️ by CSE-A Team | Faculty of Technology, University of Delhi</p>
