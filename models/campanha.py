from database import db
from models.cliente import Cliente


class Campanha(db.Model):

    __tablename__ = "campanhas"

    id = db.Column(db.Integer, primary_key=True)

    titulo = db.Column(db.String(150), nullable=False)

    destino = db.Column(db.String(500), nullable=False)

    codigo = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id"),
        nullable=False,
        default=Cliente.padrao_id
    )

    cliente = db.relationship("Cliente")