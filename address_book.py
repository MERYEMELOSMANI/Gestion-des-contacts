import sqlite3
import os
import csv
from contact import Contact

class AddressBook:
    def __init__(self):
        # Connexion à la base de données
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "address_book.db")
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
        """Signature mise à jour avec 4 arguments (plus self) pour éviter l'erreur TypeError."""
        # --- VALIDATIONS ---
        if len(nom.strip()) < 3:
            print("Erreur : Le nom est incomplet.")
            return

        # Validation email simplifiée
        if not ("@" in email and "." in email):
            print("Erreur : Format email invalide.")
            return
        
        # Validation téléphone
        if not (telephone.startswith("+") and len(telephone) >= 10):
            print("Erreur : Format téléphone invalide (+ obligatoire).")
            return

        # --- INSERTION SQL ---
        try:
            query = "INSERT INTO contacts (nom, email, telephone, entreprise) VALUES (?, ?, ?, ?)"
            self.cursor.execute(query, (nom, email, telephone, entreprise))
            self.conn.commit()
            # On importe messagebox ici ou en haut du fichier
            from tkinter import messagebox
            messagebox.showinfo("Succès", f"Contact {nom} ajouté !")
            
        except sqlite3.IntegrityError:
            from tkinter import messagebox
            messagebox.showerror("Erreur", f"Le nom '{nom}' existe déjà dans votre carnet.")

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