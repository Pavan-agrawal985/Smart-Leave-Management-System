"""
=============================================================
  SMART LEAVE MANAGEMENT SYSTEM (SLMS)
  Faculty Dashboard - app.py
  Stack: Flask + MySQL
  Author: CSE Project - University of Delhi
=============================================================
  Setup:
    1. pip install flask mysql-connector-python
    2. mysql -u root -p < mysql_setup.sql
    3. python app.py
    4. Open: http://localhost:5000
=============================================================
"""

from flask import Flask, request, render_template, redirect, url_for, session, jsonify, flash
import mysql.connector
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = "slms_faculty_secret_2026"

# ─────────────────────────────────────────────
# MySQL Connection
# ─────────────────────────────────────────────
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Pavan@985",          # ← Your MySQL password
        database="leave_system",
        auth_plugin='mysql_native_password'
    )
    cursor = db.cursor(dictionary=True)
    print("✅ MySQL Connected")
except Exception as e:
    print("❌ MySQL Error:", e)
    db = None
    cursor = None


def get_cursor():
    """Reconnect if MySQL connection drops"""
    global db, cursor
    try:
        db.ping(reconnect=True, attempts=3, delay=2)
    except Exception:
        db = mysql.connector.connect(
            host="localhost", user="root",
            password="Pavan@985", database="leave_system",
            auth_plugin='mysql_native_password'
        )
    cursor = db.cursor(dictionary=True)
    return cursor


# ─────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def faculty_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') not in ['Faculty', 'Admin']:
            flash('Access denied. Faculty only.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# PAGE 0: Home (Landing)
# ─────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('home.html')


# ─────────────────────────────────────────────
# PAGE: Register
# ─────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name  = request.form['name']
        email = request.form['email']
        pwd   = request.form['password']
        role  = request.form.get('role', 'Student')
        dept  = request.form.get('department', 'CSE')

        cur = get_cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            return render_template('register.html', error="Email already registered!")

        cur.execute(
            "INSERT INTO users(name,email,password,role,department) VALUES(%s,%s,%s,%s,%s)",
            (name, email, pwd, role, dept)
        )
        db.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


# ─────────────────────────────────────────────
# PAGE: Login
# ─────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pwd   = request.form['password']
        role  = request.form.get('role', 'Faculty')

        cur = get_cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s AND role=%s",
            (email, pwd, role)
        )
        user = cur.fetchone()
        if user:
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['email']     = user['email']
            session['role']      = user['role']
            session['dept']      = user['department']

            if user['role'] in ['Faculty', 'Admin']:
                return redirect(url_for('dashboard'))
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid email, password or role!")
    return render_template('login.html')


# ─────────────────────────────────────────────
# PAGE: Logout
# ─────────────────────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ─────────────────────────────────────────────
# PAGE 1: Faculty Dashboard Home
# ─────────────────────────────────────────────
@app.route('/faculty/dashboard')
@faculty_required
def dashboard():
    cur = get_cursor()

    # Stat counts
    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE status='Pending'")
    pending = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE status='Approved' AND MONTH(updated_at)=MONTH(NOW())")
    approved_month = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE status='Rejected' AND MONTH(updated_at)=MONTH(NOW())")
    rejected_month = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE status='Approved' AND DATE(updated_at)=CURDATE()")
    approved_today = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) as c FROM leave_requests")
    total_req = cur.fetchone()['c']

    # Today's new requests
    cur.execute("""
        SELECT lr.*, u.name as student_name, u.department
        FROM leave_requests lr JOIN users u ON lr.user_id=u.id
        WHERE lr.status='Pending' AND DATE(lr.created_at)=CURDATE()
        ORDER BY lr.created_at DESC
    """)
    today_list = cur.fetchall()

    # Quick pending (latest 5)
    cur.execute("""
        SELECT lr.*, u.name as student_name, u.department
        FROM leave_requests lr JOIN users u ON lr.user_id=u.id
        WHERE lr.status='Pending'
        ORDER BY lr.created_at DESC LIMIT 5
    """)
    quick_pending = cur.fetchall()

    # Leave type breakdown
    cur.execute("""
        SELECT leave_type, COUNT(*) as cnt
        FROM leave_requests
        GROUP BY leave_type
    """)
    breakdown = cur.fetchall()

    return render_template('faculty_dashboard.html',
        pending       = pending,
        approved_month= approved_month,
        rejected_month= rejected_month,
        approved_today= approved_today,
        total_req     = total_req,
        today_list    = today_list,
        quick_pending = quick_pending,
        breakdown     = breakdown,
    )


# ─────────────────────────────────────────────
# PAGE 2: Leave Requests (Main Page)
# ─────────────────────────────────────────────
@app.route('/faculty/requests')
@faculty_required
def requests_page():
    cur   = get_cursor()
    ltype  = request.args.get('type',   'all')
    status = request.args.get('status', 'Pending')
    dept   = request.args.get('dept',   'all')
    search = request.args.get('search', '')

    sql = """
        SELECT lr.*, u.name as student_name, u.email, u.department
        FROM leave_requests lr JOIN users u ON lr.user_id=u.id
        WHERE 1=1
    """
    params = []
    if ltype  != 'all': sql += " AND lr.leave_type=%s";    params.append(ltype)
    if status != 'all': sql += " AND lr.status=%s";         params.append(status)
    if dept   != 'all': sql += " AND u.department=%s";      params.append(dept)
    if search:          sql += " AND (u.name LIKE %s OR lr.leave_type LIKE %s)"; params += [f'%{search}%', f'%{search}%']
    sql += " ORDER BY lr.created_at DESC"

    cur.execute(sql, params)
    leaves = cur.fetchall()

    return render_template('faculty_requests.html',
        leaves=leaves, ltype=ltype, status=status, dept=dept, search=search
    )


# ─────────────────────────────────────────────
# PAGE 3: Leave Details
# ─────────────────────────────────────────────
@app.route('/faculty/leave/<int:leave_id>')
@faculty_required
def leave_details(leave_id):
    cur = get_cursor()
    cur.execute("""
        SELECT lr.*, u.name as student_name, u.email, u.department, u.phone
        FROM leave_requests lr JOIN users u ON lr.user_id=u.id
        WHERE lr.id=%s
    """, (leave_id,))
    leave = cur.fetchone()
    if not leave:
        flash('Leave request not found.', 'error')
        return redirect(url_for('requests_page'))
    return render_template('faculty_leave_details.html', leave=leave)


# ─────────────────────────────────────────────
# ACTION: Approve / Reject Leave
# ─────────────────────────────────────────────
@app.route('/faculty/review', methods=['POST'])
@faculty_required
def review_leave():
    leave_id = request.form.get('leave_id')
    decision = request.form.get('decision')    # Approved / Rejected
    remark   = request.form.get('remark', '').strip()
    redirect_to = request.form.get('redirect', 'requests_page')

    if decision not in ['Approved', 'Rejected']:
        flash('Invalid decision.', 'error')
        return redirect(url_for('requests_page'))
    if decision == 'Rejected' and not remark:
        flash('Remark is required for rejection!', 'error')
        return redirect(url_for('requests_page'))

    cur = get_cursor()
    cur.execute("""
        UPDATE leave_requests
        SET status=%s, faculty_remark=%s, reviewed_by=%s, updated_at=NOW()
        WHERE id=%s
    """, (decision, remark or 'Approved by faculty.', session['user_id'], leave_id))
    db.commit()

    flash(f'Leave {decision} successfully!', 'success')
    if redirect_to == 'details':
        return redirect(url_for('leave_details', leave_id=leave_id))
    return redirect(url_for('requests_page'))


# ─────────────────────────────────────────────
# PAGE 4: Approved Leaves
# ─────────────────────────────────────────────
@app.route('/faculty/approved')
@faculty_required
def approved_page():
    cur = get_cursor()
    cur.execute("""
        SELECT lr.*, u.name as student_name, u.department
        FROM leave_requests lr JOIN users u ON lr.user_id=u.id
        WHERE lr.status='Approved'
        ORDER BY lr.updated_at DESC
    """)
    approved = cur.fetchall()
    return render_template('faculty_approved.html', approved=approved)


# ─────────────────────────────────────────────
# PAGE 5: Rejected Leaves
# ─────────────────────────────────────────────
@app.route('/faculty/rejected')
@faculty_required
def rejected_page():
    cur = get_cursor()
    cur.execute("""
        SELECT lr.*, u.name as student_name, u.department
        FROM leave_requests lr JOIN users u ON lr.user_id=u.id
        WHERE lr.status='Rejected'
        ORDER BY lr.updated_at DESC
    """)
    rejected = cur.fetchall()
    return render_template('faculty_rejected.html', rejected=rejected)


# ─────────────────────────────────────────────
# PAGE 6: Faculty Profile
# ─────────────────────────────────────────────
@app.route('/faculty/profile', methods=['GET', 'POST'])
@faculty_required
def profile_page():
    cur = get_cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update':
            name  = request.form['name']
            phone = request.form.get('phone', '')
            dept  = request.form['department']
            cur.execute(
                "UPDATE users SET name=%s, phone=%s, department=%s WHERE id=%s",
                (name, phone, dept, session['user_id'])
            )
            db.commit()
            session['user_name'] = name
            session['dept']      = dept
            flash('Profile updated successfully!', 'success')

        elif action == 'password':
            old = request.form['old_password']
            new = request.form['new_password']
            cnf = request.form['confirm_password']
            cur.execute("SELECT password FROM users WHERE id=%s", (session['user_id'],))
            user = cur.fetchone()
            if user['password'] != old:
                flash('Current password is incorrect!', 'error')
            elif new != cnf:
                flash('New passwords do not match!', 'error')
            elif len(new) < 6:
                flash('Password must be at least 6 characters!', 'error')
            else:
                cur.execute("UPDATE users SET password=%s WHERE id=%s", (new, session['user_id']))
                db.commit()
                flash('Password changed successfully!', 'success')

        return redirect(url_for('profile_page'))

    cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()

    # Profile stats
    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE reviewed_by=%s AND status='Approved'", (session['user_id'],))
    approved_count = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE reviewed_by=%s AND status='Rejected'", (session['user_id'],))
    rejected_count = cur.fetchone()['c']

    return render_template('faculty_profile.html',
        user=user, approved_count=approved_count, rejected_count=rejected_count,
        total_reviewed=approved_count + rejected_count
    )


# ─────────────────────────────────────────────
# API: Live pending count
# ─────────────────────────────────────────────
@app.route('/api/pending-count')
@faculty_required
def api_pending():
    cur = get_cursor()
    cur.execute("SELECT COUNT(*) as c FROM leave_requests WHERE status='Pending'")
    return jsonify({'count': cur.fetchone()['c']})


if __name__ == '__main__':
    app.run(debug=True)