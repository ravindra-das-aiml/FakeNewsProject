from flask import Flask, render_template, request, redirect, url_for, session, flash
import pickle
import sqlite3
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import smtplib
import random
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "newsguard_secret_2025"

# -----------------------------
# EMAIL CONFIG
# -----------------------------
EMAIL_ADDRESS  = "agarwalji7272@gmail.com"
EMAIL_PASSWORD = "ganm uifp igiu dyhp"

# -----------------------------
# MODEL LOAD
# -----------------------------
model      = pickle.load(open("model/model.pkl", "rb"))
vectorizer = pickle.load(open("model/vectorizer.pkl", "rb"))

# -----------------------------
# DATABASE INIT
# -----------------------------
def init_db():
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role     TEXT DEFAULT 'user',
            verified INTEGER DEFAULT 0,
            created  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            news      TEXT,
            result    TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_store (
            email   TEXT PRIMARY KEY,
            otp     TEXT NOT NULL,
            expiry  INTEGER NOT NULL
        )
    """)

    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, email, password, role, verified) VALUES (?, ?, ?, ?, ?)",
            ("admin", "admin@newsguard.com", generate_password_hash("admin123"), "admin", 1)
        )

    conn.commit()
    conn.close()

init_db()

# -----------------------------
# DECORATORS
# -----------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated

# -----------------------------
# EMAIL OTP
# -----------------------------
def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "NewsGuard — Your OTP Verification Code"
        msg["From"]    = EMAIL_ADDRESS
        msg["To"]      = to_email

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;background:#0d1117;color:#e6edf3;padding:32px;border-radius:12px;border:1px solid #30363d;">
          <h2 style="color:#58a6ff;margin-bottom:8px;">🔍 NewsGuard</h2>
          <p style="color:#8b949e;margin-bottom:24px;">Email Verification</p>
          <p>Your OTP code is:</p>
          <div style="font-size:36px;font-weight:700;letter-spacing:10px;color:#58a6ff;background:#161b22;padding:20px;border-radius:8px;text-align:center;margin:20px 0;">{otp}</div>
          <p style="color:#8b949e;font-size:13px;">This code expires in <strong>5 minutes</strong>. Do not share it with anyone.</p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def generate_otp():
    return str(random.randint(100000, 999999))

def save_otp(email, otp):
    expiry = int(time.time()) + 300  # 5 minutes
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO otp_store (email, otp, expiry) VALUES (?, ?, ?)",
                   (email, otp, expiry))
    conn.commit()
    conn.close()

def verify_otp(email, otp):
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT otp, expiry FROM otp_store WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, "OTP not found."
    if int(time.time()) > row[1]:
        return False, "OTP expired. Please request a new one."
    if row[0] != otp:
        return False, "Invalid OTP."
    return True, "OK"

# -----------------------------
# HELPER
# -----------------------------
def extract_text_from_url(url):
    try:
        headers  = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        soup     = BeautifulSoup(response.text, "html.parser")
        text     = " ".join(p.get_text() for p in soup.find_all("p"))
        return text.strip()
    except Exception:
        return ""

def get_chart_data(data):
    fake_count = sum(1 for r in data if "Fake" in r[3])
    real_count = len(data) - fake_count
    fake_confs, real_confs = [], []
    for r in data:
        try:
            conf = float(r[3].split("(")[1].replace("%)","").replace("%",""))
            (fake_confs if "Fake" in r[3] else real_confs).append(conf)
        except:
            pass
    avg_fake_conf = round(sum(fake_confs)/len(fake_confs), 1) if fake_confs else 0
    avg_real_conf = round(sum(real_confs)/len(real_confs), 1) if real_confs else 0
    daily = defaultdict(lambda: {"fake": 0, "real": 0})
    for r in data:
        try:
            date = r[4].split(" ")[0] if r[4] else "Unknown"
            if "Fake" in r[3]:
                daily[date]["fake"] += 1
            else:
                daily[date]["real"] += 1
        except:
            pass
    daily_sorted = sorted(daily.items())[-7:]
    return {
        "fake_count":    fake_count,
        "real_count":    real_count,
        "avg_fake_conf": avg_fake_conf,
        "avg_real_conf": avg_real_conf,
        "daily_labels":  [d[0] for d in daily_sorted],
        "daily_fake":    [d[1]["fake"] for d in daily_sorted],
        "daily_real":    [d[1]["real"] for d in daily_sorted],
    }

# -----------------------------
# REGISTER — Step 1
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        conn   = sqlite3.connect("history.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email))
        if cursor.fetchone():
            conn.close()
            flash("Username or email already exists.", "error")
            return render_template("register.html")
        conn.close()

        # Save temp data in session
        session["reg_username"] = username
        session["reg_email"]    = email
        session["reg_password"] = generate_password_hash(password)

        # Send OTP
        otp = generate_otp()
        save_otp(email, otp)
        if send_otp_email(email, otp):
            flash(f"OTP sent to {email}. Check your inbox!", "success")
            return redirect(url_for("verify_otp_page"))
        else:
            flash("Failed to send OTP. Please try again.", "error")
            return render_template("register.html")

    return render_template("register.html")

# -----------------------------
# VERIFY OTP — Step 2
# -----------------------------
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp_page():
    if "reg_email" not in session:
        return redirect(url_for("register"))

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        email       = session.get("reg_email")

        valid, msg = verify_otp(email, entered_otp)
        if valid:
            conn   = sqlite3.connect("history.db")
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, email, password, verified) VALUES (?, ?, ?, ?)",
                    (session["reg_username"], email, session["reg_password"], 1)
                )
                conn.commit()
                conn.close()
                session.pop("reg_username", None)
                session.pop("reg_email", None)
                session.pop("reg_password", None)
                flash("Account verified! Please login. ✅", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                conn.close()
                flash("Account already exists.", "error")
        else:
            flash(msg, "error")

    return render_template("verify_otp.html", email=session.get("reg_email"))

# -----------------------------
# RESEND OTP
# -----------------------------
@app.route("/resend-otp")
def resend_otp():
    email = session.get("reg_email")
    if not email:
        return redirect(url_for("register"))
    otp = generate_otp()
    save_otp(email, otp)
    if send_otp_email(email, otp):
        flash("New OTP sent! Check your inbox.", "success")
    else:
        flash("Failed to send OTP.", "error")
    return redirect(url_for("verify_otp_page"))

# -----------------------------
# LOGIN
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn   = sqlite3.connect("history.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            if not user[5]:  # verified column
                flash("Please verify your email first.", "warning")
                return render_template("login.html")
            session["user_id"]  = user[0]
            session["username"] = user[1]
            session["role"]     = user[4]
            flash(f"Welcome back, {user[1]}! 👋", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")

# -----------------------------
# LOGOUT
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# -----------------------------
# HOME
# -----------------------------
@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    result     = None
    news_input = ""
    is_fake    = None
    confidence = None

    if request.method == "POST":
        user_input = request.form.get("news", "").strip()
        news_input = user_input

        if user_input.startswith("http"):
            news_text = extract_text_from_url(user_input)
        else:
            news_text = user_input

        if not news_text:
            result = "error"
        else:
            transformed = vectorizer.transform([news_text])
            prediction  = model.predict(transformed)
            probability = model.predict_proba(transformed)
            confidence  = round(max(probability[0]) * 100, 2)
            is_fake     = (prediction[0] == 0)
            result      = f"{'Fake' if is_fake else 'Real'} News ({confidence}%)"

            conn   = sqlite3.connect("history.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO history (user_id, news, result) VALUES (?, ?, ?)",
                (session["user_id"], user_input, result)
            )
            conn.commit()
            conn.close()

    return render_template("index.html",
                           result=result, is_fake=is_fake,
                           confidence=confidence, news_input=news_input)

# -----------------------------
# USER HISTORY
# -----------------------------
@app.route("/history")
@login_required
def history():
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history WHERE user_id = ? ORDER BY id DESC", (session["user_id"],))
    data = cursor.fetchall()
    conn.close()
    charts = get_chart_data(data)
    return render_template("history.html", data=data, **charts)

# -----------------------------
# CLEAR HISTORY
# -----------------------------
@app.route("/clear", methods=["POST"])
@login_required
def clear_history():
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE user_id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    return render_template("history.html", data=[], cleared=True,
                           fake_count=0, real_count=0,
                           avg_fake_conf=0, avg_real_conf=0,
                           daily_labels=[], daily_fake=[], daily_real=[])

# -----------------------------
# ADMIN
# -----------------------------
@app.route("/admin")
@admin_required
def admin():
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role, created FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM history")
    total_checks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM history WHERE result LIKE 'Fake%'")
    total_fake = cursor.fetchone()[0]
    conn.close()
    return render_template("admin.html", users=users,
                           total_checks=total_checks, total_fake=total_fake)

@app.route("/admin/history")
@admin_required
def admin_history():
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.id, u.username, h.news, h.result, h.timestamp
        FROM history h JOIN users u ON h.user_id = u.id
        ORDER BY h.id DESC
    """)
    data = cursor.fetchall()
    conn.close()
    return render_template("admin_history.html", data=data)

@app.route("/admin/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete yourself!", "error")
        return redirect(url_for("admin"))
    conn   = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin"))

# -----------------------------
# RUN — 0.0.0.0 for phone access
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
