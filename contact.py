class Contact:
    def __init__(self, nom, email, telephone):
        assert isinstance(nom, str), "Le nom doit être du texte"
        assert isinstance(email, str), "L'email doit être du texte"
        assert isinstance(telephone,str), "Le téléphone doit être du texte"
        
        self.nom = nom
        self.email = email
        self.telephone = telephone

    def __str__(self):
        return f"{self.nom} - {self.email} - {self.telephone}"
