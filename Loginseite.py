from flask import Flask, render_template, request, redirect, url_for, session, flash,g, send_from_directory
import sqlite3
import os
import hashlib
import re
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'klaus'  # Erforderlich für Session-Management

UPLOAD_FOLDER = 'uploads' 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 
if not os.path.exists(UPLOAD_FOLDER): 
   os.path.join(os.makedirs(UPLOAD_FOLDER))

# Bestimme den relativen Pfad zur Datenbank im gleichen Verzeichnis wie app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'Data.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                datetime TEXT,
                IPadresse BLOB
            )
        ''')
        db.commit()

init_db()

class File: 
    def __init__(self, name, uploader, upload_date, description): 
        self.name = name 
        self.uploader = uploader 
        self.upload_date = upload_date 
        self.description = description 
files = []

def is_valid_username(username):
    return re.match("^[A-Za-z0-9_]+$", username) is not None

@app.route("/", methods=["GET", "POST"])
def home():
    db = get_db() 
    cursor = db.cursor() 
    cursor.execute("SELECT * FROM files") 
    files = cursor.fetchall() 
    db.close() 
    return render_template("home.html", files=files)
   

@app.route("/upload", methods=["POST"])
def upload():
 
    file = request.files['file']
    description = request.form['description']
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

 
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone() # Hier den richtigen Nutzernamen einfügen
    upload_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    new_file = File(filename, user, upload_date, description)
    files.append(new_file)
    
    flash("Datei erfolgreich hochgeladen!")
    return redirect(url_for('home'))

@app.route("/file/<filename>")
def file_detail(filename):
    file = next((f for f in files if f.name == filename), None)
    if file:
        return render_template("file_detail.html", file=file)
    else:
        return "Datei nicht gefunden", 404

@app.route("/downloads/<filename>")
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not is_valid_username(username):
            flash("Ungültiger Benutzername. Nur Buchstaben, Zahlen und Unterstriche sind erlaubt.")
            return redirect(url_for('register'))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash("Dieser Benutzername ist bereits vergeben. Bitte wähle einen anderen.")
            return redirect(url_for('register'))

        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

        nowtime = datetime.now()       
        formatted_date_time = nowtime.strftime("%d/%m/%Y %H:%M:%S")
        REMOTEADDR = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ['REMOTE_ADDR'])

        cursor.execute("INSERT INTO users (username, email, password, datetime, IPadresse) VALUES (?, ?, ?, ?, ?)", 
                        (username, email, hashed_password, formatted_date_time, REMOTEADDR))
        db.commit()
        
        flash("Registrierung erfolgreich!")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and user[3] == hashed_password:  # Assuming the password is in the fourth column
            session['user_id'] = user[0]
            flash("Login erfolgreich!")
            return redirect(url_for('dashboard'))
        else:
            flash("Login fehlgeschlagen, bitte überprüfe deine Anmeldedaten.")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if 'user_id' in session:
        return render_template("home.html")
    else:
        return redirect(url_for('login'))

@app.route("/profil", methods=["GET", "POST"])
def profil():
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        if request.method == "POST":
            new_username = request.form.get("new_username")
            new_email = request.form.get("new_email")

            # Überprüfe, ob der neue Benutzername gültig ist
            if not is_valid_username(new_username):
                flash("Ungültiger Benutzername. Nur Buchstaben, Zahlen und Unterstriche sind erlaubt.")
                return redirect(url_for('profil'))

            # Aktualisiere die Benutzerdaten
            cursor.execute("UPDATE users SET username = ?, email = ? WHERE id = ?", 
                           (new_username, new_email, session['user_id']))
            db.commit()
            flash("Profil erfolgreich aktualisiert!")
            return redirect(url_for('profil'))

        if user:
            user_data = {
                "username": user[1],
                "email": user[2],
                "datetime": user[4]
            }
            return render_template("profil.html", user=user_data)
    return redirect(url_for('login'))

@app.route("/logout", methods=["POST"])
def logout():
    session.pop('user_id', None)
    flash("Erfolgreich abgemeldet!")
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
