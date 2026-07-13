from database import db
from datetime import datetime
from zoneinfo import ZoneInfo


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

    dispositivo = db.Column(
        db.String(100)
    )

    navegador = db.Column(
        db.String(100)
    )
    cidade = db.Column(
        db.String(100)
    )

    estado = db.Column(
        db.String(100)
    )

    pais = db.Column(
        db.String(100)
    )

    # NOVOS CAMPOS
    cidade = db.Column(
        db.String(100)
    )

    estado = db.Column(
        db.String(100)
    )

    pais = db.Column(
        db.String(100)
    )

    data = db.Column(
        db.DateTime,
        default=lambda: datetime.now(ZoneInfo("America/Sao_Paulo"))
    )

    campanha = db.relationship("Campanha")

    contato = db.relationship("Contato")