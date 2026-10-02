import requests
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from uuid import uuid4

from model.predict import predict_plant
from model.recommendations import recommendations
from model.store_data import plants_data, categories
from model.assistant_ai import get_answer


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.secret_key = "greenmind_secret_key"

PIXABAY_API_KEY = "56847495-917ce8f9934386465851ecbf9"


# ============================================================
# CACHE
# ============================================================

_cache = {
    "weather": None,
    "weather_time": 0,
    "images": {},
    "images_time": {}
}

CACHE_DURATION = 600  # 10 minutes


def ensure_marketplace_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_username TEXT NOT NULL,
            plant_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            location TEXT,
            delivery TEXT,
            date_listed TEXT NOT NULL,
            status TEXT DEFAULT 'Available'
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            plant_name TEXT NOT NULL,
            price REAL NOT NULL,
            buyer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            order_date TEXT NOT NULL
        )
        """
    )

    listing_columns = {
        column[1]
        for column in connection.execute("PRAGMA table_info(listings)")
    }
    if "approval_status" not in listing_columns:
        connection.execute(
            "ALTER TABLE listings ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'Approved'"
        )
    if "image_filename" not in listing_columns:
        connection.execute(
            "ALTER TABLE listings ADD COLUMN image_filename TEXT NOT NULL DEFAULT ''"
        )

    order_columns = {
        column[1]
        for column in connection.execute("PRAGMA table_info(orders)")
    }
    if "order_status" not in order_columns:
        connection.execute(
            "ALTER TABLE orders ADD COLUMN order_status TEXT NOT NULL DEFAULT 'Placed'"
        )
    connection.commit()


@app.context_processor
def inject_marketplace_notice():
    if session.get("username") != "amanmishra":
        return {}

    connection = sqlite3.connect("database.db")
    ensure_marketplace_schema(connection)
    pending_count = connection.execute(
        "SELECT COUNT(*) FROM listings WHERE approval_status = 'Pending'"
    ).fetchone()[0]
    connection.close()
    return {"pending_listing_count": pending_count}


# ============================================================
# SEASONAL PLANTS
# ============================================================

seasonal_plants = {
    "Summer": [
        "Watermelon",
        "Cucumber",
        "Okra",
        "Bottle Gourd",
        "Muskmelon",
        "Pumpkin",
        "Ridge Gourd",
        "Sweet Corn"
    ],

    "Monsoon": [
        "Tomato",
        "Brinjal",
        "Chilli",
        "Turmeric",
        "Ginger",
        "Beans",
        "Maize",
        "Soybean"
    ],

    "Winter": [
        "Carrot",
        "Cauliflower",
        "Peas",
        "Spinach",
        "Radish",
        "Garlic",
        "Onion",
        "Cabbage"
    ]
}


# ============================================================
# CURRENT SEASON
# ============================================================

def get_current_season():
    month = datetime.today().month

    if month in [3, 4, 5, 6]:
        return "Summer"

    elif month in [7, 8, 9]:
        return "Monsoon"

    else:
        return "Winter"


# ============================================================
# GET PLANT IMAGE
# ============================================================

def get_plant_image(plant_name):
    now = time.time()

    # Use cached image if available
    if (
        plant_name in _cache["images"]
        and
        (now - _cache["images_time"].get(plant_name, 0)) < CACHE_DURATION
    ):
        return _cache["images"][plant_name]

    try:
        url = (
            f"https://pixabay.com/api/"
            f"?key={PIXABAY_API_KEY}"
            f"&q={plant_name}+plant"
            f"&image_type=photo"
            f"&per_page=3"
        )

        response = requests.get(url, timeout=5)
        response.raise_for_status()

        data = response.json()

        if data.get("hits"):
            image_url = data["hits"][0]["webformatURL"]

            _cache["images"][plant_name] = image_url
            _cache["images_time"][plant_name] = now

            return image_url

    except Exception as e:
        app.logger.error(f"Plant image API error for {plant_name}: {e}")

    return _cache["images"].get(
        plant_name,
        "https://via.placeholder.com/300x200?text=No+Image"
    )


# ============================================================
# GET WEATHER
# ============================================================

def get_weather():
    now = time.time()

    # Return cached weather if still valid
    if (
        _cache["weather"]
        and
        (now - _cache["weather_time"]) < CACHE_DURATION
    ):
        return _cache["weather"]

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=28.6139"
            "&longitude=77.2090"
            "&current=temperature_2m,relative_humidity_2m,precipitation"
            "&timezone=Asia%2FKolkata"
        )

        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "GreenMind/1.0"
            }
        )

        # Check HTTP response
        response.raise_for_status()

        data = response.json()

        # Check API response
        if "current" not in data:
            raise ValueError(
                "Weather API did not return current weather data"
            )

        current = data["current"]

        weather = {
            "temp": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "rain": current.get("precipitation")
        }

        # Save successful weather data
        _cache["weather"] = weather
        _cache["weather_time"] = now

        return weather

    except Exception as e:
        # This will appear in Render logs
        app.logger.error(f"Weather API error: {e}")

        # Use old cached weather if available
        if _cache["weather"]:
            return _cache["weather"]

        # Keep weather card visible even if API fails
        return {
            "temp": "N/A",
            "humidity": "N/A",
            "rain": "N/A"
        }


# ============================================================
# SAVE ADDRESS
# ============================================================

def save_address(
    username,
    buyer_name,
    phone,
    address_line1,
    address_line2,
    landmark,
    city,
    state,
    pincode
):
    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO saved_addresses
        (
            username,
            buyer_name,
            phone,
            address_line1,
            address_line2,
            landmark,
            city,
            state,
            pincode
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(username) DO UPDATE SET
            buyer_name=excluded.buyer_name,
            phone=excluded.phone,
            address_line1=excluded.address_line1,
            address_line2=excluded.address_line2,
            landmark=excluded.landmark,
            city=excluded.city,
            state=excluded.state,
            pincode=excluded.pincode
        """,
        (
            username,
            buyer_name,
            phone,
            address_line1,
            address_line2,
            landmark,
            city,
            state,
            pincode
        )
    )

    conn.commit()
    conn.close()


# ============================================================
# GET SAVED ADDRESS
# ============================================================

def get_saved_address(username):
    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            buyer_name,
            phone,
            address_line1,
            address_line2,
            landmark,
            city,
            state,
            pincode
        FROM saved_addresses
        WHERE username = ?
        """,
        (username,)
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            "buyer_name": row[0],
            "phone": row[1],
            "address_line1": row[2],
            "address_line2": row[3],
            "landmark": row[4],
            "city": row[5],
            "state": row[6],
            "pincode": row[7]
        }

    return None


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    season = get_current_season()

    plant_names = seasonal_plants[season]

    plant_images = [
        {
            "name": name,
            "image": get_plant_image(name)
        }
        for name in plant_names
    ]

    farmer_image = "/static/images/dashboard-foliage.jpg"

    weather = get_weather()

    stats = None

    if "username" in session:
        conn = sqlite3.connect("database.db")
        ensure_marketplace_schema(conn)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM plant_history WHERE username = ?",
            (session["username"],)
        )

        total = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM plant_history
            WHERE username = ?
            AND condition_detected = 'Healthy'
            """,
            (session["username"],)
        )

        healthy = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM plant_history
            WHERE username = ?
            AND condition_detected != 'Healthy'
            """,
            (session["username"],)
        )

        issues = cursor.fetchone()[0]

        conn.close()

        stats = {
            "total": total,
            "healthy": healthy,
            "issues": issues
        }

    cart_count = len(session.get("cart", []))

    return render_template(
        "home.html",
        season=season,
        plant_images=plant_images,
        stats=stats,
        farmer_image=farmer_image,
        weather=weather,
        cart_count=cart_count
    )


# ============================================================
# REGISTER
# ============================================================

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
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:
            message = "Username already taken!"
            conn.close()

    return render_template(
        "register.html",
        message=message
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[2], password):
            if session.get("username") != username:
                session.pop("latest_diagnosis", None)
            session["username"] = username
            return redirect("/")

        else:
            message = "Invalid username or password!"

    return render_template(
        "login.html",
        message=message
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("latest_diagnosis", None)
    return redirect("/")


# ============================================================
# UPLOAD
# ============================================================

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        return redirect("/login")

    message = ""

    if request.method == "POST":
        file = request.files["plant_image"]

        if file:
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                file.filename
            )

            file.save(filepath)

            return redirect(
                "/result?filename=" + file.filename
            )

    bg_image = get_plant_image(
        "blooming flowers lush garden green"
    )

    return render_template(
        "upload.html",
        message=message,
        bg_image=bg_image
    )


# ============================================================
# RESULT
# ============================================================

@app.route("/result")
def result():
    filename = request.args.get("filename")

    filepath = "static/uploads/" + filename

    condition, confidence = predict_plant(filepath)

    info = recommendations[condition]

    confidence_percent = round(
        confidence * 100,
        2
    )

    session["latest_diagnosis"] = {
        "username": session["username"],
        "filename": filename,
        "condition": condition,
        "confidence": confidence_percent,
        "fertilizer": info["fertilizer"],
        "watering": info["watering"]
    }

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO plant_history
        (
            username,
            filename,
            condition_detected,
            confidence,
            upload_date
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["username"],
            filename,
            condition,
            confidence_percent,
            datetime.now().strftime(
                "%d-%m-%Y %H:%M"
            )
        )
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


# ============================================================
# HISTORY
# ============================================================

@app.route("/history")
def history():
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            filename,
            condition_detected,
            confidence,
            upload_date
        FROM plant_history
        WHERE username = ?
        ORDER BY id DESC
        """,
        (session["username"],)
    )

    records = cursor.fetchall()

    conn.close()

    return render_template(
        "history.html",
        records=records
    )


# ============================================================
# ADMIN
# ============================================================

@app.route("/admin")
def admin():
    if (
        "username" not in session
        or session["username"] != "amanmishra"
    ):
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM plant_history"
    )

    total_scans = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM plant_history
        WHERE condition_detected = 'Healthy'
        """
    )

    healthy_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM plant_history
        WHERE condition_detected != 'Healthy'
        """
    )

    issue_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            username,
            filename,
            condition_detected,
            upload_date
        FROM plant_history
        ORDER BY id DESC
        LIMIT 10
        """
    )

    recent_scans = cursor.fetchall()

    cursor.execute(
        """
        SELECT id, seller_username, plant_name, price, quantity,
               category, description, location, delivery,
               date_listed, image_filename
        FROM listings
        WHERE approval_status = 'Pending'
        ORDER BY id ASC
        """
    )
    pending_listings = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_scans=total_scans,
        healthy_count=healthy_count,
        issue_count=issue_count,
        recent_scans=recent_scans,
        pending_listings=pending_listings
    )


@app.route("/admin/listings/<int:listing_id>/<decision>", methods=["POST"])
def review_listing(listing_id, decision):
    if session.get("username") != "amanmishra":
        return redirect("/login")
    if decision not in {"approve", "reject"}:
        return redirect("/admin")

    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    approval_status = "Approved" if decision == "approve" else "Rejected"
    conn.execute(
        """
        UPDATE listings
        SET approval_status = ?
        WHERE id = ?
        AND approval_status = 'Pending'
        """,
        (approval_status, listing_id)
    )
    conn.commit()
    conn.close()
    return redirect("/admin")


# ============================================================
# STORE
# ============================================================

@app.route("/store")
def store():
    plants_with_images = []

    for plant in plants_data:
        plant_copy = plant.copy()

        plant_copy["image"] = get_plant_image(
            plant["name"]
        )

        plant_copy["is_user_listing"] = False

        plants_with_images.append(
            plant_copy
        )

    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            plant_name,
            price,
            quantity,
            category,
            description,
            seller_username,
            status,
            image_filename
        FROM listings
        WHERE status = 'Available'
        AND approval_status = 'Approved'
        AND quantity > 0
        """
    )

    user_listings = cursor.fetchall()

    conn.close()

    for listing in user_listings:
        plants_with_images.append(
            {
                "id": "user_" + str(listing[0]),
                "name": listing[1],
                "price": listing[2],
                "qty": listing[3],
                "category": listing[4],
                "desc": listing[5]
                or "Listed by a fellow gardener.",
                "seller": listing[6],
                "rating": 4.5,
                "maintenance": "Medium",
                "image": (
                    "/static/uploads/listings/" + listing[8]
                    if listing[8]
                    else get_plant_image(listing[1])
                ),
                "is_user_listing": True
            }
        )

    bg_image = get_plant_image(
        "plant nursery garden shop"
    )

    return render_template(
        "store.html",
        plants=plants_with_images,
        categories=categories,
        bg_image=bg_image
    )


# ============================================================
# ADD TO CART
# ============================================================

@app.route("/cart/add/<plant_id>")
def add_to_cart(plant_id):
    if "username" not in session:
        return redirect("/login")

    if str(plant_id).startswith("user_"):
        try:
            listing_id = int(str(plant_id).replace("user_", "", 1))
        except ValueError:
            return redirect("/store")

        conn = sqlite3.connect("database.db")
        ensure_marketplace_schema(conn)
        listing = conn.execute(
            """
            SELECT seller_username
            FROM listings
            WHERE id = ?
            AND approval_status = 'Approved'
            AND status = 'Available'
            AND quantity > 0
            """,
            (listing_id,)
        ).fetchone()
        conn.close()
        if not listing or listing[0] == session["username"]:
            return redirect("/store")
        cart_id = "user_" + str(listing_id)
    else:
        try:
            builtin_id = int(plant_id)
        except ValueError:
            return redirect("/store")
        if not any(plant["id"] == builtin_id for plant in plants_data):
            return redirect("/store")
        cart_id = builtin_id

    if "cart" not in session:
        session["cart"] = []

    cart = session["cart"]
    if cart_id not in cart:
        cart.append(cart_id)

    session["cart"] = cart

    return redirect("/cart")


# ============================================================
# REMOVE FROM CART
# ============================================================

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


# ============================================================
# ADD TO WISHLIST
# ============================================================

@app.route("/wishlist/add/<plant_id>")
def add_to_wishlist(plant_id):
    if "username" not in session:
        return redirect("/login")

    if str(plant_id).startswith("user_"):
        try:
            listing_id = int(str(plant_id).replace("user_", "", 1))
        except ValueError:
            return redirect("/store")
        conn = sqlite3.connect("database.db")
        ensure_marketplace_schema(conn)
        listing = conn.execute(
            """
            SELECT id FROM listings
            WHERE id = ?
            AND approval_status = 'Approved'
            AND status = 'Available'
            AND quantity > 0
            """,
            (listing_id,)
        ).fetchone()
        conn.close()
        if not listing:
            return redirect("/store")
        wishlist_id = "user_" + str(listing_id)
    else:
        try:
            wishlist_id = int(plant_id)
        except ValueError:
            return redirect("/store")
        if not any(plant["id"] == wishlist_id for plant in plants_data):
            return redirect("/store")

    if "wishlist" not in session:
        session["wishlist"] = []

    wishlist = session["wishlist"]

    if wishlist_id not in wishlist:
        wishlist.append(wishlist_id)

    session["wishlist"] = wishlist

    return redirect("/store")


# ============================================================
# VIEW CART
# ============================================================

@app.route("/cart")
def view_cart():
    if "username" not in session:
        return redirect("/login")

    cart_ids = session.get("cart", [])

    cart_items = []

    for cid in cart_ids:

        if str(cid).startswith("user_"):

            listing_id = int(
                str(cid).replace("user_", "")
            )

            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    plant_name,
                    price
                FROM listings
                WHERE id = ?
                AND approval_status = 'Approved'
                AND status = 'Available'
                AND quantity > 0
                """,
                (listing_id,)
            )

            row = cursor.fetchone()

            conn.close()

            if row:
                cart_items.append(
                    {
                        "id": cid,
                        "name": row[1],
                        "price": row[2]
                    }
                )

        else:
            plant = next(
                (
                    p
                    for p in plants_data
                    if p["id"] == cid
                ),
                None
            )

            if plant:
                cart_items.append(
                    {
                        "id": plant["id"],
                        "name": plant["name"],
                        "price": plant["price"]
                    }
                )

    return render_template(
        "cart.html",
        items=cart_items
    )


# ============================================================
# CART CHECKOUT
# ============================================================

@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    if "username" not in session:
        return redirect("/login")

    selected_ids = list(dict.fromkeys(request.form.getlist("selected_items")))
    cart_ids = session.get("cart", [])
    cart_id_strings = {str(cart_id) for cart_id in cart_ids}
    if not selected_ids or any(item_id not in cart_id_strings for item_id in selected_ids):
        return redirect("/cart?error=Select%20available%20items%20from%20your%20cart")

    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    ordered_plants = []
    listing_updates = []
    invalid_item = False

    for cid in selected_ids:
        if cid.startswith("user_"):
            try:
                listing_id = int(cid.replace("user_", "", 1))
            except ValueError:
                invalid_item = True
                break

            row = conn.execute(
                """
                SELECT plant_name, price, seller_username
                FROM listings
                WHERE id = ?
                AND approval_status = 'Approved'
                AND status = 'Available'
                AND quantity > 0
                """,
                (listing_id,)
            ).fetchone()
            if not row or row[2] == session["username"]:
                invalid_item = True
                break
            ordered_plants.append({"name": row[0], "price": row[1]})
            listing_updates.append(listing_id)

        else:
            try:
                builtin_id = int(cid)
            except ValueError:
                invalid_item = True
                break
            plant = next((item for item in plants_data if item["id"] == builtin_id), None)
            if not plant:
                invalid_item = True
                break
            ordered_plants.append({"name": plant["name"], "price": plant["price"]})

    if invalid_item:
        conn.close()
        return redirect("/cart?error=An%20item%20is%20no%20longer%20available")

    buyer_name = request.form["buyer_name"].strip()
    phone = request.form["phone"].strip()
    address_line1 = request.form["address_line1"].strip()
    address_line2 = request.form["address_line2"].strip()
    landmark = request.form.get("landmark", "").strip()
    city = request.form["city"].strip()
    state = request.form["state"].strip()
    pincode = request.form["pincode"].strip()
    address = f"{address_line1}, {address_line2}"
    if landmark:
        address += f" (Near {landmark})"
    address += f", {city}, {state} - {pincode}"

    total = 0
    for listing_id in listing_updates:
        updated = conn.execute(
            """
            UPDATE listings
            SET quantity = quantity - 1,
                status = CASE WHEN quantity <= 1 THEN 'Out of Stock' ELSE status END
            WHERE id = ?
            AND approval_status = 'Approved'
            AND status = 'Available'
            AND quantity > 0
            """,
            (listing_id,)
        )
        if updated.rowcount != 1:
            conn.rollback()
            conn.close()
            return redirect("/cart?error=An%20item%20just%20sold%20out")

    for plant in ordered_plants:
        conn.execute(
            """
            INSERT INTO orders
            (
                username,
                plant_name,
                price,
                buyer_name,
                phone,
                address,
                order_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["username"],
                plant["name"],
                plant["price"],
                buyer_name,
                phone,
                address,
                datetime.now().strftime(
                    "%d-%m-%Y %H:%M"
                )
            )
        )

        total += plant["price"]

    conn.commit()
    conn.close()

    save_address(
        session["username"], buyer_name, phone, address_line1,
        address_line2, landmark, city, state, pincode
    )

    remaining_cart = [
        cid
        for cid in cart_ids
        if str(cid) not in selected_ids
    ]

    session["cart"] = remaining_cart
    session.modified = True

    return render_template(
        "cart_confirmation.html",
        ordered_plants=ordered_plants,
        total=total,
        buyer_name=buyer_name
    )


# ============================================================
# SINGLE PLANT CHECKOUT
# ============================================================

@app.route("/checkout/<plant_id>", methods=["GET", "POST"])
def checkout(plant_id):
    if "username" not in session:
        return redirect("/login")

    is_user_listing = str(
        plant_id
    ).startswith("user_")

    plant = None
    available_qty = 0
    listing_id = None

    if is_user_listing:

        listing_id = int(
            str(plant_id).replace("user_", "")
        )

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                plant_name,
                price,
                quantity,
                seller_username
            FROM listings
            WHERE id = ?
            AND approval_status = 'Approved'
            AND status = 'Available'
            AND quantity > 0
            AND seller_username != ?
            """,
            (listing_id, session["username"])
        )

        row = cursor.fetchone()

        conn.close()

        if row:
            plant = {
                "id": plant_id,
                "name": row[1],
                "price": row[2]
            }

            available_qty = row[3]

    else:

        plant = next(
            (
                p
                for p in plants_data
                if p["id"] == int(plant_id)
            ),
            None
        )

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

        address = (
            f"{address_line1}, {address_line2}"
        )

        if landmark:
            address += f" (Near {landmark})"

        address += (
            f", {city}, {state} - {pincode}"
        )

        try:
            order_qty = int(request.form["order_qty"])
        except (TypeError, ValueError):
            order_qty = 0

        if order_qty < 1:
            error = "Enter a quantity of at least one."
        elif order_qty > available_qty:

            error = (
                f"Only {available_qty} unit(s) available. "
                "Please choose a lower quantity."
            )

        else:

            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO orders
                (
                    username,
                    plant_name,
                    price,
                    buyer_name,
                    phone,
                    address,
                    order_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["username"],
                    plant["name"],
                    plant["price"] * order_qty,
                    buyer_name,
                    phone,
                    address,
                    datetime.now().strftime(
                        "%d-%m-%Y %H:%M"
                    )
                )
            )

            if is_user_listing:

                updated = cursor.execute(
                    """
                    UPDATE listings
                    SET quantity = quantity - ?,
                        status = CASE WHEN quantity <= ? THEN 'Out of Stock' ELSE status END
                    WHERE id = ?
                    AND approval_status = 'Approved'
                    AND status = 'Available'
                    AND quantity >= ?
                    """,
                    (
                        order_qty,
                        order_qty,
                        listing_id,
                        order_qty
                    )
                )
                if updated.rowcount != 1:
                    conn.rollback()
                    conn.close()
                    error = "This plant is no longer available in that quantity."
                    saved = get_saved_address(session["username"])
                    return render_template(
                        "checkout.html", plant=plant,
                        available_qty=available_qty, error=error, saved=saved
                    )

            conn.commit()
            conn.close()

            save_address(
                session["username"], buyer_name, phone, address_line1,
                address_line2, landmark, city, state, pincode
            )

            return render_template(
                "order_confirmation.html",
                plant=plant,
                buyer_name=buyer_name,
                order_qty=order_qty
            )

    saved = get_saved_address(
        session["username"]
    )

    return render_template(
        "checkout.html",
        plant=plant,
        available_qty=available_qty,
        error=error,
        saved=saved
    )


# ============================================================
# SELL PLANT
# ============================================================

@app.route("/sell", methods=["GET", "POST"])
def sell():
    if "username" not in session:
        return redirect("/login")

    message = ""
    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    conn.close()

    if request.method == "POST":
        plant_name = request.form.get("plant_name", "").strip()
        category = request.form.get("category", "")
        try:
            price = float(request.form.get("price", ""))
            quantity = int(request.form.get("quantity", ""))
        except (TypeError, ValueError):
            price = 0
            quantity = 0

        if not plant_name or price <= 0 or quantity <= 0:
            message = "Enter a plant name, a price above zero, and a quantity above zero."
        elif category not in categories:
            message = "Choose a valid plant category."
        else:
            photo = request.files.get("plant_photo")
            image_filename = ""
            if photo and photo.filename:
                safe_name = secure_filename(photo.filename)
                extension = os.path.splitext(safe_name)[1].lower()
                if extension not in {".jpg", ".jpeg", ".png", ".webp", ".avif"}:
                    message = "Use a JPG, PNG, WEBP, or AVIF plant photo."
                else:
                    image_filename = uuid4().hex + extension
                    upload_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], "listings"
                    )
                    os.makedirs(upload_path, exist_ok=True)
                    photo.save(os.path.join(upload_path, image_filename))

            if not message:
                conn = sqlite3.connect("database.db")
                ensure_marketplace_schema(conn)
                conn.execute(
                    """
                    INSERT INTO listings
                    (
                        seller_username, plant_name, price, quantity,
                        category, description, location, delivery,
                        date_listed, status, approval_status, image_filename
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available', 'Pending', ?)
                    """,
                    (
                        session["username"], plant_name, price, quantity,
                        category, request.form.get("description", "").strip(),
                        request.form.get("location", "").strip(),
                        request.form.get("delivery", "Home Delivery"),
                        datetime.now().strftime("%d-%m-%Y %H:%M"), image_filename
                    )
                )
                conn.commit()
                conn.close()
                message = "Listing submitted for admin review. It will appear in GreenMarket after approval."

    bg_image = get_plant_image(
        "plant nursery garden shop"
    )

    return render_template(
        "sell.html",
        message=message,
        bg_image=bg_image
    )


# ============================================================
# MY LISTINGS
# ============================================================

@app.route("/my-listings")
def my_listings():
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            plant_name,
            price,
            quantity,
            category,
            location,
            delivery,
            date_listed,
            status,
            approval_status,
            image_filename
        FROM listings
        WHERE seller_username = ?
        ORDER BY id DESC
        """,
        (session["username"],)
    )

    listings = cursor.fetchall()

    conn.close()

    return render_template(
        "my_listings.html",
        listings=listings
    )


# ============================================================
# TOGGLE LISTING STATUS
# ============================================================

@app.route("/listing/toggle-status/<int:listing_id>")
def toggle_listing_status(listing_id):
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    ensure_marketplace_schema(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT status, approval_status
        FROM listings
        WHERE id = ?
        AND seller_username = ?
        """,
        (
            listing_id,
            session["username"]
        )
    )

    row = cursor.fetchone()

    if row and row[1] == "Approved":

        new_status = (
            "Out of Stock"
            if row[0] == "Available"
            else "Available"
        )

        cursor.execute(
            """
            UPDATE listings
            SET status = ?
            WHERE id = ?
            """,
            (
                new_status,
                listing_id
            )
        )

        conn.commit()

    conn.close()

    return redirect("/my-listings")


# ============================================================
# MY ORDERS
# ============================================================

@app.route("/my-orders")
def my_orders():
    if "username" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            plant_name,
            price,
            buyer_name,
            phone,
            address,
            order_date,
            order_status
        FROM orders
        WHERE username = ?
        ORDER BY id DESC
        """,
        (session["username"],)
    )

    orders = cursor.fetchall()

    conn.close()

    return render_template(
        "my_orders.html",
        orders=orders
    )


# ============================================================
# AI CHAT
# ============================================================

@app.route("/assistant")
def assistant():
    diagnosis = session.get("latest_diagnosis")
    if diagnosis and diagnosis.get("username") != session.get("username"):
        diagnosis = None

    return render_template(
        "assistant.html",
        diagnosis=diagnosis
    )


@app.route("/ai-chat", methods=["POST"])
def ai_chat():
    if "username" not in session:
        return {
            "answer": "🔒 Please login to use the AI Assistant.",
            "logged_in": False
        }

    question = request.form.get(
        "question",
        ""
    )

    if request.form.get("include_diagnosis") == "1":
        diagnosis = session.get("latest_diagnosis")
        if diagnosis and diagnosis.get("username") == session.get("username"):
            question = (
                "Use this recent plant diagnosis as context. "
                f"Detected condition: {diagnosis['condition']}. "
                f"Model confidence: {diagnosis['confidence']}%. "
                f"Fertilizer recommendation: {diagnosis['fertilizer']}. "
                f"Watering guidance: {diagnosis['watering']}. "
                f"User's question: {question}"
            )

    answer = get_answer(question)

    return {
        "answer": answer,
        "logged_in": True
    }


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )