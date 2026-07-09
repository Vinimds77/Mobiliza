from database import db


class Segmento(db.Model):

    __tablename__ = "segmentos"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    contatos = db.relationship(
        "Contato",
        backref="segmento",
        lazy=True
    )