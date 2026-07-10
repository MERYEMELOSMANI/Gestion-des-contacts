import sqlite3
import os
import csv
from contact import Contact

class AddressBook:
    def __init__(self, db_name="address_book.db"):
        # Connexion à la base de données
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = db_name if os.path.isabs(db_name) else os.path.join(base_dir, db_name)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.creer_table()

    def creer_table(self):
        """Crée la table avec la colonne entreprise si elle n'existe pas."""
        query = '''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT UNIQUE NOT NULL,
                email TEXT,
                telephone TEXT,
                entreprise TEXT
            )
        '''
        self.cursor.execute(query)
        self.conn.commit()

    def lister_contacts(self):
        # On récupère bien les 4 colonnes
        self.cursor.execute("SELECT nom, email, telephone, IFNULL(entreprise, 'N/A') FROM contacts ORDER BY nom")
        lignes = self.cursor.fetchall()
        
        # MODIFICATION : on passe l[3] (l'entreprise) au constructeur de Contact
        return [Contact(l[0], l[1], l[2], l[3]) for l in lignes]

    def ajouter(self, nom, email, telephone, entreprise=""):
        """Retourne (succes, message) ; l'appelant décide comment afficher le message."""
        if len(nom.strip()) < 3:
            return False, "Le nom est incomplet."

        if not ("@" in email and "." in email):
            return False, "Format email invalide."

        if not (telephone.startswith("+") and len(telephone) >= 10):
            return False, "Format téléphone invalide (+ obligatoire)."

        try:
            query = "INSERT INTO contacts (nom, email, telephone, entreprise) VALUES (?, ?, ?, ?)"
            self.cursor.execute(query, (nom, email, telephone, entreprise))
            self.conn.commit()
            return True, f"Contact {nom} ajouté !"
        except sqlite3.IntegrityError:
            return False, f"Le nom '{nom}' existe déjà dans votre carnet."

    def supprimer(self, nom):
        query = "DELETE FROM contacts WHERE nom = ?"
        self.cursor.execute(query, (nom,))
        if self.cursor.rowcount > 0:
            self.conn.commit()
            print(f"Contact '{nom}' supprimé !")
        else:
            print("Contact non trouvé.")

    def exporter_csv(self):
        """Export complet avec la colonne Entreprise."""
        self.cursor.execute("SELECT nom, email, telephone, IFNULL(entreprise, 'Non renseigné') FROM contacts")
        tous_les_contacts = self.cursor.fetchall()
        
        if not tous_les_contacts:
            print("Attention : Base vide.")
            return

        with open('export_contacts.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            # Ajout de 'Entreprise' dans l'en-tête
            writer.writerow(['Nom', 'Email', 'Téléphone', 'Entreprise']) 
            writer.writerows(tous_les_contacts)
            
        print(f"Exportation de {len(tous_les_contacts)} contacts réussie !")

    def __del__(self):
        try:
            self.conn.close()
        except:
            pass