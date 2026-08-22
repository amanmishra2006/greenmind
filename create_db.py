import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS plant_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    filename TEXT NOT NULL,
    condition_detected TEXT NOT NULL,
    confidence REAL NOT NULL,
    upload_date TEXT NOT NULL
)
""")

cursor.execute("""
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
    date_listed TEXT NOT NULL
)
""")

cursor.execute("""
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
""")

conn.commit()
conn.close()
print("Database aur tables ban gaye!")