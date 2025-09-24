from flask import Flask, render_template, request, redirect, url_for, session, send_file
import mysql.connector
import qrcode, io, base64, hashlib, time, datetime
import pandas as pd
import io
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from email.mime.text import MIMEText
import base64
import bcrypt
import os
app = Flask(__name__)
app.secret_key = os.urandom(24) 
# ---------- DATABASE CONNECTION ----------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="school_db"
    )
# ---------- SETUP TABLES ----------
def setup_db():
    db = get_db()
    cursor = db.cursor()
    # Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        roll_no VARCHAR(20),
        name VARCHAR(100),
        std VARCHAR(20),
        school VARCHAR(100),
        password VARCHAR(100),
        PRIMARY KEY (roll_no, std)
    )
    """)
    # Teachers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        teacher_id VARCHAR(20) PRIMARY KEY,
        name VARCHAR(100),
        password VARCHAR(100),
        email VARCHAR(100),
        in_charge_class VARCHAR(20)
    )
    """)
    # Attendance table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        roll_no VARCHAR(20),
        std VARCHAR(20),
        date DATE,
        present BOOLEAN,
        UNIQUE(roll_no, std, date)
    )
    """)
    db.commit()
    db.close()
# ---------- GMAIL API SETUP ----------
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
def gmail_authenticate():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("F:\Hackathon\credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)
def send_email_gmail(to, subject, body):
    service = gmail_authenticate()
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {'raw': encoded_message}
    service.users().messages().send(userId='me', body=create_message).execute()
# ---------- CHECK ATTENDANCE & NOTIFY ----------
def check_attendance_and_notify(roll_no, std):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get student's attendance
    cursor.execute(
        "SELECT COUNT(*) AS total, SUM(present) AS present FROM attendance WHERE roll_no=%s AND std=%s",
        (roll_no, std)
    )
    result = cursor.fetchone()
    total = result['total'] or 0
    present = result['present'] or 0
    percentage = (present / total * 100) if total > 0 else 0
    
    if percentage < 75:
        # Fetch teacher in charge of the class
        cursor.execute(
            "SELECT name, email FROM teachers WHERE in_charge_class=%s",
            (std,)
        )
        teacher = cursor.fetchone()
        if teacher:
            subject = f"Low Attendance Alert: Student {roll_no}"
            body = f"Dear {teacher['name']},\n\nStudent Roll number : {roll_no} in class {std} has attendance {percentage:.2f}% which is below 75%.\nPlease take necessary action."
            send_email_gmail(teacher['email'], subject, body)
    
    db.close()
# ---------- LOGIN ----------
@app.route("/", methods=["GET", "POST"])
def login():
    test_roll_no = "5"
    test_std = "1st"
    
    if request.method == "POST":
        user_type = request.form["user_type"]
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        cursor = db.cursor(dictionary=True)
        if user_type == "student":
            std = request.form["std"]
            cursor.execute(
                "SELECT * FROM students WHERE roll_no=%s AND std=%s",
                (username, std)
            )
            user = cursor.fetchone()
            db.close()
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                session["roll_no"] = username
                session["std"] = std
                session["user_type"] = "student"
                return redirect(url_for("student_dashboard"))
            else:
                return "Invalid student login!"
        elif user_type == "teacher":
            cursor.execute(
                "SELECT * FROM teachers WHERE teacher_id=%s",
                (username,)
            )
            user = cursor.fetchone()
            db.close()
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                session["teacher_id"] = username
                session["user_type"] = "teacher"
                return redirect(url_for("teacher_dashboard"))
            else:
                return "Invalid teacher login!"
    return '''
            <style>
            body {
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                display: flex;
                height: 100vh;
                justify-content: center;
                align-items: center;
                margin: 0;
            }
            .login-container {
                background: white;
                padding: 30px 40px;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                width: 320px;
            }
            h2 {
                margin-bottom: 25px;
                font-weight: 600;
                color: #333;
                text-align: center;
            }
            label {
                display: block;
                margin-bottom: 6px;
                font-weight: 500;
                color: #555;
            }
            select, input[type=text], input[type=password] {
                width: 100%;
                padding: 8px 10px;
                margin-bottom: 18px;
                border-radius: 4px;
                border: 1px solid #ccc;
                box-sizing: border-box;
                font-size: 14px;
            }
            select:focus, input[type=text]:focus, input[type=password]:focus {
                border-color: #7aaaff;
                outline: none;
                box-shadow: 0 0 5px #7aaaff;
            }
            input[type=submit] {
                width: 100%;
                padding: 10px 0;
                background-color: #4a90e2;
                color: white;
                border: none;
                font-weight: 600;
                font-size: 16px;
                border-radius: 4px;
                cursor: pointer;
                transition: background-color 0.3s ease;
            }
            input[type=submit]:hover {
                background-color: #357abd;
            }
            </style>

            <div class="login-container">
            <h2>Login</h2>
            <form method="post">
                <label for="user_type">User Type:</label>
                <select name="user_type" id="user_type">
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
                </select>

                <label for="username">Username (Roll No / Teacher ID):</label>
                <input name="username" id="username" type="text">

                <label for="password">Password:</label>
                <input type="password" name="password" id="password">

                <label for="std">Class (if Student):</label>
                <input name="std" id="std" type="text">

                <input type="submit" value="Login">
            </form>
            </div>

    '''
# ---------- STUDENT DASHBOARD ----------
@app.route("/student_dashboard")
def student_dashboard():
    if session.get("user_type") != "student":   # security check
        return redirect(url_for("login"))
    roll_no = session.get("roll_no")
    std = session.get("std")
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Get total and present count
    cursor.execute("SELECT COUNT(*) as total, SUM(present) as present FROM attendance WHERE roll_no=%s AND std=%s", 
                   (roll_no, std))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    total = result['total'] or 0
    present = result['present'] or 0
    percentage = (present / total * 100) if total > 0 else 0
    # Color logic
    color = "green" if percentage >= 75 else "red"
    
    color_class = "attendance-green" if percentage >= 75 else "attendance-red"

    return f'''
            <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f9fafb;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                min-height: 100vh;
            }}
            .dashboard-container {{
                background: white;
                margin-top: 30px;
                padding: 30px 40px;
                border-radius: 8px;
                box-shadow: 0 6px 18px rgba(0,0,0,0.1);
                width: 360px;
                box-sizing: border-box;
                position: relative;
            }}
            h2 {{
                margin-top: 0;
                font-weight: 700;
                color: #2c3e50;
                text-align: center;
            }}
            ul {{
                list-style: none;
                padding-left: 0;
                margin-top: 25px;
            }}
            ul li {{
                margin-bottom: 20px;
            }}
            ul li a {{
                text-decoration: none;
                font-weight: 600;
                color: #2980b9;
                font-size: 16px;
                display: block;
                border: 1px solid #2980b9;
                padding: 12px 16px;
                border-radius: 5px;
                transition: background-color 0.3s ease, color 0.3s ease;
            }}
            ul li a:hover {{
                background-color: #2980b9;
                color: white;
            }}
            .attendance-badge {{
                position: absolute;
                top: 15px;
                right: 15px;
                padding: 8px 14px;
                border-radius: 20px;
                font-weight: 700;
                font-size: 14px;
                color: white;
            }}
            .attendance-green {{
                background-color: #27ae60;
            }}
            .attendance-red {{
                background-color: #e74c3c;
            }}
            </style>

            <div class="dashboard-container">
            <div class="attendance-badge {color_class}">
                Attendance: {percentage:.2f}%
            </div>
            <h2>Student Dashboard</h2>
            <ul>
                <li><a href="/student_scan_qr">📷 Scan QR for Attendance</a></li>
                <li><a href="/view_my_attendance">📊 View My Attendance</a></li>
                <li><a href="/download_my_attendance">⬇ Download My Attendance (Excel)</a></li>
            </ul>
            </div>


    '''
@app.route("/view_my_attendance")
def view_my_attendance():
    if session.get("user_type") != "student":
        return redirect(url_for("login"))
    roll_no = session["roll_no"]
    std = session["std"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT date, present 
        FROM attendance 
        WHERE roll_no=%s AND std=%s 
        ORDER BY date DESC
    """, (roll_no, std))
    records = cursor.fetchall()
    db.close()

    return f'''
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: #f9fafb;
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        min-height: 100vh;
      }}
      .attendance-container {{
        background: white;
        margin-top: 30px;
        padding: 30px 40px;
        border-radius: 8px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
        width: 460px;
        box-sizing: border-box;
      }}
      h2 {{
        margin-top: 0;
        font-weight: 700;
        color: #2c3e50;
        text-align: center;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
      }}
      th, td {{
        border: 1px solid #ccc;
        padding: 10px 15px;
        text-align: center;
        font-size: 15px;
      }}
      th {{
        background-color: #2980b9;
        color: white;
        font-weight: 600;
      }}
      tr:nth-child(even) {{
        background-color: #f4f7fa;
      }}
      a {{
        display: inline-block;
        margin-top: 20px;
        color: #2980b9;
        text-decoration: none;
        font-weight: 600;
        font-size: 15px;
        border: 1px solid #2980b9;
        padding: 8px 15px;
        border-radius: 5px;
        transition: background-color 0.3s ease, color 0.3s ease;
      }}
      a:hover {{
        background-color: #2980b9;
        color: white;
      }}
      p {{
        text-align: center;
        color: #555;
        font-size: 15px;
        margin-top: 20px;
      }}
    </style>

    <div class="attendance-container">
      <h2>Your Attendance</h2>
      {"""
        <p>No attendance records found!</p>
      """ if not records else f'''
      <table>
        <tr><th>Date</th><th>Status</th></tr>
        {''.join(f"<tr><td>{r[0]}</td><td>{'Present ✅' if r[1] else 'Absent ❌'}</td></tr>" for r in records)}
      </table>
      '''}
      <a href="/student_dashboard">⬅ Back</a>
    </div>
    '''

# ---------- DOWNLOAD MY ATTENDANCE (Excel) ----------
@app.route("/download_my_attendance")
def download_my_attendance():
    if session.get("user_type") != "student":
        return redirect(url_for("login"))
    roll_no = session["roll_no"]
    std = session["std"]
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT date, present 
        FROM attendance 
        WHERE roll_no=%s AND std=%s 
        ORDER BY date DESC
    """, (roll_no, std))
    records = cursor.fetchall()
    db.close()
    if not records:
        return "No attendance records found!"
    # Convert to DataFrame
    df = pd.DataFrame(records)
    df['present'] = df['present'].apply(lambda x: 'Present' if x else 'Absent')
    # Save to Excel in memory
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name=f"{roll_no}_{std}")
    output.seek(0)
    return send_file(output,
                     download_name=f"MyAttendance_{roll_no}_{std}.xlsx",
                     as_attachment=True)
# ---------- STUDENT SCAN PAGE ----------
@app.route("/student_scan_qr")
def student_scan_qr():
    if session.get("user_type") != "student":
        return redirect(url_for("login"))
    return '''
    <style>
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: #f9fafb;
    margin: 0;
    padding: 20px;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 100vh;
  }
  .scan-container {
    background: white;
    padding: 30px 40px;
    border-radius: 8px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.1);
    width: 360px;
    box-sizing: border-box;
    text-align: center;
  }
  h2 {
    margin-top: 0;
    font-weight: 700;
    color: #2c3e50;
    margin-bottom: 25px;
  }
  video {
    border-radius: 8px;
    border: 1px solid black;
  }
  #result {
    margin-top: 20px;
    font-weight: 600;
    font-size: 16px;
    color: #2980b9;
    min-height: 24px;
  }
</style>

<div class="scan-container">
  <h2>Scan QR Code</h2>
  <video id="video" width="300" height="200"></video>
  <canvas id="canvas" hidden></canvas>
  <p id="result">QR Code Result: None</p>
</div>

<script src="https://cdn.jsdelivr.net/npm/jsqr/dist/jsQR.js"></script>
<script>
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const context = canvas.getContext('2d');
const resultElem = document.getElementById('result');
// Access camera
navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
    .then(stream => {
        video.srcObject = stream;
        video.setAttribute("playsinline", true); // required for iOS
        video.play();
        requestAnimationFrame(tick);
    });
function tick() {
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, canvas.width, canvas.height);
        if (code) {
            resultElem.textContent = "QR Code Result: " + code.data;
            // Auto submit to server
            fetch("/scan", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "code=" + encodeURIComponent(code.data)
            })
            .then(response => response.text())
            .then(data => alert(data))
            .catch(err => alert(err));
        }
    }
    requestAnimationFrame(tick);
}
</script>

    '''
# ---------- SCAN QR ----------
@app.route("/scan", methods=["POST"])
def scan():
    if session.get("user_type") != "student":
        return redirect(url_for("login"))
    scanned_code = request.form["code"]
    secret = "mysecretkey"
    valid = False
    std = session["std"]  # student's class
    # Check for current/previous/next 30-second slot
    for offset in [-1, 0, 1]:
        slot = int(time.time() // 30) + offset
        expected = hashlib.sha256(f"{slot}:{secret}:{std}".encode()).hexdigest()
        if scanned_code == expected:
            valid = True
            break
    if not valid:
        return "Invalid or expired QR!"
    today = datetime.date.today()
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO attendance (roll_no, std, date, present) VALUES (%s, %s, %s, %s)",
            (session["roll_no"], session["std"], today, True)
        )
        db.commit()
    except mysql.connector.errors.IntegrityError:
        pass
    db.close()
    check_attendance_and_notify(session["roll_no"], session["std"])
    return "Attendance marked!"
# ---------- TEACHER DASHBOARD ----------
@app.route("/teacher_dashboard", methods=["GET", "POST"])
def teacher_dashboard():
    if session.get("user_type") != "teacher":
        return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT std FROM students")
    classes = [c[0] for c in cursor.fetchall()]
    db.close()
    if request.method == "POST":
        selected_class = request.form.get("class_export")
        if selected_class:
            # Export attendance for selected class
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT s.roll_no, s.name, a.date, a.present
                FROM students s
                LEFT JOIN attendance a 
                 ON s.roll_no = a.roll_no AND s.std = a.std
                WHERE s.std = %s
                ORDER BY s.roll_no, a.date
            """, (selected_class,))
            records = cursor.fetchall()
            db.close()
            # Create DataFrame
            df = pd.DataFrame(records)
            df['present'] = df['present'].apply(lambda x: 'Present' if x else 'Absent' if x is not None else '-')
            df['date'] = df['date'].fillna('-')
            # Save to Excel in memory
            output = io.BytesIO()
            df.to_excel(output, index=False, sheet_name=selected_class)
            output.seek(0)
            return send_file(output, download_name=f"Attendance_{selected_class}.xlsx", as_attachment=True)

    class_list = "".join([
        f'<li>{c} - '
        f'<a href="/generate_qr/{c}">Generate QR</a> | '
        f'<a href="/view_attendance/{c}">View Attendance</a></li>'
        for c in classes
    ])
    class_options = "".join([f'<option value="{c}">{c}</option>' for c in classes])

    return f'''
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f9fafb;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
      }}
      .dashboard-container {{
        background: white;
        width: 460px;
        padding: 30px 40px;
        border-radius: 8px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
        box-sizing: border-box;
      }}
      h2, h3 {{
        color: #2c3e50;
        font-weight: 700;
        margin-top: 0;
      }}
      ul {{
        list-style: none;
        padding-left: 0;
        margin-bottom: 25px;
      }}
      li {{
        margin-bottom: 12px;
        font-size: 16px;
        color: #34495e;
      }}
      li a {{
        color: #2980b9;
        text-decoration: none;
        margin-left: 8px;
        font-weight: 600;
      }}
      li a:hover {{
        text-decoration: underline;
      }}
      a {{
        display: inline-block;
        margin-bottom: 15px;
        color: #2980b9;
        text-decoration: none;
        font-weight: 600;
        font-size: 15px;
        border: 1px solid #2980b9;
        padding: 7px 15px;
        border-radius: 5px;
        transition: background-color 0.3s ease, color 0.3s ease;
      }}
      a:hover {{
        background-color: #2980b9;
        color: white;
      }}
      form {{
        margin-top: 15px;
      }}
      select {{
        padding: 8px 10px;
        font-size: 15px;
        border-radius: 4px;
        border: 1px solid #ccc;
        margin-right: 10px;
        min-width: 140px;
      }}
      input[type="submit"] {{
        padding: 8px 20px;
        font-size: 15px;
        font-weight: 600;
        color: white;
        background-color: #2980b9;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s ease;
      }}
      input[type="submit"]:hover {{
        background-color: #1f6391;
      }}
      hr {{
        margin: 25px 0;
        border: none;
        border-top: 1px solid #ddd;
      }}
    </style>

    <div class="dashboard-container">
      <h2>Teacher Dashboard</h2>
      <ul>
        {class_list}
      </ul>
      <a href="/add_student">Add New Student</a><br>
      <a href="/add_teacher">Add New Teacher</a>
      <hr>
      <h3>Export Attendance to Excel</h3>
      <form method="post">
        <select name="class_export" required>
          {class_options}
        </select>
        <input type="submit" value="Download Excel">
      </form>
    </div>
    '''

# ---------- VIEW ATTENDANCE FOR A CLASS WITH % ----------
@app.route("/view_attendance/<std>")
def view_attendance(std):
    if session.get("user_type") != "teacher":
        return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor(dictionary=True)
    # Fetch all students in the class
    cursor.execute("SELECT roll_no, name FROM students WHERE std=%s ORDER BY roll_no", (std,))
    students = cursor.fetchall()
    # Fetch all attendance for this class
    cursor.execute("SELECT roll_no, present FROM attendance WHERE std=%s", (std,))
    attendance = cursor.fetchall()
    db.close()
    # Build a mapping of roll_no -> [presents, total_days]
    attendance_map = {}
    for s in students:
        attendance_map[s['roll_no']] = {'name': s['name'], 'present': 0, 'total': 0}
    for a in attendance:
        if a['roll_no'] in attendance_map:
            attendance_map[a['roll_no']]['total'] += 1
            if a['present']:
                attendance_map[a['roll_no']]['present'] += 1
    # Build HTML rows
    html_rows = ""
    for roll_no, data in attendance_map.items():
        total = data['total']
        present = data['present']
        perc = (present / total * 100) if total > 0 else 0
        color = "green" if perc >= 75 else "red"
        html_rows += f"<tr><td>{roll_no}</td><td>{data['name']}</td><td>{present}/{total}</td><td style='color:{color};font-weight:bold'>{perc:.1f}%</td></tr>"

    return f'''
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f9fafb;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
      }}
      .attendance-container {{
        background: white;
        width: 600px;
        padding: 30px 40px;
        border-radius: 8px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
        box-sizing: border-box;
      }}
      h2 {{
        color: #2c3e50;
        font-weight: 700;
        margin-top: 0;
        text-align: center;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
      }}
      th, td {{
        border: 1px solid #ccc;
        padding: 10px 15px;
        text-align: center;
        font-size: 15px;
      }}
      th {{
        background-color: #2980b9;
        color: white;
        font-weight: 600;
      }}
      tr:nth-child(even) {{
        background-color: #f4f7fa;
      }}
      a {{
        display: inline-block;
        margin-top: 20px;
        color: #2980b9;
        text-decoration: none;
        font-weight: 600;
        font-size: 15px;
        border: 1px solid #2980b9;
        padding: 8px 15px;
        border-radius: 5px;
        transition: background-color 0.3s ease, color 0.3s ease;
      }}
      a:hover {{
        background-color: #2980b9;
        color: white;
      }}
    </style>

    <div class="attendance-container">
      <h2>Attendance for Class {std}</h2>
      <table>
        <tr><th>Roll No</th><th>Name</th><th>Present/Total</th><th>Attendance %</th></tr>
        {html_rows}
      </table>
      <a href="/teacher_dashboard">⬅ Back</a>
    </div>
    '''

# ---------- ADD NEW STUDENT WITH EXCEL UPLOAD ----------
import pandas as pd
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if session.get("user_type") != "teacher":
        return redirect(url_for("login"))
    message = ""
    if request.method == "POST":
        # ---------- Manual Add ----------
        if "roll_no" in request.form:
            roll_no = request.form["roll_no"]
            name = request.form["name"]
            std = request.form["std"]
            school = request.form["school"]
            password = request.form["password"]
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db = get_db()
            cursor = db.cursor()
            try:
                cursor.execute(
                    "INSERT INTO students (roll_no, name, std, school, password) VALUES (%s,%s,%s,%s,%s)",
                    (roll_no, name, std, school, hashed_password)
                )
                db.commit()
                message = "Student added successfully!"
            except mysql.connector.errors.IntegrityError:
                message = "Student already exists!"
            db.close()
        # ---------- Excel Upload ----------
        elif "file" in request.files:
            file = request.files["file"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                try:
                    if filename.endswith(".csv"):
                        df = pd.read_csv(filepath)
                    else:
                        df = pd.read_excel(filepath)
                    # Try to detect required columns flexibly
                    df_columns = [c.lower().strip() for c in df.columns]
                    roll_col = next((c for c in df.columns if 'roll' in c.lower()), None)
                    name_col = next((c for c in df.columns if 'name' in c.lower()), None)
                    std_col = next((c for c in df.columns if 'class' in c.lower() or 'std' in c.lower()), None)
                    school_col = next((c for c in df.columns if 'school' in c.lower()), None)
                    password_col = next((c for c in df.columns if 'password' in c.lower()), None)
                    missing_cols = []
                    for col, name in zip([roll_col,name_col,std_col,school_col,password_col],
                                         ['Roll No','Name','Class','School','Password']):
                        if col is None:
                            missing_cols.append(name)
                    if missing_cols:
                        message = f"Missing required columns in Excel: {', '.join(missing_cols)}"
                    else:
                        db = get_db()
                        cursor = db.cursor()
                        added, skipped = 0, 0
                        for _, row in df.iterrows():
                            try:
                                raw_password = str(row[password_col])
                                hashed_password = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                                cursor.execute(
                                    "INSERT INTO students (roll_no, name, std, school, password) VALUES (%s,%s,%s,%s,%s)",
                                    (row[roll_col], row[name_col], row[std_col], row[school_col], hashed_password)
                                )
                                added += 1
                            except mysql.connector.errors.IntegrityError:
                                skipped += 1
                        db.commit()
                        db.close()
                        message = f"Excel processed! Added: {added}, Skipped (already exist): {skipped}"
                except Exception as e:
                    message = f"Error reading Excel file: {str(e)}"
            else:
                message = "Invalid file type! Only xlsx, xls, csv allowed."

    return f'''
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f9fafb;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        min-height: 100vh;
      }}
      .form-container {{
        background: white;
        width: 460px;
        padding: 30px 40px;
        border-radius: 8px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
        box-sizing: border-box;
      }}
      h2, h3 {{
        margin-top: 0;
        font-weight: 700;
        color: #2c3e50;
      }}
      h2 {{
        text-align: center;
        margin-bottom: 20px;
      }}
      p.message {{
        color: green;
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 20px;
        text-align: center;
      }}
      form {{
        margin-bottom: 30px;
      }}
      label {{
        display: block;
        font-weight: 600;
        color: #34495e;
        margin-bottom: 6px;
        font-size: 15px;
      }}
      input[type="text"], input[type="password"], input[type="file"] {{
        width: 100%;
        padding: 10px 12px;
        margin-bottom: 18px;
        border-radius: 5px;
        border: 1px solid #ccc;
        box-sizing: border-box;
        font-size: 15px;
      }}
      input[type="submit"] {{
        padding: 12px 0;
        width: 100%;
        background-color: #2980b9;
        border: none;
        border-radius: 5px;
        color: white;
        font-weight: 700;
        font-size: 16px;
        cursor: pointer;
        transition: background-color 0.3s ease;
      }}
      input[type="submit"]:hover {{
        background-color: #1f6391;
      }}
      hr {{
        margin: 35px 0;
        border: none;
        border-top: 1px solid #ddd;
      }}
      a {{
        display: inline-block;
        color: #2980b9;
        text-decoration: none;
        font-weight: 600;
        font-size: 15px;
        margin-top: 10px;
      }}
      a:hover {{
        text-decoration: underline;
      }}
    </style>

    <div class="form-container">
      <h2>Add New Student</h2>
      <p class="message">{message}</p>

      <h3>Manual Entry</h3>
      <form method="post">
        <label for="roll_no">Roll No:</label>
        <input name="roll_no" id="roll_no" type="text" required>

        <label for="name">Name:</label>
        <input name="name" id="name" type="text" required>

        <label for="std">Class:</label>
        <input name="std" id="std" type="text" required>

        <label for="school">School:</label>
        <input name="school" id="school" type="text" required>

        <label for="password">Password:</label>
        <input name="password" id="password" type="password" required>

        <input type="submit" value="Add Student">
      </form>

      <hr>

      <h3>Upload Excel / CSV</h3>
      <form method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".xlsx,.xls,.csv" required><br><br>
        <input type="submit" value="Upload">
      </form>

      <p>Excel columns can have flexible names containing: roll, name, class/std, school, password</p>
      <a href="/teacher_dashboard">⬅ Back</a>
    </div>
    '''

# ---------- ADD NEW TEACHER ----------
@app.route("/add_teacher", methods=["GET", "POST"])
def add_teacher():
    if session.get("user_type") != "teacher":
        return redirect(url_for("login"))
    if request.method == "POST":
        teacher_id = request.form["teacher_id"]
        name = request.form["name"]
        password = request.form["password"]
        email = request.form["email"]
        in_charge_class = request.form["in_charge_class"]
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO teachers (teacher_id, name, password, email, in_charge_class) VALUES (%s,%s,%s,%s,%s)",
                (teacher_id, name, hashed_password, email, in_charge_class)
            )
            db.commit()
            db.close()
            return "Teacher added successfully!"
        except mysql.connector.errors.IntegrityError:
            db.close()
            return "Teacher already exists!"

    return '''
    <style>
      body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f9fafb;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        min-height: 100vh;
      }
      .form-container {
        background: white;
        width: 400px;
        padding: 30px 35px;
        border-radius: 8px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
        box-sizing: border-box;
      }
      h2 {
        margin-top: 0;
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 25px;
        text-align: center;
      }
      label {
        display: block;
        font-weight: 600;
        color: #34495e;
        margin-bottom: 6px;
        font-size: 15px;
      }
      input[type="text"], input[type="password"], input[type="email"] {
        width: 100%;
        padding: 10px 12px;
        margin-bottom: 18px;
        border-radius: 5px;
        border: 1px solid #ccc;
        box-sizing: border-box;
        font-size: 15px;
      }
      input[type="submit"] {
        width: 100%;
        padding: 12px 0;
        background-color: #2980b9;
        border: none;
        border-radius: 5px;
        color: white;
        font-weight: 700;
        font-size: 16px;
        cursor: pointer;
        transition: background-color 0.3s ease;
      }
      input[type="submit"]:hover {
        background-color: #1f6391;
      }
    </style>

    <div class="form-container">
      <h2>Add New Teacher</h2>
      <form method="post">
        <label for="teacher_id">Teacher ID:</label>
        <input name="teacher_id" id="teacher_id" type="text" required>

        <label for="name">Name:</label>
        <input name="name" id="name" type="text" required>

        <label for="password">Password:</label>
        <input name="password" id="password" type="password" required>

        <label for="email">Email:</label>
        <input name="email" id="email" type="email" required>

        <label for="in_charge_class">Class In-Charge:</label>
        <input name="in_charge_class" id="in_charge_class" type="text" required>

        <input type="submit" value="Add Teacher">
      </form>
    </div>
    '''

@app.route("/generate_qr/<std>")
def generate_qr(std):
    if session.get("user_type") != "teacher":
        return redirect(url_for("login"))
    secret = "mysecretkey"
    slot_duration = 30  # QR changes every 30 seconds
    current_time = int(time.time())
    current_slot = current_time // slot_duration
    remaining_time = slot_duration - (current_time % slot_duration)  # seconds left
    raw_code = f"{current_slot}:{secret}:{std}"  # QR tied to class
    qr_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    img = qrcode.make(qr_hash)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return f'''
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: #f9fafb;
        margin: 0;
        padding: 20px;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
      }}
      .qr-container {{
        background: white;
        padding: 40px 50px;
        border-radius: 8px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        text-align: center;
        box-sizing: border-box;
        width: 380px;
      }}
      h2 {{
        margin-top: 0;
        color: #2c3e50;
        font-weight: 700;
        margin-bottom: 30px;
      }}
      img {{
        max-width: 100%;
        height: auto;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
      }}
      p {{
        font-size: 18px;
        font-weight: 600;
        color: #2980b9;
        margin-top: 25px;
      }}
      #timer {{
        font-weight: 700;
        font-size: 22px;
        color: #e74c3c;
      }}
      a.button {{
        display: inline-block;
        margin-top: 30px;
        padding: 10px 20px;
        background-color: #2980b9;
        color: white;
        text-decoration: none;
        font-weight: 700;
        border-radius: 6px;
        transition: background-color 0.3s ease;
      }}
      a.button:hover {{
        background-color: #1f6391;
      }}
    </style>

    <div class="qr-container">
      <h2>QR for class {std}</h2>
      <img src="data:image/png;base64,{img_b64}" alt="QR Code for class {std}">
      <p>QR will change in <span id="timer">{remaining_time}</span> seconds</p>
      <a href="/teacher_dashboard" class="button">⬅ Back to Dashboard</a>
    </div>

    <script>
    let timer = {remaining_time};
    let timerElement = document.getElementById("timer");
    setInterval(function() {{
        timer -= 1;
        if(timer <= 0) {{
            location.reload();  // reload page to generate new QR
        }} else {{
            timerElement.textContent = timer;
        }}
    }}, 1000);
    </script>
    '''

if __name__ == "__main__":
    setup_db()
    print("Check completed. If attendance <75%, an email should have been sent.")
    app.run(host="0.0.0.0", port=5000, debug=True)
