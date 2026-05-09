from address_book import AddressBook

def main():
    mon_carnet = AddressBook()

    while True:
        print("\n--- MENU ---")
        print("1 - Ajouter un contact")
        print("2 - Supprimer un contact")
        print("3 - Afficher tous les contacts")
        print("4 - Quitter")
        
        choix = input("Votre choix : ")

        if choix == "1":
            nom = ""
            while len(nom.strip()) < 3:
                nom = input("Nom (3 caractères min) : ")
            
            email = ""
            while True:
                email = input("Email : ")
                if "@" in email and "." in email:
                    at_index = email.find("@")
                    dot_index = email.rfind(".")
                    if at_index > 0 and dot_index > at_index + 1 and dot_index < len(email) - 1:
                        break
                print("Erreur : L'email n'est pas valide (ex: nom@domaine.com)")
            
            tel = ""
            while True:
                tel = input("Téléphone (ex: +212612345678) : ")
                if tel.startswith("+") and len(tel) >= 10:
                    if tel[1:].isdigit():
                        break
                print("Erreur : Le numéro doit commencer par '+' et faire au moins 10 chiffres.")
                
            mon_carnet.ajouter(nom, email, tel)

        elif choix == "2":
            nom = input("Nom à supprimer : ")
            mon_carnet.supprimer(nom)

        elif choix == "3":
            print("\nListe des contacts :")
            for c in mon_carnet.contacts:
                print(c)

        elif choix == "4":
            print("Au revoir !")
            break
        else:
            print("Choix invalide !")

if __name__ == "__main__":
    main()
