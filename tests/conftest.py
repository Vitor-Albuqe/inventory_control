"""Fixtures compartilhadas.

Cada teste roda contra um SQLite em memória criado do zero pelo metadata do
SQLAlchemy — nenhum teste toca o banco de desenvolvimento, e a ordem de
execução não importa.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.seed import DEFAULT_TENANT_ID, ensure_default_tenant
import app.models  # noqa: F401  — registra as tabelas no metadata
from app.models.product import Product


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        ensure_default_tenant(s)
        yield s


@pytest.fixture
def hoje() -> date:
    return date.today()


def _criar_produto(session, **kwargs) -> Product:
    defaults = dict(
        tenant_id=DEFAULT_TENANT_ID,
        nome="Café",
        tipo_produto="materia_prima",
        unidade_medida="kg",
        estoque_minimo=2.0,
        controla_abertura=True,
        validade_apos_abertura=30,
    )
    defaults.update(kwargs)
    p = Product(**defaults)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@pytest.fixture
def criar_produto(session):
    """Fábrica de produtos — permite vários produtos no mesmo teste."""
    def _factory(**kwargs):
        return _criar_produto(session, **kwargs)
    return _factory


@pytest.fixture
def produto(session):
    return _criar_produto(session)


@pytest.fixture
def ontem(hoje) -> date:
    return hoje - timedelta(days=1)
