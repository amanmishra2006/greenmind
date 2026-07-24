from datetime import datetime
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from model.predict import predict_plant
from model.recommendations import recommendations

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.secret_key = "greenmind_secret_key"

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            message = "Username already taken!"
            conn.close()

    return render_template("register.html", message=message)

@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["username"] = username
            return redirect("/")
        else:
            message = "Invalid username or password!"

    return render_template("login.html", message=message)

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    message = ""
    if request.method == "POST":
        if "username" not in session:
            return redirect("/login")

        file = request.files["plant_image"]
        if file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)
            return redirect("/result?filename=" + file.filename)

    return render_template("upload.html", message=message)

@app.route("/result")
def result():
    filename = request.args.get("filename")
    filepath = "static/uploads/" + filename

    condition, confidence = predict_plant(filepath)
    info = recommendations[condition]
    confidence_percent = round(confidence * 100, 2)

    # Database me save karo
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO plant_history (username, filename, condition_detected, confidence, upload_date) VALUES (?, ?, ?, ?, ?)",
        (session["username"], filename, condition, confidence_percent, datetime.now().strftime("%d-%m-%Y %H:%M"))
    )
    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        filename=filename,
        condition=condition,
        confidence=confidence_percent,
        fertilizer=info["fertilizer"],
        watering=info["watering"]
    )

@app.route("/history")
def history():
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT filename, condition_detected, confidence, upload_date FROM plant_history WHERE username = ? ORDER BY id DESC",
        (session["username"],)
    )
    records = cursor.fetchall()
    conn.close()

    return render_template("history.html", records=records)

if __name__ == "__main__":
    app.run(debug=True)