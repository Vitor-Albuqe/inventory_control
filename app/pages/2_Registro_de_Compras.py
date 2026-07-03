from datetime import date

import streamlit as st


import pandas as pd


from app.utils.ui_formater import (
    format_price_variation,
    format_data_compra_badge,
)
from app.utils.data_formater import format_validade
from app.services import (
    dashboard_estoque,
    historico_produto,
    registrar_ajuste_ui,
    registrar_compra_ui,
)

previous_prices = {}


st.set_page_config(
    page_title="Controle de Estoque",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.header("2) Registro de Compras")
st.write("O preço total é calculado automaticamente: quantidade * preço unitário.")

products = dashboard_estoque()


if not products:
    st.warning("Cadastre pelo menos um produto antes de registrar compras.")
    st.stop()

product_options = {f'{p["nome"]} ({p["unidade_medida"]})': p["id"] for p in products}

with st.form("form_compra"):
    product_label = st.selectbox("Produto", list(product_options.keys()))
    quantidade = st.number_input("Quantidade", min_value=0.01, step=1.0)
    preco_unitario = st.number_input("Preço unitário (R$)", min_value=0.01, step=0.5)
    data_compra = st.date_input(
        "Data da compra", value=date.today(), format="DD/MM/YYYY"
    )
    data_validade = st.date_input("Data de validade", value=None, format="DD/MM/YYYY")
    fornecedor = st.text_input("Fornecedor")
    tempo_entrega = st.number_input("Tempo de entrega (dias)", min_value=0, step=1)

    submitted = st.form_submit_button("Registrar compra")

if submitted:
    mov = registrar_compra_ui(
        product_options[product_label],
        quantidade,
        preco_unitario,
        data_compra,
        data_validade,
        fornecedor,
        tempo_entrega,
    )
    st.success(f"Entrada registrada! Preço total: R$ {mov.preco_total:.2f}")


with st.expander("Últimas entradas"):

    h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 2, 1.5, 1.5, 1.5, 1.2, 0.8])

    h1.markdown("**Produto**")
    h2.markdown("**Qtd**")
    h3.markdown("**Preço Unit.**")
    h4.markdown("**Preço Total**")
    h5.markdown("**Data**")
    h6.markdown("**Status**")
    h7.markdown("**Ação**")

    st.divider()

    for p in products:

        historico = historico_produto(p["id"], limit=10)

        entradas = [m for m in historico if m["tipo"] == "entrada"]

        ajustes_origem = {
            m["movimento_referencia_id"]
            for m in historico
            if m["movimento_referencia_id"]
        }

        for e in entradas:

            corrigido = e["id"] in ajustes_origem

            if corrigido:
                continue
            status = "⚠️ Corrigido" if corrigido else "✅ OK"

            valor_unitario = float(e["preco_unitario"] or 0)

            quantidade = float(e["quantidade"] or 0)

            valor_total = valor_unitario * quantidade

            c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 1.5, 1.5, 1.5, 1.2, 0.8])

            c1.write(p["nome"])

            c2.write(f"{quantidade:.0f} {p['unidade_medida']}")

            c3.write(f"R$ {valor_unitario:.2f}")

            c4.write(f"R$ {valor_total:.2f}")

            c5.write(e["data"].strftime("%d/%m/%Y"))

            c6.write(status)

            if c7.button(
                "↩️",
                key=f"ajuste_{e['id']}",
                disabled=corrigido,
            ):

                registrar_ajuste_ui(
                    product_id=p["id"],
                    quantidade=abs(e["quantidade"]),
                    direcao="saida",
                    motivo="Correção de entrada registrada incorretamente",
                    observacao=f"Correção da movimentação {e['id']}",
                    movimento_referencia_id=e["id"],
                )

                st.success("Entrada corrigida!")

                st.rerun()

            st.divider()
