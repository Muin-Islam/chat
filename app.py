from datetime import datetime
import os
from uuid import uuid4
from flask import (
    Flask, render_template, redirect, url_for,
    request, flash, send_from_directory, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from config import Config
from flask_socketio import SocketIO
import os

# ----------------- App / extensions -----------------
app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet", manage_session=False)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Use PORT from Render or default to 5000
    socketio.run(app, host='0.0.0.0', port=port)

app.config.from_object(Config)

db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode="eventlet", manage_session=False)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ----------------- Models -----------------
class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)   # hashed
    messages = db.relationship("Message", backref="author", lazy=True)

class Message(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    type      = db.Column(db.String(10), default="text")  # 'text' or 'image'
    content   = db.Column(db.Text, nullable=True)         # text body
    filename  = db.Column(db.String(260), nullable=True)  # image path
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

# ----------------- Login -----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ----------------- Helpers -----------------
def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )

# ----------------- Routes -----------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))

from werkzeug.security import check_password_hash, generate_password_hash

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email    = request.form["email"]
        password = request.form["password"]

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.")
            return redirect(url_for("register"))

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("chat"))
        flash("Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/chat")
@login_required
def chat():
    history = (
        Message.query.order_by(Message.timestamp.asc())
        .limit(100)
        .all()
    )
    return render_template("chat.html", history=history)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(f"{uuid4().hex}_{file.filename}")
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(save_path)

    # Save DB record
    msg = Message(type="image", filename=filename, user_id=current_user.id)
    db.session.add(msg)
    db.session.commit()

    # Broadcast via SocketIO
    emit_data = {
        "type": "image",
        "username": current_user.username,
        "url": url_for("uploaded_file", filename=filename)
    }
    socketio.emit("new_message", emit_data, to='*')
    return jsonify(emit_data), 201

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ----------------- Socket.IO events -----------------
@socketio.on("text_message")
def handle_text(msg):
    if not current_user.is_authenticated:
        return
    # Save message
    m = Message(type="text", content=msg, user_id=current_user.id)
    db.session.add(m)
    db.session.commit()

    emit("new_message", {
        "type": "text",
        "username": current_user.username,
        "content": msg
    }, to='*')

@socketio.on("connect")
def announce_user():
    if current_user.is_authenticated:
        emit("user_status", {
            "msg": f"🟢 {current_user.username} connected."
        }, broadcast=True)

@socketio.on("disconnect")
def left_user():
    if current_user.is_authenticated:
        emit("user_status", {
            "msg": f"🔴 {current_user.username} disconnected."
        }, broadcast=True)

# ----------------- Main -----------------
