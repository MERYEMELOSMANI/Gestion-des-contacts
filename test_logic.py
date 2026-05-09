from address_book import AddressBook
import os

def test_address_book():
    filename = "test_contacts.txt"
    if os.path.exists(filename):
        os.remove(filename)

    app = AddressBook(filename)
    
    # Test ajout valide
    success, msg = app.ajouter_contact("Alice", "alice@example.com", "0123456789")
    print(f"Ajout Alice: {success}, {msg}")
    
    # Test doublon email
    success, msg = app.ajouter_contact("Bob", "alice@example.com", "0987654321")
    print(f"Ajout Bob (email Alice): {success}, {msg}")
    
    # Test email invalide
    success, msg = app.ajouter_contact("Charlie", "invalid-email", "0123456789")
    print(f"Ajout Charlie (email invalide): {success}, {msg}")
    
    # Test persistance
    app2 = AddressBook(filename)
    contacts = app2.lister_contacts()
    print(f"Contacts charges: {[c.nom for c in contacts]}")
    
    if len(contacts) == 1 and contacts[0].nom == "Alice":
        print("VERIFICATION REUSSIE")
    else:
        print("VERIFICATION ECHOUEE")

    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    test_address_book()
