import tkinter as tk
from tkinter import messagebox
from address_book import AddressBook

class AddressBookGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Allo ! - Gestion SQLite")
        self.root.geometry("600x700") # Légèrement plus grand pour le nouveau champ
        
        self.carnet = AddressBook()

        # --- Zone Supérieure : Saisie ---
        self.frameH = tk.Frame(self.root, padx=10, pady=10)
        self.frameH.pack(side=tk.TOP, fill=tk.X)

        tk.Label(self.frameH, text="Nom:").grid(row=0, column=0, sticky="w")
        self.entry_nom = tk.Entry(self.frameH)
        self.entry_nom.grid(row=0, column=1, sticky="ew", padx=5)

        tk.Label(self.frameH, text="Email:").grid(row=1, column=0, sticky="w")
        self.entry_email = tk.Entry(self.frameH)
        self.entry_email.grid(row=1, column=1, sticky="ew", padx=5)

        tk.Label(self.frameH, text="Tel:").grid(row=2, column=0, sticky="w")
        self.entry_tel = tk.Entry(self.frameH)
        self.entry_tel.grid(row=2, column=1, sticky="ew", padx=5)

        # Nouveau champ Entreprise (Partie 5)
        tk.Label(self.frameH, text="Entreprise:").grid(row=3, column=0, sticky="w")
        self.entry_ent = tk.Entry(self.frameH)
        self.entry_ent.grid(row=3, column=1, sticky="ew", padx=5)

        tk.Label(self.frameH, text="Chercher:", fg="blue").grid(row=4, column=0, sticky="w", pady=10)
        self.entry_recherche = tk.Entry(self.frameH, bg="#f0f8ff")
        self.entry_recherche.grid(row=4, column=1, sticky="ew", padx=5)
        self.entry_recherche.bind("<KeyRelease>", lambda e: self.charger_liste())

        # --- Zone Médiane : Listbox ---
        self.frameM = tk.Frame(self.root, padx=10, pady=10)
        self.frameM.pack(expand=True, fill=tk.BOTH)

        self.scrollbar = tk.Scrollbar(self.frameM)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(self.frameM, yscrollcommand=self.scrollbar.set)
        self.listbox.pack(expand=True, fill=tk.BOTH)
        self.scrollbar.config(command=self.listbox.yview)
        self.listbox.bind('<Double-1>', lambda e: self.preparer_modification())

        # --- Zone Inférieure : Boutons ---
        self.frameB = tk.Frame(self.root, padx=10, pady=10)
        self.frameB.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Button(self.frameB, text="Ajouter", command=self.ajouter_contact).pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(self.frameB, text="Supprimer", command=self.supprimer_contact, bg="#ffebee").pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(self.frameB, text="Exporter CSV", command=self.carnet.exporter_csv, bg="#e8f5e9").pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(self.frameB, text="Afficher Tout", command=self.reset_recherche).pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.charger_liste()

    def charger_liste(self):
            """Récupère les données depuis SQLite via AddressBook."""
            self.listbox.delete(0, tk.END)
            critere = self.entry_recherche.get().lower()
            
            # On récupère la liste des contacts (qui contient maintenant l'entreprise)
            contacts = self.carnet.lister_contacts()
            
            for c in contacts:
                if critere in c.nom.lower() or critere in c.email.lower():
                    # Maintenant c.entreprise contiendra la vraie valeur ou 'N/A'
                    display_text = f"{c.nom} | {c.email} | {c.telephone} | {c.entreprise}"
                    self.listbox.insert(tk.END, display_text)

    def clear_entries(self):
        self.entry_nom.delete(0, tk.END)
        self.entry_email.delete(0, tk.END)
        self.entry_tel.delete(0, tk.END)
        self.entry_ent.delete(0, tk.END)

    def ajouter_contact(self):
        nom = self.entry_nom.get().strip()
        email = self.entry_email.get().strip()
        tel = self.entry_tel.get().strip()
        ent = self.entry_ent.get().strip()
        
        if nom:
            self.carnet.ajouter(nom, email, tel, ent)
            self.charger_liste()
            self.clear_entries()
        else:
            messagebox.showwarning("Erreur", "Le nom est obligatoire.")

    def supprimer_contact(self):
        try:
            index = self.listbox.curselection()[0]
            ligne = self.listbox.get(index)
            nom = ligne.split("|")[0].strip()
            if messagebox.askyesno("Confirmation", f"Supprimer {nom} de la base de données ?"):
                self.carnet.supprimer(nom)
                self.charger_liste()
        except IndexError:
            messagebox.showwarning("Erreur", "Sélectionnez un contact.")

    def reset_recherche(self):
        self.entry_recherche.delete(0, tk.END)
        self.charger_liste()
        
    def preparer_modification(self, event=None):
        # ... (Gardez votre logique de split | pour remplir les champs)
        pass