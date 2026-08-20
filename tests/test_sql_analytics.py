"""Camada SQL de `sql/`.

Query analítica quebrada é pior que query ausente: ela devolve um número
errado com cara de certo. Estes testes rodam cada arquivo .sql contra um banco
montado do zero e conferem o resultado contra valores calculados à mão.

As queries são executadas por conexão direta (não pelo engine global do
`analytics_repository`), para não depender do banco de desenvolvimento.
"""

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.seed import DEFAULT_TENANT_ID, ensure_default_tenant
import app.models  # noqa: F401
from app.models.product import Product
from app.repositories.analytics_repository import carregar_query, listar_queries
import app.services as svc

HOJE = date.today()

# Parâmetros mínimos para cada query rodar
PARAMS = {
    "01_posicao_estoque": {},
    "02_alertas_reposicao": {"dias_validade": 7, "dias_cobertura": 15},
    "03_giro_estoque": {"data_inicio": None, "data_fim": None},
    "04_curva_abc": {"data_inicio": None, "data_fim": None},
    "05_evolucao_mensal": {},
    "06_margem_por_receita": {"data_inicio": None, "data_fim": None},
    "07_desempenho_fornecedores": {"data_inicio": None, "data_fim": None},
    "08_perdas_por_causa": {"data_inicio": None, "data_fim": None},
}


@pytest.fixture(scope="module")
def banco_analitico(tmp_path_factory):
    """Banco com uma operação pequena e conhecida, para conferir os números."""
    caminho = tmp_path_factory.mktemp("db") / "analitico.db"
    engine = create_engine(f"sqlite:///{caminho}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as s:
        ensure_default_tenant(s)

        cafe = Product(
            tenant_id=DEFAULT_TENANT_ID, nome="Café", tipo_produto="materia_prima",
            unidade_medida="kg", estoque_minimo=5.0, controla_abertura=True,
        )
        bolo = Product(
            tenant_id=DEFAULT_TENANT_ID, nome="Bolo", tipo_produto="produto_final",
            unidade_medida="un", estoque_minimo=2.0, controla_abertura=True,
            preco_venda=10.00,
        )
        s.add_all([cafe, bolo])
        s.commit()
        s.refresh(cafe)
        s.refresh(bolo)

        # Café: compra 10 kg a R$ 20/kg de dois fornecedores diferentes
        svc.registrar_entrada(s, cafe.id, 6.0, 20.0, HOJE - timedelta(days=20),
                              fornecedor="Fornecedor A", tempo_entrega=2)
        svc.registrar_entrada(s, cafe.id, 4.0, 30.0, HOJE - timedelta(days=10),
                              fornecedor="Fornecedor B", tempo_entrega=5)
        # Abre 3 kg e consome 1; perde 0.5 por quebra
        svc.registrar_abertura(s, cafe.id, 3.0, HOJE - timedelta(days=9))
        svc.registrar_consumo(s, cafe.id, 1.0, HOJE - timedelta(days=5))
        svc.registrar_perda(s, cafe.id, 0.5, "Quebra no manuseio",
                            HOJE - timedelta(days=3), estoque_afetado="aberto")

        # Bolo: compra 1 un, fica abaixo do mínimo de 2
        svc.registrar_entrada(s, bolo.id, 1.0, 4.0, HOJE - timedelta(days=8),
                              fornecedor="Padaria", tempo_entrega=1)

        ids = {"cafe": cafe.id, "bolo": bolo.id}

    yield engine, ids
    engine.dispose()


def rodar(engine, nome: str, **extra) -> pd.DataFrame:
    params = {"tenant_id": DEFAULT_TENANT_ID}
    for chave, valor in PARAMS[nome].items():
        params[chave] = valor
    if "data_inicio" in params and params["data_inicio"] is None:
        params["data_inicio"] = (HOJE - timedelta(days=365)).isoformat()
        params["data_fim"] = HOJE.isoformat()
    params.update(extra)
    with engine.connect() as conn:
        return pd.read_sql_query(text(carregar_query(nome)), conn, params=params)


class TestTodasAsQueries:
    """Barreira mínima: nenhuma query pode ter erro de sintaxe ou de coluna."""

    def test_todas_as_queries_estao_mapeadas(self):
        # Query nova sem entrada em PARAMS passaria despercebida pelos testes
        assert set(listar_queries()) == set(PARAMS), (
            "Toda query em sql/ precisa de uma entrada em PARAMS neste teste."
        )

    @pytest.mark.parametrize("nome", sorted(PARAMS))
    def test_query_executa(self, banco_analitico, nome):
        engine, _ = banco_analitico
        df = rodar(engine, nome)
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) > 0

    @pytest.mark.parametrize("nome", sorted(PARAMS))
    def test_query_nao_tem_coluna_duplicada(self, banco_analitico, nome):
        # Coluna duplicada quebra silenciosamente no pandas e no Power BI
        engine, _ = banco_analitico
        df = rodar(engine, nome)
        assert len(set(df.columns)) == len(df.columns), f"colunas repetidas: {list(df.columns)}"


class TestPosicaoEstoque:

    def test_saldo_bate_com_a_camada_de_servico(self, banco_analitico):
        engine, ids = banco_analitico
        df = rodar(engine, "01_posicao_estoque").set_index("produto")

        # Café: 10 comprados - 3 abertos = 7 fechado
        #       3 abertos - 1 consumido - 0.5 perdido = 1.5 aberto
        assert df.loc["Café", "estoque_fechado"] == pytest.approx(7.0)
        assert df.loc["Café", "estoque_aberto"] == pytest.approx(1.5)
        assert df.loc["Café", "estoque_total"] == pytest.approx(8.5)

    def test_status_marca_quem_esta_abaixo_do_minimo(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "01_posicao_estoque").set_index("produto")
        # Bolo: 1 un contra mínimo de 2
        assert df.loc["Bolo", "status_estoque"] == "ABAIXO DO MINIMO"
        # Café: 8.5 kg contra mínimo de 5 -> acima de 1.5x, portanto OK
        assert df.loc["Café", "status_estoque"] == "OK"

    def test_indice_de_cobertura(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "01_posicao_estoque").set_index("produto")
        assert df.loc["Bolo", "indice_cobertura"] == pytest.approx(0.5)   # 1 / 2
        assert df.loc["Café", "indice_cobertura"] == pytest.approx(1.7)   # 8.5 / 5


class TestAlertas:

    def test_bolo_entra_na_lista_de_compras(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "02_alertas_reposicao")
        linha = df[(df["produto"] == "Bolo") & (df["motivo"] == "ABAIXO DO MINIMO")]
        assert len(linha) == 1

    def test_cafe_nao_entra_na_lista(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "02_alertas_reposicao")
        assert "Café" not in set(df[df["motivo"] != "VENCE EM BREVE"]["produto"])


class TestGiro:

    def test_saida_soma_consumo_e_perda(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "03_giro_estoque").set_index("produto")
        assert df.loc["Café", "qtd_consumida"] == pytest.approx(1.0)
        assert df.loc["Café", "qtd_perdida"] == pytest.approx(0.5)
        assert df.loc["Café", "qtd_saida"] == pytest.approx(1.5)

    def test_percentual_de_perda(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "03_giro_estoque").set_index("produto")
        # 0.5 perdido de 1.5 que saiu = 33.33%
        assert df.loc["Café", "perc_perda"] == pytest.approx(33.33, abs=0.01)

    def test_custo_medio_e_ponderado_pela_quantidade(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "03_giro_estoque").set_index("produto")
        # (6 x 20 + 4 x 30) / 10 = 24, não a média simples de 20 e 30 (= 25)
        assert df.loc["Café", "custo_unitario_medio"] == pytest.approx(24.0)


class TestFornecedores:

    def test_compara_fornecedores_do_mesmo_insumo(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "07_desempenho_fornecedores")
        cafe = df[df["produto"] == "Café"].set_index("fornecedor")

        assert cafe.loc["Fornecedor A", "rank_preco"] == 1     # 20 < 30
        assert cafe.loc["Fornecedor B", "rank_preco"] == 2
        assert cafe.loc["Fornecedor A", "avaliacao"] == "MELHOR PRECO"
        # B cobrou 50% acima do melhor preço
        assert cafe.loc["Fornecedor B", "acima_do_melhor_pct"] == pytest.approx(50.0)
        assert cafe.loc["Fornecedor B", "avaliacao"] == "REVISAR CONTRATO"

    def test_economia_potencial(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "07_desempenho_fornecedores")
        cafe_b = df[(df["produto"] == "Café") & (df["fornecedor"] == "Fornecedor B")]
        # (30 - 20) x 4 kg = R$ 40 pagos a mais
        assert cafe_b["economia_potencial"].iloc[0] == pytest.approx(40.0)

    def test_fornecedor_unico_e_sinalizado(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "07_desempenho_fornecedores")
        bolo = df[df["produto"] == "Bolo"]
        assert bolo["avaliacao"].iloc[0] == "FORNECEDOR UNICO"


class TestPerdas:

    def test_classifica_a_causa_pelo_motivo(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "08_perdas_por_causa")
        assert set(df["causa"]) == {"QUEBRA/MANUSEIO"}

    def test_valoriza_a_perda_em_reais(self, banco_analitico):
        engine, _ = banco_analitico
        df = rodar(engine, "08_perdas_por_causa")
        # 0.5 kg x custo médio 24 = R$ 12
        assert df["valor_perdido"].sum() == pytest.approx(12.0)


class TestSegurancaDasQueries:

    def test_nenhuma_query_usa_interpolacao_de_string(self):
        # Parâmetro tem que ser :bind, nunca f-string ou concatenação em Python.
        # Se alguém colar um `.format()` num .sql, isso aqui não pega — mas
        # pega o caso comum de sobrar um placeholder de formatação Python.
        for nome in listar_queries():
            sql = carregar_query(nome)
            assert "{" not in sql, f"{nome} tem placeholder de format() — use :bind"
            assert "%s" not in sql, f"{nome} usa %s — use :bind"

    def test_toda_query_filtra_por_tenant(self):
        # tenant_id não isola nada hoje, mas a query precisa estar pronta:
        # esquecer o filtro agora vira vazamento entre clientes na Fase 3.
        for nome in listar_queries():
            assert ":tenant_id" in carregar_query(nome), f"{nome} não filtra tenant"
