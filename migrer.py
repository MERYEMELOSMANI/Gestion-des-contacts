"""
migrer.py — Met à jour la base de données avec toutes les tables et colonnes nécessaires.
Lance : python migrer.py
"""
import sqlite3, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "address_book.db")

MIGRATIONS = [
    ("categorie", "TEXT DEFAULT 'Client'"),
    ("adresse",   "TEXT DEFAULT ''"),
    ("fonction",  "TEXT DEFAULT ''"),
    ("is_favorite", "INTEGER DEFAULT 0"),
]

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# 1. Mise à jour de la table contacts
cur.execute("PRAGMA table_info(contacts)")
existing = {row[1] for row in cur.fetchall()}

for col, definition in MIGRATIONS:
    if col not in existing:
        cur.execute(f"ALTER TABLE contacts ADD COLUMN {col} {definition}")
        print(f"  [OK]  Colonne '{col}' ajoutée.")
    else:
        print(f"  –  Colonne '{col}' déjà présente.")

# 2. Table rendez_vous
cur.execute("""
    CREATE TABLE IF NOT EXISTS rendez_vous (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id  INTEGER NOT NULL,
        date_rdv    TEXT    NOT NULL,
        heure_rdv   TEXT    NOT NULL,
        motif       TEXT    DEFAULT '',
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
        UNIQUE(date_rdv, heure_rdv)
    )
""")
print("  [OK]  Table 'rendez_vous' prête.")

# 3. Table historique_messages
cur.execute("""
    CREATE TABLE IF NOT EXISTS historique_messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id  INTEGER NOT NULL,
        type_msg    TEXT    NOT NULL, -- 'email' ou 'whatsapp'
        contenu     TEXT    NOT NULL,
        date_envoi  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
    )
""")
print("  [OK]  Table 'historique_messages' prête.")

conn.commit()
conn.close()
print("\nMigration terminée avec succès.")
