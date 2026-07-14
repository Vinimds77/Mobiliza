from database import db
from datetime import datetime, timezone


class Cliente(db.Model):

    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)

    criado_em = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    @staticmethod
    def padrao_id():
        padrao = Cliente.query.filter_by(nome="Cliente Padrão").first()
        return padrao.id if padrao else None
