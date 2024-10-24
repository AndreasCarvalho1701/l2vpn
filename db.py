import sqlite3

# Function to connect to the database
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to create the cities table if it doesn't exist
def initialize_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ip TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
