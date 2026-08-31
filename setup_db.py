import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    plastic_type TEXT NOT NULL,
    quantity_estimate TEXT NOT NULL,
    status TEXT DEFAULT 'sighted',
    date_reported TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
print("Database created successfully!")