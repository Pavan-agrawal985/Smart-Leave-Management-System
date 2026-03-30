from flask import Flask, request, render_template, redirect, session, url_for
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

# MySQL connection
try:

    db=mysql.connector.connect(
        host="localhost",
        user="root",
        password="Kasana@2005",
        database="leave_system",
        auth_plugin='mysql_native_password'
    )

    cursor=db.cursor()

    print("MySQL Connected")

except Exception as e:
    print("Error:",e)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
            session['role'] = user[4] if len(user) > 4 else 'Student'
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