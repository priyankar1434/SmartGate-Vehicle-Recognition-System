from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import sqlite3, cv2, pytesseract, os
from datetime import datetime
from PIL import Image

app = Flask(__name__)

# Tesseract Path (Windows Default)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DB_PATH = "database/vehicles.db"

# --- DB Helper Functions ---
def init_db():
    if not os.path.exists("database"):
        os.makedirs("database")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Authorized vehicles table
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT NOT NULL,
                owner_name TEXT NOT NULL)''')
    # Logs table
    c.execute('''CREATE TABLE IF NOT EXISTS vehicle_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT,
                status TEXT,
                timestamp TEXT)''')
    conn.commit()
    conn.close()

# Initialize DB and preload data
def preload_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM authorized_vehicles")
    if c.fetchone()[0] == 0:
        sample = [("UP65AB1234", "Prof. Sharma"), ("UP65CD5678", "Staff Urvashi")]
        c.executemany("INSERT INTO authorized_vehicles(vehicle_number, owner_name) VALUES (?,?)", sample)
        conn.commit()
    conn.close()

# Log entry
def log_vehicle(number, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO vehicle_logs(vehicle_number, status, timestamp) VALUES (?,?,?)",
              (number, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# Check authorized vehicle
def is_authorized(number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM authorized_vehicles WHERE vehicle_number=?", (number,))
    result = c.fetchone()
    conn.close()
    return result

# Import vehicles from Excel (optional utility)
def import_vehicles_from_excel(excel_path):
    import pandas as pd
    df = pd.read_excel(excel_path)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for _, row in df.iterrows():
        c.execute("INSERT INTO authorized_vehicles(vehicle_number, owner_name) VALUES (?, ?)",
                  (row['vehicle_number'], row['owner_name']))
    conn.commit()
    conn.close()

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs')
def logs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT vehicle_number, status, timestamp FROM vehicle_logs ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return render_template('logs.html', logs=data)

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        print("No image in request")
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    if file.filename == '':
        print("No selected file")
        return jsonify({'error': 'No selected file'}), 400
    filepath = "temp.jpg"
    file.save(filepath)
    print("File saved:", os.path.exists(filepath))
    import time; time.sleep(0.1)
    img = cv2.imread(filepath)
    if img is None:
        print("cv2.imread failed")
        os.remove(filepath)
        return jsonify({'error': 'Invalid image file'}), 400

    # --- Improved OCR Processing ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)  # Resize for better OCR
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config='--psm 8').strip().replace(" ", "").upper()
    print("OCR Output:", text)
    # --------------------------------

    if is_authorized(text):
        status = "Authorized"
    else:
        status = "Unauthorized"
    log_vehicle(text, status)
    os.remove(filepath)
    return jsonify({'number': text, 'status': status})

@app.route('/export_csv')
def export_csv():
    csv_path = "vehicle_logs.csv"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT vehicle_number, status, timestamp FROM vehicle_logs")
    data = c.fetchall()
    conn.close()

    # Write CSV
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("Vehicle Number,Status,Timestamp\n")
        for row in data:
            f.write(",".join(str(item) for item in row) + "\n")

    return send_file(csv_path, as_attachment=True)

# Route to add authorized vehicle via web form
@app.route('/add_vehicle', methods=['GET', 'POST'])
def add_vehicle():
    msg = ""
    if request.method == 'POST':
        number = request.form.get('vehicle_number', '').strip().upper()
        owner = request.form.get('owner_name', '').strip()
        if number and owner:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO authorized_vehicles(vehicle_number, owner_name) VALUES (?,?)", (number, owner))
            conn.commit()
            conn.close()
            msg = "Vehicle added successfully!"
        else:
            msg = "Please provide both vehicle number and owner name."
    return render_template('add_vehicle.html', msg=msg)

if __name__ == '__main__':
    init_db()
    preload_data()
    # import_vehicles_from_excel('vehicles.xlsx')  # Uncomment if you want to import from Excel
    app.run(debug=True)