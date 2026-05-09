import tkinter as tk
from auth import LoginWindow
from gui import AddressBookGUI

def lancer_application_principale():
    """Fonction appelée si l'authentification réussit."""
    root = tk.Tk()
    app = AddressBookGUI(root)
    root.mainloop()

def main():
    """Point d'entrée du programme : lance la fenêtre de connexion."""
    login_root = tk.Tk()
    app_login = LoginWindow(login_root, lancer_application_principale)
    login_root.mainloop()

if __name__ == "__main__":
    main()
