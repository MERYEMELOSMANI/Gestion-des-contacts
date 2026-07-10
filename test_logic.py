from address_book import AddressBook
import os

def test_address_book():
    filename = "test_contacts.db"
    if os.path.exists(filename):
        os.remove(filename)

    app = AddressBook(filename)

    # Test ajout valide
    success, msg = app.ajouter("Alice", "alice@example.com", "+10123456789")
    print(f"Ajout Alice: {success}, {msg}")

    # Test doublon de nom
    success, msg = app.ajouter("Alice", "autre@example.com", "+10987654321")
    print(f"Ajout Alice (doublon nom): {success}, {msg}")

    # Test email invalide
    success, msg = app.ajouter("Charlie", "invalid-email", "+10123456789")
    print(f"Ajout Charlie (email invalide): {success}, {msg}")

    # Test téléphone invalide
    success, msg = app.ajouter("David", "david@example.com", "0123456789")
    print(f"Ajout David (telephone invalide): {success}, {msg}")

    # Test persistance
    app2 = AddressBook(filename)
    contacts = app2.lister_contacts()
    print(f"Contacts charges: {[c.nom for c in contacts]}")

    if len(contacts) == 1 and contacts[0].nom == "Alice":
        print("VERIFICATION REUSSIE")
    else:
        print("VERIFICATION ECHOUEE")

    del app, app2
    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    test_address_book()
