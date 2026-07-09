from database import db
from datetime import datetime


class CampanhaContato(db.Model):

    __tablename__ = "campanhas_contatos"

    id = db.Column(db.Integer, primary_key=True)

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

    codigo = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    total_cliques = db.Column(
        db.Integer,
        default=0
    )

    clicou = db.Column(
        db.Boolean,
        default=False
    )

    primeiro_clique = db.Column(
        db.DateTime
    )

    ultimo_clique = db.Column(
        db.DateTime
    )

    campanha = db.relationship("Campanha")

    contato = db.relationship("Contato")
    