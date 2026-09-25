import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify,abort
import random
from datetime import datetime
import datetime
from dateutil.relativedelta import relativedelta
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import re
from werkzeug.security import generate_password_hash, check_password_hash



app = Flask(__name__)
app.secret_key = 'ncp_secret_key'

# MySQL Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ncp_portal'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                role_name VARCHAR(50) UNIQUE NOT NULL
            )
        ''')
        cursor.execute("INSERT IGNORE INTO roles (role_name) VALUES ('Super Admin'), ('User')")

        # 3. Departments Table 
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT NOT NULL
            )
        ''')

        # 1. App Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                gmail VARCHAR(255) UNIQUE NOT NULL,
                designation VARCHAR(255),
                password VARCHAR(255) NOT NULL,
                role_id INT DEFAULT 2,
                department_id INT,
                reset_token VARCHAR(255),
                token_expiry DATETIME,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE SET NULL,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
            )
        ''')
        
        # 4. Team Members Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNIQUE,
                name VARCHAR(255) NOT NULL,
                designation VARCHAR(255) NOT NULL,
                department_id INT,
                FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
            )
        ''')
        
        # 2. Projects Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                progress INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'Active',
                created_by INT,
                start_date DATE,
                end_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            project_id INT,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            assigned_to INT,
            created_by INT,
            start_date DATE,
            end_date DATE,
            status VARCHAR(50) DEFAULT 'Active',
            progress INT DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES team_members(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
);''')
        
        # 5. Project Assignments Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_assignments (
                project_id INT,
                employee_id INT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (employee_id) REFERENCES team_members(id) ON DELETE CASCADE
            )
        ''')

        # Default Admin Insert 
        cursor.execute('''
            INSERT INTO app_users (name, gmail, designation, password, role_id) 
            SELECT 'Admin', 'admin@ncp.com', 'System Administrator', 'admin123', 1
            WHERE NOT EXISTS (SELECT * FROM app_users WHERE role_id = 1)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                message TEXT NOT NULL,
                is_read TINYINT(1) DEFAULT 0, -- 0 matlab unseen, 1 matlab seen
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES app_users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database & Tables Initialized Successfully!")
        
    except Exception as e:
        print("Database Error:", e)

# 1. Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        identifier = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.*, r.role_name 
            FROM app_users u 
            LEFT JOIN roles r ON u.role_id = r.id 
            WHERE u.gmail = %s
        """, (identifier,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['user'] = user['gmail']
            session['email'] = user['gmail']
            session['name'] = user['name']
            session['designation'] = user.get('designation', 'N/A')
            session['role'] = user.get('role_name', 'User')
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid Gmail or Password!'
            
    return render_template('login.html', error=error)

# --- Gmail SMTP Configuration ---


def send_otp_email(user_email, otp):
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = "NCP Portal - Registration Verification"
        msg['From'] = f"NCP Portal <{SENDER_GMAIL}>"
        msg['To'] = user_email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: auto; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #6366f1; text-align: center;">NCP Portal Verification</h2>
            <p>Hello,</p>
            <p>Thank you for registering with NCP Portal. Please use the following OTP to complete your registration:</p>
            <div style="background: #f8fafc; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1e293b; border-radius: 8px; margin: 20px 0; border: 1px dashed #cbd5e1;">
                {otp}
            </div>
            <p style="color: #64748b; font-size: 14px;">This code is valid for 10 minutes. If you did not request this, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="font-size: 12px; color: #94a3b8; text-align: center;">Best Regards,<br><strong>NCP Portal Team</strong></p>
        </div>
        """
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_GMAIL, APP_PASSWORD)
        server.sendmail(SENDER_GMAIL, user_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"*** GMAIL SMTP EXCEPTION: {e} ***")
        return False

def send_welcome_email(user_email, user_name):
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = "Welcome to NCP Portal!"
        msg['From'] = f"NCP Portal <{SENDER_GMAIL}>"
        msg['To'] = user_email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: auto; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #6366f1; text-align: center;">Welcome, {user_name}!</h2>
            <p>Congratulations! Your account at NCP Portal has been successfully created and you are now ready to log in.</p>
            <p>We are glad to have you on board. If you have any questions, feel free to contact our support team.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://127.0.0.1:5000/login" style="background-color: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Login to Portal</a>
            </div>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="font-size: 12px; color: #94a3b8; text-align: center;">Best Regards,<br><strong>NCP Portal Team</strong></p>
        </div>
        """
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_GMAIL, APP_PASSWORD)
        server.sendmail(SENDER_GMAIL, user_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Welcome Email Exception: {e}")
        return False

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        session.pop('pending_user_data', None)
        session.pop('pending_otp', None)
        session.pop('otp_timestamp', None)

    error = None
    
    # Fetch departments safely
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM departments')
    departments = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        gmail = (request.form.get('gmail') or '').strip()
        designation = (request.form.get('designation') or '').strip()
        department_id = request.form.get('department_id')
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        if not name or not gmail or not password:
            error = 'All fields are required!'
            return render_template('register.html', error=error, departments=departments)

        if password != confirm_password:
            error = 'Passwords do not match!'
            return render_template('register.html', error=error, departments=departments)

        # 🔒 Strong Password Validation Checks
        if len(password) < 8:
            error = 'Password must be at least 8 characters long!'
            return render_template('register.html', error=error, departments=departments)
        
        if not re.search(r'[A-Za-z]', password):
            error = 'Password must contain at least one alphabet letter!'
            return render_template('register.html', error=error, departments=departments)
            
        if not re.search(r'\d', password):
            error = 'Password must contain at least one number!'
            return render_template('register.html', error=error, departments=departments)
            
        if not re.search(r'[@$!%*?&._#]', password):
            error = 'Password must contain at least one special character (e.g., @$!%*?&)'
            return render_template('register.html', error=error, departments=departments)

        if not department_id:
            error = 'Please select a department!'
            return render_template('register.html', error=error, departments=departments)

        # Check if Gmail already exists
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM app_users WHERE gmail = %s', (gmail,))
        existing_user = cursor.fetchone()
        cursor.close()
        conn.close()

        if existing_user:
            error = 'This Gmail is already registered!'
            return render_template('register.html', error=error, departments=departments)

        # Hash password before storing in session
        hashed_password = generate_password_hash(password)

        otp = random.randint(100000, 999999)
        session['pending_otp'] = otp
        session['otp_timestamp'] = time.time()
        session['pending_user_data'] = {
            'name': name,
            'gmail': gmail,
            'designation': designation,
            'password': hashed_password,
            'department_id': department_id
        }

        print(f"*** DEBUG OTP FOR {gmail}: {otp} ***")

        if send_otp_email(gmail, otp):
            flash(f'OTP has been sent to your Gmail ({gmail}). Please check your inbox.', 'info')
        else:
            flash('Email sending failed. (Check terminal for debug OTP).', 'warning')

        return redirect(url_for('verify_otp_page'))

    return render_template('register.html', error=error, departments=departments)

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp_page():
    if 'pending_user_data' not in session:
        return redirect(url_for('register'))

    error = None
    if request.method == 'POST':
        user_entered_otp = request.form.get('otp')
        session_otp = session.get('pending_otp')
        otp_timestamp = session.get('otp_timestamp', 0)

        if time.time() - otp_timestamp > 600:
            error = 'OTP has expired! Please request a new OTP.'
        elif session_otp and int(user_entered_otp) == int(session_otp):
            reg_data = session.get('pending_user_data')
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'INSERT INTO app_users (name, gmail, designation, password, role_id, department_id) VALUES (%s, %s, %s, %s, 2, %s)',
                    (reg_data['name'], reg_data['gmail'], reg_data['designation'], reg_data['password'], reg_data['department_id'])
                )
                conn.commit()
                
                send_welcome_email(reg_data['gmail'], reg_data['name'])

                session.clear()
                flash('Registration successful! A welcome email has been sent to you.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                error = f"Database Error: {e}"
            finally:
                cursor.close()
                conn.close()
        else:
            error = 'Invalid OTP! Please try again.'

    return render_template('verify_otp.html', error=error)

@app.route('/resend_otp')
def resend_otp():
    if 'pending_user_data' not in session:
        return redirect(url_for('register'))

    last_sent = session.get('otp_timestamp', 0)
    if time.time() - last_sent < 60:
        flash('Please wait at least 1 minute before requesting a new OTP!', 'warning')
        return redirect(url_for('verify_otp_page'))

    new_otp = random.randint(100000, 999999)
    session['pending_otp'] = new_otp
    session['otp_timestamp'] = time.time()

    print(f"*** RESENT DEBUG OTP: {new_otp} ***")
    send_otp_email(session['pending_user_data']['gmail'], new_otp)
    flash('A new OTP has been resent to your Gmail.', 'info')
    return redirect(url_for('verify_otp_page'))

# --- Password Strength Validation Helper ---
def is_strong_password(password):
    # Minimum 8 characters, at least one letter (upper or lower), one number, and one special character
    if len(password) < 8:
        return False
    if not re.search(r"[a-zA-Z]", password):  # Letter (upper or lower)
        return False
    if not re.search(r"[0-9]", password):     # Number
        return False
    if not re.search(r"[@$!%*?&]", password): # Special character
        return False
    return True

# --- Forgot Password Route ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    if request.method == 'POST':
        gmail = request.form.get('gmail').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id, name FROM app_users WHERE gmail = %s', (gmail,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            error = 'This Gmail is not registered with any account!'
            return render_template('forgot_password.html', error=error)
        
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(minutes=15)
        
        cursor.execute(
            'UPDATE app_users SET reset_token = %s, token_expiry = %s WHERE gmail = %s',
            (token, expiry, gmail)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        reset_link = url_for('reset_password_with_token', token=token, _external=True)
        print(f"*** DEBUG RESET LINK FOR {gmail}: {reset_link} ***")
        
        if send_reset_link_email(gmail, reset_link):
            flash(f'Password reset link has been sent to your Gmail ({gmail}). Please check your inbox.', 'info')
        else:
            flash('Email sending failed. (Check terminal for debug link).', 'warning')
            
        return redirect(url_for('login'))
        
    return render_template('forgot_password.html', error=error)

# --- Email Sending Function ---
def send_reset_link_email(user_email, reset_link):
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = "NCP Portal - Password Reset Request"
        msg['From'] = f"NCP Portal <{SENDER_GMAIL}>"
        msg['To'] = user_email

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: auto; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #6366f1; text-align: center;">Password Reset</h2>
            <p>Hello,</p>
            <p>We received a request to reset your password for your NCP Portal account. Click the button below to set a new password:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" style="background-color: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #64748b; font-size: 14px;">This link is valid for 15 minutes. If you did not request a password reset, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="font-size: 12px; color: #94a3b8; text-align: center;">Best Regards,<br><strong>NCP Portal Team</strong></p>
        </div>
        """
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_GMAIL, APP_PASSWORD)
        server.sendmail(SENDER_GMAIL, user_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"*** GMAIL SMTP EXCEPTION: {e} ***")
        return False

# --- Reset Password with Token Route ---
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_with_token(token):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute(
        'SELECT * FROM app_users WHERE reset_token = %s AND token_expiry > %s',
        (token, datetime.now())
    )
    user = cursor.fetchone()
    
    if not user:
        cursor.close()
        conn.close()
        return "<h1>Invalid or Expired Link</h1><p>This password reset link is invalid or has expired (valid for 15 minutes). Please request a new one.</p>"
        
    error = None
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            error = 'Passwords do not match!'
        elif not is_strong_password(new_password):
            error = 'Password must be at least 8 characters long and include at least one letter, one number, and one special character.'
        else:
            cursor.execute(
                'UPDATE app_users SET password = %s, reset_token = NULL, token_expiry = NULL WHERE id = %s',
                (new_password, user['id'])
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Password updated successfully! You can now log in with your new password.', 'success')
            return redirect(url_for('login'))
            
    cursor.close()
    conn.close()
    return render_template('reset_password.html', error=error)

# 3. Logout Route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user', None)
    session.pop('role', None)
    session.clear()
    
    return redirect(url_for('login'))

# 15. Messages Hub Route (Inbox & Chat Window)
# 15. Messages Hub Route (Inbox & Chat Window)
@app.route('/messages', methods=['GET'])
def messages_hub():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    current_user_id = session.get('user_id')
    
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (current_user_id,))
    user = cursor.fetchone()
    
    # Baqi saare users ki list fetch karein
    cursor.execute("SELECT id, name, gmail, designation FROM app_users WHERE id != %s", (current_user_id,))
    all_users = cursor.fetchall()
    
    # Har user ke liye unread/unseen message count check karein
    for u in all_users:
        cursor.execute("""
            SELECT COUNT(*) as unread_cnt FROM messages 
            WHERE sender_id = %s AND receiver_id = %s AND is_read = 0 AND is_deleted_everyone = 0 AND deleted_by_receiver = 0
        """, (u['id'], current_user_id))
        res = cursor.fetchone()
        u['unread_count'] = res['unread_cnt'] if res else 0
        u['has_unseen'] = True if u['unread_count'] > 0 else False

    receiver_id = request.args.get('receiver_id')
    active_receiver = None
    chat_messages = []
    
    if receiver_id:
        cursor.execute("SELECT id, name, gmail, designation FROM app_users WHERE id = %s", (receiver_id,))
        active_receiver = cursor.fetchone()
        
        if active_receiver:
            # Jaise hi chat khulegi, doosre bande ke bheje hue unread messages ko 'seen' (1) kar denge
            cursor.execute("""
                UPDATE messages 
                SET is_read = 1 
                WHERE sender_id = %s AND receiver_id = %s AND is_read = 0
            """, (receiver_id, current_user_id))
            conn.commit()

            # Yahan JOIN lagaya hai taake har message ke sath sender ka naam (sender_name) bhi aaye
            cursor.execute("""
                SELECT m.*, u.name as sender_name 
                FROM messages m
                JOIN app_users u ON m.sender_id = u.id
                WHERE ((m.sender_id = %s AND m.receiver_id = %s AND m.deleted_by_sender = 0) 
                   OR (m.sender_id = %s AND m.receiver_id = %s AND m.deleted_by_receiver = 0))
                  AND m.is_deleted_everyone = 0
                ORDER BY m.timestamp ASC
            """, (current_user_id, receiver_id, receiver_id, current_user_id))
            chat_messages = cursor.fetchall()
            
    cursor.close()
    conn.close()
    
    return render_template('messages.html', 
                           user=user, 
                           all_users=all_users, 
                           active_receiver=active_receiver, 
                           chat_messages=chat_messages)

@app.context_processor
def inject_messages_data():
    if 'user' not in session:
        return {'unread_messages_count': 0, 'recent_messages_list': []}
        
    current_user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Total Unread Count
    cursor.execute("""
        SELECT COUNT(*) as total_unread FROM messages 
        WHERE receiver_id = %s AND is_read = 0 AND is_deleted_everyone = 0 AND deleted_by_receiver = 0
    """, (current_user_id,))
    unread_res = cursor.fetchone()
    unread_count = unread_res['total_unread'] if unread_res else 0

    # 2. Recent Messages List for Dropdown
    cursor.execute("""
        SELECT m.id, m.sender_id, m.message, m.timestamp as time, m.is_read, u.name as sender_name
        FROM messages m
        JOIN app_users u ON m.sender_id = u.id
        WHERE m.receiver_id = %s AND m.deleted_by_receiver = 0 AND m.is_deleted_everyone = 0
        ORDER BY m.timestamp DESC
    """, (current_user_id,))
    recent_raw = cursor.fetchall()
    
    # Unique senders filter karna
    seen = set()
    recent_list = []
    for msg in recent_raw:
        if msg['sender_id'] not in seen:
            seen.add(msg['sender_id'])
            recent_list.append(msg)
            
    cursor.close()
    conn.close()
    
    return {
        'unread_messages_count': unread_count,
        'recent_messages_list': recent_list
    }

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx', 'txt', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    sender_id = session.get('user_id')
    receiver_id = request.form.get('receiver_id')
    message_text = request.form.get('message', '')
    
    file_path = None
    
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Database se sender ka naam nikal lein taake file name mein add kiya ja sake
            conn_temp = get_db_connection()
            cursor_temp = conn_temp.cursor(dictionary=True)
            cursor_temp.execute("SELECT name FROM app_users WHERE id = %s", (sender_id,))
            sender_user = cursor_temp.fetchone()
            cursor_temp.close()
            conn_temp.close()
            
            # Sender ka naam clean kar lein (spaces remove karne ke liye)
            sender_name_clean = secure_filename(sender_user['name']) if sender_user else "user"
            
            # Unique filename jisme sirf sender ki ID aur Naam ho (Baghair timestamp ke)
            unique_filename = f"id_{sender_id}_{sender_name_clean}_{filename}"
            
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            save_location = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(save_location)
            
            file_path = f"uploads/{unique_filename}"

    if receiver_id and (message_text.strip() or file_path):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, message, attachment, is_read, is_edited, is_deleted_everyone, deleted_by_sender, deleted_by_receiver, timestamp) 
                VALUES (%s, %s, %s, %s, 0, 0, 0, 0, 0, NOW())
            """, (sender_id, receiver_id, message_text, file_path))
            conn.commit()
        except Exception as e:
            print("Error sending message with attachment:", e)
        finally:
            cursor.close()
            conn.close()
             
    return redirect(url_for('messages_hub', receiver_id=receiver_id))


# 17. Mark Chat Messages as Read Route (AJAX ke liye)
@app.route('/mark_messages_read', methods=['POST'])
def mark_messages_read():
    if 'user' not in session:
        return jsonify({'status': 'unauthorized'}), 401
        
    current_user_id = session.get('user_id')
    data = request.get_json() or {}
    sender_id = data.get('sender_id')
    
    if sender_id and current_user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE messages 
                SET is_read = 1 
                WHERE sender_id = %s AND receiver_id = %s AND is_read = 0
            """, (sender_id, current_user_id))
            conn.commit()
        except Exception as e:
            print("Error marking messages read:", e)
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({'status': 'success'})


# 18. Edit Message Route
@app.route('/edit_message/<int:message_id>', methods=['POST'])
def edit_message(message_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session.get('user_id')
    updated_message = request.form.get('updated_message')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    receiver_id = None
    try:
        # Note: Agar aapke database mein time wale column ka naam 'created_at' hai, 
        # toh 'timestamp' ki jagah 'created_at' likh lijiyega.
        cursor.execute("SELECT sender_id, receiver_id, timestamp FROM messages WHERE id = %s", (message_id,))
        msg = cursor.fetchone()
        
        if msg and msg['sender_id'] == current_user_id:
            receiver_id = msg['receiver_id']
            
            # 30 Minutes Time Check for Editing
            if msg['timestamp']:
                if datetime.now() - msg['timestamp'] > timedelta(minutes=30):
                    print("Edit limit exceeded (more than 30 minutes).")
                    cursor.close()
                    conn.close()
                    if receiver_id:
                        return redirect(url_for('messages_hub', receiver_id=receiver_id))
                    return redirect(url_for('messages_hub'))

            cursor.execute("""
                UPDATE messages 
                SET message = %s, is_edited = 1 
                WHERE id = %s
            """, (updated_message, message_id))
            conn.commit()
    except Exception as e:
        print("Error editing message:", e)
    finally:
        cursor.close()
        conn.close()
        
    if receiver_id:
        return redirect(url_for('messages_hub', receiver_id=receiver_id))
    return redirect(url_for('messages_hub'))


# 19. Delete Message Route (Delete for Me & Delete for Everyone)
@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session.get('user_id')
    delete_type = request.form.get('delete_type') # 'me' ya 'everyone'
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    receiver_id = None
    try:
        cursor.execute("SELECT sender_id, receiver_id, timestamp FROM messages WHERE id = %s", (message_id,))
        msg = cursor.fetchone()
        
        if msg:
            receiver_id = msg['receiver_id'] if msg['sender_id'] == current_user_id else msg['sender_id']
            
            if delete_type == 'everyone' and msg['sender_id'] == current_user_id:
                # 30 Minutes Time Check sirf 'Delete for Everyone' ke liye
                if msg['timestamp']:
                    if datetime.now() - msg['timestamp'] > timedelta(minutes=30):
                        print("Delete for everyone limit exceeded (more than 30 minutes).")
                        cursor.close()
                        conn.close()
                        if receiver_id:
                            return redirect(url_for('messages_hub', receiver_id=receiver_id))
                        return redirect(url_for('messages_hub'))

                cursor.execute("UPDATE messages SET is_deleted_everyone = 1 WHERE id = %s", (message_id,))
                conn.commit()
                
            elif delete_type == 'me':
                # Delete for me par koi time restriction nahi hai
                if msg['sender_id'] == current_user_id:
                    cursor.execute("UPDATE messages SET deleted_by_sender = 1 WHERE id = %s", (message_id,))
                else:
                    cursor.execute("UPDATE messages SET deleted_by_receiver = 1 WHERE id = %s", (message_id,))
                conn.commit()
    except Exception as e:
        print("Error deleting message:", e)
    finally:
        cursor.close()
        conn.close()
        
    if receiver_id:
        return redirect(url_for('messages_hub', receiver_id=receiver_id))
    return redirect(url_for('messages_hub'))
@app.route('/clear_chat/<int:receiver_id>', methods=['POST'])
def clear_chat(receiver_id):
    if 'user' not in session:
        return {'status': 'unauthorized'}, 401
        
    current_user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Agar current user sender hai, toh deleted_by_sender = 1 karein
        cursor.execute("""
            UPDATE messages 
            SET deleted_by_sender = 1 
            WHERE sender_id = %s AND receiver_id = %s
        """, (current_user_id, receiver_id))
        
        # Agar current user receiver hai, toh deleted_by_receiver = 1 karein
        cursor.execute("""
            UPDATE messages 
            SET deleted_by_receiver = 1 
            WHERE sender_id = %s AND receiver_id = %s
        """, (receiver_id, current_user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {'status': 'success'}
    except Exception as e:
        print(f"Error clearing chat: {e}")
        cursor.close()
        conn.close()
        return {'status': 'error'}, 500
        
# 4. Dashboard Route
# 4. Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    # Fetch current user data for navbar
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    current_date = datetime.today()
    current_year = current_date.year
    
    # 12 Months rolling window bounds
    start_bound = current_date - relativedelta(years=1)
    start_bound_str = start_bound.strftime('%Y-%m-%d')
    end_bound_str = current_date.strftime('%Y-%m-%d')
    
    if user_role == 'Super Admin':
        cursor.execute("""
            SELECT p.id, p.name, p.progress, p.status, p.start_date, p.end_date, COUNT(pa.employee_id) AS team_count 
            FROM projects p 
            LEFT JOIN project_assignments pa ON p.id = pa.project_id 
            GROUP BY p.id, p.name, p.progress, p.status, p.start_date, p.end_date
        """)
    else:
        cursor.execute("""
            SELECT p.id, p.name, p.progress, p.status, p.start_date, p.end_date, COUNT(pa.employee_id) AS team_count 
            FROM projects p 
            LEFT JOIN project_assignments pa ON p.id = pa.project_id 
            LEFT JOIN team_members t ON pa.employee_id = t.id
            JOIN app_users u ON u.id = %s AND TRIM(LOWER(t.name)) = TRIM(LOWER(u.name)) AND TRIM(LOWER(t.designation)) = TRIM(LOWER(u.designation))
            WHERE (p.created_by = %s OR t.id IS NOT NULL)
            GROUP BY p.id, p.name, p.progress, p.status, p.start_date, p.end_date
        """, (user_id, user_id))
        
    raw_projects_data = cursor.fetchall()

    all_projects_data = []
    start_date_obj = datetime.strptime(start_bound_str, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_bound_str, '%Y-%m-%d').date()

    for p in raw_projects_data:
        # DB me agar 'Active' hai toh display/logic ke liye 'Initiated' karlo
        if p.get('status') == 'Active':
            p['status'] = 'Initiated'
            
        is_visible = False
        p_start = p.get('start_date')
        p_end = p.get('end_date')
        
        if p_start:
            if isinstance(p_start, datetime):
                p_start = p_start.date()
            elif isinstance(p_start, str):
                try:
                    p_start = datetime.strptime(p_start.split()[0], '%Y-%m-%d').date()
                except Exception:
                    p_start = None
                    
        if p_end:
            if isinstance(p_end, datetime):
                p_end = p_end.date()
            elif isinstance(p_end, str):
                try:
                    p_end = datetime.strptime(p_end.split()[0], '%Y-%m-%d').date()
                except Exception:
                    p_end = None

        if p_start:
            effective_end = p_end if p_end else datetime.max.date()
            if p_start <= end_date_obj and effective_end >= start_date_obj:
                is_visible = True
        else:
            is_visible = True
        
        if is_visible:
            all_projects_data.append(p)

    total_projects = len(all_projects_data)
    initiated_count = sum(1 for p in all_projects_data if p.get('status') == 'Initiated')
    in_progress_count = sum(1 for p in all_projects_data if p.get('status') == 'In Progress')
    completed_projects_count = sum(1 for p in all_projects_data if p.get('status') == 'Completed')

    rolling_months = [current_date - relativedelta(months=i) for i in range(11, -1, -1)]
    month_data_map = {m_date.strftime('%Y-%m'): 0 for m_date in rolling_months}

    try:
        if user_role == 'Super Admin':
            cursor.execute("SELECT start_date, end_date FROM projects")
        else:
            cursor.execute("""
                SELECT p.start_date, p.end_date 
                FROM projects p 
                LEFT JOIN project_assignments pa ON p.id = pa.project_id
                LEFT JOIN team_members t ON pa.employee_id = t.id
                JOIN app_users u ON u.id = %s AND TRIM(LOWER(t.name)) = TRIM(LOWER(u.name)) AND TRIM(LOWER(t.designation)) = TRIM(LOWER(u.designation))
                WHERE (p.created_by = %s OR t.id IS NOT NULL)
            """, (user_id, user_id))
            
        for row in cursor.fetchall():
            p_start = row.get('start_date')
            p_end = row.get('end_date')
            
            if p_start:
                if isinstance(p_start, datetime):
                    p_start_date = p_start.date()
                elif isinstance(p_start, str):
                    try:
                        p_start_date = datetime.strptime(p_start.split()[0], '%Y-%m-%d').date()
                    except:
                        continue
                else:
                    continue
            else:
                continue
                
            if p_end:
                if isinstance(p_end, datetime):
                    p_end_date = p_end.date()
                elif isinstance(p_end, str):
                    try:
                        p_end_date = datetime.strptime(p_end.split()[0], '%Y-%m-%d').date()
                    except:
                        p_end_date = datetime.max.date()
                else:
                    p_end_date = datetime.max.date()
            else:
                p_end_date = datetime.max.date()

            for m_date in rolling_months:
                m_start = m_date.replace(day=1).date()
                m_next = (m_start + relativedelta(months=1))
                
                if p_start_date < m_next and p_end_date >= m_start:
                    ym_key = m_date.strftime('%Y-%m')
                    if ym_key in month_data_map:
                        month_data_map[ym_key] += 1
    except Exception:
        pass

    last_year_counts = [month_data_map[m_date.strftime('%Y-%m')] for m_date in rolling_months]
    last_year_months = [m_date.strftime('%b %Y') for m_date in rolling_months]

    years_range = []
    year_counts = []
    if user_role == 'Super Admin':
        try:
            start_year = current_year - 6
            years_range = [str(y) for y in range(start_year, current_year + 1)]
            year_data_map = {str(y): 0 for y in range(start_year, current_year + 1)}
            
            cursor.execute("SELECT start_date, end_date FROM projects")
            for row in cursor.fetchall():
                p_start = row.get('start_date')
                p_end = row.get('end_date')
                
                def extract_year(val):
                    if not val:
                        return None
                    if isinstance(val, datetime):
                        return val.year
                    if hasattr(val, 'year'):
                        return val.year
                    if isinstance(val, str):
                        try:
                            clean_str = val.strip().split()[0]
                            return int(clean_str[:4])
                        except:
                            pass
                    return None

                p_start_year = extract_year(p_start)
                p_end_year = extract_year(p_end)

                if p_start_year is None and p_end_year is None:
                    continue
                
                effective_start_y = p_start_year if p_start_year is not None else p_end_year
                effective_end_y = p_end_year if p_end_year is not None else p_start_year

                for y_str in years_range:
                    y_int = int(y_str)
                    if effective_start_y <= y_int <= effective_end_y:
                        if y_str in year_data_map:
                            year_data_map[y_str] += 1
                            
            year_counts = [year_data_map[y] for y in years_range]
        except Exception as e:
            years_range = []
            year_counts = []

    # Workload query
    cursor.execute('''
        SELECT t.name AS member_name, p.status, p.name AS project_name 
        FROM team_members t 
        LEFT JOIN project_assignments pa ON t.id = pa.employee_id 
        LEFT JOIN projects p ON pa.project_id = p.id
    ''')
    raw_workload = cursor.fetchall()

    cursor.execute('SELECT id, name FROM team_members')
    all_team_rows = cursor.fetchall()
    members_set = sorted(list(set([row['name'] for row in all_team_rows])))

    initiated_counts = {m: 0 for m in members_set}
    in_progress_counts = {m: 0 for m in members_set}
    initiated_projects_dict = {m: [] for m in members_set}
    in_progress_projects_dict = {m: [] for m in members_set}

    for row in raw_workload:
        m = row['member_name']
        status = row['status']
        if status == 'Active':
            status = 'Initiated'
        proj_name = row['project_name']

        if m in members_set:
            if status == 'Initiated':
                initiated_counts[m] += 1
                if proj_name and proj_name not in initiated_projects_dict[m]:
                    initiated_projects_dict[m].append(proj_name)
            elif status == 'In Progress':
                in_progress_counts[m] += 1
                if proj_name and proj_name not in in_progress_projects_dict[m]:
                    in_progress_projects_dict[m].append(proj_name)

    workload_members = members_set
    workload_initiated = [initiated_counts[m] for m in members_set]
    workload_in_progress = [in_progress_counts[m] for m in members_set]
    workload_initiated_projects = [initiated_projects_dict[m] for m in members_set]
    workload_in_progress_projects = [in_progress_projects_dict[m] for m in members_set]
    
    cursor.execute('SELECT COUNT(*) as cnt FROM team_members')
    total_members_count = cursor.fetchone()['cnt']
    total_users_count = total_members_count

    # --- Corrected Active/Engaged & Available Count Logic ---
    # Sirf unhi members ko count karein jo 'Active', 'Initiated' ya 'In Progress' projects par hain (Completed wale excluded taake available mein jayein)
    cursor.execute("""
    SELECT COUNT(DISTINCT pa.employee_id) as cnt 
    FROM project_assignments pa
    JOIN projects p ON pa.project_id = p.id
    WHERE p.status IN ('Active', 'Initiated', 'In Progress')
    """)
    engaged_count = cursor.fetchone()['cnt']
    free_count = max(0, total_users_count - engaged_count)

   # --- Tasks Fetching for Projects & Chart ---
    project_tasks = []
    project_initiated_task_counts = []
    project_inprogress_task_counts = []
    project_completed_task_counts = []
    
    project_initiated_task_names = []
    project_inprogress_task_names = []
    project_completed_task_names = []

    for proj in all_projects_data:
        p_id = proj['id']
        cursor.execute("""
            SELECT title, status 
            FROM tasks 
            WHERE project_id = %s
            ORDER BY id DESC
        """, (p_id,))
        tasks_for_proj = cursor.fetchall()
        project_tasks.append(tasks_for_proj)

        for t in tasks_for_proj:
            if t.get('status') == 'Active':
                t['status'] = 'Initiated'

        init_names = [t['title'] for t in tasks_for_proj if t.get('status') == 'Initiated']
        inp_names = [t['title'] for t in tasks_for_proj if t.get('status') == 'In Progress']
        cmp_names = [t['title'] for t in tasks_for_proj if t.get('status') == 'Completed']

        project_initiated_task_names.append(init_names)
        project_inprogress_task_names.append(inp_names)
        project_completed_task_names.append(cmp_names)

        project_initiated_task_counts.append(len(init_names))
        project_inprogress_task_counts.append(len(inp_names))
        project_completed_task_counts.append(len(cmp_names))

    cursor.close()
    conn.close()
    
    if total_projects > 0:
        initiated_pct = round((initiated_count / total_projects) * 100, 1)
        in_progress_pct = round((in_progress_count / total_projects) * 100, 1)
        completed_pct = round((completed_projects_count / total_projects) * 100, 1)
    else:
        initiated_pct = in_progress_pct = completed_pct = 0

    project_names = [p['name'] for p in all_projects_data]
    project_progress = [p['progress'] for p in all_projects_data]
    project_statuses = [p['status'] for p in all_projects_data]
    team_counts = [p['team_count'] for p in all_projects_data]
    
    task_chart_labels = project_names
    task_chart_values = [
        (init_c + i + c) for init_c, i, c in zip(project_initiated_task_counts, project_inprogress_task_counts, project_completed_task_counts)
    ]

    stats = {
        'total_projects': total_projects,
        'initiated': initiated_count,
        'in_progress': in_progress_count,
        'completed_projects': completed_projects_count,
        'total_users': total_users_count,
        'engaged_count': engaged_count,
        'free_count': free_count
    }
    
    return render_template('dashboard.html', 
                           user=user,
                           stats=stats,
                           project_names=project_names,
                           project_progress=project_progress,
                           project_statuses=project_statuses,
                           team_counts=team_counts,
                           project_tasks=project_tasks,
                           project_initiated_task_counts=project_initiated_task_counts,
                           project_inprogress_task_counts=project_inprogress_task_counts,
                           project_completed_task_counts=project_completed_task_counts,
                           task_chart_labels=task_chart_labels,
                           task_chart_values=task_chart_values,
                           status_percentages=[initiated_pct, in_progress_pct, completed_pct],
                           project_initiated_task_names=project_initiated_task_names,
                           project_inprogress_task_names=project_inprogress_task_names,
                           project_completed_task_names=project_completed_task_names,
                           last_year_months=last_year_months,
                           last_year_counts=last_year_counts,
                           years_range=years_range,
                           year_counts=year_counts,
                           workload_members=workload_members,
                           workload_initiated=workload_initiated,
                           workload_in_progress=workload_in_progress,
                           workload_initiated_projects=workload_initiated_projects,
                           workload_in_progress_projects=workload_in_progress_projects,
                           initiated_projects=project_initiated_task_counts)
def get_user_activities(user_id, user_role):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    current_date = datetime.today()
    one_week_ago = (current_date - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    raw_activities = []

    if user_role == 'Super Admin':
        try:
            cursor.execute("""
                SELECT id, name, status, updated_at 
                FROM projects 
                WHERE updated_at >= %s 
                ORDER BY updated_at DESC LIMIT 10
            """, (one_week_ago,))
            for p in cursor.fetchall():
                t_val = p.get('updated_at')
                time_str = t_val.strftime('%b %d, %I:%M %p') if isinstance(t_val, datetime) else "Just now"
                raw_activities.append({
                    'id': f"proj_status_{p['id']}_{p['status']}_{p.get('updated_at')}",
                    'icon': 'bi-arrow-repeat',
                    'color': 'bg-indigo-subtle text-indigo',
                    'title': f"Project '{p['name']}' status updated to: {p['status']}",
                    'time': time_str,
                    'sort_time': t_val if isinstance(t_val, datetime) else datetime.min
                })
        except Exception:
            pass
    else:
        try:
            cursor.execute("""
                SELECT DISTINCT p.id, p.name, p.status, p.updated_at, p.created_at
                FROM projects p 
                LEFT JOIN project_assignments pa ON p.id = pa.project_id
                LEFT JOIN team_members tm ON pa.employee_id = tm.id
                JOIN app_users u ON u.id = %s AND (TRIM(LOWER(tm.name)) = TRIM(LOWER(u.name)) OR p.created_by = %s)
                WHERE p.updated_at >= %s OR p.created_at >= %s
                ORDER BY p.updated_at DESC LIMIT 10
            """, (user_id, user_id, one_week_ago, one_week_ago))
            
            for p in cursor.fetchall():
                t_val = p.get('updated_at') or p.get('created_at')
                time_str = t_val.strftime('%b %d, %I:%M %p') if isinstance(t_val, datetime) else "Recently"
                raw_activities.append({
                    'id': f"user_assigned_proj_{p['id']}_{p['status']}",
                    'icon': 'bi-briefcase',
                    'color': 'bg-info-subtle text-info',
                    'title': f"Assigned/Updated Project: '{p['name']}' ({p['status']})",
                    'time': time_str,
                    'sort_time': t_val if isinstance(t_val, datetime) else datetime.min
                })
        except Exception:
            pass

    raw_activities.sort(key=lambda x: x['sort_time'], reverse=True)

    cursor.execute("SELECT notification_id FROM user_notification_reads WHERE user_id = %s", (user_id,))
    read_db_rows = cursor.fetchall()
    read_notification_ids = {row['notification_id'] for row in read_db_rows}

    recent_activities = []
    unread_count = 0
    for act in raw_activities:
        is_read = act['id'] in read_notification_ids
        if not is_read:
            unread_count += 1
        recent_activities.append({**act, 'is_read': is_read})

    cursor.close()
    conn.close()
    return recent_activities, unread_count

@app.context_processor
def inject_notifications():
    if 'user' not in session:
        return dict(recent_activities=[], unread_count=0)
    user_id = session.get('user_id')
    user_role = session.get('role')
    recent_activities, unread_count = get_user_activities(user_id, user_role)
    return dict(recent_activities=recent_activities, unread_count=unread_count)


# API Endpoint to mark individual notification read in Database
@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    if 'user' not in session:
        return {'status': 'unauthorized'}, 401
    
    user_id = session.get('user_id')
    data = request.get_json() or {}
    notif_id = data.get('id')
    
    if notif_id and user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT IGNORE INTO user_notification_reads (user_id, notification_id) VALUES (%s, %s)",
                (user_id, notif_id)
            )
            conn.commit()
        except Exception as e:
            print("Error marking notification read:", e)
        finally:
            cursor.close()
            conn.close()
                
    return {'status': 'success'}

# 5. Projects Route
@app.route('/projects')
def projects():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    # Dropdown ke liye saare team members fetch karna (Super Admin ya sab ke liye)
    cursor.execute("SELECT id, name FROM team_members ORDER BY name ASC")
    all_team_members = cursor.fetchall()
    
    # URL query parameter se selected member ki ID lena (e.g. /projects?member_id=3)
    selected_member_id = request.args.get('member_id', type=int)
    
    # Pehle team_members table mein check karein ke is app_user ki apni team_member ID kya hai
    cursor.execute("SELECT id FROM team_members WHERE user_id = %s", (user_id,))
    team_member_record = cursor.fetchone()
    team_member_id = team_member_record['id'] if team_member_record else None
    
    if session.get('role') == 'Super Admin':
        if selected_member_id:
            # Agar Super Admin ne koi specific team member select kiya hai
            cursor.execute('''
                SELECT DISTINCT p.id, p.name, p.description, p.progress, p.status, p.created_by, p.start_date, p.end_date,
                       l.name AS team_lead,
                       (
                           SELECT GROUP_CONCAT(t2.name SEPARATOR ', ')
                           FROM project_assignments pa2
                           JOIN team_members t2 ON pa2.employee_id = t2.id
                           WHERE pa2.project_id = p.id AND (p.team_owner_id IS NULL OR pa2.employee_id != p.team_owner_id)
                       ) AS assigned_employees
                FROM projects p
                LEFT JOIN team_members l ON p.team_owner_id = l.id
                LEFT JOIN project_assignments pa ON p.id = pa.project_id
                WHERE p.team_owner_id = %s OR pa.employee_id = %s
                ORDER BY p.id DESC
            ''', (selected_member_id, selected_member_id))
        else:
            # Super Admin ke liye saare projects
            cursor.execute('''
                SELECT p.id, p.name, p.description, p.progress, p.status, p.created_by, p.start_date, p.end_date,
                       l.name AS team_lead,
                       (
                           SELECT GROUP_CONCAT(t2.name SEPARATOR ', ')
                           FROM project_assignments pa2
                           JOIN team_members t2 ON pa2.employee_id = t2.id
                           WHERE pa2.project_id = p.id AND (p.team_owner_id IS NULL OR pa2.employee_id != p.team_owner_id)
                       ) AS assigned_employees
                FROM projects p
                LEFT JOIN team_members l ON p.team_owner_id = l.id
                GROUP BY p.id
                ORDER BY p.id DESC
            ''')
    else:
        # Normal user ke liye filtering
        filter_id = selected_member_id if selected_member_id else team_member_id
        cursor.execute('''
            SELECT DISTINCT p.id, p.name, p.description, p.progress, p.status, p.created_by, p.start_date, p.end_date,
                   l.name AS team_lead,
                   (
                       SELECT GROUP_CONCAT(t2.name SEPARATOR ', ')
                       FROM project_assignments pa2
                       JOIN team_members t2 ON pa2.employee_id = t2.id
                       WHERE pa2.project_id = p.id AND (p.team_owner_id IS NULL OR pa2.employee_id != p.team_owner_id)
                   ) AS assigned_employees
            FROM projects p
            LEFT JOIN team_members l ON p.team_owner_id = l.id
            WHERE p.created_by = %s 
               OR p.team_owner_id = %s
               OR p.id IN (
                   SELECT project_id FROM project_assignments WHERE employee_id = %s
               )
            ORDER BY p.id DESC
        ''', (user_id, filter_id, filter_id))
        
    all_projects = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('projects.html', 
                           projects=all_projects, 
                           user=user, 
                           all_team_members=all_team_members, 
                           selected_member_id=selected_member_id)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/tasks-hub', methods=['GET', 'POST'])
def tasks_hub():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    cursor.execute("SELECT id FROM team_members WHERE user_id = %s", (user_id,))
    team_member_record = cursor.fetchone()
    team_member_id = team_member_record['id'] if team_member_record else None

    if request.method == 'POST':
        task_code = request.form.get('task_code') # Table wali 6-digits unique task ID
        project_id = request.form.get('project_id')
        title = request.form.get('name') 
        description = request.form.get('description') 
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        status = request.form.get('status', 'Active')
        
        progress = request.form.get('progress')
        if status == 'Completed':
            progress = 100
        elif not progress:
            progress = 0

        assigned_members = request.form.getlist('assigned_to')

        if not title or not project_id:
            flash('Error: Task Title and Project selection are required!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('tasks_hub', action='add'))

        if start_date and end_date and start_date >= end_date:
            flash('Task End date must be after Start date!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('tasks_hub', action='add'))

        # Project ki start_date aur end_date fetch kar rahe hain
        cursor.execute("SELECT name, start_date, end_date FROM projects WHERE id = %s", (project_id,))
        project_info = cursor.fetchone()
        
        if project_info and project_info['start_date']:
            if start_date and str(start_date) < str(project_info['start_date']):
                flash(f"Task start date cannot be before the project's start date ({project_info['start_date']})!", 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('tasks_hub', action='add'))

        # Yahan task ki end date par validation lagayi hai jo project ki end date se bari nahi ho sakti
        if project_info and project_info.get('end_date'):
            if end_date and str(end_date) > str(project_info['end_date']):
                flash(f"Task end date cannot be after the project's end date ({project_info['end_date']})!", 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('tasks_hub', action='add'))

        if user_role != 'Super Admin':
            assigned_members = [str(team_member_id)] if team_member_id else []

        try:
            if not assigned_members:
                flash('Error: Please select at least one team member to assign the task!', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('tasks_hub', action='add'))

            safe_project_name = "".join(c for c in project_info['name'] if c.isalnum() or c in ('_', '-')).strip() if project_info else "Project"
            primary_assignee = assigned_members[0]
            
            # Database me 6-digit task_code save ho raha hai
            cursor.execute("""
                INSERT INTO tasks (task_code, project_id, title, description, assigned_to, created_by, start_date, end_date, status, progress)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (task_code, project_id, title, description, primary_assignee, user_id, start_date if start_date else None, end_date if end_date else None, status, progress))
            conn.commit()
            
            new_task_id = cursor.lastrowid

            cursor.execute("SELECT name FROM team_members WHERE id = %s", (primary_assignee,))
            assigned_member = cursor.fetchone()
            assignee_name = assigned_member['name'] if assigned_member else "User"

            attachment_filename = None
            if 'attachment' in request.files:
                file = request.files['attachment']
                if file and file.filename != '' and allowed_file(file.filename):
                    original_filename = secure_filename(file.filename)
                    safe_assignee_name = "".join(c for c in assignee_name if c.isalnum() or c in ('_', '-')).strip()
                    
                    current_task_code = task_code if task_code else str(new_task_id)
                    
                    project_folder_path = os.path.join(UPLOAD_FOLDER, safe_project_name)
                    task_folder_name = f"{current_task_code}_{safe_assignee_name}"
                    task_upload_path = os.path.join(project_folder_path, task_folder_name)
                    
                    os.makedirs(task_upload_path, exist_ok=True)
                    
                    backend_filename = f"{current_task_code}_{original_filename}"
                    file.save(os.path.join(task_upload_path, backend_filename))
                    
                    attachment_filename = f"{safe_project_name}/{task_folder_name}/{backend_filename}"

                    cursor.execute("UPDATE tasks SET attachment = %s WHERE id = %s", (attachment_filename, new_task_id))
                    conn.commit()

            flash('Task added successfully with selected team members!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error adding task: {e}', 'danger')
            
        cursor.close()
        conn.close()
        return redirect(url_for('tasks_hub'))

    action = request.args.get('action')

    if user_role == 'Super Admin':
        cursor.execute("SELECT id, name, start_date, end_date, team_owner_id FROM projects")
        projects_list = cursor.fetchall()
        cursor.execute("SELECT id, name, designation FROM team_members")
        team_members_list = cursor.fetchall() 
    else:
        cursor.execute("""
            SELECT DISTINCT p.id, p.name, p.start_date, p.end_date, p.team_owner_id FROM projects p 
            LEFT JOIN project_assignments pa ON p.id = pa.project_id
            WHERE p.created_by = %s OR p.team_owner_id = %s OR pa.employee_id = %s
        """, (user_id, team_member_id, team_member_id))
        projects_list = cursor.fetchall()
        team_members_list = []

    if action == 'add':
        if user_role == 'Super Admin':
            cursor.execute("SELECT id, name, start_date, end_date, team_owner_id FROM projects")
        else:
            cursor.execute("""
                SELECT DISTINCT p.id, p.name, p.start_date, p.end_date, p.team_owner_id FROM projects p 
                LEFT JOIN project_assignments pa ON p.id = pa.project_id
                WHERE p.created_by = %s OR pa.employee_id = %s
            """, (user_id, team_member_id))
        projects_list = cursor.fetchall()

        cursor.execute("SELECT id, name, designation FROM team_members")
        team_members_list = cursor.fetchall()

        cursor.execute("SELECT project_id, employee_id FROM project_assignments")
        assignments_list = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('add_task.html', 
                               user=user, 
                               projects=projects_list, 
                               team_members=team_members_list,
                               assignments=assignments_list)
    
    if user_role == 'Super Admin':
        cursor.execute("""
            SELECT t.*, t.task_code, t.title AS name, p.name AS project_name, tm.name AS assignee_name, p.team_owner_id 
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN team_members tm ON t.assigned_to = tm.id
            ORDER BY t.id DESC
        """)
    else:
        cursor.execute("""
            SELECT t.*, t.task_code, t.title AS name, p.name AS project_name, tm.name AS assignee_name, p.team_owner_id 
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN team_members tm ON t.assigned_to = tm.id
            WHERE t.assigned_to = %s OR t.created_by = %s
            ORDER BY t.id DESC
        """, (team_member_id, user_id))
        
    tasks_list = cursor.fetchall()

    for task in tasks_list:
        if task.get('assigned_to'):
            cursor.execute("SELECT id, name FROM team_members WHERE id = %s", (task['assigned_to'],))
            task['assigned_members'] = cursor.fetchall()
        else:
            task['assigned_members'] = []

        proj_id = task.get('project_id')
        proj_owner_id = None
        if proj_id:
            cursor.execute("SELECT team_owner_id FROM projects WHERE id = %s", (proj_id,))
            p_owner_res = cursor.fetchone()
            if p_owner_res:
                proj_owner_id = p_owner_res.get('team_owner_id')

        for member in task['assigned_members']:
            if proj_owner_id and str(member['id']) == str(proj_owner_id):
                member['display_name'] = f"{member['name']} (Lead)"
            else:
                member['display_name'] = member['name']

        if task.get('attachment'):
            filename_part = task['attachment'].split('/')[-1]
            if '_' in filename_part:
                parts = filename_part.split('_', 1)
                task['display_filename'] = parts[1] if len(parts) > 1 else filename_part
            else:
                task['display_filename'] = filename_part
        else:
            task['display_filename'] = None

    if user_role == 'Super Admin':
        cursor.execute("SELECT id, name FROM projects")
        dropdown_projects = cursor.fetchall()
    else:
        dropdown_projects = projects_list

    cursor.execute("SELECT id, name, designation FROM team_members")
    all_members = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('tasks_hub.html', 
                           user=user, 
                           tasks=tasks_list, 
                           projects=dropdown_projects, 
                           all_members=all_members)

# --- API Endpoint: Project ke mutabiq uske assigned members laane ke liye ---
@app.route('/get_project_members/<int:project_id>')
def get_project_members(project_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_role = session.get('role')
    team_member_id = session.get('team_member_id') or session.get('user_id')
    session_user_val = session.get('user')  # Yeh email ho sakti hai
    
    try:
        if user_role == 'Super Admin':
            cursor.execute("""
                SELECT tm.id, tm.name, tm.designation 
                FROM team_members tm
                JOIN project_assignments pa ON tm.id = pa.employee_id
                WHERE pa.project_id = %s
            """, (project_id,))
            members = cursor.fetchall()
        else:
            # 1. Pehle team_members table se record uthao
            cursor.execute("""
                SELECT id, name, designation 
                FROM team_members 
                WHERE id = %s
            """, (team_member_id,))
            members = cursor.fetchall()
            
            # 2. Agar team_members mein name nahi mila ya email save hai, toh users table se email match karke 'name' fetch karo
            if not members or not members[0].get('name') or '@' in str(members[0].get('name')):
                cursor.execute("""
                    SELECT id, name, '' as designation 
                    FROM users 
                    WHERE id = %s OR email = %s
                """, (team_member_id, session_user_val))
                user_record = cursor.fetchone()
                if user_record and user_record.get('name'):
                    members = [user_record]

            # 3. Agar database mein bhi name na mile, tab ja kar session wali email ko clean karo
            if not members or not members[0].get('name') or '@' in str(members[0].get('name') or ''):
                raw_session_user = session_user_val if session_user_val else 'Team Member'
                clean_name = raw_session_user.split('@')[0] if '@' in str(raw_session_user) else raw_session_user
                clean_name = clean_name.replace('.', ' ').title()
                
                members = [{'id': team_member_id, 'name': clean_name, 'designation': ''}]
                
        return jsonify(members)
    except Exception as e:
        print("Error fetching project members:", e)
        if user_role != 'Super Admin':
            raw_session_user = session_user_val if session_user_val else 'Team Member'
            clean_name = raw_session_user.split('@')[0].replace('.', ' ').title() if '@' in str(raw_session_user) else raw_session_user
            return jsonify([{'id': team_member_id, 'name': clean_name, 'designation': ''}])
        return jsonify([]), 500
    finally:
        cursor.close()
        conn.close()
@app.route('/update_task/<int:task_id>', methods=['GET', 'POST'])
def update_task(task_id):
    if 'user' not in session and 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = session.get('user_id') or session.get('user')
    user_role = session.get('role')

    cursor.execute("SELECT * FROM app_users WHERE id = %s OR name = %s", (user_id, user_id))
    logged_in_user = cursor.fetchone()

    # Team member id find karna for non-super-admin validation
    cursor.execute("SELECT id FROM team_members WHERE user_id = %s", (session.get('user_id'),))
    team_member_record = cursor.fetchone()
    team_member_id = team_member_record['id'] if team_member_record else None

    if request.method == 'POST':
        task_code = request.form.get('task_code')
        name = request.form.get('name')
        project_id = request.form.get('project_id')
        description = request.form.get('description') 
        status = request.form.get('status')
        assigned_members = request.form.getlist('assigned_to')
        
        progress = request.form.get('progress')
        if status == 'Completed':
            progress = 100
        elif not progress:
            progress = 0

        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not name or not project_id:
            flash('Error: Task Name and Project selection are required!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('update_task', task_id=task_id))

        if start_date and end_date and start_date >= end_date:
            flash('Task End date must be after Start date!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('update_task', task_id=task_id))
            
        cursor.execute("SELECT name, start_date FROM projects WHERE id = %s", (project_id,))
        project_info = cursor.fetchone()
        
        if project_info and project_info['start_date']:
            if start_date and str(start_date) < str(project_info['start_date']):
                flash(f"Task start date cannot be before the project's start date ({project_info['start_date']})!", 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('update_task', task_id=task_id))

        # Agar user Super Admin nahi hai, toh woh sirf khud ko assign kar sakta hai
        if user_role != 'Super Admin':
            assigned_members = [str(team_member_id)] if team_member_id else []

        if not assigned_members:
            flash('Error: Please select at least one team member to assign the task!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('update_task', task_id=task_id))

        primary_assignee = assigned_members[0]

        cursor.execute("SELECT attachment FROM tasks WHERE id = %s", (task_id,))
        existing_task = cursor.fetchone()
        attachment_filename = existing_task['attachment'] if existing_task else None

        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                assignee_name = "User"
                if primary_assignee:
                    cursor.execute("SELECT name FROM team_members WHERE id = %s", (primary_assignee,))
                    assignee_rec = cursor.fetchone()
                    if assignee_rec:
                        assignee_name = assignee_rec['name']

                safe_project_name = "".join(c for c in project_info['name'] if c.isalnum() or c in ('_', '-')).strip() if project_info else "Project"
                safe_assignee_name = "".join(c for c in assignee_name if c.isalnum() or c in ('_', '-')).strip()
                
                project_folder_path = os.path.join(UPLOAD_FOLDER, safe_project_name)
                task_folder_name = f"task_{task_id}_{safe_assignee_name}"
                task_upload_path = os.path.join(project_folder_path, task_folder_name)
                
                os.makedirs(task_upload_path, exist_ok=True)
                file.save(os.path.join(task_upload_path, filename))
                
                attachment_filename = f"{safe_project_name}/{task_folder_name}/{filename}"

        try:
            cursor.execute("""
                UPDATE tasks 
                SET task_code = %s, title = %s, project_id = %s, description = %s, status = %s, progress = %s, start_date = %s, end_date = %s, assigned_to = %s, attachment = %s
                WHERE id = %s
            """, (task_code, name, project_id, description, status, progress, start_date if start_date else None, end_date if end_date else None, primary_assignee, attachment_filename, task_id))
            conn.commit()
            flash('Task updated successfully with project folder structure!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error updating task: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('tasks_hub'))

    cursor.execute("SELECT *, title AS name FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        cursor.close()
        conn.close()
        flash('Task not found!', 'danger')
        return redirect(url_for('tasks_hub'))

    if user_role == 'Super Admin':
        # Yahan projects table mein team owner/lead column select karein (misal ke taur par team_owner_id ya lead_id)
        cursor.execute("SELECT id, name, start_date, end_date, team_owner_id FROM projects")
        projects = cursor.fetchall()
        cursor.execute("SELECT id, name, designation FROM team_members")
        team_members = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT DISTINCT p.id, p.name, p.start_date, p.end_date, p.team_owner_id FROM projects p 
            LEFT JOIN project_assignments pa ON p.id = pa.project_id
            WHERE p.created_by = %s OR pa.employee_id = %s
        """, (user_id, team_member_id))
        projects = cursor.fetchall()
        cursor.execute("SELECT id, name, designation FROM team_members WHERE id = %s", (team_member_id,))
        team_members = cursor.fetchall()

    assigned_member_ids = [task['assigned_to']] if task.get('assigned_to') else []

    cursor.close()
    conn.close()

    return render_template('edit_task.html', 
                           task=task, 
                           projects=projects, 
                           team_members=team_members, 
                           assigned_member_ids=assigned_member_ids,
                           user=logged_in_user)  # <--- Yeh line missing thi jo add kar di gayi hai!

    return render_template('edit_task.html', task=task, projects=projects, user=logged_in_user)
@app.route('/delete_task_attachment/<int:task_id>')
def delete_task_attachment(task_id):
    if 'user' not in session and 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check current attachment file
    cursor.execute("SELECT attachment FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    
    if task and task['attachment']:
        file_path = os.path.join(UPLOAD_FOLDER, task['attachment'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file: {e}")
                
        # Database se attachment ka naam NULL/empty kar dein
        cursor.execute("UPDATE tasks SET attachment = NULL WHERE id = %s", (task_id,))
        conn.commit()
        flash('Task attachment deleted successfully!', 'success')
        
    cursor.close()
    conn.close()
    return redirect(url_for('tasks_hub'))    

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user' not in session and 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        conn.commit()
        flash('Task deleted successfully!', 'danger')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting task: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('tasks_hub'))
@app.route('/projects/view/<int:project_id>')
def view_project(project_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Get logged-in user details
    user_id = session.get('user_id')
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    # 2. Fetch project details and get Team Lead name from team_members
    cursor.execute("""
        SELECT p.*, tm.name AS team_lead 
        FROM projects p
        LEFT JOIN team_members tm ON p.team_owner_id = tm.id
        WHERE p.id = %s
    """, (project_id,))
    project = cursor.fetchone()
    
    if not project:
        flash('Project not found!', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('projects'))
        
    # 3. Fetch all assigned members and format them into a single comma-separated string
    cursor.execute("""
        SELECT tm.name 
        FROM project_assignments pa
        JOIN team_members tm ON pa.employee_id = tm.id
        WHERE pa.project_id = %s
    """, (project_id,))
    members = cursor.fetchall()
    
    # Convert list of dictionaries into a clean string (e.g., "Ali, Ahmed, Sara")
    if members:
        project['assigned_employees'] = ", ".join([m['name'] for m in members])
    else:
        project['assigned_employees'] = None
    
    cursor.close()
    conn.close()
    
    return render_template('view_project.html', user=user, project=project) 
# 6. Add Project Route
@app.route('/projects/add', methods=['GET', 'POST'])
def add_project():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'Super Admin':
        flash('Access Denied!', 'danger')
        return redirect(url_for('projects'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    selected_dept_id = request.args.get('department_id')
    employees = []

    if selected_dept_id and selected_dept_id != 'None':
        cursor.execute("SELECT id, name, designation FROM team_members WHERE department_id = %s", (selected_dept_id,))
        employees = cursor.fetchall()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        status = request.form.get('status', 'Active')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        department_id = request.form.get('department_id')
        employee_ids = request.form.getlist('employee_ids')
        team_owner_id = request.form.get('team_owner_id')
        created_by = session['user_id']
        
        # --- Validation: Project Name is required ---
        if not name or name.strip() == '':
            flash('Error: Project Name is required!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('add_project', department_id=selected_dept_id))

        # --- Validation: Department is required ---
        if not department_id or department_id == 'None':
            flash('Error: Please select a Department!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('add_project'))

        # --- Validation: Start Date and End Date are required ---
        if not start_date or not end_date:
            flash('Error: Both Start Date and End Date are required!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('add_project', department_id=selected_dept_id))

        # --- Validation: End Date must be greater than Start Date ---
        if start_date and end_date:
            if datetime.strptime(end_date, '%Y-%m-%d') <= datetime.strptime(start_date, '%Y-%m-%d'):
                flash('Error: End Date must be greater than Start Date!', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('add_project', department_id=selected_dept_id))

        # --- Validation: Team Owner is required ---
        if not team_owner_id or team_owner_id == '':
            flash('Error: Please select a Team Owner for the project!', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('add_project', department_id=selected_dept_id))
        
        if status == 'Active':
            progress = 0
        elif status == 'Completed':
            progress = 100
        else:
            progress = request.form.get('progress', 0)
        
        if name:
            cursor.execute("""
                INSERT INTO projects (name, description, progress, status, created_by, start_date, end_date, team_owner_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, description, progress, status, created_by, start_date, end_date, team_owner_id))
            project_id = cursor.lastrowid
            
            assigned_set = set(employee_ids)
            if team_owner_id:
                assigned_set.add(str(team_owner_id))
            
            for emp_id in assigned_set:
                cursor.execute("INSERT INTO project_assignments (project_id, employee_id) VALUES (%s, %s)", (project_id, emp_id))
            
            conn.commit()
            flash('Project created and team assigned successfully!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('projects'))
    
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('add_project.html', 
                           user=user,
                           departments=departments, 
                           employees=employees, 
                           selected_dept_id=int(selected_dept_id) if selected_dept_id and selected_dept_id != 'None' else None)

@app.route('/api/get_department_members/<int:dept_id>')
def get_department_members(dept_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, designation FROM team_members WHERE department_id = %s", (dept_id,))
    members = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(members)

# 7. Edit Project Route
@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
def edit_project(project_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    
    if not project:
        flash('Project not found!', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('projects'))
        
    is_assigned_to_user = False
    if session.get('role') != 'Super Admin':
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM project_assignments pa
            JOIN team_members t ON pa.employee_id = t.id
            JOIN app_users u ON u.id = %s 
            WHERE pa.project_id = %s 
              AND TRIM(LOWER(t.name)) = TRIM(LOWER(u.name)) 
              AND TRIM(LOWER(t.designation)) = TRIM(LOWER(u.designation))
        """, (session['user_id'], project_id))
        result = cursor.fetchone()
        if result['cnt'] > 0:
            is_assigned_to_user = True

    if session.get('role') != 'Super Admin' and project.get('created_by') != session.get('user_id') and not is_assigned_to_user:
        flash('Access Denied!', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('projects'))
        
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    selected_dept_id = request.args.get('department_id')
    
    if not selected_dept_id:
        cursor.execute("""
            SELECT department_id FROM team_members t 
            JOIN project_assignments pa ON t.id = pa.employee_id 
            WHERE pa.project_id = %s LIMIT 1
        """, (project_id,))
        first_emp = cursor.fetchone()
        if first_emp:
            selected_dept_id = str(first_emp['department_id'])
            
    employees = []
    if selected_dept_id and selected_dept_id != 'None':
        cursor.execute("SELECT id, name, designation FROM team_members WHERE department_id = %s", (selected_dept_id,))
        employees = cursor.fetchall()
        
    cursor.execute("SELECT employee_id FROM project_assignments WHERE project_id = %s", (project_id,))
    assigned_emp_rows = cursor.fetchall()
    assigned_employee_ids = [row['employee_id'] for row in assigned_emp_rows]

    if request.method == 'POST':
        status = request.form.get('status', 'Active')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        # --- Validation: End Date must be greater than Start Date ---
        if start_date and end_date:
            if datetime.strptime(end_date, '%Y-%m-%d') <= datetime.strptime(start_date, '%Y-%m-%d'):
                flash('Error: End Date must be greater than Start Date!', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('edit_project', project_id=project_id))
        
        if status == 'Active':
            progress = 0
        elif status == 'Completed':
            progress = 100
        else:
            progress = request.form.get('progress', 0)
        
        # --- Super Admin Edit Block ---
        if session.get('role') == 'Super Admin':
            name = request.form.get('name')
            description = request.form.get('description')
            employee_ids = request.form.getlist('employee_ids')
            team_owner_id = request.form.get('team_owner_id')  # Team Owner
            
            # Backend Validation for required fields
            if not name or not name.strip():
                flash('Error: Project Name is required!', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('edit_project', project_id=project_id))
                
            if not team_owner_id or team_owner_id == '':
                flash('Error: Please select a Team Owner for the project!', 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('edit_project', project_id=project_id))
            
            cursor.execute("""
                UPDATE projects 
                SET name = %s, description = %s, progress = %s, status = %s, start_date = %s, end_date = %s, team_owner_id = %s 
                WHERE id = %s
            """, (name, description, progress, status, start_date if start_date else None, end_date if end_date else None, team_owner_id, project_id))
            
            cursor.execute("DELETE FROM project_assignments WHERE project_id = %s", (project_id,))
            
            # Team Owner ko employees ki list ke sath automatically merge karna
            assigned_set = set(employee_ids)
            if team_owner_id:
                assigned_set.add(str(team_owner_id))
                
            for emp_id in assigned_set:
                cursor.execute("INSERT INTO project_assignments (project_id, employee_id) VALUES (%s, %s)", (project_id, emp_id))
                
            conn.commit()
            flash('Project and team assignments updated successfully!', 'success')
            
        else:
            cursor.execute("""
                UPDATE projects 
                SET progress = %s, status = %s, start_date = %s, end_date = %s 
                WHERE id = %s
            """, (progress, status, start_date if start_date else None, end_date if end_date else None, project_id))
            
            conn.commit()
            flash('Project progress updated successfully!', 'success')
            
        cursor.close()
        conn.close()
        return redirect(url_for('projects'))
        
    cursor.close()
    conn.close()
    
    return render_template('edit_project.html', 
                           user=user,
                           project=project, 
                           departments=departments, 
                           employees=employees, 
                           selected_dept_id=int(selected_dept_id) if selected_dept_id and selected_dept_id != 'None' else None,
                           assigned_employee_ids=assigned_employee_ids)

@app.route('/get_employees/<int:department_id>')
def get_employees(department_id):
    if 'user' not in session:
        return jsonify([]), 401
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Raw SQL query for MySQL connector
    cursor.execute("SELECT id, name, designation FROM team_members WHERE department_id = %s", (department_id,))
    employees = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(employees)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Please login first to update your profile.', 'danger')
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    name = request.form.get('name')
    designation = request.form.get('designation')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check karein ke app_users table mein 'profile_pic' column mojood hai ya nahi
        cursor.execute("SHOW COLUMNS FROM app_users LIKE 'profile_pic'")
        has_profile_pic_col = cursor.fetchone()
        
        # Profile Picture Upload Handling
        if 'profile_pic' in request.files and has_profile_pic_col:
            file = request.files['profile_pic']
            if file and file.filename != '':
                # File extension extract karein (misal ke tor par .jpg ya .png)
                ext = os.path.splitext(secure_filename(file.filename))[1]
                
                # User ka name safe format mein banayein (spaces ko underscore mein badal kar)
                safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
                
                # Naya filename: id_name_extension (misal ke tor par: 5_Ali_Khan.jpg)
                filename = f"{user_id}_{safe_name}{ext}"
                
                upload_folder = os.path.join('static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                
                cursor.execute(
                    "UPDATE app_users SET name = %s, designation = %s, profile_pic = %s WHERE id = %s", 
                    (name, designation, filename, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE app_users SET name = %s, designation = %s WHERE id = %s", 
                    (name, designation, user_id)
                )
        else:
            cursor.execute(
                "UPDATE app_users SET name = %s, designation = %s WHERE id = %s", 
                (name, designation, user_id)
            )
            
        conn.commit()
        flash('Profile updated successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error updating profile: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/delete_profile_picture')
def delete_profile_picture():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # User ki current profile picture ka naam database se nikalen
    cursor.execute("SELECT profile_pic FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if user and user['profile_pic']:
        # Optional: Agar aap folder se bhi physical file delete karna chahtay hain
        try:
            pic_path = os.path.join(app.root_path, 'static', 'uploads', user['profile_pic'])
            if os.path.exists(pic_path):
                os.remove(pic_path)
        except Exception as e:
            print("File delete error:", e)
            
        # Database mein profile_pic column ko NULL kar dein
        cursor.execute("UPDATE app_users SET profile_pic = NULL WHERE id = %s", (user_id,))
        conn.commit()
        flash('Profile picture removed successfully!', 'success')
    else:
        flash('No profile picture found to remove.', 'warning')
        
    cursor.close()
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_password = request.form.get('current_password') or ''
    new_password = request.form.get('new_password') or ''
    confirm_password = request.form.get('confirm_password') or ''
    
    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required!', 'danger')
        return redirect(request.referrer or url_for('projects'))

    if new_password != confirm_password:
        flash('New passwords do not match!', 'danger')
        return redirect(request.referrer or url_for('projects'))
        
    # 🔒 Strong Password Validation Checks for New Password
    if len(new_password) < 8:
        flash('New password must be at least 8 characters long!', 'danger')
        return redirect(request.referrer or url_for('projects'))
        
    if not re.search(r'[A-Za-z]', new_password):
        flash('New password must contain at least one alphabet letter!', 'danger')
        return redirect(request.referrer or url_for('projects'))
        
    if not re.search(r'\d', new_password):
        flash('New password must contain at least one number!', 'danger')
        return redirect(request.referrer or url_for('projects'))
        
    if not re.search(r'[@$!%*?&._#]', new_password):
        flash('New password must contain at least one special character (e.g., @$!%*?&)', 'danger')
        return redirect(request.referrer or url_for('projects'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    # Verify current password securely using check_password_hash
    # (Agar aapke purane users plain text mein hain, toh fallback check bhi rakh sakte hain: user['password'] != current_password)
    if not user or not check_password_hash(user['password'], current_password):
        cursor.close()
        conn.close()
        flash('Incorrect current password!', 'danger')
        return redirect(request.referrer or url_for('projects'))
        
    # Hash the new password before updating
    hashed_new_password = generate_password_hash(new_password)

    cursor.execute("UPDATE app_users SET password = %s WHERE id = %s", (hashed_new_password, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Password updated successfully!', 'success')
    return redirect(request.referrer or url_for('projects'))
# 8. Delete Project Route
@app.route('/delete_project/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    
    if session.get('role') != 'Super Admin' and (not project or project['created_by'] != session['user_id']):
        flash('Access Denied!', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('projects'))
        
    cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Project deleted successfully!', 'danger')
    return redirect(url_for('projects'))

@app.template_filter('regex_replace')
def regex_replace_filter(s, find, replace):
    return re.sub(find, replace, str(s))
# 1. Project Reporting Route (With Project & Team Member Filtering)
@app.route('/reports/projects')
def project_reports():
    if 'user_id' not in session and 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    user_role = str(session.get('role', '')).strip()
    
    user = None
    if user_id:
        cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
    user_name = user.get('name') if user else ''
    is_admin = user_role in ['Super Admin', 'Admin', 'Manager', 'super admin', 'admin', 'manager']
    
    # 1. Fetch Projects
    if is_admin:
        cursor.execute("SELECT id, name, description, status, progress, start_date, end_date FROM projects ORDER BY name ASC")
        all_projects = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT DISTINCT p.id, p.name, p.description, p.status, p.progress, p.start_date, p.end_date 
            FROM projects p
            JOIN project_assignments pa ON p.id = pa.project_id
            JOIN team_members tm ON pa.employee_id = tm.id
            WHERE TRIM(LOWER(tm.name)) = TRIM(LOWER(%s)) OR tm.id = %s
            ORDER BY p.name ASC
        """, (user_name, user_id))
        all_projects = cursor.fetchall()
    
    selected_project_id = request.args.get('project_id', 'All')
    selected_member_id = request.args.get('member_id', 'All')
    selected_status = request.args.get('status', 'All')
    
    if not is_admin and selected_project_id != 'All':
        allowed_ids = [str(p['id']) for p in all_projects]
        if str(selected_project_id) not in allowed_ids:
            selected_project_id = 'All'

    # 2. Fetch Team Members: Only fetch if a specific project is selected
    project_team_members = []
    if selected_project_id != 'All':
        cursor.execute("""
            SELECT DISTINCT tm.id, tm.name, tm.designation 
            FROM team_members tm
            JOIN project_assignments pa ON tm.id = pa.employee_id
            WHERE pa.project_id = %s
        """, (selected_project_id,))
        project_team_members = cursor.fetchall()
    else:
        # Reset member filter if 'All' projects is selected
        selected_member_id = 'All'
    
    # 3. All Projects Overview Summary
    all_projects_summary = []
    if selected_project_id == 'All':
        summary_source = all_projects
        for p in summary_source:
            cursor.execute("""
                SELECT tm.name FROM team_members tm
                JOIN project_assignments pa ON tm.id = pa.employee_id
                WHERE pa.project_id = %s
            """, (p['id'],))
            members = [m['name'] for m in cursor.fetchall()]
            p['assigned_members'] = members if members else ['No members assigned']
            
            cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE project_id = %s", (p['id'],))
            t_count = cursor.fetchone()
            p['total_tasks'] = t_count['total'] if t_count else 0
            
            all_projects_summary.append(p)

    # 4. Target Project details
    target_project = None
    if selected_project_id != 'All':
        cursor.execute("SELECT id, name, description, status, progress, start_date, end_date FROM projects WHERE id = %s", (selected_project_id,))
        target_project = cursor.fetchone()

    # 5. Tasks Query
    task_query = """
        SELECT t.id, t.title AS name, t.status, t.progress, t.start_date, t.end_date, p.name AS project_name,
               COALESCE(tm_assigned.name, t.assigned_to) AS assigned_member_name,
               t.assigned_to AS assigned_raw, p.id AS proj_id
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        LEFT JOIN team_members tm_assigned ON t.assigned_to = CAST(tm_assigned.id AS CHAR) OR TRIM(LOWER(t.assigned_to)) = TRIM(LOWER(tm_assigned.name))
        WHERE 1=1
    """
    task_params = []
    
    if not is_admin:
        allowed_project_ids = [p['id'] for p in all_projects]
        if allowed_project_ids:
            format_strings = ','.join(['%s'] * len(allowed_project_ids))
            task_query += f" AND t.project_id IN ({format_strings})"
            task_params.extend(allowed_project_ids)
        else:
            task_query += " AND 1=0"

    if selected_project_id != 'All':
        task_query += " AND t.project_id = %s"
        task_params.append(selected_project_id)
        
    if selected_member_id != 'All':
        task_query += " AND (CAST(t.assigned_to AS CHAR) = CAST(%s AS CHAR) OR tm_assigned.id = %s)"
        task_params.extend([selected_member_id, selected_member_id])
        
    if selected_status != 'All':
        if selected_status == 'Initiated':
            task_query += " AND (t.status IN ('Active', 'Initiated', '', 'initiated') OR t.status IS NULL)"
        else:
            task_query += " AND t.status = %s"
            task_params.append(selected_status)
            
    task_query += " ORDER BY t.id DESC"
    cursor.execute(task_query, tuple(task_params))
    raw_tasks = cursor.fetchall()
    
    project_tasks = []
    for t in raw_tasks:
        status_val = t.get('status')
        if not status_val or str(status_val).strip() == '' or str(status_val).strip().lower() in ['none', 'null', 'active', 'initiated']:
            t['status'] = 'Initiated'
        else:
            t['status'] = str(status_val).strip()
        project_tasks.append(t)
        
    total_project_tasks = len(project_tasks)
        
    cursor.close()
    conn.close()
    
    return render_template('project_reports.html',
                           user=user,
                           all_projects=all_projects,
                           project_team_members=project_team_members,
                           selected_project_id=selected_project_id,
                           selected_member_id=selected_member_id,
                           selected_status=selected_status,
                           target_project=target_project,
                           all_projects_summary=all_projects_summary,
                           project_tasks=project_tasks,
                           total_project_tasks=total_project_tasks)

# 2. Task Performance Reporting Route
@app.route('/reports/tasks')
def task_reports():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    selected_status = request.args.get('status', 'All')
    selected_member_id = request.args.get('member_id', 'All')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')
    
    # Fetch all team members for Super Admin filter dropdown
    all_team_members = []
    if user_role == 'Super Admin':
        cursor.execute("SELECT id, name FROM team_members ORDER BY name ASC")
        all_team_members = cursor.fetchall()
    
    # Master Task Query
    if user_role == 'Super Admin':
        task_query = """
            SELECT t.id, t.title AS name, t.status, t.progress, t.start_date, t.end_date, p.name AS project_name,
                   COALESCE(tm_assigned.name, t.assigned_to) AS assigned_member_name,
                   t.assigned_to AS assigned_raw
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN team_members tm_assigned ON t.assigned_to = CAST(tm_assigned.id AS CHAR) OR TRIM(LOWER(t.assigned_to)) = TRIM(LOWER(tm_assigned.name))
        """
        task_params = []
    else:
        task_query = """
            SELECT t.id, t.title AS name, t.status, t.progress, t.start_date, t.end_date, p.name AS project_name,
                   COALESCE(tm_assigned.name, t.assigned_to) AS assigned_member_name,
                   t.assigned_to AS assigned_raw
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN project_assignments pa ON p.id = pa.project_id
            LEFT JOIN team_members tm ON pa.employee_id = tm.id
            LEFT JOIN team_members tm_assigned ON t.assigned_to = CAST(tm_assigned.id AS CHAR) OR TRIM(LOWER(t.assigned_to)) = TRIM(LOWER(tm_assigned.name))
            JOIN app_users u ON u.id = %s AND TRIM(LOWER(tm.name)) = TRIM(LOWER(u.name))
            WHERE (p.created_by = %s OR tm.id IS NOT NULL)
        """
        task_params = [user_id, user_id]
        
    task_conditions = []
    
    # Super Admin Team Member filter condition
    if user_role == 'Super Admin' and selected_member_id and selected_member_id != 'All':
        task_conditions.append("(t.assigned_to = %s OR tm_assigned.id = %s)")
        task_params.extend([selected_member_id, selected_member_id])

    if selected_status and selected_status != 'All':
        if selected_status == 'Initiated':
            task_conditions.append("(t.status IN ('Active', 'Initiated', '', 'initiated') OR t.status IS NULL)")
        else:
            task_conditions.append("t.status = %s")
            task_params.append(selected_status)
            
    if start_date_filter:
        task_conditions.append("t.start_date >= %s")
        task_params.append(start_date_filter)
        
    if end_date_filter:
        task_conditions.append("t.end_date <= %s")
        task_params.append(end_date_filter)
        
    if task_conditions:
        if "WHERE" in task_query:
            task_query += " AND (" + " AND ".join(task_conditions) + ")"
        else:
            task_query += " WHERE (" + " AND ".join(task_conditions) + ")"
            
    task_query += " ORDER BY t.id DESC"
    
    cursor.execute(task_query, tuple(task_params))
    raw_tasks = cursor.fetchall()
    
    report_tasks = []
    for t in raw_tasks:
        status_val = t.get('status')
        if not status_val or str(status_val).strip() == '' or str(status_val).strip().lower() in ['none', 'null', 'active', 'initiated']:
            t['status'] = 'Initiated'
        else:
            t['status'] = str(status_val).strip()
        report_tasks.append(t)
        
    cursor.close()
    conn.close()
    
    return render_template('task_reports.html',
                           user=user,
                           report_tasks=report_tasks,
                           all_team_members=all_team_members,
                           selected_status=selected_status,
                           selected_member_id=selected_member_id,
                           start_date_filter=start_date_filter,
                           end_date_filter=end_date_filter)
# 8. Departments Route
@app.route('/departments', methods=['GET', 'POST'])
def departments_page():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'Super Admin':
        flash('Access Denied!', 'danger')
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if request.method == 'POST':
        if session.get('role') != 'Super Admin':
            flash('Access Denied! Only Super Admin have access.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('departments_page'))
            
        name = request.form.get('name')
        description = request.form.get('description')
        
        if name and description:
            cursor.execute("INSERT INTO departments (name, description) VALUES (%s, %s)", (name, description))
            conn.commit()
            flash('Department added successfully!', 'success')
            
        cursor.close()
        conn.close()
        return redirect(url_for('departments_page'))
        
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('departments.html', departments=departments, user=user)

# Team Member Route
# Team Member Route
@app.route('/team_members', methods=['GET', 'POST'])
def team_members_page():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'Super Admin':
        flash('Access Denied!', 'danger')
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Current logged-in user ka data fetch karein
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (session.get('user_id'),))
    current_user = cursor.fetchone()

    if request.method == 'POST':
        department_id = request.form.get('department_id')
        user_id = request.form.get('user_id')
        
        if user_id and department_id:
            try:
                cursor.execute("SELECT name, designation FROM app_users WHERE id = %s", (user_id,))
                selected_user = cursor.fetchone()
                
                if selected_user:
                    # team_members table mein sirf standard columns insert honge
                    cursor.execute(
                        "INSERT INTO team_members (user_id, name, designation, department_id) VALUES (%s, %s, %s, %s)",
                        (user_id, selected_user['name'], selected_user['designation'], department_id)
                    )
                    conn.commit()
                    flash('Team member added successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'An error occurred: {str(e)}', 'danger')
            finally:
                cursor.close()
                conn.close()
                
        return redirect(url_for('team_members_page'))
        
    # Departments fetch karein
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    # Wo registered users fetch karein jo abhi tak team_members mein shamil nahi hue
    cursor.execute('''
        SELECT id, name, designation, department_id, profile_pic FROM app_users 
        WHERE role_id != 1 AND id NOT IN (SELECT IFNULL(user_id, 0) FROM team_members WHERE user_id IS NOT NULL)
    ''')
    available_users = cursor.fetchall()
    
    # Existing team members fetch karein (app_users table ke sath JOIN kar ke profile_pic la rahe hain)
    cursor.execute('''
        SELECT team_members.id, team_members.name, team_members.designation, 
               departments.name AS dept_name, 
               app_users.profile_pic AS profile_pic
        FROM team_members 
        LEFT JOIN departments ON team_members.department_id = departments.id
        LEFT JOIN app_users ON team_members.user_id = app_users.id
    ''')
    team_members = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(
        'team_members.html', 
        team_members=team_members, 
        departments=departments, 
        available_users=available_users, 
        user=current_user
    )
# 9. Users / Profile Route
@app.route('/users', methods=['GET', 'POST'])
def users_page():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        new_gmail = request.form.get('gmail')
        new_designation = request.form.get('designation')
        new_password = request.form.get('password')
        current_user = session['user']
        
        if new_gmail:
            if new_password and new_password.strip() != "":
                cursor.execute("""
                    UPDATE app_users 
                    SET name = %s, gmail = %s, designation = %s, password = %s 
                    WHERE gmail = %s
                """, (new_name, new_gmail, new_designation, new_password, current_user))
            else:
                cursor.execute("""
                    UPDATE app_users 
                    SET name = %s, gmail = %s, designation = %s 
                    WHERE gmail = %s
                """, (new_name, new_gmail, new_designation, current_user))
                
            conn.commit()
            session['user'] = new_gmail
            flash('Profile updated successfully!', 'success')
            
        cursor.close()
        conn.close()
        return redirect(url_for('users_page'))
    
    current_user_email = session['user']
    cursor.execute("SELECT * FROM app_users WHERE gmail = %s", (current_user_email,))
    user = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('users.html', user=user)

# 11. Delete Department Route
@app.route('/delete_department/<int:dept_id>', methods=['POST'])
def delete_department(dept_id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'Super Admin':
        flash('Access denied! Only Super Admin can delete departments.', 'danger')
        return redirect(url_for('departments_page'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("DELETE FROM departments WHERE id = %s", (dept_id,))
    conn.commit()
    
    cursor.execute("SELECT id FROM departments ORDER BY id ASC")
    remaining_depts = cursor.fetchall()
    
    if len(remaining_depts) == 0:
        cursor.execute("ALTER TABLE departments AUTO_INCREMENT = 1")
        conn.commit()
    else:
        new_id = 1
        for dept in remaining_depts:
            old_id = dept['id']
            cursor.execute("UPDATE departments SET id = %s WHERE id = %s", (new_id, old_id))
            conn.commit()
            new_id += 1
            
        cursor.execute(f"ALTER TABLE departments AUTO_INCREMENT = {new_id}")
        conn.commit()
        
    cursor.close()
    conn.close()
    
    flash('Department deleted and IDs re-ordered successfully!', 'danger')
    return redirect(url_for('departments_page'))

# 13. Delete Team Member Route
@app.route('/delete_team_member/<int:id>', methods=['POST'])
def delete_team_member(id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') != 'Super Admin':
        flash('Access denied! Only Super Admin can delete team members.', 'danger')
        return redirect(url_for('team_members_page'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("DELETE FROM project_assignments WHERE employee_id = %s", (id,))
        cursor.execute("DELETE FROM team_members WHERE id = %s", (id,))
        conn.commit()
        
        flash('Team member deleted successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting team member: {e}', 'danger')
        
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('team_members_page'))

# 14. Edit Team Member Route
@app.route('/edit_team_member/<int:id>', methods=['GET', 'POST'])
def edit_team_member(id):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    cursor.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    current_user = cursor.fetchone()
    
    if request.method == 'POST':
        name = request.form.get('name')
        designation = request.form.get('designation')
        department_id = request.form.get('department_id')
        
        if name and designation and department_id:
            cursor.execute("""
                UPDATE team_members 
                SET name = %s, designation = %s, department_id = %s 
                WHERE id = %s
            """, (name, designation, department_id, id))
            
            cursor.execute("""
                UPDATE app_users 
                SET name = %s, designation = %s 
                WHERE designation = %s OR id = %s
            """, (name, designation, designation, id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Team member updated successfully!', 'success')
            return redirect(url_for('team_members_page'))
            
    cursor.execute("SELECT * FROM team_members WHERE id = %s", (id,))
    member = cursor.fetchone()
    
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('edit_team_member.html', member=member, departments=departments, user=current_user)

@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
