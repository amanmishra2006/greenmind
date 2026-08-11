import requests
from model.soil_logic import analyze_soil
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
PIXABAY_API_KEY = "56847495-917ce8f9934386465851ecbf9"

seasonal_plants = {
    "Summer": ["Watermelon", "Cucumber", "Okra", "Bottle Gourd"],
    "Monsoon": ["Tomato", "Brinjal", "Chilli", "Turmeric"],
    "Winter": ["Carrot", "Cauliflower", "Peas", "Spinach"]
}

def get_current_season():
    month = datetime.today().month
    if month in [3, 4, 5, 6]:
        return "Summer"
    elif month in [7, 8, 9]:
        return "Monsoon"
    else:
        return "Winter"

def get_plant_image(plant_name):
    try:
        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={plant_name}+plant&image_type=photo&per_page=3"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data["hits"]:
            return data["hits"][0]["webformatURL"]
    except Exception:
        pass
    return "https://via.placeholder.com/300x200?text=No+Image"
def get_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&current=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia%2FKolkata"
        response = requests.get(url, timeout=5)
        data = response.json()
        current = data["current"]
        return {
            "temp": current["temperature_2m"],
            "humidity": current["relative_humidity_2m"],
            "rain": current["precipitation"]
        }
    except Exception:
        return None

@app.route("/")
def home():
    season = get_current_season()
    plant_names = seasonal_plants[season]
    plant_images = [{"name": name, "image": get_plant_image(name)} for name in plant_names]
    farmer_image = get_plant_image("indian farmer field")
    weather = get_weather()

    stats = None
    if "username" in session:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM plant_history WHERE username = ?", (session["username"],))
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM plant_history WHERE username = ? AND condition_detected = 'Healthy'", (session["username"],))
        healthy = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM plant_history WHERE username = ? AND condition_detected != 'Healthy'", (session["username"],))
        issues = cursor.fetchone()[0]
        conn.close()
        stats = {"total": total, "healthy": healthy, "issues": issues}

    return render_template("home.html", season=season, plant_images=plant_images, stats=stats, farmer_image=farmer_image, weather=weather)

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
    if "username" not in session:
        return redirect("/login")

    message = ""
    if request.method == "POST":
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

@app.route("/admin")
def admin():
    if "username" not in session or session["username"] != "amanmishra":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM plant_history")
    total_scans = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM plant_history WHERE condition_detected = 'Healthy'")
    healthy_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM plant_history WHERE condition_detected != 'Healthy'")
    issue_count = cursor.fetchone()[0]

    cursor.execute("SELECT username, filename, condition_detected, upload_date FROM plant_history ORDER BY id DESC LIMIT 10")
    recent_scans = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_scans=total_scans,
        healthy_count=healthy_count,
        issue_count=issue_count,
        recent_scans=recent_scans
    )
@app.route("/soil", methods=["GET", "POST"])
def soil():
    if "username" not in session:
        return redirect("/login")

    recommendations = None
    disclaimer = None
    if request.method == "POST":
        soil_type = request.form["soil_type"]
        ph = float(request.form["ph"])
        nitrogen = float(request.form["nitrogen"])
        phosphorus = float(request.form["phosphorus"])
        potassium = float(request.form["potassium"])
        moisture = float(request.form["moisture"])
        organic_matter = float(request.form["organic_matter"])

        recommendations, disclaimer = analyze_soil(soil_type, ph, nitrogen, phosphorus, potassium, moisture, organic_matter)

    return render_template("soil.html", recommendations=recommendations, disclaimer=disclaimer)
if __name__ == "__main__":
    app.run(debug=True)