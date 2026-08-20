from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from app.services import (
    PERIODOS_DASHBOARD,
    criar_gasto,
    dados_dashboard_financeiro,
    excluir_gasto,
    intervalo_por_periodo,
    obter_gasto,
)

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Dashboard Financeiro",
    layout="wide",
)

st.title("☕ Dashboard Financeiro")


# =====================================================
# FILTRO DE PERÍODO
# =====================================================

col_periodo, col_custom_inicio, col_custom_fim = st.columns([2, 1, 1])

with col_periodo:
    periodo = st.selectbox(
        "📅 Período",
        PERIODOS_DASHBOARD + ["Personalizado"],
        index=1,
    )

if periodo == "Personalizado":
    with col_custom_inicio:
        data_inicio = st.date_input("De", value=date.today().replace(day=1))
    with col_custom_fim:
        data_fim = st.date_input("Até", value=date.today())
else:
    data_inicio, data_fim = intervalo_por_periodo(periodo)

st.divider()


# =====================================================
# DADOS DA TELA
# =====================================================

dashboard_data = dados_dashboard_financeiro(data_inicio, data_fim)

receita = dashboard_data["receita"]
investimento = dashboard_data["investimento"]
gastos = dashboard_data["gastos"]
lucro = dashboard_data["lucro"]
vendas = dashboard_data["vendas"]


# =====================================================
# KPI PRINCIPAL
# =====================================================

m1, m2, m3, m4 = st.columns(4)

m1.metric("💰 Receita Total", f"R$ {receita:,.2f}")

m2.metric("📦 Investimento Estoque", f"R$ {investimento:,.2f}")

m3.metric("🧾 Gastos Gerais", f"R$ {gastos:,.2f}")

m4.metric("📈 Lucro Estimado", f"R$ {lucro:,.2f}")

st.divider()


# =====================================================
# GRÁFICOS
# =====================================================

c1, c2 = st.columns(2)


# =====================================================
# EVOLUÇÃO DE VENDAS
# =====================================================

sales_df = pd.DataFrame(dashboard_data["sales"])

if not sales_df.empty:

    sales_grouped = sales_df.groupby("Data")["Valor"].sum().reset_index()

    fig_sales = px.line(
        sales_grouped,
        x="Data",
        y="Valor",
        title="📈 Evolução das Vendas",
        markers=True,
    )

    c1.plotly_chart(fig_sales, use_container_width=True)

else:

    c1.info("Nenhuma venda registrada")


# =====================================================
# GASTOS
# =====================================================

expense_df = pd.DataFrame(dashboard_data["expenses_chart"])

if not expense_df.empty:

    expense_grouped = expense_df.groupby("Categoria")["Valor"].sum().reset_index()

    fig_expenses = px.pie(
        expense_grouped,
        names="Categoria",
        values="Valor",
        title="💸 Distribuição de Gastos",
    )

    c2.plotly_chart(fig_expenses, use_container_width=True)

else:

    c2.info("Nenhum gasto registrado")


st.divider()


# =====================================================
# PERFORMANCE
# =====================================================

st.subheader("📊 Performance do Café")


p1, p2, p3 = st.columns(3)


p1.metric("🛒 Total de Vendas", vendas)


if lucro > 0:

    p2.success("O negócio está operando com lucro")

else:

    p2.error("O negócio está operando no prejuízo")


margem = 0

if receita > 0:

    margem = (lucro / receita) * 100


p3.metric("📌 Margem de Lucro", f"{margem:.1f}%")


st.divider()


# =====================================================
# FORM GASTOS
# =====================================================

st.subheader("➕ Adicionar Gasto")


with st.form("expense_form"):

    nome = st.text_input("Nome do gasto")

    categoria = st.selectbox(
        "Categoria",
        [
            "fixo",
            "variavel",
        ],
    )

    valor = st.number_input(
        "Valor",
        min_value=0.0,
        step=0.01,
    )

    data_gasto = st.date_input("Data", value=date.today())

    submitted = st.form_submit_button("Salvar gasto")

    if submitted:

        criar_gasto(nome, categoria, valor, data_gasto)

        st.success("Gasto cadastrado!")

        st.rerun()


st.divider()


# =====================================================
# TABELA GASTOS
# =====================================================
expenses = dashboard_data["expenses"]

st.subheader("📋 Gastos Registrados")

if expenses:

    cab1, cab2, cab3, cab4, cab5 = st.columns([3, 2, 2, 2, 1])

    cab1.markdown("**Nome**")
    cab2.markdown("**Categoria**")
    cab3.markdown("**Valor**")
    cab4.markdown("**Data**")
    cab5.markdown("**Ações**")

    st.divider()

    for expense in expenses:

        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])

        with col1:
            st.write(expense["nome"])

        with col2:
            st.write(expense["categoria"])

        with col3:
            st.write(f"R$ {expense['valor']:,.2f}")

        with col4:
            st.write(expense["data"].strftime("%d/%m/%Y"))

        with col5:

            if st.button(
                "🗑️", key=f"delete_expense_{expense['id']}", help="Excluir gasto"
            ):
                st.session_state["expense_to_delete"] = expense["id"]

    # ==================================================
    # MODAL DE CONFIRMAÇÃO
    # ==================================================

    if "expense_to_delete" in st.session_state:

        expense_id = st.session_state["expense_to_delete"]

        expense = obter_gasto(expense_id)

        if expense:

            with st.container(border=True):

                st.warning(
                    f"Tem certeza que deseja excluir " f"o gasto '{expense['nome']}'?"
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "✅ Confirmar Exclusão",
                        use_container_width=True,
                    ):

                        excluir_gasto(expense_id)

                        del st.session_state["expense_to_delete"]

                        st.success("Gasto removido com sucesso!")

                        st.rerun()

                with col2:

                    if st.button(
                        "❌ Cancelar",
                        use_container_width=True,
                    ):

                        del st.session_state["expense_to_delete"]

                        st.rerun()

else:

    st.info("Nenhum gasto registrado.")
