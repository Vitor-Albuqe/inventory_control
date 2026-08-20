"""Testes do service."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.seed import DEFAULT_TENANT_ID, ensure_default_tenant
import app.models  # noqa: F401
from app.models.product import Product
import app.services as svc


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        ensure_default_tenant(s)
        yield s


@pytest.fixture
def produto(session):
    p = Product(
        tenant_id=DEFAULT_TENANT_ID,
        nome="Café",
        categoria="Bebidas",
        unidade_medida="kg",
        estoque_minimo=2.0,
        controla_abertura=True,
        validade_apos_abertura=30,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


class TestEstoqueFechado:

    def test_sem_movimentacoes_retorna_zero(self, session, produto):
        assert svc.get_estoque_fechado(session, produto.id) == 0.0

    def test_entrada_aumenta_estoque(self, session, produto):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, date.today())
        assert svc.get_estoque_fechado(session, produto.id) == 10.0

    def test_abertura_subtrai_do_fechado(self, session, produto):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, date.today())
        svc.registrar_abertura(session, produto.id, 1.0, date.today())
        assert svc.get_estoque_fechado(session, produto.id) == 9.0

    def test_perda_fechado_subtrai(self, session, produto):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, date.today())
        svc.registrar_perda(
            session, produto.id, 2.0, "Vencimento", date.today(), estoque_afetado="fechado"
        )
        assert svc.get_estoque_fechado(session, produto.id) == 8.0


class TestEstoqueAberto:

    def test_abertura_cria_lote(self, session, produto):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, date.today())
        svc.registrar_abertura(session, produto.id, 1.0, date.today())
        assert svc.get_estoque_aberto(session, produto.id) == 1.0

    def test_consumo_subtrai_do_aberto(self, session, produto):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, date.today())
        svc.registrar_abertura(session, produto.id, 1.0, date.today())
        svc.registrar_consumo(session, produto.id, 0.5, date.today())
        assert svc.get_estoque_aberto(session, produto.id) == 0.5


class TestAlertas:

    def test_proximos_vencimento(self, session, produto):
        svc.registrar_entrada(session, produto.id, 5.0, 25.0, date.today())
        vence_amanha = date.today() + timedelta(days=1)
        svc.registrar_abertura(
            session, produto.id, 1.0, date.today(), validade_aberto=vence_amanha
        )
        proximos = svc.get_abertos_proximos_vencimento(session, dias=3)
        assert len(proximos) == 1
        assert proximos[0]["dias_restantes"] == 1

    def test_proximos_vencimento_some_apos_consumo_total(self, session, produto):
        svc.registrar_entrada(session, produto.id, 5.0, 25.0, date.today())
        vence_amanha = date.today() + timedelta(days=1)
        svc.registrar_abertura(
            session, produto.id, 1.0, date.today(), validade_aberto=vence_amanha
        )
        svc.registrar_consumo(session, produto.id, 1.0, date.today())
        assert svc.get_abertos_proximos_vencimento(session, dias=3) == []


class TestValidacoes:

    def test_consumo_sem_estoque_aberto_levanta_erro(self, session, produto):
        with pytest.raises(ValueError, match="insuficiente"):
            svc.registrar_consumo(session, produto.id, 1.0, date.today())
