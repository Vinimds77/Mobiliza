import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "database.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Neon fecha conexões ociosas do lado do servidor; sem pool_pre_ping o
    # SQLAlchemy pode entregar uma conexão já morta para a próxima query
    # (é a causa do "SSL connection has been closed unexpectedly").
    # pool_pre_ping testa a conexão antes de reutilizá-la; pool_recycle
    # descarta conexões do pool antes que o servidor tenha chance de fechá-las.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300
    }

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-apenas-local-nao-usar-em-producao")