from database import db
from flask_login import UserMixin


class Usuario(db.Model, UserMixin):

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)

    senha_hash = db.Column(db.String(255), nullable=False)
