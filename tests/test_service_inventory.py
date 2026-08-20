"""Saldos de estoque derivados do ledger e dos lotes.

O sistema nunca guarda "quantidade em estoque" numa coluna: o saldo é sempre
recalculado a partir de stock_movements (fechado) e stock_lots (aberto). Estes
testes travam a regra de sinal de cada tipo de movimento.
"""

from datetime import timedelta

import pytest

import app.services as svc


class TestEstoqueFechado:

    def test_sem_movimentacoes_retorna_zero(self, session, produto):
        assert svc.get_estoque_fechado(session, produto.id) == 0.0

    def test_entrada_aumenta_estoque(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        assert svc.get_estoque_fechado(session, produto.id) == 10.0

    def test_abertura_subtrai_do_fechado(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_abertura(session, produto.id, 1.0, hoje)
        assert svc.get_estoque_fechado(session, produto.id) == 9.0

    def test_perda_fechado_subtrai(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_perda(
            session, produto.id, 2.0, "Vencimento", hoje, estoque_afetado="fechado"
        )
        assert svc.get_estoque_fechado(session, produto.id) == 8.0

    def test_perda_no_aberto_nao_mexe_no_fechado(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_abertura(session, produto.id, 2.0, hoje)
        svc.registrar_perda(
            session, produto.id, 1.0, "Quebra", hoje, estoque_afetado="aberto"
        )
        # A perda saiu do lote em uso; o lacrado continua intocado
        assert svc.get_estoque_fechado(session, produto.id) == 8.0
        assert svc.get_estoque_aberto(session, produto.id) == pytest.approx(1.0)

    def test_ajuste_respeita_a_direcao(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_ajuste(
            session, produto.id, 2.0, "saida", "Contagem mensal", hoje
        )
        assert svc.get_estoque_fechado(session, produto.id) == 8.0

        svc.registrar_ajuste(
            session, produto.id, 3.0, "entrada", "Sobra encontrada", hoje
        )
        assert svc.get_estoque_fechado(session, produto.id) == 11.0


class TestEstoqueAberto:

    def test_abertura_cria_lote(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_abertura(session, produto.id, 1.0, hoje)
        assert svc.get_estoque_aberto(session, produto.id) == 1.0

    def test_consumo_subtrai_do_aberto(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_abertura(session, produto.id, 1.0, hoje)
        svc.registrar_consumo(session, produto.id, 0.5, hoje)
        assert svc.get_estoque_aberto(session, produto.id) == 0.5


class TestAlertas:

    def test_proximos_vencimento(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 5.0, 25.0, hoje)
        svc.registrar_abertura(
            session, produto.id, 1.0, hoje,
            validade_aberto=hoje + timedelta(days=1),
        )
        proximos = svc.get_abertos_proximos_vencimento(session, dias=3)
        assert len(proximos) == 1
        assert proximos[0]["dias_restantes"] == 1

    def test_proximos_vencimento_some_apos_consumo_total(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 5.0, 25.0, hoje)
        svc.registrar_abertura(
            session, produto.id, 1.0, hoje,
            validade_aberto=hoje + timedelta(days=1),
        )
        svc.registrar_consumo(session, produto.id, 1.0, hoje)
        assert svc.get_abertos_proximos_vencimento(session, dias=3) == []

    def test_produto_abaixo_do_minimo_aparece(self, session, criar_produto, hoje):
        p = criar_produto(nome="Leite", unidade_medida="L", estoque_minimo=8.0)
        svc.registrar_entrada(session, p.id, 3.0, 6.0, hoje)

        nomes = [x["nome"] for x in svc.get_produtos_abaixo_minimo(session)]
        assert "Leite" in nomes

    def test_produto_acima_do_minimo_nao_aparece(self, session, criar_produto, hoje):
        p = criar_produto(nome="Açúcar", unidade_medida="kg", estoque_minimo=3.0)
        svc.registrar_entrada(session, p.id, 10.0, 5.0, hoje)

        nomes = [x["nome"] for x in svc.get_produtos_abaixo_minimo(session)]
        assert "Açúcar" not in nomes


class TestValidacoes:

    def test_consumo_sem_estoque_aberto_levanta_erro(self, session, produto, hoje):
        with pytest.raises(ValueError, match="insuficiente"):
            svc.registrar_consumo(session, produto.id, 1.0, hoje)

    @pytest.mark.parametrize("quantidade", [0, -1, -0.5])
    def test_entrada_com_quantidade_invalida(self, session, produto, hoje, quantidade):
        with pytest.raises(ValueError):
            svc.registrar_entrada(session, produto.id, quantidade, 25.0, hoje)

    def test_entrada_com_preco_negativo(self, session, produto, hoje):
        with pytest.raises(ValueError):
            svc.registrar_entrada(session, produto.id, 1.0, -5.0, hoje)
