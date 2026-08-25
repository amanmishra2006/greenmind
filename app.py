import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from model.predict import predict_plant
from model.recommendations import recommendations
from model.soil_logic import analyze_soil
from model.store_data import plants_data, categories
from model.assistant_ai import get_answer

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.secret_key = "greenmind_secret_key"
PIXABAY_API_KEY = "56847495-917ce8f9934386465851ecbf9"

seasonal_plants = {
    "Summer": ["Watermelon", "Cucumber", "Okra", "Bottle Gourd", "Muskmelon", "Pumpkin", "Ridge Gourd", "Sweet Corn"],
    "Monsoon": ["Tomato", "Brinjal", "Chilli", "Turmeric", "Ginger", "Beans", "Maize", "Soybean"],
    "Winter": ["Carrot", "Cauliflower", "Peas", "Spinach", "Radish", "Garlic", "Onion", "Cabbage"]
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
def save_address(username, buyer_name, phone, address_line1, address_line2, landmark, city, state, pincode):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO saved_addresses (username, buyer_name, phone, address_line1, address_line2, landmark, city, state, pincode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            buyer_name=excluded.buyer_name, phone=excluded.phone, address_line1=excluded.address_line1,
            address_line2=excluded.address_line2, landmark=excluded.landmark, city=excluded.city,
            state=excluded.state, pincode=excluded.pincode
    """, (username, buyer_name, phone, address_line1, address_line2, landmark, city, state, pincode))
    conn.commit()
    conn.close()

def get_saved_address(username):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT buyer_name, phone, address_line1, address_line2, landmark, city, state, pincode FROM saved_addresses WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"buyer_name": row[0], "phone": row[1], "address_line1": row[2], "address_line2": row[3], "landmark": row[4], "city": row[5], "state": row[6], "pincode": row[7]}
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

    cart_count = len(session.get("cart", []))

    return render_template("home.html", season=season, plant_images=plant_images, stats=stats, farmer_image=farmer_image, weather=weather, cart_count=cart_count)

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

    bg_image = get_plant_image("blooming flowers lush garden green")
    return render_template("upload.html", message=message, bg_image=bg_image)

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
        watering=info["watering"],
        bg_image="images/result-bg.png"
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

    recommendations_result = None
    disclaimer = None
    if request.method == "POST":
        soil_type = request.form["soil_type"]
        ph = float(request.form["ph"])
        nitrogen = float(request.form["nitrogen"])
        phosphorus = float(request.form["phosphorus"])
        potassium = float(request.form["potassium"])
        moisture = float(request.form["moisture"])
        organic_matter = float(request.form["organic_matter"])

        recommendations_result, disclaimer = analyze_soil(soil_type, ph, nitrogen, phosphorus, potassium, moisture, organic_matter)

    bg_image = get_plant_image("soil field farmland")
    return render_template("soil.html", recommendations=recommendations_result, disclaimer=disclaimer, bg_image=bg_image)

@app.route("/store")
def store():
    if "username" not in session:
        return redirect("/login")

    plants_with_images = []
    for plant in plants_data:
        plant_copy = plant.copy()
        plant_copy["image"] = get_plant_image(plant["name"])
        plant_copy["is_user_listing"] = False
        plants_with_images.append(plant_copy)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, plant_name, price, quantity, category, description, seller_username, status FROM listings WHERE status = 'Available' AND quantity > 0")
    user_listings = cursor.fetchall()
    conn.close()

    for listing in user_listings:
        plants_with_images.append({
            "id": "user_" + str(listing[0]),
            "name": listing[1],
            "price": listing[2],
            "qty": listing[3],
            "category": listing[4],
            "desc": listing[5] or "Listed by a fellow gardener.",
            "seller": listing[6],
            "rating": 4.5,
            "maintenance": "Medium",
            "image": get_plant_image(listing[1]),
            "is_user_listing": True
        })

    bg_image = get_plant_image("plant nursery garden shop")
    return render_template("store.html", plants=plants_with_images, categories=categories, bg_image=bg_image)

@app.route("/cart/add/<int:plant_id>")
def add_to_cart(plant_id):
    if "username" not in session:
        return redirect("/login")

    if "cart" not in session:
        session["cart"] = []

    cart = session["cart"]
    cart.append(plant_id)
    session["cart"] = cart

    return redirect("/store")

@app.route("/cart/remove/<item_id>")
def remove_from_cart(item_id):
    if "username" not in session:
        return redirect("/login")

    cart = session.get("cart", [])
    new_cart = []
    for cid in cart:
        if str(cid) != str(item_id):
            new_cart.append(cid)
    session["cart"] = new_cart
    session.modified = True

    return redirect("/cart")

@app.route("/wishlist/add/<int:plant_id>")
def add_to_wishlist(plant_id):
    if "username" not in session:
        return redirect("/login")

    if "wishlist" not in session:
        session["wishlist"] = []

    wishlist = session["wishlist"]
    if plant_id not in wishlist:
        wishlist.append(plant_id)
    session["wishlist"] = wishlist

    return redirect("/store")

@app.route("/cart")
def view_cart():
    if "username" not in session:
        return redirect("/login")

    cart_ids = session.get("cart", [])
    cart_items = []

    for cid in cart_ids:
        if str(cid).startswith("user_"):
            listing_id = int(str(cid).replace("user_", ""))
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id, plant_name, price FROM listings WHERE id = ?", (listing_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                cart_items.append({"id": cid, "name": row[1], "price": row[2]})
        else:
            plant = next((p for p in plants_data if p["id"] == cid), None)
            if plant:
                cart_items.append({"id": plant["id"], "name": plant["name"], "price": plant["price"]})

    return render_template("cart.html", items=cart_items)

@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    if "username" not in session:
        return redirect("/login")

    selected_ids = request.form.getlist("selected_items")
    buyer_name = request.form["buyer_name"]
    phone = request.form["phone"]
    address_line1 = request.form["address_line1"]
    address_line2 = request.form["address_line2"]
    landmark = request.form.get("landmark", "")
    city = request.form["city"]
    state = request.form["state"]
    pincode = request.form["pincode"]
    address = f"{address_line1}, {address_line2}"
    if landmark:
        address += f" (Near {landmark})"
    address += f", {city}, {state} - {pincode}"
    save_address(session["username"], buyer_name, phone, address_line1, address_line2, landmark, city, state, pincode)

    cart_ids = session.get("cart", [])
    ordered_plants = []

    for cid in selected_ids:
        if cid.startswith("user_"):
            listing_id = int(cid.replace("user_", ""))
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT plant_name, price FROM listings WHERE id = ?", (listing_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                ordered_plants.append({"name": row[0], "price": row[1]})
        else:
            plant = next((p for p in plants_data if p["id"] == int(cid)), None)
            if plant:
                ordered_plants.append({"name": plant["name"], "price": plant["price"]})

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    total = 0
    for p in ordered_plants:
        cursor.execute(
            "INSERT INTO orders (username, plant_name, price, buyer_name, phone, address, order_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["username"], p["name"], p["price"], buyer_name, phone, address, datetime.now().strftime("%d-%m-%Y %H:%M"))
        )
        total += p["price"]
    conn.commit()
    conn.close()

    remaining_cart = [cid for cid in cart_ids if str(cid) not in selected_ids]
    session["cart"] = remaining_cart
    session.modified = True

    return render_template("cart_confirmation.html", ordered_plants=ordered_plants, total=total, buyer_name=buyer_name)

@app.route("/checkout/<plant_id>", methods=["GET", "POST"])
def checkout(plant_id):
    if "username" not in session:
        return redirect("/login")

    is_user_listing = str(plant_id).startswith("user_")
    plant = None
    available_qty = 0
    listing_id = None

    if is_user_listing:
        listing_id = int(str(plant_id).replace("user_", ""))
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, plant_name, price, quantity FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            plant = {"id": plant_id, "name": row[1], "price": row[2]}
            available_qty = row[3]
    else:
        plant = next((p for p in plants_data if p["id"] == int(plant_id)), None)
        if plant:
            available_qty = plant["qty"]

    if not plant:
        return redirect("/store")

    error = None
    if request.method == "POST":
        buyer_name = request.form["buyer_name"]
        phone = request.form["phone"]
        address_line1 = request.form["address_line1"]
        address_line2 = request.form["address_line2"]
        landmark = request.form.get("landmark", "")
        city = request.form["city"]
        state = request.form["state"]
        pincode = request.form["pincode"]
        address = f"{address_line1}, {address_line2}"
        if landmark:
            address += f" (Near {landmark})"
        address += f", {city}, {state} - {pincode}"
        order_qty = int(request.form["order_qty"])

        save_address(session["username"], buyer_name, phone, address_line1, address_line2, landmark, city, state, pincode)

        if order_qty > available_qty:
            error = f"Only {available_qty} unit(s) available. Please choose a lower quantity."
        else:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (username, plant_name, price, buyer_name, phone, address, order_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session["username"], plant["name"], plant["price"] * order_qty, buyer_name, phone, address, datetime.now().strftime("%d-%m-%Y %H:%M"))
            )

            if is_user_listing:
                new_qty = available_qty - order_qty
                cursor.execute("UPDATE listings SET quantity = ? WHERE id = ?", (new_qty, listing_id))

            conn.commit()
            conn.close()

            return render_template("order_confirmation.html", plant=plant, buyer_name=buyer_name, order_qty=order_qty)

    saved = get_saved_address(session["username"])
    return render_template("checkout.html", plant=plant, available_qty=available_qty, error=error, saved=saved)

@app.route("/sell", methods=["GET", "POST"])
def sell():
    if "username" not in session:
        return redirect("/login")

    message = ""
    if request.method == "POST":
        plant_name = request.form["plant_name"]
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        category = request.form["category"]
        description = request.form["description"]
        location = request.form["location"]
        delivery = request.form["delivery"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO listings (seller_username, plant_name, price, quantity, category, description, location, delivery, date_listed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session["username"], plant_name, price, quantity, category, description, location, delivery, datetime.now().strftime("%d-%m-%Y %H:%M"))
        )
        conn.commit()
        conn.close()

        message = "Thank you! Your plant listing has been submitted successfully."

    bg_image = get_plant_image("plant nursery garden shop")
    return render_template("sell.html", message=message, bg_image=bg_image)

@app.route("/my-listings")
def my_listings():
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, plant_name, price, quantity, category, location, delivery, date_listed, status FROM listings WHERE seller_username = ? ORDER BY id DESC",
        (session["username"],)
    )
    listings = cursor.fetchall()
    conn.close()

    return render_template("my_listings.html", listings=listings)

@app.route("/listing/toggle-status/<int:listing_id>")
def toggle_listing_status(listing_id):
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM listings WHERE id = ? AND seller_username = ?", (listing_id, session["username"]))
    row = cursor.fetchone()
    if row:
        new_status = "Out of Stock" if row[0] == "Available" else "Available"
        cursor.execute("UPDATE listings SET status = ? WHERE id = ?", (new_status, listing_id))
        conn.commit()
    conn.close()

    return redirect("/my-listings")

@app.route("/my-orders")
def my_orders():
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT plant_name, price, buyer_name, phone, address, order_date FROM orders WHERE username = ? ORDER BY id DESC",
        (session["username"],)
    )
    orders = cursor.fetchall()
    conn.close()

    return render_template("my_orders.html", orders=orders)

@app.route("/ai-chat", methods=["POST"])
def ai_chat():
    if "username" not in session:
        return {"answer": "🔒 Please login to use the AI Assistant.", "logged_in": False}

    question = request.form.get("question", "")
    answer = get_answer(question)
    return {"answer": answer, "logged_in": True}

if __name__ == "__main__":
    app.run(debug=True)