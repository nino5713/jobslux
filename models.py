from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    couleur = db.Column(db.String(7), default="#6C63FF")

    # Géolocalisation
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    last_location_update = db.Column(db.DateTime, nullable=True)
    ville = db.Column(db.String(120), nullable=True)

    messages_envoyes = db.relationship(
        "Message", backref="expediteur", lazy=True, foreign_keys="Message.sender_id"
    )
    photos = db.relationship("Photo", backref="uploader", lazy=True)
    projets_crees = db.relationship("Projet", backref="createur", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "username": self.username,
            "couleur": self.couleur,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "ville": self.ville,
            "last_location_update": self.last_location_update.isoformat()
            if self.last_location_update
            else None,
        }


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    lu = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_nom": self.expediteur.nom,
            "sender_couleur": self.expediteur.couleur,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "lu": self.lu,
        }


class Photo(db.Model):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    legende = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "uploader_id": self.uploader_id,
            "uploader_nom": self.uploader.nom,
            "filename": self.filename,
            "legende": self.legende,
            "timestamp": self.timestamp.isoformat(),
        }


class Projet(db.Model):
    __tablename__ = "projets"

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    statut = db.Column(db.String(20), default="a_faire")  # a_faire / en_cours / termine
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "titre": self.titre,
            "description": self.description,
            "statut": self.statut,
            "created_by": self.created_by,
            "createur_nom": self.createur.nom,
            "created_at": self.created_at.isoformat(),
        }
