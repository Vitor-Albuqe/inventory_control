"""Análises gerenciais em SQL puro.

Cada aba roda uma query de `sql/`, com o SQL exposto ao usuário — o objetivo
é que a regra de cálculo seja auditável por quem toma a decisão, não uma
caixa-preta. O botão de exportar entrega o mesmo resultado em CSV.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from app.repositories import analytics_repository as an

st.set_page_config(page_title="Análises SQL", layout="wide")

st.title("📊 Análises Gerenciais (SQL)")
st.caption(
    "Consultas analíticas executadas direto no banco. O SQL de cada análise "
    "fica visível em 'Ver a query' — mesmo arquivo que alimenta o Power BI."
)

# ---------------------------------------------------------------------------
# Filtro de período — compartilhado por todas as abas que aceitam intervalo
# ---------------------------------------------------------------------------

col_ini, col_fim, _ = st.columns([1, 1, 2])
with col_ini:
    data_inicio = st.date_input("De", value=date.today() - timedelta(days=180))
with col_fim:
    data_fim = st.date_input("Até", value=date.today())

if data_inicio > data_fim:
    st.error("A data inicial não pode ser maior que a final.")
    st.stop()

st.divider()


def mostrar(nome_query: str, df: pd.DataFrame, vazio: str) -> bool:
    """Renderiza tabela + SQL + download. Devolve False se não houver dados."""
    if df.empty:
        st.info(vazio)
        with st.expander("Ver a query"):
            st.code(an.carregar_query(nome_query), language="sql")
        return False

    st.dataframe(df, use_container_width=True, hide_index=True)

    col_sql, col_csv = st.columns([4, 1])
    with col_sql:
        with st.expander("Ver a query"):
            st.code(an.carregar_query(nome_query), language="sql")
    with col_csv:
        st.download_button(
            "⬇️ CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{nome_query}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    return True


abas = st.tabs([
    "Posição de estoque",
    "Reposição",
    "Giro",
    "Curva ABC",
    "Evolução mensal",
    "Margem",
    "Fornecedores",
    "Perdas",
])

# ---------------------------------------------------------------------------
# 1. Posição de estoque
# ---------------------------------------------------------------------------
with abas[0]:
    st.subheader("Quanto tenho de cada item, e quem está abaixo do mínimo")
    df = an.posicao_estoque()

    if not df.empty:
        criticos = int((df["status_estoque"].isin(["RUPTURA", "ABAIXO DO MINIMO"])).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Itens monitorados", len(df))
        c2.metric("Abaixo do mínimo", criticos)
        c3.metric("Em ruptura", int((df["status_estoque"] == "RUPTURA").sum()))

    mostrar("01_posicao_estoque", df, "Sem produtos cadastrados.")

# ---------------------------------------------------------------------------
# 2. Alertas de reposição
# ---------------------------------------------------------------------------
with abas[1]:
    st.subheader("A lista de compras de hoje")
    c1, c2 = st.columns(2)
    dias_validade = c1.slider("Janela de vencimento (dias)", 1, 30, 7)
    dias_cobertura = c2.slider("Comprar para quantos dias", 3, 60, 15)

    df = an.alertas_reposicao(dias_validade=dias_validade, dias_cobertura=dias_cobertura)
    st.caption(
        "A sugestão de compra vem do consumo médio diário dos últimos 30 dias, "
        "não de um valor fixo cadastrado."
    )
    mostrar("02_alertas_reposicao", df, "✅ Nenhum alerta ativo.")

# ---------------------------------------------------------------------------
# 3. Giro de estoque
# ---------------------------------------------------------------------------
with abas[2]:
    st.subheader("O que gira e o que está parado travando capital")
    df = an.giro_estoque(data_inicio, data_fim)

    if mostrar("03_giro_estoque", df, "Sem movimentações no período."):
        grafico = df.dropna(subset=["giro"]).head(15)
        if not grafico.empty:
            fig = px.bar(
                grafico.sort_values("giro"),
                x="giro", y="produto", orientation="h",
                color="classificacao_giro",
                labels={"giro": "Giro no período", "produto": ""},
                title="Giro por produto (maior = sai mais rápido da prateleira)",
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 4. Curva ABC
# ---------------------------------------------------------------------------
with abas[3]:
    st.subheader("Quais itens sustentam o faturamento (Pareto)")
    df = an.curva_abc(data_inicio, data_fim)

    if mostrar("04_curva_abc", df, "Sem vendas no período."):
        resumo = df.groupby("classe_abc").agg(
            itens=("produto", "count"),
            receita=("receita", "sum"),
            perc=("perc_receita", "sum"),
        ).reset_index()
        c1, c2 = st.columns([1, 2])
        with c1:
            st.dataframe(resumo, use_container_width=True, hide_index=True)
            st.caption(
                "A = até 80% da receita · B = 80–95% · C = os 5% finais. "
                "Classe C é candidata a sair do cardápio."
            )
        with c2:
            fig = px.line(
                df, x="posicao", y="perc_acumulado", markers=True,
                labels={"posicao": "Produtos (do maior para o menor)",
                        "perc_acumulado": "% acumulado da receita"},
                title="Curva de Pareto do faturamento",
            )
            fig.add_hline(y=80, line_dash="dash", annotation_text="80%")
            st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 5. Evolução mensal
# ---------------------------------------------------------------------------
with abas[4]:
    st.subheader("O consumo acompanha a receita, ou estou desperdiçando mais?")
    df = an.evolucao_mensal()

    if mostrar("05_evolucao_mensal", df, "Sem histórico."):
        fig = px.line(
            df, x="ano_mes", y=["receita", "investido_compras", "gastos_operacionais"],
            markers=True,
            labels={"ano_mes": "Mês", "value": "R$", "variable": ""},
            title="Receita x compras x gastos operacionais",
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.bar(
            df, x="ano_mes", y="consumo_por_real",
            labels={"ano_mes": "Mês", "consumo_por_real": "Insumo consumido por R$ faturado"},
            title="Consumo por real faturado (subindo = desperdício ou porção fora de controle)",
        )
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# 6. Margem
# ---------------------------------------------------------------------------
with abas[5]:
    st.subheader("O mais vendido é o mais lucrativo?")
    df = an.margem_por_receita(data_inicio, data_fim)

    if mostrar("06_margem_por_receita", df, "Sem produtos com preço de venda."):
        grafico = df.dropna(subset=["margem_pct", "qtd_vendida"])
        if not grafico.empty:
            fig = px.scatter(
                grafico, x="qtd_vendida", y="margem_pct",
                size="lucro_bruto_total", color="tipo_produto",
                hover_name="produto",
                labels={"qtd_vendida": "Quantidade vendida",
                        "margem_pct": "Margem %"},
                title="Volume x margem (bolha = lucro bruto total)",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Canto superior direito = os campeões. Inferior direito = vende "
                "muito e dá pouco: candidato a reajuste de preço ou de ficha técnica."
            )

# ---------------------------------------------------------------------------
# 7. Fornecedores
# ---------------------------------------------------------------------------
with abas[6]:
    st.subheader("Estou comprando do fornecedor certo?")
    df = an.desempenho_fornecedores(data_inicio, data_fim)

    if not df.empty:
        economia = float(df["economia_potencial"].sum())
        st.metric(
            "Economia potencial no período",
            f"R$ {economia:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            help="Diferença entre o que foi pago e o melhor preço encontrado "
                 "para cada insumo no mesmo período.",
        )

    mostrar("07_desempenho_fornecedores", df, "Sem compras com fornecedor no período.")

# ---------------------------------------------------------------------------
# 8. Perdas
# ---------------------------------------------------------------------------
with abas[7]:
    st.subheader("Quanto é jogado fora, e por quê")
    df = an.perdas_por_causa(data_inicio, data_fim)

    if mostrar("08_perdas_por_causa", df, "✅ Nenhuma perda registrada no período."):
        por_causa = df.groupby("causa", as_index=False)["valor_perdido"].sum()
        c1, c2 = st.columns(2)
        with c1:
            fig = px.pie(
                por_causa, names="causa", values="valor_perdido", hole=0.45,
                title="Perda por causa (R$)",
            )
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            por_mes = df.groupby("ano_mes", as_index=False)["valor_perdido"].sum()
            fig2 = px.bar(
                por_mes, x="ano_mes", y="valor_perdido",
                labels={"ano_mes": "Mês", "valor_perdido": "R$ perdidos"},
                title="Perda mensal",
            )
            st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "Vencimento se resolve comprando menos e com mais frequência; "
            "quebra se resolve com processo e treinamento. São ações diferentes."
        )
