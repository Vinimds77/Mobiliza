"""
Adiciona a coluna `ativa` em campanhas (soft delete / arquivamento).
Toda campanha já existente é marcada como ativa=True — nada muda pra
quem já estava cadastrado, e nenhum dado é apagado.

Idempotente: pode ser rodado mais de uma vez sem duplicar nem sobrescrever.

Uso:
    python migrations/002_add_campanha_ativa.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import app, db
from models.campanha import Campanha


def coluna_existe(conn, tabela, coluna, dialeto):

    if dialeto == "postgresql":

        resultado = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :tabela AND column_name = :coluna"
            ),
            {"tabela": tabela, "coluna": coluna}
        )

        return resultado.first() is not None

    resultado = conn.execute(text(f"PRAGMA table_info({tabela})"))

    return any(linha[1] == coluna for linha in resultado)


def migrar():

    with app.app_context():

        db.create_all()

        dialeto = db.engine.dialect.name

        with db.engine.begin() as conn:

            if coluna_existe(conn, "campanhas", "ativa", dialeto):
                print("[SKIP] campanhas já tem a coluna ativa")

            else:
                conn.execute(text(
                    "ALTER TABLE campanhas ADD COLUMN ativa BOOLEAN"
                ))
                print("[OK] coluna ativa adicionada em campanhas")

        atualizadas = Campanha.query.filter_by(ativa=None).update(
            {"ativa": True}
        )
        db.session.commit()

        print(f"[OK] {atualizadas} campanha(s) existente(s) marcada(s) como ativa=True")

        print("Migração concluída. Nenhum registro foi apagado ou alterado além do campo 'ativa'.")


if __name__ == "__main__":
    migrar()
