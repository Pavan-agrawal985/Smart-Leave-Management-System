# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, redirect, session
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "smart_leave_secret_key"
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = None
cursor = None

def connect_db():
    global db, cursor
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Kasana@2005",
        database="leave_system",
        auth_plugin='mysql_native_password'
    )
    cursor = db.cursor()

def q(sql, vals=None):
    """Execute a query with auto-reconnect on stale connection."""
    global db, cursor
    try:
        if db is None or not db.is_connected():
            connect_db()
        if vals:
            cursor.execute(sql, vals)
        else:
            cursor.execute(sql)
    except mysql.connector.errors.OperationalError:
        connect_db()
        if vals:
            cursor.execute(sql, vals)
        else:
            cursor.execute(sql)

def commit():
    db.commit()

# Initial connection + migrations
try:
    connect_db()
    print("MySQL Connected")

    # users table extra columns
    for col, definition in [
        ("phone",      "VARCHAR(20) DEFAULT ''"),
        ("department", "VARCHAR(100) DEFAULT ''"),
        ("bio",        "TEXT DEFAULT ''"),
    ]:
        try:
            q(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            commit()
        except Exception:
            pass

    # leaves table extra columns
    for col, definition in [
        ("faculty_name", "VARCHAR(100) DEFAULT ''"),
        ("remarks",      "TEXT DEFAULT ''"),
    ]:
        try:
            q(f"ALTER TABLE leaves ADD COLUMN {col} {definition}")
            commit()
        except Exception:
            pass

except Exception as e:
    print("MySQL Error:", e)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Home ──────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template("home.html")

# ── Register ──────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role', 'Student')

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")

        try:
            q("INSERT INTO users(name, email, password, role) VALUES(%s,%s,%s,%s)",
              (name, email, password, role))
            commit()
        except mysql.connector.errors.IntegrityError:
            return render_template("register.html", error="Email already registered.")

        return redirect('/login')

    return render_template("register.html")

# ── Login ─────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        q("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id']    = user[0]
            session['user_name']  = user[1]
            session['user_email'] = user[2]
            session['role'] = user[4] if len(user) > 4 else 'Student'

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
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ── USER ROUTES ───────────────────────────────────────────────────────────────

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect('/login')

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
        total_leaves=total,
        approved_leaves=approved,
        pending_leaves=pending,
        rejected_leaves=rejected
    )

@app.route('/user/apply_leave', methods=['GET', 'POST'])
def apply_leave():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        from_date = request.form.get('from_date')
        to_date = request.form.get('to_date')
        reason = request.form.get('reason')
        user_id = session['user_id']

        # basic validation
        if not leave_type or not from_date or not to_date or not reason:
            return "All required fields must be filled."

        if from_date > to_date:
            return "From Date cannot be greater than To Date."

        document_path = None

        # optional document upload
        if 'document' in request.files:
            file = request.files['document']

            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    document_path = file_path
                else:
                    return "Invalid file type. Allowed: pdf, jpg, jpeg, png, doc, docx"

        sql = """
        INSERT INTO leaves (user_id, leave_type, from_date, to_date, reason, status, document_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (user_id, leave_type, from_date, to_date, reason, 'Pending', document_path)

        cursor.execute(sql, values)
        db.commit()

        return redirect('/user/leave_history')

    return render_template('user Dashboard/apply_leave.html')

@app.route('/user/leave_history')
def leave_history():
    if 'user_id' not in session:
        return redirect('/login')

    q("SELECT id, leave_type, from_date, to_date, status FROM leaves WHERE user_id=%s ORDER BY id DESC",
      (session['user_id'],))
    return render_template('user Dashboard/leave_history.html', leaves=cursor.fetchall())

@app.route('/user/leave_status')
def leave_status():
    if 'user_id' not in session:
        return redirect('/login')

    q("SELECT id, leave_type, from_date, to_date, status, faculty_name, remarks FROM leaves WHERE user_id=%s ORDER BY id DESC",
      (session['user_id'],))
    return render_template('user Dashboard/leave_status.html', leave_status_data=cursor.fetchall())

@app.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    if 'user_id' not in session:
        return redirect('/login')

    uid = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            q("UPDATE users SET name=%s, email=%s, phone=%s, department=%s, bio=%s WHERE id=%s",
              (request.form['name'], request.form['email'],
               request.form.get('phone',''), request.form.get('department',''),
               request.form.get('bio',''), uid))
            commit()
            session['user_name']  = request.form['name']
            session['user_email'] = request.form['email']

        elif action == 'change_password':
            q("SELECT password FROM users WHERE id=%s", (uid,))
            row = cursor.fetchone()
            if row and row[0] == request.form['current_password']:
                if request.form['new_password'] == request.form['confirm_password']:
                    q("UPDATE users SET password=%s WHERE id=%s", (request.form['new_password'], uid))
                    commit()
                    return redirect('/user/profile?pw=success')
                else:
                    return redirect('/user/profile?pw=mismatch')
            else:
                return redirect('/user/profile?pw=wrong')

        return redirect('/user/profile')

    try:
        q("SELECT id, name, email, role, phone, department, bio FROM users WHERE id=%s", (uid,))
        raw = cursor.fetchone()
        user = (raw[0], raw[1], raw[2], raw[3], raw[4] or '', raw[5] or '', raw[6] or '') if raw else None
    except Exception:
        q("SELECT id, name, email, role FROM users WHERE id=%s", (uid,))
        raw = cursor.fetchone()
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


# ── FACULTY ROUTES ────────────────────────────────────────────────────────────

def faculty_required():
    return 'user_id' in session and session.get('role') == 'Faculty'

@app.route('/faculty/dashboard')
def faculty_dashboard():
    if not faculty_required():
        return redirect('/login')

    q("SELECT COUNT(*) FROM leaves WHERE status='Pending'")
    pending = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE status='Approved'")
    approved = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE status='Rejected'")
    rejected = cursor.fetchone()[0]

    q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.status
         FROM leaves l JOIN users u ON l.user_id = u.id
         WHERE l.status = 'Pending' ORDER BY l.id DESC LIMIT 10""")
    pending_leaves = cursor.fetchall()

    return render_template(
        'faculty Dashboard/Faculty_Dashboard.html',
        faculty_name=session.get('user_name'),
        pending=pending, approved=approved, rejected=rejected,
        pending_leaves=pending_leaves
    )

@app.route('/faculty/leaves')
def faculty_leaves():
    if not faculty_required():
        return redirect('/login')

    status_filter = request.args.get('status', '')
    if status_filter:
        q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.reason, l.status
             FROM leaves l JOIN users u ON l.user_id = u.id
             WHERE l.status = %s ORDER BY l.id DESC""", (status_filter,))
    else:
        q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.reason, l.status
             FROM leaves l JOIN users u ON l.user_id = u.id ORDER BY l.id DESC""")

    return render_template('faculty Dashboard/Faculty_Leave.html',
                           leaves=cursor.fetchall(), status_filter=status_filter)

@app.route('/faculty/leave/<int:leave_id>/approve', methods=['POST'])
def faculty_approve_leave(leave_id):
    if not faculty_required():
        return redirect('/login')
    q("UPDATE leaves SET status='Approved', faculty_name=%s, remarks=%s WHERE id=%s",
      (session.get('user_name'), request.form.get('remarks', ''), leave_id))
    commit()
    return redirect('/faculty/leaves')

@app.route('/faculty/leave/<int:leave_id>/reject', methods=['POST'])
def faculty_reject_leave(leave_id):
    if not faculty_required():
        return redirect('/login')
    q("UPDATE leaves SET status='Rejected', faculty_name=%s, remarks=%s WHERE id=%s",
      (session.get('user_name'), request.form.get('remarks', ''), leave_id))
    commit()
    return redirect('/faculty/leaves')


# ── ADMIN ROUTES ──────────────────────────────────────────────────────────────

def admin_required():
    return 'user_id' in session and session.get('role') == 'Admin'

@app.route('/admin/dashboard')
def admin_dashboard():
    if not admin_required():
        return redirect('/login')

    q("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves")
    total_leaves = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]
    q("SELECT COUNT(*) FROM leaves WHERE status='Approved'")
    approved_leaves = cursor.fetchone()[0]

    q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.status
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
def admin_users():
    if not admin_required():
        return redirect('/login')
    q("SELECT id, name, email, role FROM users ORDER BY id DESC")
    return render_template('admin Dashboard/admin_users.html', users=cursor.fetchall())

@app.route('/admin/leaves')
def admin_leaves():
    if not admin_required():
        return redirect('/login')
    q("""SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.reason, l.status
         FROM leaves l JOIN users u ON l.user_id = u.id ORDER BY l.id DESC""")
    return render_template('admin Dashboard/admin_leaves.html', leaves=cursor.fetchall())

@app.route('/admin/leave/<int:leave_id>/approve', methods=['POST'])
def approve_leave(leave_id):
    if not admin_required():
        return redirect('/login')
    q("UPDATE leaves SET status='Approved' WHERE id=%s", (leave_id,))
    commit()
    return redirect('/admin/leaves')

@app.route('/admin/leave/<int:leave_id>/reject', methods=['POST'])
def reject_leave(leave_id):
    if not admin_required():
        return redirect('/login')
    q("UPDATE leaves SET status='Rejected' WHERE id=%s", (leave_id,))
    commit()
    return redirect('/admin/leaves')


if __name__ == '__main__':
    app.run(debug=True)
