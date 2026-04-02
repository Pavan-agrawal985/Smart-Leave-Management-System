from flask import Flask, request, render_template, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = "smart_leave_secret_key"

# MySQL connection
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Pavan@985",
        database="leave_system",
        auth_plugin='mysql_native_password'
    )
    cursor = db.cursor()
    print("MySQL Connected")

    # Add extra profile columns if they don't exist yet
    for col, definition in [
        ("phone",      "VARCHAR(20) DEFAULT ''"),
        ("department", "VARCHAR(100) DEFAULT ''"),
        ("bio",        "TEXT DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            db.commit()
        except Exception:
            pass  # Column already exists

except Exception as e:
    print("Error:", e)

# ── Home ──────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template("home.html")

# ── Register ──────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'Student')

        if not name or not email or not password:
            return "Name, email, and password are required."

        cursor.execute(
            "INSERT INTO users(name, email, password, role) VALUES(%s, %s, %s, %s)",
            (name, email, password, role)
        )
        db.commit()
        return redirect('/login')

    return render_template("register.html")

# ── Login ─────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
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

# ══════════════════════════════════════════════════════════════════════════════
# USER ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s", (user_id,))
    total_leaves = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Approved'", (user_id,))
    approved_leaves = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Pending'", (user_id,))
    pending_leaves = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Rejected'", (user_id,))
    rejected_leaves = cursor.fetchone()[0]

    return render_template(
        'user Dashboard/user_dashboard.html',
        user_name=session.get('user_name'),
        total_leaves=total_leaves,
        approved_leaves=approved_leaves,
        pending_leaves=pending_leaves,
        rejected_leaves=rejected_leaves
    )

@app.route('/user/apply_leave', methods=['GET', 'POST'])
def apply_leave():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        from_date = request.form['from_date']
        to_date = request.form['to_date']
        reason = request.form['reason']
        user_id = session['user_id']

        cursor.execute(
            "INSERT INTO leaves (user_id, leave_type, from_date, to_date, reason, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, leave_type, from_date, to_date, reason, 'Pending')
        )
        db.commit()
        return redirect('/user/leave_history')

    return render_template('user Dashboard/apply_leave.html')

@app.route('/user/leave_history')
def leave_history():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor.execute(
        "SELECT id, leave_type, from_date, to_date, status FROM leaves WHERE user_id=%s ORDER BY id DESC",
        (user_id,)
    )
    leaves = cursor.fetchall()
    return render_template('user Dashboard/leave_history.html', leaves=leaves)

@app.route('/user/leave_status')
def leave_status():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor.execute(
        "SELECT id, leave_type, from_date, to_date, status, faculty_name, remarks FROM leaves WHERE user_id=%s ORDER BY id DESC",
        (user_id,)
    )
    leave_status_data = cursor.fetchall()
    return render_template('user Dashboard/leave_status.html', leave_status_data=leave_status_data)

@app.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            name  = request.form['name']
            email = request.form['email']
            phone = request.form.get('phone', '')
            dept  = request.form.get('department', '')
            bio   = request.form.get('bio', '')
            cursor.execute(
                "UPDATE users SET name=%s, email=%s, phone=%s, department=%s, bio=%s WHERE id=%s",
                (name, email, phone, dept, bio, user_id)
            )
            db.commit()
            session['user_name']  = name
            session['user_email'] = email

        elif action == 'change_password':
            current_pw  = request.form['current_password']
            new_pw      = request.form['new_password']
            confirm_pw  = request.form['confirm_password']
            cursor.execute("SELECT password FROM users WHERE id=%s", (user_id,))
            row = cursor.fetchone()
            if row and row[0] == current_pw:
                if new_pw == confirm_pw:
                    cursor.execute("UPDATE users SET password=%s WHERE id=%s", (new_pw, user_id))
                    db.commit()
                    return redirect('/user/profile?pw=success')
                else:
                    return redirect('/user/profile?pw=mismatch')
            else:
                return redirect('/user/profile?pw=wrong')

        return redirect('/user/profile')

    # Fetch full profile — gracefully handle missing columns
    try:
        cursor.execute("SELECT id, name, email, role, phone, department, bio FROM users WHERE id=%s", (user_id,))
        raw = cursor.fetchone()
        user = (raw[0], raw[1], raw[2], raw[3], raw[4] or '', raw[5] or '', raw[6] or '') if raw else None
    except Exception:
        cursor.execute("SELECT id, name, email, role FROM users WHERE id=%s", (user_id,))
        raw = cursor.fetchone()
        user = (raw[0], raw[1], raw[2], raw[3], '', '', '') if raw else None

    if not user:
        return redirect('/logout')

    # Leave stats for profile
    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s", (user_id,))
    total_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Approved'", (user_id,))
    approved_leaves = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leaves WHERE user_id=%s AND status='Pending'", (user_id,))
    pending_leaves = cursor.fetchone()[0]

    return render_template(
        'user Dashboard/user_profile.html',
        user=user,
        total_leaves=total_leaves,
        approved_leaves=approved_leaves,
        pending_leaves=pending_leaves,
        pw_status=request.args.get('pw')
    )

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

def admin_required():
    return 'user_id' in session and session.get('role') == 'Admin'

@app.route('/admin/dashboard')
def admin_dashboard():
    if not admin_required():
        return redirect('/login')

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leaves")
    total_leaves = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leaves WHERE status='Pending'")
    pending_leaves = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leaves WHERE status='Approved'")
    approved_leaves = cursor.fetchone()[0]

    cursor.execute("""
        SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.status
        FROM leaves l JOIN users u ON l.user_id = u.id
        ORDER BY l.id DESC LIMIT 10
    """)
    recent_leaves = cursor.fetchall()

    return render_template(
        'admin Dashboard/admin_dashboard.html',
        total_users=total_users,
        total_leaves=total_leaves,
        pending_leaves=pending_leaves,
        approved_leaves=approved_leaves,
        recent_leaves=recent_leaves
    )

@app.route('/admin/users')
def admin_users():
    if not admin_required():
        return redirect('/login')

    cursor.execute("SELECT id, name, email, role FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    return render_template('admin Dashboard/admin_users.html', users=users)

@app.route('/admin/leaves')
def admin_leaves():
    if not admin_required():
        return redirect('/login')

    cursor.execute("""
        SELECT l.id, u.name, l.leave_type, l.from_date, l.to_date, l.reason, l.status
        FROM leaves l JOIN users u ON l.user_id = u.id
        ORDER BY l.id DESC
    """)
    leaves = cursor.fetchall()
    return render_template('admin Dashboard/admin_leaves.html', leaves=leaves)

@app.route('/admin/leave/<int:leave_id>/approve', methods=['POST'])
def approve_leave(leave_id):
    if not admin_required():
        return redirect('/login')

    cursor.execute("UPDATE leaves SET status='Approved' WHERE id=%s", (leave_id,))
    db.commit()
    return redirect('/admin/leaves')

@app.route('/admin/leave/<int:leave_id>/reject', methods=['POST'])
def reject_leave(leave_id):
    if not admin_required():
        return redirect('/login')

    cursor.execute("UPDATE leaves SET status='Rejected' WHERE id=%s", (leave_id,))
    db.commit()
    return redirect('/admin/leaves')

# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(debug=True)
