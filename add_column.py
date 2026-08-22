import sqlite3

conn = sqlite3.connect("database.db")
try:
    conn.execute("ALTER TABLE listings ADD COLUMN status TEXT DEFAULT 'Available'")
    conn.commit()
    print("Column added successfully!")
except Exception as e:
    print("Error (might already exist):", e)
conn.close()