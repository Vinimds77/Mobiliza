from database import db
from models.cliente import Cliente


class Segmento(db.Model):

    __tablename__ = "segmentos"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id"),
        nullable=False,
        default=Cliente.padrao_id
    )

    cliente = db.relationship("Cliente")

    contatos = db.relationship(
        "Contato",
        backref="segmento",
        lazy=True
    )