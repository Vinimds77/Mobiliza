from database import db
from datetime import datetime, timedelta


class Clique(db.Model):

    __tablename__ = "cliques"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    campanha_id = db.Column(
        db.Integer,
        db.ForeignKey("campanhas.id"),
        nullable=False
    )

    contato_id = db.Column(
        db.Integer,
        db.ForeignKey("contatos.id"),
        nullable=False
    )

    ip = db.Column(
        db.String(100)
    )

    data = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() - timedelta(hours=3)
    )

    campanha = db.relationship("Campanha")

    contato = db.relationship("Contato")