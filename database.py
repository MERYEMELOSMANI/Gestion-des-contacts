import sqlite3
from werkzeug.security import generate_password_hash

class Database:
    def __init__(self, db_name="address_book.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Table pour les contacts
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT UNIQUE NOT NULL,
                email TEXT,
                telephone TEXT,
                entreprise TEXT
            )
        ''')
        # Table pour les admins
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def execute_query(self, query, params=()):
        self.cursor.execute(query, params)
        self.conn.commit()
        return self.cursor

    def fetch_all(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

if __name__ == "__main__":
    # Ce code s'exécute uniquement si on lance "python database.py"
    db = Database()
    username = "admin"
    password_hash = generate_password_hash("admin123")

    try:
        db.execute_query("INSERT INTO admins (username, password) VALUES (?, ?)", (username, password_hash))
        print("Compte administrateur créé avec succès !")
    except sqlite3.IntegrityError:
        print("Le compte admin existe déjà (Doublon ignoré).")
    except Exception as e:
        print(f"Erreur : {e}")