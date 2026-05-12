import tkinter as tk
from tkinter import messagebox
import hashlib
from database import Database  # On importe votre nouvelle classe

class LoginWindow:
    def __init__(self, root, on_success_callback):
        self.root = root
        self.on_success = on_success_callback
        self.db = Database() # Initialisation de la connexion à la base
        
        self.root.title("Connexion - Carnet d'adresses")
        self.root.geometry("300x250")
        self.root.resizable(False, False)

        # Interface
        tk.Label(self.root, text="ADMINISTRATION", font=("Arial", 12, "bold")).pack(pady=10)
        
        tk.Label(self.root, text="Identifiant :").pack(pady=(10, 5))
        self.entry_username = tk.Entry(self.root)
        self.entry_username.pack()

        tk.Label(self.root, text="Mot de passe :").pack(pady=5)
        self.entry_password = tk.Entry(self.root, show="*")
        self.entry_password.pack()

        tk.Button(self.root, text="Se connecter", command=self.verifier_identifiants, bg="#4CAF50", fg="white").pack(pady=20)

        self.root.bind('<Return>', lambda event: self.verifier_identifiants())

    def verifier_identifiants(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        
        # Hachage de la saisie pour comparer avec la DB
        hashed_input = hashlib.sha256(password.encode()).hexdigest()
        
        # Requête SQL pour vérifier si l'admin existe
        query = "SELECT * FROM admins WHERE username = ? AND password = ?"
        resultat = self.db.fetch_all(query, (username, hashed_input))
        
        if len(resultat) > 0:
            # Succès : l'utilisateur a été trouvé en base
            self.root.destroy()
            self.on_success()
        else:
            messagebox.showerror("Erreur d'authentification", "Identifiant ou mot de passe incorrect.")