import tkinter as tk
from tkinter import messagebox
import hashlib

class LoginWindow:
    def __init__(self, root, on_success_callback):
        self.root = root
        self.on_success = on_success_callback
        
        self.root.title("Connexion - Carnet d'adresses")
        self.root.geometry("300x200")
        self.root.resizable(False, False)

        # Compte administrateur hardcodé
        # Identifiant : admin
        # Mot de passe : admin123 -> haché en SHA-256
        self.admin_user = "admin"
        self.admin_pass_hash = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"

        # Interface
        tk.Label(self.root, text="Identifiant :").pack(pady=(20, 5))
        self.entry_username = tk.Entry(self.root)
        self.entry_username.pack()

        tk.Label(self.root, text="Mot de passe :").pack(pady=5)
        self.entry_password = tk.Entry(self.root, show="*")
        self.entry_password.pack()

        tk.Button(self.root, text="Se connecter", command=self.verifier_identifiants).pack(pady=20)

        # Lier la touche Entrée à la validation
        self.root.bind('<Return>', lambda event: self.verifier_identifiants())

    def verifier_identifiants(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        
        hashed_input = hashlib.sha256(password.encode()).hexdigest()
        
        if username == self.admin_user and hashed_input == self.admin_pass_hash:
            self.root.destroy()
            self.on_success()
        else:
            messagebox.showerror("Erreur d'authentification", "Identifiant ou mot de passe incorrect.")
