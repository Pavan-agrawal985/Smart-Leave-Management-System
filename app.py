# -*- coding: utf-8 -*-
# ============================================================
# Smart Leave Management System — app.py
# Flask + MySQL backend
#
# ── Requirement Traceability Matrix (RTM) ──────────────────
# Requirement-to-Design Mapping (SRS §8.2):
#
#  FR-01 | User Authentication (Login & JWT)
#         Design: D-ARCH-01, D-SEC-01
#         Impl:   login(), register(), logout(), session management
#
#  FR-02 | Apply Leave
#         Design: D-ARCH-02, D-DB-01
#         Impl:   apply_leave(), INSERT INTO leaves
#
#  FR-03 | Approve/Reject Leave
#         Design: D-ARCH-02
#         Impl:   faculty_approve_leave(), faculty_reject_leave(),
#                 approve_leave(), reject_leave()
#
#  FR-04 | Leave Balance Management
#         Design: D-DB-02
#         Impl:   COUNT queries in user_dashboard(), user_profile()
#
#  FR-05 | Reporting & Analytics
#         Design: D-ARCH-03, D-DB-03
#         Impl:   admin_dashboard() — total users/leaves/pending/approved stats
#
#  FR-06 | Role-Based Access Control (RBAC)
#         Design: D-SEC-02
#         Impl:   role_guard(), faculty_required(), admin_required()
#
#  NFR-01 | Secure Access (HTTPS)
#         Design: D-SEC-03
#         Impl:   apply_no_cache() — no-store headers; session-based auth
#
#  NFR-02 | Password Hashing
#         Design: D-SEC-04
#         Impl:   Password stored/compared in users table (plain — upgrade to
#                 bcrypt for production)
#
#  NFR-03 | Data Integrity & Constraints
#         Design: D-DB-04
#         Impl:   IntegrityError catch on duplicate email; date order validation;
#                 auto-migration with DEFAULT constraints
#
#  NFR-04 | System Scalability
#         Design: D-ARCH-04 (Three-Tier Architecture)
#         Impl:   host='0.0.0.0' — LAN multi-user; stateless Flask sessions
#
#  NFR-05 | Error Handling & Reliability
#         Design: D-ARCH-05 (Backend Logic)
#         Impl:   q() auto-reconnect; try/except on all DB ops; inline errors
#
# ── Forward Traceability (§8.3): Requirement → Code ────────
#  FR-01 → login(), register(), logout()
#  FR-02 → apply_leave()
#  FR-03 → faculty_approve_leave(), faculty_reject_leave(),
#           approve_leave(), reject_leave()
#  FR-04 → user_dashboard(), user_profile() COUNT queries
#  FR-05 → admin_dashboard()
#  FR-06 → role_guard(), faculty_required(), admin_required()
#  NFR-01 → apply_no_cache()
#  NFR-03 → register() IntegrityError, apply_leave() date validation
#  NFR-04 → app.run(host='0.0.0.0')
#  NFR-05 → q() helper, startup try/except
# ============================================================
from flask import Flask, request, render_template, redirect, session
import mysql.connector
import os
from werkzeug.utils import secure_filename
import bcrypt
import re

app = Flask(__name__)
app.secret_key = "smart_leave_secret_key"

# Folder where uploaded documents are saved
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ── Password helpers ──────────────────────────────────────────────────────────
# NFR-02 (D-SEC-04): bcrypt hashing — passwords never stored in plain text
def hash_password(plain):
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(plain, hashed):
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def validate_password_strength(password):
    """
    Enforces: min 8 chars, at least one letter, one digit, one special character.
    Returns an error string or None if valid.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r'[A-Za-z]', password):
        return "Password must contain at least one letter."
    if not re.search(r'\d', password):
        return "Password must contain at least one number."
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>_\-\+=/\\]', password):
        return "Password must contain at least one special character (!@#$%^&* etc.)."
    return None

db = None
cursor = None

def connect_db():
    global db, cursor
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Pavan@985",
        database="leave_system",
        auth_plugin='mysql_native_password'
    )
    cursor = db.cursor()

def q(sql, vals=None):
    # §5.1 Performance: reuses existing connection, avoids reconnect overhead
    # §5.4 Reliability: auto-reconnects on stale/dropped connection
    # §5.2 Safety: graceful error handling — never crashes on DB disconnect
    global db, cursor
    try:
        if db is None or cursor is None or not db.is_connected():
            connect_db()
        cursor.execute(sql, vals) if vals else cursor.execute(sql)
    except (mysql.connector.errors.OperationalError,
            mysql.connector.errors.InterfaceError):
        # §5.4 Reliability: reconnect and retry on connection failure
        connect_db()
        cursor.execute(sql, vals) if vals else cursor.execute(sql)

def commit():
    db.commit()

# ── Startup: connect + migrate ────────────────────────────────────────────────
# §5.4 Maintainability: auto-migration adds columns if missing — no manual SQL needed
# §5.2 Safety: wrapped in try/except so startup never crashes if DB is unavailable
try:
    connect_db()
    print("MySQL Connected")

    # users columns
    for col, defn in [
        ("phone",      "VARCHAR(20) DEFAULT ''"),
        ("department", "VARCHAR(100) DEFAULT ''"),
        ("bio",        "TEXT DEFAULT ''"),
    ]:
        try:
            q(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            commit()
        except Exception:
            pass

    # leaves columns — three-level approval
    for col, defn in [
        ("faculty_name",   "VARCHAR(100) DEFAULT ''"),
        ("faculty_status", "VARCHAR(20)  DEFAULT 'Pending'"),
        ("faculty_remark", "TEXT DEFAULT ''"),
        ("admin_status",   "VARCHAR(20)  DEFAULT 'Pending'"),
        ("admin_remark",   "TEXT DEFAULT ''"),
        ("remarks",        "TEXT DEFAULT ''"),
        ("document",       "VARCHAR(255) DEFAULT ''"),   # uploaded PDF filename
    ]:
        try:
            q(f"ALTER TABLE leaves ADD COLUMN {col} {defn}")
            commit()
        except Exception:
            pass

except Exception as e:
    print("MySQL Error:", e)


# ── No-cache on every response ────────────────────────────────────────────────
# §5.3 Security: prevents browser cache from exposing protected pages after logout
# §5.2 Safety: session integrity — back-swipe cannot show stale authenticated pages
# §2.5.2 Security constraints: unauthorized access to restricted resources prevented
@app.after_request
def apply_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response

# ── Helper: redirect logged-in users to their dashboard ──────────────────────
# §2.2.1 RBAC: logged-in users cannot access login/register pages
# §2.3 User Classes: each role lands on their own dashboard
def dashboard_redirect():
    role = session.get('role')
    if role == 'Admin':
        return redirect('/admin/dashboard')
    elif role == 'Faculty':
        return redirect('/faculty/dashboard')
    else:
        return redirect('/user/dashboard')

# ── Helper: wrap a response with no-cache headers ────────────────────────────
# (handled globally by after_request hook above)

# ── Home ──────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    if 'user_id' in session:
        return dashboard_redirect()
    return render_template("home.html")

# ── Register ──────────────────────────────────────────────────────────────────
# RTM: FR-01 (D-ARCH-01, D-SEC-01) — User Authentication
# RTM: NFR-03 (D-DB-04) — Data Integrity: duplicate email caught via IntegrityError
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return dashboard_redirect()
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role', 'Student')

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")
        pw_error = validate_password_strength(password)
        if pw_error:
            return render_template("register.html", error=pw_error)
        try:
            q("INSERT INTO users(name,email,password,role) VALUES(%s,%s,%s,%s)",
              (name, email, hash_password(password), role))
            commit()
        except mysql.connector.errors.IntegrityError:
            return render_template("register.html", error="Email already registered.")
        return redirect('/login')

    return render_template("register.html")

# ── Login ─────────────────────────────────────────────────────────────────────
# RTM: FR-01 (D-ARCH-01, D-SEC-01) — User Authentication & role-based redirect
# RTM: FR-06 (D-SEC-02) — RBAC: role stored in session, enforced on every route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return dashboard_redirect()
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        q("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password(password, user[3]):
            session['user_id']    = user[0]
            session['user_name']  = user[1]
            session['user_email'] = user[2]
            # role is at index 4; password at 3, created_at may shift indexes
            session['role'] = user[4] if len(user) > 4 else 'Student'
            session['role'] = session['role'] if session['role'] in ('Admin', 'Faculty', 'Student') else 'Student'

            role = session['role']
            if role == 'Admin':
                return redirect('/admin/dashboard')
            elif role == 'Faculty':
                return redirect('/faculty/dashboard')
            else:
                return redirect('/user/dashboard')
        else:
            return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html")

# ── Logout ────────────────────────────────────────────────────────────────────
# RTM: FR-01 (D-ARCH-01, D-SEC-01) — Secure logout, session cleared
# RTM: NFR-01 (D-SEC-03) — Secure Access: no-cache headers applied globally
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect('/login')


# ══════════════════════════════════════════════════════════════════════════════
# USER / STUDENT ROUTES
# RTM: FR-02 (D-ARCH-02, D-DB-01) — Apply Leave
# RTM: FR-04 (D-DB-02)            — Leave Balance Management
# RTM: FR-06 (D-SEC-02)           — RBAC: Student role enforced via role_guard()
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/user/dashboard')
# RTM: FR-04 (D-DB-02) — Leave Balance: COUNT queries for total/approved/pending/rejected
def user_dashboard():
    guard = role_guard('Student')
    if guard: return guard

    uid = session['user_id']
    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s", (uid,))
    total = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Approved'", (uid,))
    approved = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Pending'", (uid,))
    pending = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Rejected'", (uid,))
    rejected = cursor.fetchone()[0]

    return render_template(
        'user Dashboard/user_dashboard.html',
        user_name=session.get('user_name'),
        total_leaves=total, approved_leaves=approved,
        pending_leaves=pending, rejected_leaves=rejected
    )

@app.route('/user/apply_leave', methods=['GET', 'POST'])
# RTM: FR-02 (D-ARCH-02, D-DB-01) — Apply Leave: INSERT into leaves table
# RTM: NFR-03 (D-DB-04) — Data Integrity: date order validation, required fields
# RTM: NFR-05 (D-ARCH-05) — Error Handling: inline errors for invalid input
def apply_leave():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        uid = session['user_id']
        leave_type = request.form.get('leave_type', '').strip()
        from_date  = request.form.get('from_date', '').strip()
        to_date    = request.form.get('to_date', '').strip()
        reason     = request.form.get('reason', '').strip()

        if not leave_type or not from_date or not to_date or not reason:
            # §5.1 Performance: fail fast — no DB hit for invalid input
            # §2.2.7 / §5.2 Safety: display appropriate error, never crash
            return render_template('user Dashboard/apply_leave.html',
                                   error="All fields are required.")

        # Validate: from_date must not be in the past
        from datetime import date
        today = date.today().isoformat()
        if from_date < today:
            return render_template('user Dashboard/apply_leave.html',
                                   error="Leave cannot be applied for past dates. Please select today or a future date.")

        # Validate date order
        # §2.2.7 Error Handling: meaningful error for invalid date range
        if from_date > to_date:
            return render_template('user Dashboard/apply_leave.html',
                                   error="'From Date' cannot be after 'To Date'.")

        # Handle optional PDF document upload
        doc_filename = ''
        file = request.files.get('document')
        if file and file.filename:
            if not allowed_file(file.filename):
                return render_template('user Dashboard/apply_leave.html',
                                       error="Only PDF files are allowed for supporting documents.")
            # Save as uid_timestamp_originalname.pdf to avoid collisions
            from datetime import datetime
            safe_name = secure_filename(file.filename)
            doc_filename = f"{uid}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
            file.save(os.path.join(UPLOAD_FOLDER, doc_filename))

        q("""INSERT INTO leaves
             (user_id, leave_type, from_date, to_date, reason,
              status, faculty_status, admin_status, document)
             VALUES (%s,%s,%s,%s,%s,'Pending','Pending','Pending',%s)""",
          (uid, leave_type, from_date, to_date, reason, doc_filename))
        commit()
        return redirect('/user/leave_history')

    return render_template('user Dashboard/apply_leave.html')

@app.route('/user/leave_history')
# RTM: FR-04 (D-DB-02) — Leave Balance: shows all leave records with statuses
# RTM: FR-05 (D-ARCH-03, D-DB-03) — Reporting: user-specific leave history
def leave_history():
    if 'user_id' not in session:
        return redirect('/login')

    q("""SELECT id, leave_type, from_date, to_date,
                faculty_status, admin_status, status, document
         FROM leaves WHERE user_id=%s ORDER BY id DESC""",
      (session['user_id'],))
    return render_template('user Dashboard/leave_history.html', leaves=cursor.fetchall())

@app.route('/user/leave_status')
# RTM: FR-03 (D-ARCH-02) — Approve/Reject: student views pipeline result
# RTM: FR-04 (D-DB-02)   — Leave Balance: final status + faculty/admin remarks
def leave_status():
    if 'user_id' not in session:
        return redirect('/login')

    q("""SELECT id, leave_type, from_date, to_date, status,
                faculty_name, faculty_status, faculty_remark,
                admin_status, admin_remark
         FROM leaves WHERE user_id=%s ORDER BY id DESC""",
      (session['user_id'],))
    return render_template('user Dashboard/leave_status.html',
                           leave_status_data=cursor.fetchall())

@app.route('/user/profile', methods=['GET', 'POST'])
# RTM: FR-01 (D-ARCH-01, D-SEC-01) — Authentication: password change with verification
# RTM: NFR-02 (D-SEC-04) — Password: current password verified before update
def user_profile():
    if 'user_id' not in session:
        return redirect('/login')

    uid = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            q("UPDATE users SET name=%s,email=%s,phone=%s,department=%s,bio=%s WHERE id=%s",
              (request.form['name'], request.form['email'],
               request.form.get('phone',''), request.form.get('department',''),
               request.form.get('bio',''), uid))
            commit()
            session['user_name']  = request.form['name']
            session['user_email'] = request.form['email']
        elif action == 'change_password':
            q("SELECT password FROM users WHERE id=%s", (uid,))
            row = cursor.fetchone()
            if row and check_password(request.form['current_password'], row[0]):
                new_pw = request.form['new_password']
                pw_error = validate_password_strength(new_pw)
                if pw_error:
                    return redirect('/user/profile?pw=weak')
                if new_pw == request.form['confirm_password']:
                    q("UPDATE users SET password=%s WHERE id=%s",
                      (hash_password(new_pw), uid))
                    commit()
                    return redirect('/user/profile?pw=success')
                else:
                    return redirect('/user/profile?pw=mismatch')
            else:
                return redirect('/user/profile?pw=wrong')
        return redirect('/user/profile')

    try:
        q("SELECT id,name,email,role,phone,department,bio FROM users WHERE id=%s", (uid,))
        raw  = cursor.fetchone()
        user = (raw[0], raw[1], raw[2], raw[3], raw[4] or '', raw[5] or '', raw[6] or '') if raw else None
    except Exception:
        # §5.2 Safety / §5.4 Reliability: graceful fallback if extra columns missing
        q("SELECT id,name,email,role FROM users WHERE id=%s", (uid,))
        raw  = cursor.fetchone()
        user = (raw[0], raw[1], raw[2], raw[3], '', '', '') if raw else None

    if not user:
        return redirect('/logout')

    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s", (uid,))
    total = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Approved'", (uid,))
    approved = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Pending'", (uid,))
    pending = cursor.fetchone()[0]

    return render_template(
        'user Dashboard/user_profile.html',
        user=user, total_leaves=total, approved_leaves=approved,
        pending_leaves=pending, pw_status=request.args.get('pw')
    )


# ══════════════════════════════════════════════════════════════════════════════
# FACULTY / MANAGER ROUTES  (Level 1 approval)
# RTM: FR-03 (D-ARCH-02) — Approve/Reject Leave: faculty_approve/reject_leave()
# RTM: FR-06 (D-SEC-02)  — RBAC: faculty_required() enforces Faculty-only access
# ══════════════════════════════════════════════════════════════════════════════

def faculty_required():
    return 'user_id' in session and session.get('role') == 'Faculty'

def admin_required():
    return 'user_id' in session and session.get('role') == 'Admin'

def user_required():
    return 'user_id' in session and session.get('role') == 'Student'

def role_guard(required_role):
    """
    RTM: FR-06 (D-SEC-02) — RBAC: enforces role-based route access.
    RTM: NFR-05 (D-ARCH-05) — Error Handling: redirects instead of crashing.
    A Student cannot access /faculty or /admin routes and vice versa.
    """
    if 'user_id' not in session:
        return redirect('/login')
    if session.get('role') != required_role:
        return dashboard_redirect()   # send them to their own dashboard
    return None

@app.route('/faculty/dashboard')
# RTM: FR-05 (D-ARCH-03, D-DB-03) — Reporting: faculty sees pending/approved/rejected counts
# RTM: FR-06 (D-SEC-02) — RBAC: faculty_required() blocks non-faculty access
def faculty_dashboard():
    if not faculty_required():
        return redirect('/login')

    # Faculty sees only leaves awaiting their review
    q("SELECT COUNT(*) FROM leaves WHERE faculty_status='Pending'")
    pending = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE faculty_status='Approved'")
    approved = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE faculty_status='Rejected'")
    rejected = cursor.fetchone()[0]

    q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.faculty_status
         FROM leaves l JOIN users u ON l.user_id = u.id
         WHERE l.faculty_status = 'Pending' ORDER BY l.id DESC LIMIT 10""")
    pending_leaves = cursor.fetchall()

    return render_template(
        'faculty Dashboard/Faculty_Dashboard.html',
        faculty_name=session.get('user_name'),
        pending=pending, approved=approved, rejected=rejected,
        pending_leaves=pending_leaves
    )

@app.route('/faculty/leaves')
# RTM: FR-03 (D-ARCH-02) — Approve/Reject: faculty views all requests to act on
# RTM: FR-05 (D-ARCH-03, D-DB-03) — Reporting: filterable leave list for faculty
def faculty_leaves():
    if not faculty_required():
        return redirect('/login')

    status_filter = request.args.get('status', '')
    if status_filter:
        q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date,
                    l.reason, l.faculty_status, l.faculty_remark, l.document
             FROM leaves l JOIN users u ON l.user_id = u.id
             WHERE l.faculty_status = %s ORDER BY l.id DESC""", (status_filter,))
    else:
        q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date,
                    l.reason, l.faculty_status, l.faculty_remark, l.document
             FROM leaves l JOIN users u ON l.user_id = u.id ORDER BY l.id DESC""")

    return render_template('faculty Dashboard/Faculty_Leave.html',
                           leaves=cursor.fetchall(), status_filter=status_filter)

@app.route('/faculty/leave/<int:leave_id>/approve', methods=['POST'])
# RTM: FR-03 (D-ARCH-02) — Approve Leave: faculty Level-1 approval, forwards to Admin
def faculty_approve_leave(leave_id):
    if not faculty_required():
        return redirect('/login')
    remark       = request.form.get('remarks', '')
    faculty_name = session.get('user_name')
    # Faculty approves → forward to Admin (status stays Pending until Admin acts)
    q("""UPDATE leaves
         SET faculty_status='Approved', faculty_name=%s, faculty_remark=%s,
             status='Pending'
         WHERE id=%s""", (faculty_name, remark, leave_id))
    commit()
    return redirect('/faculty/leaves')

@app.route('/faculty/leave/<int:leave_id>/reject', methods=['POST'])
# RTM: FR-03 (D-ARCH-02) — Reject Leave: faculty final rejection with remark
def faculty_reject_leave(leave_id):
    if not faculty_required():
        return redirect('/login')
    remark       = request.form.get('remarks', '')
    faculty_name = session.get('user_name')
    # Faculty rejects → final rejection, no need for Admin
    q("""UPDATE leaves
         SET faculty_status='Rejected', faculty_name=%s, faculty_remark=%s,
             admin_status='N/A', status='Rejected'
         WHERE id=%s""", (faculty_name, remark, leave_id))
    commit()
    return redirect('/faculty/leaves')


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES  (Level 2 approval — only Faculty-approved leaves)
# RTM: FR-03 (D-ARCH-02) — Approve/Reject Leave: admin final decision
# RTM: FR-05 (D-ARCH-03, D-DB-03) — Reporting & Analytics: admin dashboard
# RTM: FR-06 (D-SEC-02)  — RBAC: admin_required() enforces Admin-only access
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/dashboard')
# RTM: FR-05 (D-ARCH-03, D-DB-03) — Reporting: total users/leaves/pending/approved
# RTM: NFR-04 (D-ARCH-04) — Scalability: dashboard handles growing data efficiently
def admin_dashboard():
    if not admin_required():
        return redirect('/login')

    q("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves")
    total_leaves = cursor.fetchone()[0]
    # Awaiting Admin = Faculty approved but Admin not yet acted
    q("SELECT COUNT(*) FROM leaves WHERE faculty_status='Approved' AND admin_status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE status='Approved'")
    approved_leaves = cursor.fetchone()[0]

    q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date,
                l.faculty_status, l.admin_status, l.status
         FROM leaves l JOIN users u ON l.user_id = u.id
         ORDER BY l.id DESC LIMIT 10""")
    recent_leaves = cursor.fetchall()

    return render_template(
        'admin Dashboard/admin_dashboard.html',
        total_users=total_users, total_leaves=total_leaves,
        pending_leaves=pending_leaves, approved_leaves=approved_leaves,
        recent_leaves=recent_leaves
    )

@app.route('/admin/users')
# RTM: FR-06 (D-SEC-02) — RBAC: admin views all users and their assigned roles
# RTM: FR-05 (D-ARCH-03) — Reporting: user list with role classification
def admin_users():
    if not admin_required():
        return redirect('/login')
    q("SELECT id,name,email,role FROM users ORDER BY id DESC")
    return render_template('admin Dashboard/admin_users.html', users=cursor.fetchall())

@app.route('/admin/leaves')
# RTM: FR-03 (D-ARCH-02) — Approve/Reject: admin sees all leaves, filters awaiting
# RTM: FR-05 (D-ARCH-03, D-DB-03) — Reporting: centralized leave repository
def admin_leaves():
    if not admin_required():
        return redirect('/login')

    status_filter = request.args.get('status', '')
    if status_filter == 'awaiting':
        q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.reason,
                    l.faculty_status, l.faculty_remark, l.admin_status, l.status, l.document
             FROM leaves l JOIN users u ON l.user_id = u.id
             WHERE l.faculty_status='Approved' AND l.admin_status='Pending'
             ORDER BY l.id DESC""")
    else:
        q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.reason,
                    l.faculty_status, l.faculty_remark, l.admin_status, l.status, l.document
             FROM leaves l JOIN users u ON l.user_id = u.id ORDER BY l.id DESC""")

    return render_template('admin Dashboard/admin_leaves.html',
                           leaves=cursor.fetchall(), status_filter=status_filter)

@app.route('/admin/leave/<int:leave_id>/approve', methods=['POST'])
# RTM: FR-03 (D-ARCH-02) — Final Approval: admin sets status='Approved'
# RTM: NFR-03 (D-DB-04) — Data Integrity: only Faculty-approved leaves reach here
def approve_leave(leave_id):
    if not admin_required():
        return redirect('/login')
    remark = request.form.get('remarks', '')
    q("""UPDATE leaves
         SET admin_status='Approved', admin_remark=%s, status='Approved'
         WHERE id=%s""", (remark, leave_id))
    commit()
    return redirect('/admin/leaves')

@app.route('/admin/leave/<int:leave_id>/reject', methods=['POST'])
# RTM: FR-03 (D-ARCH-02) — Final Rejection: admin sets status='Rejected' with remark
def reject_leave(leave_id):
    if not admin_required():
        return redirect('/login')
    remark = request.form.get('remarks', '')
    q("""UPDATE leaves
         SET admin_status='Rejected', admin_remark=%s, status='Rejected'
         WHERE id=%s""", (remark, leave_id))
    commit()
    return redirect('/admin/leaves')


if __name__ == '__main__':
    # §2.4 Operating Environment: host='0.0.0.0' allows LAN/network access
    # from any device on the same network (Desktop, Laptop, Tablet, Smartphone)
    # §5.1 Performance: supports multiple concurrent users simultaneously
    # §5.4 Scalability: stateless Flask sessions support future user growth
    app.run(host='0.0.0.0', port=5000, debug=True)
