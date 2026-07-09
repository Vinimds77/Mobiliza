from database import db


class Contato(db.Model):

    __tablename__ = "contatos"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)

    telefone = db.Column(db.String(20), nullable=False)

    cargo = db.Column(db.String(100))

    segmento_id = db.Column(
        db.Integer,
        db.ForeignKey("segmentos.id"),
        nullable=True
    )