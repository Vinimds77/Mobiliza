from database import db
from datetime import datetime, timezone
from flask_login import UserMixin


class Usuario(db.Model, UserMixin):

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)

    senha_hash = db.Column(db.String(255), nullable=False)

    criado_em = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
