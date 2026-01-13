import sqlite3


DB_FILE = "tetes.db"

def initialisationBDD():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS faces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        image BLOB
    )
    """)
    conn.commit()
    conn.close()

