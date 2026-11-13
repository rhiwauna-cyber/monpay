import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

import os
import cv2
import base64
import numpy as np

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'monpay_super_secret_key_yang_sangat_aman_dan_panjang'

from flask_mail import Mail, Message
import random

# Konfigurasi Flask-Mail untuk Gmail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'rhiwauna@gmail.com'       # Ganti pakai email Gmail kamu
app.config['MAIL_PASSWORD'] = 'nokr gruh qytw dpyr'  # Ganti pakai 16 digit App Password Google
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

# Konfigurasi Database MySQL (Laragon/XAMPP)
# Konfigurasi Database MySQL (Otomatis deteksi Railway atau Local Laragon)
db_config = {
    'host': os.environ.get('MYSQLHOST', 'shuttle.proxy.rlwy.net'),
    'user': os.environ.get('MYSQLUSER', 'root'),
    'password': os.environ.get('MYSQLPASSWORD') or os.environ.get('MYSQL_ROOT_PASSWORD', ''),
    'database': os.environ.get('MYSQLDATABASE') or os.environ.get('MYSQL_DATABASE', 'monpay_db'),
    'port': int(os.environ.get('MYSQLPORT', 38481))
}
def get_db_connection():
    try:
        # Gunakan host publik Railway agar tidak timeout/tertahan jaringan internal
        connection = mysql.connector.connect(
            host=os.environ.get('MYSQLHOST', 'shuttle.proxy.rlwy.net'),
            user=os.environ.get('MYSQLUSER', 'root'),
            password=os.environ.get('MYSQLPASSWORD'),
            database=os.environ.get('MYSQLDATABASE', 'monpay_db'),
            port=int(os.environ.get('MYSQLPORT', 38481)),
            connection_timeout=10
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def send_otp_email(receiver_email, otp):
    try:
        msg = Message('Kode Verifikasi 2FA MonPay Ledger',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[receiver_email])

        msg.body = f"Halo,\n\nKode verifikasi Two-Factor Authentication (2FA) MonPay Anda adalah: {otp}\n\nKode ini berlaku selama 5 menit.\n\nSalam,\nMonPay Security Team"
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Gagal kirim email: {e}")
        return False

@app.route('/')
def index():
    if 'user_id' in session and session.get('face_verified'):
        return render_template('index.html')
    elif 'user_id' in session:
        return redirect(url_for('face_id_page'))
    return render_template('login.html')

# --- RUTE HALAMAN FACE ID ---
# --- RUTE HALAMAN FACE ID ---
@app.route('/face-id')
def face_id_page():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('face_id.html')

# RUTE LOGIN (TAHAP 1)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Koneksi database gagal!'}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cursor.fetchone()
    
    if not user:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Username atau password salah!'}), 401

    if user.get('is_locked', 0) == 1:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Akun terkunci karena 3x salah sandi!'}), 403

    password_matched = False
    try:
        if check_password_hash(user['password'], password):
            password_matched = True
    except ValueError:
        pass

    if not password_matched and user['password'] == password:
        password_matched = True

    if password_matched:
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=5)

        cursor.execute('UPDATE users SET failed_login_attempts = 0, otp_code = %s, otp_expiry = %s WHERE id = %s', (otp, expiry, user['id']))
        conn.commit()

        email_tujuan = user.get('email', user['username'])
        send_otp_email(email_tujuan, otp)
        
        cursor.close()
        conn.close()

        print(f"\n[KODE OTP 2FA DARI TERMINAL]: {otp}\n")

        return jsonify({
            'status': 'require_otp', 
            'message': 'Password benar! Masukkan kode OTP.',
            'username': username
        })
    else:
        attempts = user.get('failed_login_attempts', 0) + 1
        if attempts >= 3:
            cursor.execute('UPDATE users SET failed_login_attempts = %s, is_locked = 1 WHERE id = %s', (attempts, user['id']))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Akun terkunci karena 3x salah sandi.'}), 403
        else:
            cursor.execute('UPDATE users SET failed_login_attempts = %s WHERE id = %s', (attempts, user['id']))
            conn.commit()
            cursor.close()
            conn.close()
            sisa = 3 - attempts
            return jsonify({'status': 'error', 'message': f'Password salah! Sisa kesempatan {sisa} kali.'}), 401

# RUTE VERIFIKASI OTP (TAHAP 2)
@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json or {}
    username = data.get('username')
    entered_otp = data.get('otp')

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Koneksi database gagal!'}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'User tidak ditemukan'}), 404

    if user.get('otp_code') and user['otp_code'] == entered_otp:
        if user.get('otp_expiry') and datetime.now() <= user['otp_expiry']:
            cursor.execute('UPDATE users SET otp_code = NULL, otp_expiry = NULL WHERE id = %s', (user['id'],))
            conn.commit()
            cursor.close()
            conn.close()

            # Set sesi login, tapi belum diverifikasi face ID (mengarahkan ke /face-id)
            session['user_id'] = user['id']
            session['face_verified'] = False 
            
            return jsonify({'status': 'success', 'message': 'OTP Berhasil! Lanjutkan ke Face ID.'})
        else:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Kode OTP kedaluwarsa!'}), 400
    else:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Kode OTP salah!'}), 400

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/user-data', methods=['GET'])
def get_user_data():
    if 'user_id' not in session or not session.get('face_verified'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT full_name, account_number, balance FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute('SELECT type, title, recipient, amount, category, date FROM transactions WHERE user_id = %s ORDER BY id DESC', (session['user_id'],))
    transactions = cursor.fetchall()

    cursor.close()
    conn.close()

    for t in transactions:
        t['amount'] = float(t['amount'])
        t['date'] = t['date'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(t['date'], datetime) else str(t['date'])

    return jsonify({
        'status': 'success',
        'user': {
            'full_name': user['full_name'],
            'account_number': user['account_number'],
            'balance': float(user['balance'])
        },
        'transactions': transactions
    })

@app.route('/api/transaction', methods=['POST'])
def process_transaction():
    if 'user_id' not in session or not session.get('face_verified'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    tx_type = data.get('type')
    title = data.get('title')
    recipient = data.get('recipient')
    amount = float(data.get('amount', 0))
    category = data.get('category')

    if amount <= 0:
        return jsonify({'status': 'error', 'message': 'Nominal tidak valid!'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT balance FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()
    current_balance = float(user['balance'])

    if tx_type == 'OUT' and current_balance < amount:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Saldo tidak mencukupi!'}), 400

    new_balance = current_balance + amount if tx_type == 'IN' else current_balance - amount

    cursor.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, session['user_id']))
    cursor.execute('''
        INSERT INTO transactions (user_id, type, title, recipient, amount, category)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (session['user_id'], tx_type, title, recipient, amount, category))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'status': 'success',
        'message': 'Transaksi berhasil diproses',
        'new_balance': new_balance
    })

# --- AUTO-DOWNLOAD & LOAD CASCADE DETECTOR ---
import urllib.request

FACE_DIR = 'face_data'
if not os.path.exists(FACE_DIR):
    os.makedirs(FACE_DIR)

cascade_path = os.path.join(FACE_DIR, 'haarcascade_frontalface_default.xml')
if not os.path.exists(cascade_path):
    url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
    try:
        urllib.request.urlretrieve(url, cascade_path)
    except Exception as e:
        print("Gagal download cascade:", e)

face_cascade = cv2.CascadeClassifier(cascade_path)
def decode_base64_image(data_url):
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)

@app.route('/process-face-id', methods=['POST'])
def process_face_id():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Sesi login habis, silakan login ulang.'}), 401

    user_id = str(session['user_id'])
    model_path = os.path.join(FACE_DIR, f'model_{user_id}.yml')
    
    data = request.get_json()
    action = data.get('action') # 'register' atau 'verify'
    image_data = data.get('image')

    if not image_data:
        return jsonify({'success': False, 'message': 'Gambar tidak diterima.'})

    gray_img = decode_base64_image(image_data)
    faces = face_cascade.detectMultiScale(gray_img, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))

    if len(faces) == 0:
        return jsonify({'success': False, 'message': 'Wajah tidak terdeteksi! Posisikan wajah jelas di depan kamera.'})

    # Ambil area wajah terbesar yang terdeteksi
    (x, y, w, h) = faces[0]
    face_roi = cv2.resize(gray_img[y:y+h, x:x+w], (200, 200))

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    # MODE 1: DAFTARKAN WAJAH LU PERTAMA KALI
    if action == 'register' or not os.path.exists(model_path):
        # Latih model khusus dengan wajah lu saat ini
        recognizer.train([face_roi], np.array([int(user_id)]))
        recognizer.save(model_path)
        session['face_verified'] = True
        return jsonify({
            'success': True, 
            'message': 'Wajah berhasil didaftarkan sebagai kunci biometrik!',
            'redirect': url_for('index')
        })

    # MODE 2: VERIFIKASI WAJAH (MENCOCOKKAN DENGAN WAJAH LU)
    recognizer.read(model_path)
    label, confidence = recognizer.predict(face_roi)

    # Di LBPH OpenCV, makin KECIL angka confidence = makin MIRIP.
    # Batas aman biasanya di bawah 65 - 75. Kalau muka orang lain, angkanya bakal di atas 85-100+.
    print(f"[DEBUG FACE ID] User: {user_id} | Confidence Score: {confidence}")

    if confidence < 70:
        session['face_verified'] = True
        return jsonify({
            'success': True, 
            'message': f'Wajah dikenali! (Skor kemiripan: {round(100 - confidence, 1)}%)',
            'redirect': url_for('index')
        })
    else:
        return jsonify({
            'success': False, 
            'message': 'AKSES DITOLAK! Wajah tidak cocok dengan pemilik akun ini.'
        })

    # --- RUTE KIRIM OTP KE EMAIL ---
@app.route('/api/send-otp', methods=['POST'])
def api_send_otp():
    data = request.json or {}
    username = data.get('username')

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Koneksi database gagal!'}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'User tidak ditemukan'}), 404

    # Generate OTP 6 digit
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=5)

    # Simpan OTP ke database
    cursor.execute('UPDATE users SET otp_code = %s, otp_expiry = %s WHERE id = %s', (otp, expiry, user['id']))
    conn.commit()
    cursor.close()
    conn.close()

    # Kirim via Flask-Mail ke email user
    receiver_email = user.get('email', user['username']) # Sesuaikan kalau kolom email beda
    
    try:
        msg = Message('Kode Verifikasi 2FA MonPay Ledger',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[receiver_email])

        msg.body = f"Halo {user.get('full_name', 'User')},\n\nKode verifikasi Two-Factor Authentication (2FA) MonPay Anda adalah: {otp}\n\nKode ini berlaku selama 5 menit.\n\nSalam,\nMonPay Security Team"
        
        mail.send(msg)
        return jsonify({'status': 'success', 'message': 'Kode OTP berhasil dikirim ke email!'})
    except Exception as e:
        print(f"Gagal kirim email: {e}")
        return jsonify({'status': 'error', 'message': f'Gagal mengirim email: {str(e)}'}), 500
