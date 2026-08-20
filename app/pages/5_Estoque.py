from __future__ import annotations

import html
from datetime import date

import streamlit as st

from app.services  import (
    abertos_proximos_vencimento,
    abrir_produto,
    dashboard_estoque,
    esgotar_lote,
    lotes_abertos_detalhados,
    produtos_ativos_opcoes,
    registrar_ajuste_ui,
    registrar_consumo_ui,
    registrar_perda_ui,
)
from app.utils import formatar_quantidade_estoque

st.set_page_config(
    page_title="Controle de Estoque",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📦 Controle de Estoque")


st.subheader("📊 Estoque atual")
busca = st.text_input("🔍 Buscar produto")

try:
    stock_data = dashboard_estoque()

    if stock_data:
        if busca:
            stock_data = [p for p in stock_data if busca.lower() in p["nome"].lower()]

        col = st.columns([3, 2, 1.1, 1.1, 1.1, 1.1, 1.2, 1.4])
        col[0].markdown("**🧾 Produto**")
        col[1].markdown("**📁 Tipo**")
        col[2].markdown("**📦 Fechado**")
        col[3].markdown("**🧊 Em uso**")
        col[4].markdown("**📦 Total**")
        col[5].markdown("**⚠️ Mín**")
        col[6].markdown("**Abrir qtde**")

        st.divider()

        for item in stock_data:
            produto_id = item["id"]
            unidade = item["unidade_medida"]
            fechado = item["estoque_fechado"]
            em_uso = item["estoque_aberto"]
            total = item["estoque_total"]

            col = st.columns([3, 2, 1.1, 1.1, 1.1, 1.1, 1.2, 1.4])

            col[0].markdown(
                (
                    f"<span style='font-size:30px'><b>{html.escape(item['nome'])}</b>  \n"
                    f"<span style='font-size:15px;color:gray'>"
                    f"{unidade}</span>"
                ),
                unsafe_allow_html=True,
            )
            col[1].markdown(
                f"<span style='font-size:20px'>{item['tipo']}</span>",
                unsafe_allow_html=True,
            )
            col[2].markdown(
                f"<span style='font-size:20px;font-weight:600'>"
                f"{formatar_quantidade_estoque(fechado, unidade)}</span>",
                unsafe_allow_html=True,
            )
            col[3].markdown(
                f"<span style='font-size:20px'>"
                f"{formatar_quantidade_estoque(em_uso, unidade)}</span>",
                unsafe_allow_html=True,
            )
            col[4].markdown(
                f"<span style='font-size:20px'>"
                f"{formatar_quantidade_estoque(total, unidade)}</span>",
                unsafe_allow_html=True,
            )
            col[5].markdown(
                f"<span style='font-size:20px'>"
                f"{formatar_quantidade_estoque(item['estoque_minimo'], unidade)}</span>",
                unsafe_allow_html=True,
            )

            controla = item.get("controla_abertura", False)

            if controla and fechado > 0:
                with col[6]:
                    with st.form(key=f"form_abrir_{produto_id}", border=False):
                        qtd = st.number_input(
                            "Qtd",
                            min_value=min(1.0, float(fechado)),
                            max_value=float(fechado),
                            value=min(1.0, float(fechado)),
                            step=1.0,
                            label_visibility="collapsed",
                        )
                        abrir = st.form_submit_button(
                            "Abrir",
                            use_container_width=True,
                        )
                if abrir:
                    try:
                        abrir_produto(produto_id, float(qtd))
                        st.success(f"Produto aberto ({qtd})!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            else:
                col[6].write("-")
                col[7].write("")

            st.divider()

    # Lotes em uso (uma lista só — evita duplicar na seção de validade)
    st.header("🧊 Lotes em uso")
    lotes = lotes_abertos_detalhados()
    proximos_ids = {p["lot_id"] for p in abertos_proximos_vencimento(dias=3)}

    if lotes:
        por_produto: dict[str, int] = {}
        for lot in lotes:
            por_produto[lot["produto"]] = por_produto.get(lot["produto"], 0) + 1

        for nome, qtd in por_produto.items():
            if qtd > 1:
                st.warning(
                    f"**{nome}**: {qtd} lotes abertos. "
                    "Se não for intencional, consuma o lote antigo antes de abrir outro."
                )

        for lot in lotes:
            urgente = lot["lot_id"] in proximos_ids
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1.2, 1.5, 1])
                titulo = f"**{lot['produto']}** — Lote #{lot['lot_id']}"
                if urgente:
                    titulo += " ⏳"
                c1.markdown(titulo)
                c2.metric(
                    "Em uso",
                    formatar_quantidade_estoque(lot["quantidade_atual"], lot["unidade_medida"]),
                )
                if lot["validade"]:
                    dias = lot["dias_restantes"]
                    if dias is not None and dias <= 0:
                        c3.error("Vencido")
                    elif dias is not None and dias <= 3:
                        c3.warning(f"{dias} dias")
                    else:
                        c3.success(f"{dias} dias")
                    c4.caption(f"Validade: {lot['validade'].strftime('%d/%m/%Y')}")
                else:
                    c3.caption("Sem validade")
                if c5.button(
                    "Esgotar",
                    key=f"esgotar_{lot['lot_id']}",
                    help="Registra consumo de todo o lote",
                ):
                    try:
                        esgotar_lote(lot["lot_id"])
                        st.success("Lote esgotado.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
    else:
        st.info("Nenhum lote em uso.")

    # Ações rápidas
    st.header("⚙️ Ações rápidas")

    opcoes = produtos_ativos_opcoes()
    lotes_abertos = lotes_abertos_detalhados()
    lotes_por_produto: dict[int, list] = {}
    for lot in lotes_abertos:
        lotes_por_produto.setdefault(lot["product_id"], []).append(lot)

    tab1, tab2, tab3 = st.tabs(["✅ Consumo", "🗑️ Perda", "🛠️ Ajuste"])

    with tab1:
        nome = st.selectbox("Produto", list(opcoes.keys()), key="consumo_produto")
        if nome is None:
            st.stop()
        pid = opcoes[nome]
        lotes_prod = lotes_por_produto.get(pid, [])
        lot_id = None
        if lotes_prod:
            lot_labels = {
                f"Lote #{l['lot_id']} — {l['quantidade_atual']} un."
                + (
                    f" (vence {l['validade'].strftime('%d/%m')})"
                    if l["validade"]
                    else ""
                ): l["lot_id"]
                for l in lotes_prod
            }
            modo = st.radio(
                "Alocação",
                ["FEFO automático", "Escolher lote"],
                horizontal=True,
                key="consumo_modo",
            )
            if modo == "Escolher lote":
                lot_id = lot_labels[
                    st.selectbox("Lote", list(lot_labels.keys()), key="consumo_lote")
                ]
        qty = st.number_input(
            "Quantidade", min_value=0.01, value=1.0, step=0.5, key="consumo_qty"
        )
        obs = st.text_input("Observação (opcional)", key="consumo_obs")
        with st.form("form_consumo", clear_on_submit=True):
            enviar = st.form_submit_button("Registrar consumo", type="primary")
        if enviar:
            try:
                registrar_consumo_ui(
                    pid,
                    float(qty),
                    lot_id=lot_id,
                    observacao=obs or None,
                )
                st.success("Consumo registrado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with tab2:
        nome = st.selectbox("Produto", list(opcoes.keys()), key="perda_produto")
        pid = opcoes[nome]
        estoque_afetado = st.selectbox(
            "Estoque afetado",
            ["fechado", "aberto"],
            key="perda_estoque",
        )
        lot_id = None
        if estoque_afetado == "aberto":
            lotes_prod = lotes_por_produto.get(pid, [])
            if lotes_prod:
                modo = st.radio(
                    "Alocação",
                    ["FEFO automático", "Escolher lote"],
                    horizontal=True,
                    key="perda_modo",
                )
                if modo == "Escolher lote":
                    lot_labels = {
                        f"Lote #{l['lot_id']} — {l['quantidade_atual']} un.": l[
                            "lot_id"
                        ]
                        for l in lotes_prod
                    }
                    lot_id = lot_labels[
                        st.selectbox("Lote", list(lot_labels.keys()), key="perda_lote")
                    ]
        qty = st.number_input(
            "Quantidade", min_value=0.01, value=1.0, step=0.5, key="perda_qty"
        )
        motivo = st.text_input("Motivo (obrigatório)", key="perda_motivo")
        obs = st.text_input("Observação (opcional)", key="perda_obs")
        with st.form("form_perda", clear_on_submit=True):
            enviar = st.form_submit_button("Registrar perda", type="primary")
        if enviar:
            try:
                registrar_perda_ui(
                    pid,
                    float(qty),
                    motivo,
                    estoque_afetado=estoque_afetado,
                    lot_id=lot_id,
                    observacao=obs or None,
                )
                st.success("Perda registrada.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with tab3:
        nome = st.selectbox("Produto", list(opcoes.keys()), key="ajuste_produto")
        direcao = st.selectbox("Direção", ["entrada", "saida"], key="ajuste_direcao")
        qty = st.number_input(
            "Quantidade", min_value=0.01, value=1.0, step=0.5, key="ajuste_qty"
        )
        motivo = st.text_input("Motivo (obrigatório)", key="ajuste_motivo")
        obs = st.text_input("Observação (opcional)", key="ajuste_obs")
        if st.button("Registrar ajuste", type="primary"):
            try:
                registrar_ajuste_ui(
                    opcoes[nome],
                    float(qty),
                    direcao=direcao,
                    motivo=motivo,
                    observacao=obs or None,
                )
                st.success("Ajuste registrado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


except ValueError as e:
    st.error(str(e))
