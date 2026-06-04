"""
migrer.py — Ajoute les colonnes categorie, adresse, fonction à la table contacts
Lance une seule fois : python migrer.py
"""
import sqlite3, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "address_book.db")

MIGRATIONS = [
    ("categorie", "TEXT DEFAULT 'Client'"),
    ("adresse",   "TEXT DEFAULT ''"),
    ("fonction",  "TEXT DEFAULT ''"),
]

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# Colonnes existantes
cur.execute("PRAGMA table_info(contacts)")
existing = {row[1] for row in cur.fetchall()}

for col, definition in MIGRATIONS:
    if col not in existing:
        cur.execute(f"ALTER TABLE contacts ADD COLUMN {col} {definition}")
        print(f"  ✔  Colonne '{col}' ajoutée.")
    else:
        print(f"  –  Colonne '{col}' déjà présente.")

# Table rendez-vous (Partie 9)
cur.execute("""
    CREATE TABLE IF NOT EXISTS rendez_vous (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id  INTEGER NOT NULL,
        date_rdv    TEXT    NOT NULL,   -- format YYYY-MM-DD
        heure_rdv   TEXT    NOT NULL,   -- format HH:MM
        motif       TEXT    DEFAULT '',
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
        UNIQUE(date_rdv, heure_rdv)
    )
""")
print("  ✔  Table 'rendez_vous' prête.")

conn.commit()
conn.close()
print("\nMigration terminée.")