import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS saved_addresses (
    username TEXT PRIMARY KEY,
    buyer_name TEXT,
    phone TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    landmark TEXT,
    city TEXT,
    state TEXT,
    pincode TEXT
)
""")
conn.commit()
print("Table created!")
conn.close()