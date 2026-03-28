from flask import Flask, request, redirect, session, render_template, jsonify, send_from_directory, url_for, make_response, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import bcrypt
import os
import secrets
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta

# --- CONFIGURACIÓN DE RUTAS DINÁMICAS (COMPATIBILIDAD SERVER/LAPTOP) ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Si existe la ruta del servidor la usa, si no, usa la carpeta actual del script
WORK_DIR = "/srv/app" if os.path.exists("/srv/app") else BASE_DIR

LOG_FILE = os.path.join(WORK_DIR, "nas_app.log")
DB = os.path.join(WORK_DIR, "users.db")
NAS = os.path.join(WORK_DIR, "nas", "users")
PUBLIC_NAS = os.path.join(WORK_DIR, "nas", "public")

# --- INICIALIZACIÓN AUTOMÁTICA DE INFRAESTRUCTURA ---
def init_infrastructure():
    """Crea carpetas, DB y solicita el primer admin si no existe."""
    print("\n[!] Verificando infraestructura del sistema...")
    
    # Crear directorios
    for folder in [NAS, PUBLIC_NAS, os.path.dirname(LOG_FILE)]:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            print(f"[OK] Carpeta creada: {folder}")

    # Inicializar Base de Datos
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                  password TEXT NOT NULL, 
                  role TEXT DEFAULT 'user')''')
    
    # Verificar si el sistema está vacío (Primer inicio)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        print("\n" + "="*50)
        print("CONFIGURACIÓN DE PRIMER ADMINISTRADOR (MODO SETUP)")
        print("="*50)
        new_user = input("Nombre de usuario admin: ")
        new_pass = input("Contraseña admin: ")
        
        hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt(12))
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      (new_user, hashed.decode(), 'admin'))
            conn.commit()
            print(f"\n[OK] Administrador '{new_user}' creado exitosamente.")
            os.makedirs(os.path.join(NAS, new_user), exist_ok=True)
        except Exception as e:
            print(f"[ERROR] No se pudo crear el usuario: {e}")
    
    conn.close()
    print("[OK] Sistema listo.\n")

init_infrastructure()

# --- CONFIGURACIÓN DE LOGS (ROTATIVOS) ---
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-7s | %(name)s | %(message)s'))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
logger = logging.getLogger("nas_app")

# --- CLASES Y LOGIN MANAGER ---
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
csrf = CSRFProtect(app)

app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024 * 1024 # 1GB limit
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=4),
    SESSION_REFRESH_EACH_REQUEST=True
)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor inicia sesión primero."

limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])
Talisman(app, content_security_policy={
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
})

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'zip'}
MAX_USER_QUOTA = 5 * 1024 * 1024 * 1024 # 5 GB

# --- UTILIDADES ---
def log_action(level, message, extra=None):
    user_val = current_user.username if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else "anonymous"
    ctx = {"user": user_val, "ip": request.remote_addr, "path": request.path, **(extra or {})}
    logger.log(level, message, extra=ctx)

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return User(row[0], row[1], row[2]) if row else None

def ensure_user_folder(user):
    path = os.path.join(NAS, user)
    os.makedirs(path, exist_ok=True)
    return path

def get_folder_size(path):
    return sum(f.stat().st_size for f in os.scandir(path) if f.is_file())

# --- RUTAS DE NAVEGACIÓN ---
@app.route("/", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username, password = request.form.get("user"), request.form.get("pass")
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT id, password, role FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        if row and bcrypt.checkpw(password.encode(), row[1].encode()):
            login_user(User(row[0], username, row[2]))
            log_action(logging.INFO, "Login exitoso")
            return redirect(url_for("dashboard"))
        log_action(logging.WARNING, "Login fallido", {"username_attempt": username})
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=current_user.username)

# --- API DE ARCHIVOS ---
@app.route("/api/files", methods=["GET"])
@app.route("/api/files/<target_user>", methods=["GET"])
@login_required
def list_files(target_user=None):
    user_to_view = target_user if (current_user.role == "admin" and target_user) else current_user.username
    folder = ensure_user_folder(user_to_view)
    files = []
    for f in os.listdir(folder):
        if os.path.isfile(os.path.join(folder, f)):
            size = os.path.getsize(os.path.join(folder, f))
            files.append({
                "name": f, "size": size,
                "size_human": f"{size / 1024 / 1024:.2f} MB",
                "modified": os.path.getmtime(os.path.join(folder, f))
            })
    return jsonify({"status": "ok", "user": user_to_view, "files": files, "total_size_mb": get_folder_size(folder)/1024**2})

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get('file')
    if not file or file.filename == '' or not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
        return jsonify({"error": "Archivo no permitido"}), 400
    
    filename = secure_filename(file.filename)
    folder = ensure_user_folder(current_user.username)
    if get_folder_size(folder) + (file.content_length or 0) > MAX_USER_QUOTA:
        return jsonify({"error": "Cuota excedida"}), 403

    save_path = os.path.join(folder, filename)
    file.save(save_path)
    log_action(logging.INFO, f"Archivo subido: {filename}")
    return jsonify({"status": "ok", "filename": filename})

@app.route("/download/<filename>")
@login_required
def download_file(filename):
    folder = ensure_user_folder(current_user.username)
    file_path = os.path.join(folder, filename)
    if not os.path.isfile(file_path): return jsonify({"error": "No existe"}), 404
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route("/api/files/<filename>", methods=["DELETE"])
@login_required
@csrf.exempt
def delete_file(filename):
    folder = ensure_user_folder(current_user.username)
    path = os.path.join(folder, filename)
    if os.path.isfile(path):
        os.remove(path)
        log_action(logging.INFO, f"Archivo eliminado: {filename}")
        return jsonify({"status": "ok"})
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/haloce", methods=["GET"])
@login_required
def download_haloce():
    response = make_response()
    response.headers["Content-Disposition"] = "attachment; filename=HaloCE.zip"
    response.headers["X-Accel-Redirect"] = "/protected/haloce"
    response.headers["Content-Type"] = "application/zip"
    return response

@app.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    # Host 0.0.0.0 para que sea accesible en tu red local (DuckDNS/VPN)
    app.run(host="0.0.0.0", port=5000)
