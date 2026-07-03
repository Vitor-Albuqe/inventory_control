"""Página PDV — Ponto de Venda."""

from datetime import date
from babel.numbers import format_currency

import pandas as pd
import plotly.express as px
import streamlit as st

from app.services import (
    listar_produtos_vendaveis,
    listar_vendas_ui,
    registrar_venda_com_consumo_ui,
    resumo_vendas_hoje,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

st.set_page_config(page_title="PDV — Vendas", layout="wide")

# ─── SESSION STATE ────────────────────────────────────────────────────────────

if "carrinho" not in st.session_state:
    # {product_id: {nome, preco, qtd, tipo}}
    st.session_state.carrinho = {}

# ─── HELPERS ─────────────────────────────────────────────────────────────────


def _fmt(v: float) -> str:
    return format_currency(v, "BRL", locale="pt_BR")


def _total_carrinho() -> float:
    return sum(i["preco"] * i["qtd"] for i in st.session_state.carrinho.values())


def _adicionar(pid: int, nome: str, preco: float, tipo: str) -> None:
    if pid in st.session_state.carrinho:
        st.session_state.carrinho[pid]["qtd"] += 1
    else:
        st.session_state.carrinho[pid] = {
            "nome": nome,
            "preco": preco,
            "qtd": 1,
            "tipo": tipo,
        }


def _alterar_qtd(pid: int, delta: int) -> None:
    if pid not in st.session_state.carrinho:
        return
    nova = st.session_state.carrinho[pid]["qtd"] + delta
    if nova <= 0:
        st.session_state.carrinho.pop(pid)
    else:
        st.session_state.carrinho[pid]["qtd"] = nova


def _remover(pid: int) -> None:
    st.session_state.carrinho.pop(pid, None)


def _limpar() -> None:
    st.session_state.carrinho = {}


# ─── KPIs ─────────────────────────────────────────────────────────────────────

st.title("☕ Ponto de Venda")

resumo = resumo_vendas_hoje()
c1, c2, c3 = st.columns(3)
c1.metric("💰 Receita Hoje", _fmt(resumo["total"]))
c2.metric("🛒 Vendas Hoje", resumo["count"])
c3.metric("🎯 Ticket Médio", _fmt(resumo["ticket_medio"]))

# ─── FLASH MESSAGES (exibidas após rerun) ────────────────────────────────────

if st.session_state.get("flash_success"):
    st.success(f"✅ {st.session_state.pop('flash_success')}")
for _msg in st.session_state.pop("flash_warnings", []):
    st.warning(_msg)
for _msg in st.session_state.pop("flash_errors", []):
    st.error(_msg)

st.divider()

# ─── LAYOUT PRINCIPAL ─────────────────────────────────────────────────────────

col_prod, col_cart = st.columns([2, 1], gap="large")

# ══════════════════════════════════════════════════════════════════════════════
# PAINEL DE PRODUTOS
# ══════════════════════════════════════════════════════════════════════════════

with col_prod:
    st.subheader("📦 Produtos")
    produtos = listar_produtos_vendaveis()

    if not produtos:
        st.warning(
            "Nenhum produto disponível para venda. "
            "Cadastre produtos do tipo **Produto Final** ou **Receita** "
            "com preço de venda definido."
        )
    else:
        busca = st.text_input(
            "Buscar produto",
            placeholder="🔍  Pesquisar...",
            label_visibility="collapsed",
        )

        filtrados = (
            [p for p in produtos if busca.lower() in p["nome"].lower()]
            if busca
            else produtos
        )

        if not filtrados:
            st.info("Nenhum produto encontrado para a busca.")
        else:
            COLS_POR_LINHA = 3
            for row_start in range(0, len(filtrados), COLS_POR_LINHA):
                linha = filtrados[row_start : row_start + COLS_POR_LINHA]
                grid = st.columns(COLS_POR_LINHA)

                for j, p in enumerate(linha):
                    with grid[j]:
                        with st.container(border=True):
                            tipo_label = (
                                "Receita" if p["tipo"] == "receita" else "Produto Final"
                            )
                            st.markdown(f"**{p['nome']}**")

                            if p["preco_venda"] is not None:
                                st.markdown(
                                    f"<p style='font-size:1.15rem;font-weight:700;"
                                    f"color:#6F4E37;margin:2px 0 4px'>"
                                    f"{_fmt(p['preco_venda'])}</p>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.caption("sem preço cadastrado")

                            st.caption(tipo_label)

                            no_cart = p["id"] in st.session_state.carrinho
                            qtd_cart = (
                                st.session_state.carrinho[p["id"]]["qtd"]
                                if no_cart
                                else 0
                            )
                            btn_label = (
                                f"✅  {qtd_cart}× no carrinho"
                                if no_cart
                                else "＋  Adicionar"
                            )

                            if st.button(
                                btn_label,
                                key=f"add_{p['id']}",
                                use_container_width=True,
                                disabled=p["preco_venda"] is None,
                            ):
                                _adicionar(
                                    p["id"], p["nome"], p["preco_venda"], p["tipo"]
                                )
                                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAINEL DO CARRINHO
# ══════════════════════════════════════════════════════════════════════════════

with col_cart:
    st.subheader("🧾 Carrinho")

    if not st.session_state.carrinho:
        st.info("Carrinho vazio.\nSelecione um produto ao lado.")
    else:
        for pid, item in list(st.session_state.carrinho.items()):
            with st.container(border=True):
                st.markdown(f"**{item['nome']}**")

                q1, q2, q3, q4 = st.columns([1, 1, 1, 1])

                with q1:
                    if st.button("−", key=f"menos_{pid}", use_container_width=True):
                        _alterar_qtd(pid, -1)
                        st.rerun()
                with q2:
                    st.markdown(
                        f"<div style='text-align:center;padding-top:6px;"
                        f"font-weight:700;font-size:1.1rem'>{item['qtd']}</div>",
                        unsafe_allow_html=True,
                    )
                with q3:
                    if st.button("＋", key=f"mais_{pid}", use_container_width=True):
                        _alterar_qtd(pid, +1)
                        st.rerun()
                with q4:
                    if st.button("🗑", key=f"rm_{pid}", use_container_width=True):
                        _remover(pid)
                        st.rerun()

                subtotal = item["preco"] * item["qtd"]
                st.text(
                    f"{item['qtd']} × {_fmt(item['preco'])} = {_fmt(subtotal)}"
                )

        st.divider()

        total = _total_carrinho()
        st.markdown(
            f"<div style='text-align:center;font-size:1.6rem;"
            f"font-weight:800;color:#6F4E37;padding:8px 0'>"
            f"Total: {_fmt(total)}</div>",
            unsafe_allow_html=True,
        )

        st.markdown("")
        data_venda = st.date_input(
            "📅 Data da venda", value=date.today(), key="pdv_data"
        )

        if st.button(
            "✅  Finalizar Venda",
            type="primary",
            use_container_width=True,
        ):
            pids_sucesso: list[int] = []
            avisos: list[str] = []
            erros: list[str] = []
            total_vendido: float = 0.0

            for pid, item in list(st.session_state.carrinho.items()):
                try:
                    res = registrar_venda_com_consumo_ui(
                        product_id=pid,
                        quantidade=float(item["qtd"]),
                        valor_unitario=item["preco"],
                        data_venda=data_venda,
                    )
                    pids_sucesso.append(pid)
                    total_vendido += res["valor_total"]
                    avisos.extend(res.get("avisos", []))
                except Exception as exc:
                    erros.append(f"**{item['nome']}**: {exc}")

            for pid in pids_sucesso:
                st.session_state.carrinho.pop(pid, None)

            if pids_sucesso:
                st.session_state.flash_success = (
                    f"{len(pids_sucesso)} item(s) vendido(s) — Total: {_fmt(total_vendido)}"
                )
            st.session_state.flash_warnings = avisos
            st.session_state.flash_errors = erros
            st.rerun()

        if st.button("🗑  Limpar carrinho", use_container_width=True):
            _limpar()
            st.rerun()

# ─── HISTÓRICO ────────────────────────────────────────────────────────────────

st.divider()

with st.expander("📋 Histórico de Vendas", expanded=False):
    hf1, hf2, hf3 = st.columns(3)

    with hf1:
        h_inicio = st.date_input(
            "De",
            value=None,
            key="h_inicio",
            help="Deixe em branco para ver todo o histórico",
        )
    with hf2:
        h_fim = st.date_input("Até", value=date.today(), key="h_fim")
    with hf3:
        h_limite = st.selectbox("Exibir até", [50, 100, 200, 500], index=0)

    vendas = listar_vendas_ui(data_inicio=h_inicio, data_fim=h_fim, limit=h_limite)

    if not vendas:
        st.info("Nenhuma venda encontrada para o período selecionado.")
    else:
        df = pd.DataFrame(vendas)

        df_dia = (
            df.groupby("data")["valor_total"]
            .sum()
            .reset_index()
            .rename(columns={"data": "Data", "valor_total": "Receita (R$)"})
        )
        df_dia["Data"] = pd.to_datetime(df_dia["Data"])
        df_dia = df_dia.sort_values("Data")

        if len(df_dia) > 1:
            fig = px.bar(
                df_dia,
                x="Data",
                y="Receita (R$)",
                title="📊 Receita por Dia",
                color_discrete_sequence=["#6F4E37"],
            )
            fig.update_layout(
                xaxis_title="", yaxis_title="Receita (R$)", showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

        df_tab = df.copy()
        df_tab["data"] = pd.to_datetime(df_tab["data"]).dt.strftime("%d/%m/%Y")
        df_tab["valor_unitario"] = df_tab["valor_unitario"].apply(_fmt)
        df_tab["valor_total"] = df_tab["valor_total"].apply(_fmt)
        df_tab = df_tab.rename(
            columns={
                "data": "Data",
                "produto_nome": "Produto",
                "quantidade": "Qtd",
                "valor_unitario": "Preço Unit.",
                "valor_total": "Total",
            }
        )
        st.dataframe(
            df_tab[["Data", "Produto", "Qtd", "Preço Unit.", "Total"]],
            use_container_width=True,
            hide_index=True,
        )

        total_periodo = sum(v["valor_total"] for v in vendas)
        st.markdown(
            f"**Total no período: {_fmt(total_periodo)}** ({len(vendas)} vendas)"
        )
