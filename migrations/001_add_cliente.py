"""
Etapa A do multi-cliente: cria a tabela `clientes`, adiciona a coluna
`cliente_id` em segmentos/contatos/campanhas e associa todos os
registros existentes a um "Cliente Padrão".

Idempotente: pode ser rodado mais de uma vez sem duplicar dados.

Uso:
    python migrations/001_add_cliente.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import app, db
from models.cliente import Cliente
from models.segmento import Segmento
from models.contato import Contato
from models.campanha import Campanha

TABELAS = ["segmentos", "contatos", "campanhas"]

MODELOS = [
    (Segmento, "segmentos"),
    (Contato, "contatos"),
    (Campanha, "campanhas"),
]


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

            for tabela in TABELAS:

                if coluna_existe(conn, tabela, "cliente_id", dialeto):
                    print(f"[SKIP] {tabela} já tem a coluna cliente_id")
                    continue

                if dialeto == "postgresql":
                    conn.execute(text(
                        f"ALTER TABLE {tabela} "
                        f"ADD COLUMN cliente_id INTEGER REFERENCES clientes(id)"
                    ))
                else:
                    conn.execute(text(
                        f"ALTER TABLE {tabela} ADD COLUMN cliente_id INTEGER"
                    ))

                print(f"[OK] coluna cliente_id adicionada em {tabela}")

        padrao = Cliente.query.filter_by(nome="Cliente Padrão").first()

        if padrao is None:
            padrao = Cliente(nome="Cliente Padrão")
            db.session.add(padrao)
            db.session.commit()
            print(f"[OK] Cliente Padrão criado (id={padrao.id})")
        else:
            print(f"[SKIP] Cliente Padrão já existe (id={padrao.id})")

        for modelo, tabela in MODELOS:

            atualizados = modelo.query.filter_by(cliente_id=None).update(
                {"cliente_id": padrao.id}
            )
            db.session.commit()

            print(f"[OK] {atualizados} linha(s) de {tabela} associada(s) ao Cliente Padrão")

        if dialeto == "postgresql":

            with db.engine.begin() as conn:

                for tabela in TABELAS:
                    conn.execute(text(
                        f"ALTER TABLE {tabela} ALTER COLUMN cliente_id SET NOT NULL"
                    ))

            print("[OK] cliente_id marcada como NOT NULL em segmentos/contatos/campanhas")

        else:
            print(
                "[AVISO] SQLite não suporta ALTER COLUMN — a constraint NOT NULL "
                "não foi aplicada no banco local. Sem efeito prático: o SQLite "
                "local não guarda dado real, é só pra testar o boot da app."
            )

        print("Migração concluída.")


if __name__ == "__main__":
    migrar()
