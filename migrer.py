import sqlite3

def migrer_donnees():
    conn = sqlite3.connect('address_book.db')
    cursor = conn.cursor()
    
    try:
        with open('contacts.txt', 'r') as f:
            for ligne in f:
                donnees = ligne.strip().split(";")
                if len(donnees) == 3:
                    nom, email, tel = donnees
                    # On insère dans SQLite
                    cursor.execute("INSERT INTO contacts (nom, email, telephone) VALUES (?, ?, ?)", 
                                   (nom, email, tel))
        conn.commit()
        print("Migration réussie : Tous les contacts du fichier texte sont dans SQLite !")
    except FileNotFoundError:
        print("Erreur : Le fichier contacts.txt n'existe pas.")
    finally:
        conn.close()

if __name__ == "__main__":
    migrer_donnees()