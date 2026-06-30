from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class CasDeTest(db.Model):
    """Un cas de test = une instruction pour l'agent IA"""
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
    """Résultat d'une exécution d'un cas de test (agent IA)"""
    __tablename__ = "resultats_test"

    id = db.Column(db.Integer, primary_key=True)
    cas_id = db.Column(db.Integer, db.ForeignKey("cas_de_test.id"), nullable=False)
    statut = db.Column(db.String(20), nullable=False)   # succes / echec
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


class SessionEnregistree(db.Model):
    """
    Session = séquence d'actions enregistrées manuellement par l'utilisateur.
    Les actions sont stockées en JSON dans la colonne `actions_json`.
    """
    __tablename__ = "sessions_enregistrees"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    nom_application = db.Column(db.String(200), default="Sans nom")  # ← nouveau : regroupe les sessions par app
    url_depart = db.Column(db.String(500), nullable=False)
    nb_actions = db.Column(db.Integer, default=0)
    actions_json = db.Column(db.Text, nullable=False)   # JSON stringifié
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    # Résultats des replays de cette session
    replays = db.relationship("ResultatReplay", backref="session", lazy=True, cascade="all, delete-orphan")

    @property
    def actions(self):
        return json.loads(self.actions_json)

    @actions.setter
    def actions(self, val):
        self.actions_json = json.dumps(val, ensure_ascii=False)
        self.nb_actions = len(val)

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "nom_application": self.nom_application,
            "url_depart": self.url_depart,
            "nb_actions": self.nb_actions,
            "actions": self.actions,
            "date_creation": self.date_creation.strftime("%d/%m/%Y %H:%M")
        }

    def to_dict_light(self):
        """Version sans les actions (pour les listes)"""
        return {
            "id": self.id,
            "nom": self.nom,
            "nom_application": self.nom_application,
            "url_depart": self.url_depart,
            "nb_actions": self.nb_actions,
            "date_creation": self.date_creation.strftime("%d/%m/%Y %H:%M")
        }


class ResultatReplay(db.Model):
    """Résultat d'un replay d'une session enregistrée"""
    __tablename__ = "resultats_replay"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions_enregistrees.id"), nullable=False)
    statut = db.Column(db.String(20), nullable=False)   # succes / partiel / echec
    nb_succes = db.Column(db.Integer, default=0)
    nb_echecs = db.Column(db.Integer, default=0)
    taux_succes = db.Column(db.Float, default=0.0)
    log_json = db.Column(db.Text)
    date_execution = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "statut": self.statut,
            "nb_succes": self.nb_succes,
            "nb_echecs": self.nb_echecs,
            "taux_succes": self.taux_succes,
            "log": json.loads(self.log_json) if self.log_json else [],
            "date_execution": self.date_execution.strftime("%d/%m/%Y %H:%M:%S")
        }


class ResultatSmartTest(db.Model):
    """Résultat persistant d'un Smart Test (génération auto de données + détection de failles)"""
    __tablename__ = "resultats_smart_test"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions_enregistrees.id"), nullable=False)
    nom_session = db.Column(db.String(200))
    total_tests = db.Column(db.Integer, default=0)
    nb_succes = db.Column(db.Integer, default=0)
    nb_echecs = db.Column(db.Integer, default=0)
    taux_succes = db.Column(db.Float, default=0.0)
    resultats_json = db.Column(db.Text)              # détail de chaque scénario testé
    validations_manquantes_json = db.Column(db.Text) # liste des failles détectées
    recommandations_json = db.Column(db.Text)
    date_execution = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "nom_session": self.nom_session,
            "total": self.total_tests,
            "succes": self.nb_succes,
            "echecs": self.nb_echecs,
            "taux": self.taux_succes,
            "resultats": json.loads(self.resultats_json) if self.resultats_json else [],
            "validations_manquantes": json.loads(self.validations_manquantes_json) if self.validations_manquantes_json else [],
            "recommandations": json.loads(self.recommandations_json) if self.recommandations_json else [],
            "date_execution": self.date_execution.strftime("%d/%m/%Y %H:%M:%S")
        }