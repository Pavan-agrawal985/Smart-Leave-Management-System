from flask import Flask,request,render_template,redirect
import mysql.connector

app = Flask(__name__)

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
@app.route('/register',methods=['GET','POST'])
def register():

    if request.method=='POST':

        name=request.form['name']
        email=request.form['email']
        password=request.form['password']

        sql="INSERT INTO users(name,email,password) VALUES(%s,%s,%s)"

        values=(name,email,password)

        cursor.execute(sql,values)

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
            return "Login Successful"

        else:
            return "Invalid Login"

    return render_template("login.html")


app.run(debug=True)