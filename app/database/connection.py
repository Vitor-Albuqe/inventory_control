"""Configuração de conexão com o banco de dados SQLite.

Este módulo concentra tudo que é necessário para o SQLAlchemy
conversar com o banco. Ao separar esta parte, evitamos repetir
configuração em vários lugares da aplicação.
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

if getattr(sys, "frozen", False):
    # Executável empacotado (PyInstaller): grava o banco ao lado do .exe,
    # não dentro da pasta temporária onde o app é extraído em tempo de
    # execução (isso apagaria os dados a cada reinício).
    _DB_DIR = Path(sys.executable).resolve().parent
else:
    # Raiz do projeto (pai de app/), não Path.cwd(): se alguém rodar
    # `streamlit run app/main.py` de dentro de app/ (ou de qualquer lugar
    # que não seja a raiz), Path.cwd() apontaria para outro diretório e o
    # banco seria criado (vazio!) num lugar errado, em vez do banco real.
    _DB_DIR = Path(__file__).resolve().parent.parent.parent

DATABASE_URL = f"sqlite:///{_DB_DIR / 'cafeteria_estoque.db'}"

# Engine é o objeto que sabe "como" conectar ao banco.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # necessário para Streamlit + SQLite
)

# SessionLocal cria sessões de banco quando precisamos ler/escrever dados.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()