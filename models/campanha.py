from database import db
from datetime import datetime, timezone
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

    ativa = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    criado_em = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    cliente = db.relationship("Cliente")