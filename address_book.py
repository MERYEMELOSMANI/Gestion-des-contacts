from contact import Contact
import os

class AddressBook:
    def __init__(self):
        self.contacts = []
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.nom_fichier = os.path.join(base_dir, "contacts.txt")
        
        self.charger()

    def charger(self):
            self.contacts = [] # On vide la mémoire actuelle
            try:
                if os.path.exists(self.nom_fichier):
                    with open(self.nom_fichier, "r") as f:
                        for ligne in f:
                            donnees = ligne.split(";")
                            if len(donnees) == 3:
                                c = Contact(donnees[0], donnees[1], donnees[2].strip())
                                self.contacts.append(c)
            except Exception as e:
                print(f"Erreur lors du chargement : {e}")

    def enregistrer(self):
        f = open(self.nom_fichier, "w")
        for c in self.contacts:
            f.write(f"{c.nom};{c.email};{c.telephone}\n")
        f.close()

    def ajouter(self, nom, email, telephone):
        assert isinstance(nom, str)
        assert isinstance(email, str)
        assert isinstance(telephone, str)

        if len(nom.strip()) < 3:
            print("Erreur : Le nom est incomplet ou vide.")
            return

        est_valide = False
        if "@" in email and "." in email:
            at_pos = email.find("@")
            dot_pos = email.rfind(".")
            if at_pos > 0 and dot_pos > at_pos + 1 and dot_pos < len(email) - 1:
                est_valide = True

        if not est_valide:
            print("Erreur : L'email n'est pas au bon format.")
            return
        
        tel_valide = False
        if telephone.startswith("+") and len(telephone) >= 10:
            if telephone[1:].isdigit():
                tel_valide = True

        if not tel_valide:
            print("Erreur : Le téléphone doit commencer par '+' et avoir au moins 10 chiffres.")
            return

        for c in self.contacts:
            if c.nom == nom:
                print("Erreur : Ce nom existe déjà")
                return

        nouveau = Contact(nom, email, telephone)
        self.contacts.append(nouveau)
        self.enregistrer()
        print("Contact ajouté !")

    def supprimer(self, nom):
        pour_garder = []
        trouve = False
        for c in self.contacts:
            if c.nom == nom:
                trouve = True
            else:
                pour_garder.append(c)
        
        self.contacts = pour_garder
        if trouve:
            self.enregistrer()
            print("Contact supprimé !")
        else:
            print("Contact non trouvé.")

def tester_mon_application():
    test_app = AddressBook()
    test_app.contacts = []
    
    test_app.ajouter("TestUser", "test@mail.com", "12345678")
    assert len(test_app.contacts) == 1
    assert test_app.contacts[0].nom == "TestUser"
    
    print(">>> Test avec 'assert' réussi !")
