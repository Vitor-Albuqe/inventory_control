"""Conversão e formatação de unidades.

O usuário digita a receita em grama/ml (o que faz sentido no balcão), mas o
estoque é guardado em kg/L. Errar o fator de 1000 aqui significa consumir mil
vezes mais ou mil vezes menos insumo por venda — o tipo de bug que só aparece
no inventário do fim do mês.
"""

import pytest

from app.utils.unit_converter import (
    converter_para_estoque,
    formatar_quantidade_estoque,
    formatar_receita,
    quantidade_exibicao,
    unidade_exibicao,
    _to_float,
)


class TestConversaoParaEstoque:

    @pytest.mark.parametrize("entrada,unidade,esperado", [
        (1000, "kg", 1.0),      # 1000 g = 1 kg
        (250, "kg", 0.25),
        (1500, "L", 1.5),       # 1500 ml = 1.5 L
        (8, "un", 8),           # unidade não converte
    ])
    def test_converte_para_a_unidade_do_estoque(self, entrada, unidade, esperado):
        assert converter_para_estoque(entrada, unidade) == pytest.approx(esperado)

    def test_ida_e_volta_preserva_o_valor(self, ):
        # Conversão em pares tem que ser reversível, senão o estoque "vaza"
        for unidade in ("kg", "L", "un"):
            for valor in (1, 250, 1000, 3333):
                estoque = converter_para_estoque(valor, unidade)
                assert quantidade_exibicao(estoque, unidade) == pytest.approx(valor)


class TestUnidadeDeExibicao:

    @pytest.mark.parametrize("estoque,exibicao", [
        ("kg", "g"), ("L", "ml"), ("un", "un"),
    ])
    def test_unidade_mostrada_ao_usuario(self, estoque, exibicao):
        assert unidade_exibicao(estoque) == exibicao


class TestFormatacao:

    @pytest.mark.parametrize("qtd,unidade,esperado", [
        (0.008, "kg", "8 g"),
        (0.150, "L", "150 ml"),
        (2, "un", "2 un"),
    ])
    def test_formatar_receita(self, qtd, unidade, esperado):
        assert formatar_receita(qtd, unidade) == esperado

    @pytest.mark.parametrize("qtd,unidade,esperado", [
        (2.5, "kg", "2.5 kg"),
        (2.0, "kg", "2 kg"),          # sem zeros à toa
        (0.0001, "kg", "0 kg"),       # abaixo do grama arredonda para zero
        (3.4, "un", "3 un"),          # unidade não é fracionada
        (0, "L", "0 L"),
    ])
    def test_formatar_quantidade_estoque(self, qtd, unidade, esperado):
        assert formatar_quantidade_estoque(qtd, unidade) == esperado


class TestToFloat:

    def test_none_vira_zero(self):
        # SUM() de tabela vazia devolve None; sem isso o dashboard quebraria
        assert _to_float(None) == 0.0

    def test_decimal_do_banco_vira_float(self):
        from decimal import Decimal
        assert _to_float(Decimal("12.34")) == pytest.approx(12.34)
