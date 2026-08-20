"""FEFO — a regra de consumo que define quanto a cafeteria desperdiça.

É a regra de negócio mais cara de errar do sistema: consumir na ordem errada
significa jogar fora produto que ainda dava para vender. Os testes aqui
cobrem a ordem, os empates e o caso em que o lote vence antes de acabar.
"""

from datetime import timedelta

import pytest

import app.services as svc


def _abrir_lote(session, produto, qtd, hoje, validade):
    """Compra e abre uma embalagem com validade explícita."""
    svc.registrar_entrada(session, produto.id, qtd, 25.0, hoje)
    return svc.registrar_abertura(
        session, produto.id, qtd, hoje, validade_aberto=validade
    )


class TestOrdemDeConsumo:

    def test_consome_do_lote_que_vence_primeiro(self, session, produto, hoje):
        # Lote longe do vencimento é aberto ANTES do que vence logo:
        # se a regra fosse FIFO (ordem de entrada), este seria consumido antes.
        _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=30))
        _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=2))

        svc.registrar_consumo(session, produto.id, 1.0, hoje)

        restantes = svc.get_lotes_abertos(session, produto.id)
        assert len(restantes) == 1
        # Sobrou o de validade longa => o de validade curta foi consumido
        assert restantes[0].validade == hoje + timedelta(days=30)

    def test_lote_sem_validade_fica_por_ultimo(self, session, produto, hoje):
        _abrir_lote(session, produto, 1.0, hoje, None)
        _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=10))

        svc.registrar_consumo(session, produto.id, 1.0, hoje)

        restantes = svc.get_lotes_abertos(session, produto.id)
        assert len(restantes) == 1
        assert restantes[0].validade is None

    def test_consumo_atravessa_dois_lotes(self, session, produto, hoje):
        _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=2))
        _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=20))

        # 1.5 kg > 1 kg do primeiro lote: precisa quebrar entre os dois
        svc.registrar_consumo(session, produto.id, 1.5, hoje)

        assert svc.get_estoque_aberto(session, produto.id) == pytest.approx(0.5)
        restantes = svc.get_lotes_abertos(session, produto.id)
        assert len(restantes) == 1
        assert restantes[0].validade == hoje + timedelta(days=20)
        assert restantes[0].quantidade_atual == pytest.approx(0.5)

    def test_lote_zerado_e_fechado(self, session, produto, hoje):
        mov = _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=5))
        svc.registrar_consumo(session, produto.id, 1.0, hoje)

        from app.models import StockLot

        lote = (
            session.query(StockLot).filter_by(abertura_movement_id=mov.id).one()
        )
        assert lote.quantidade_atual == 0
        assert lote.status == "closed"


class TestLoteVencido:

    def test_lote_vencido_sai_da_fila_de_consumo(self, session, produto, hoje, ontem):
        # Vencido ontem: continua na tabela, mas o FEFO não pode encostar nele
        _abrir_lote(session, produto, 1.0, ontem, ontem)
        _abrir_lote(session, produto, 1.0, hoje, hoje + timedelta(days=10))

        disponiveis = svc.get_lotes_abertos(session, produto.id)
        assert len(disponiveis) == 1
        assert disponiveis[0].validade == hoje + timedelta(days=10)

    def test_estoque_aberto_ignora_lote_vencido(self, session, produto, hoje, ontem):
        _abrir_lote(session, produto, 1.0, ontem, ontem)
        # Sem isso o saldo viraria "fantasma": somado no total, inacessível ao FEFO
        assert svc.get_estoque_aberto(session, produto.id) == 0.0

    def test_consumo_falha_se_so_ha_lote_vencido(self, session, produto, ontem):
        _abrir_lote(session, produto, 1.0, ontem, ontem)
        with pytest.raises(ValueError, match="insuficiente"):
            svc.registrar_consumo(session, produto.id, 0.5, ontem)


class TestConservacaoDeEstoque:

    def test_abertura_nao_cria_nem_destroi_estoque(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        total_antes = svc.get_estoque_total(session, produto.id)

        svc.registrar_abertura(session, produto.id, 3.0, hoje)

        # Abrir move fechado -> aberto; o total tem que continuar o mesmo
        assert svc.get_estoque_total(session, produto.id) == pytest.approx(total_antes)
        assert svc.get_estoque_fechado(session, produto.id) == pytest.approx(7.0)
        assert svc.get_estoque_aberto(session, produto.id) == pytest.approx(3.0)

    def test_consumo_reduz_o_total(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 10.0, 25.0, hoje)
        svc.registrar_abertura(session, produto.id, 3.0, hoje)
        svc.registrar_consumo(session, produto.id, 1.0, hoje)

        assert svc.get_estoque_total(session, produto.id) == pytest.approx(9.0)

    def test_nao_abre_mais_do_que_o_estoque_fechado(self, session, produto, hoje):
        svc.registrar_entrada(session, produto.id, 2.0, 25.0, hoje)
        with pytest.raises(ValueError):
            svc.registrar_abertura(session, produto.id, 5.0, hoje)
