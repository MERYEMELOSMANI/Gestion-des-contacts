import tkinter as tk
from auth import LoginWindow
from gui import AddressBookGUI
from database import Database # Import pour initialiser la DB au lancement

def lancer_application_principale():
    """Lance l'interface du carnet d'adresses après succès du login."""
    root = tk.Tk()
    # AddressBookGUI utilisera en interne AddressBook qui communique avec SQLite
    app = AddressBookGUI(root)
    root.mainloop()

def main():
    """Initialise la DB et lance l'écran de connexion."""
    # 1. Initialisation de la base de données (création des tables si besoin)
    try:
        Database() 
    except Exception as e:
        print(f"Erreur d'initialisation de la base : {e}")

    # 2. Lancement de la fenêtre de login
    login_root = tk.Tk()
    # On passe 'lancer_application_principale' comme callback
    app_login = LoginWindow(login_root, lancer_application_principale)
    login_root.mainloop()

if __name__ == "__main__":
    main()