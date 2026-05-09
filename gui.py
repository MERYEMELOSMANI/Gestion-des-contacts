import tkinter as tk
from tkinter import messagebox
from address_book import AddressBook
import os

class AddressBookGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Allo !")
        self.root.geometry("600x650")
        
        self.carnet = AddressBook()

        # --- Zone Supérieure (frameH) : Saisie & RECHERCHE ---
        self.frameH = tk.Frame(self.root, padx=10, pady=10)
        self.frameH.pack(side=tk.TOP, fill=tk.X)

        # Champs de saisie classiques
        tk.Label(self.frameH, text="Nom:").grid(row=0, column=0, sticky="w")
        self.entry_nom = tk.Entry(self.frameH)
        self.entry_nom.grid(row=0, column=1, sticky="ew", padx=5)

        tk.Label(self.frameH, text="Email:").grid(row=1, column=0, sticky="w")
        self.entry_email = tk.Entry(self.frameH)
        self.entry_email.grid(row=1, column=1, sticky="ew", padx=5)

        tk.Label(self.frameH, text="Tel:").grid(row=2, column=0, sticky="w")
        self.entry_tel = tk.Entry(self.frameH)
        self.entry_tel.grid(row=2, column=1, sticky="ew", padx=5)

        # BARRE DE RECHERCHE (Nouveau)
        tk.Label(self.frameH, text="Chercher:", fg="blue").grid(row=3, column=0, sticky="w", pady=10)
        self.entry_recherche = tk.Entry(self.frameH, bg="#f0f8ff")
        self.entry_recherche.grid(row=3, column=1, sticky="ew", padx=5)
        # On lie la recherche à chaque touche tapée
        self.entry_recherche.bind("<KeyRelease>", lambda e: self.charger_liste())

        self.btn_effacer = tk.Button(self.frameH, text="Effacer Champs", command=self.clear_entries)
        self.btn_effacer.grid(row=4, column=1, pady=5)

        self.frameH.columnconfigure(1, weight=1)

        # --- Zone Médiane (frameM) : Listbox ---
        self.frameM = tk.Frame(self.root, padx=10, pady=10)
        self.frameM.pack(expand=True, fill=tk.BOTH)

        self.scrollbar = tk.Scrollbar(self.frameM)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(self.frameM, yscrollcommand=self.scrollbar.set)
        self.listbox.pack(expand=True, fill=tk.BOTH)
        self.scrollbar.config(command=self.listbox.yview)
        # Double-clic pour charger les infos dans les cases
        self.listbox.bind('<Double-1>', lambda e: self.preparer_modification())

        # --- Zone Inférieure (frameB) : Boutons ---
        self.frameB = tk.Frame(self.root, padx=10, pady=10)
        self.frameB.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Button(self.frameB, text="Ajouter", command=self.ajouter_contact).pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(self.frameB, text="Modifier", command=self.modifier_contact, bg="#e1f5fe").pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(self.frameB, text="Supprimer", command=self.supprimer_contact, bg="#ffebee").pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Button(self.frameB, text="Afficher Tout", command=self.reset_recherche).pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.charger_liste()

    def charger_liste(self):
            """Force la relecture du fichier et met à jour la Listbox."""
            # 1. On demande à la logique métier de relire le fichier texte
            self.carnet.charger() 
            
            # 2. On vide l'affichage actuel de la Listbox
            self.listbox.delete(0, tk.END)
            
            # 3. On récupère le filtre de recherche (si vous en avez un)
            critere = self.entry_recherche.get().lower() if hasattr(self, 'entry_recherche') else ""
            
            # 4. On remplit la liste avec les données fraîches
            contacts_filtres = [
                c for c in self.carnet.contacts 
                if critere in c.nom.lower() or critere in c.email.lower()
            ]
            
            for c in sorted(contacts_filtres, key=lambda x: x.nom.lower()):
                self.listbox.insert(tk.END, f"{c.nom} | {c.email} | {c.telephone}")

    def preparer_modification(self, event=None):
            """Remplit les champs de saisie pour permettre la modification."""
            try:
                # 1. Récupérer l'index de l'élément sélectionné
                index = self.listbox.curselection()[0]
                ligne = self.listbox.get(index)
                
                # 2. Découper la ligne pour extraire les infos
                # On utilise split("|") car c'est le séparateur qu'on a défini dans charger_liste
                infos = [item.strip() for item in ligne.split("|")]
                
                if len(infos) >= 3:
                    nom, email, tel = infos[0], infos[1], infos[2]
                    
                    # 3. Remplir les cases de saisie
                    self.clear_entries()
                    self.entry_nom.insert(0, nom)
                    self.entry_email.insert(0, email)
                    self.entry_tel.insert(0, tel)
                    
                    # Optionnel : Garder le nom original en mémoire si vous voulez changer le nom lui-même
                    self.nom_en_cours_de_modif = nom 
            except IndexError:
                pass

    def modifier_contact(self):
        """Enregistre les modifications apportées aux champs."""
        if not hasattr(self, 'nom_en_cours_de_modif'):
            messagebox.showwarning("Attention", "Double-cliquez d'abord sur un contact pour le charger.")
            return

        nom_nouveau = self.entry_nom.get().strip()
        email_nouveau = self.entry_email.get().strip()
        tel_nouveau = self.entry_tel.get().strip()

        if nom_nouveau and email_nouveau and tel_nouveau:
            # 1. Supprimer l'ancienne version (basée sur le nom stocké lors du double-clic)
            self.carnet.supprimer(self.nom_en_cours_de_modif)
            
            # 2. Ajouter la nouvelle version
            self.carnet.ajouter(nom_nouveau, email_nouveau, tel_nouveau)
            
            # 3. Rafraîchir l'interface
            self.charger_liste()
            self.clear_entries()
            messagebox.showinfo("Succès", "Le contact a été mis à jour.")
        else:
            messagebox.showwarning("Erreur", "Tous les champs doivent être remplis.")

    def reset_recherche(self):
        self.entry_recherche.delete(0, tk.END)
        self.charger_liste()

    def clear_entries(self):
        self.entry_nom.delete(0, tk.END)
        self.entry_email.delete(0, tk.END)
        self.entry_tel.delete(0, tk.END)

    def ajouter_contact(self):
        nom = self.entry_nom.get()
        email = self.entry_email.get()
        tel = self.entry_tel.get()
        self.carnet.ajouter(nom, email, tel) # [cite: 20]
        self.charger_liste()
        self.clear_entries()

    def supprimer_contact(self):
        try:
            index = self.listbox.curselection()[0]
            ligne = self.listbox.get(index)
            nom = ligne.split("|")[0].strip()
            if messagebox.askyesno("Confirmation", f"Supprimer {nom} ?"):
                self.carnet.supprimer(nom) # [cite: 22]
                self.charger_liste()
        except IndexError:
            messagebox.showwarning("Erreur", "Sélectionnez un contact à supprimer.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AddressBookGUI(root)
    root.mainloop()