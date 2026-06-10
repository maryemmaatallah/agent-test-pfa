from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class CasDeTest(db.Model):
    """Un cas de test = une instruction pour l'agent"""
    __tablename__ = "cas_de_test"
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    instruction = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500), nullable=False)
    categorie = db.Column(db.String(100), default="General")
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    resultats = db.relationship("ResultatTest", backref="cas", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "instruction": self.instruction,
            "url": self.url,
            "categorie": self.categorie,
            "date_creation": self.date_creation.strftime("%d/%m/%Y %H:%M")
        }

class ResultatTest(db.Model):
    """Résultat d'une exécution d'un cas de test"""
    __tablename__ = "resultats_test"
    
    id = db.Column(db.Integer, primary_key=True)
    cas_id = db.Column(db.Integer, db.ForeignKey("cas_de_test.id"), nullable=False)
    statut = db.Column(db.String(20), nullable=False)  # succes / echec
    message = db.Column(db.Text)
    date_execution = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "cas_id": self.cas_id,
            "statut": self.statut,
            "message": self.message,
            "date_execution": self.date_execution.strftime("%d/%m/%Y %H:%M:%S")
        }