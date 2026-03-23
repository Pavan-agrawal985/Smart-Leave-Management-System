from flask import Flask, request, render_template, redirect, session, url_for
import mysql.connector

app = Flask(__name__)
app.secret_key = "smart_leave_secret_key"

# MySQL connection
try:

    db=mysql.connector.connect(
        host="localhost",
        user="root",
        password="Pavan@985",
        database="leave_system",
        auth_plugin='mysql_native_password'
    )

    cursor=db.cursor()

    print("MySQL Connected")

except Exception as e:
    print("Error:",e)

#Home
@app.route('/')
def home():
    return render_template("home.html")

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'Student')

        if not name or not email or not password:
            return "Name, email, and password are required."

        sql = "INSERT INTO users(name, email, password, role) VALUES(%s, %s, %s, %s)"
        values = (name, email, password, role)

        cursor.execute(sql, values)
        db.commit()

        return redirect('/login')

    return render_template("register.html")


# Login
@app.route('/login',methods=['GET','POST'])
def login():

    if request.method=='POST':

        email=request.form['email']
        password=request.form['password']

        sql="SELECT * FROM users WHERE email=%s AND password=%s"

        values=(email,password)

        cursor.execute(sql,values)

        user=cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['user_email'] = user[2]
            session['role'] = user[3] if len(user) > 3 else 'Student'
            return redirect('/user/dashboard')

        else:
            return "Invalid Login"

    return render_template("login.html")
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
        'user_dashboard.html',
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

        sql = """
        INSERT INTO leaves (user_id, leave_type, from_date, to_date, reason, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (user_id, leave_type, from_date, to_date, reason, 'Pending')
        cursor.execute(sql, values)
        db.commit()

        return redirect('/user/leave_history')

    return render_template('apply_leave.html')
@app.route('/user/leave_history')
def leave_history():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor.execute("""
        SELECT id, leave_type, from_date, to_date, status
        FROM leaves
        WHERE user_id=%s
        ORDER BY id DESC
    """, (user_id,))
    leaves = cursor.fetchall()

    return render_template('leave_history.html', leaves=leaves)
@app.route('/user/leave_status')
def leave_status():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor.execute("""
        SELECT id, leave_type, from_date, to_date, status, faculty_name, remarks
        FROM leaves
        WHERE user_id=%s
        ORDER BY id DESC
    """, (user_id,))
    leave_status_data = cursor.fetchall()

    return render_template('leave_status.html', leave_status_data=leave_status_data)
@app.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']

        cursor.execute("UPDATE users SET name=%s, email=%s WHERE id=%s", (name, email, user_id))
        db.commit()

        session['user_name'] = name
        session['user_email'] = email

        return redirect('/user/profile')

    cursor.execute("SELECT id, name, email FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    return render_template('user_profile.html', user=user)
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

app.run(debug=True)