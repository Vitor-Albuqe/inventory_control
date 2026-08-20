from datetime import date

import streamlit as st

from app.services import (
    abertos_proximos_vencimento,
    correcoes_recentes,
    produtos_abaixo_minimo,
)
from app.utils import formatar_quantidade_estoque

st.set_page_config(
    page_title="Alertas Operacionais",
    layout="wide",
)

st.title("🚨 Alertas Operacionais")

st.caption("Produtos que precisam de atenção imediata.")


# =========================================================
# ESTOQUE BAIXO
# =========================================================

st.subheader("📉 Produtos abaixo do estoque mínimo")

baixo_minimo = produtos_abaixo_minimo()

if baixo_minimo:

    for p in baixo_minimo:

        st.error(
            f"{p['nome']} "
            f"({formatar_quantidade_estoque(p['estoque_total'], p['unidade_medida'])}) "
            f"abaixo do mínimo "
            f"({formatar_quantidade_estoque(p['estoque_minimo'], p['unidade_medida'])})"
        )

else:

    st.success("✅ Nenhum produto abaixo do estoque mínimo.")

# =========================================================
# PRODUTOS ABERTOS PRÓXIMOS DO VENCIMENTO
# =========================================================

st.subheader("⏳ Produtos abertos próximos do vencimento")

proximos = abertos_proximos_vencimento(dias=3)

if proximos:

    for item in proximos:

        dias = item["dias_restantes"]

        quantidade_formatada = formatar_quantidade_estoque(
            item["quantidade"], item["unidade_medida"]
        )
        mensagem = (
            f"{item['produto']} "
            f"vence em {dias} dias "
            f"({quantidade_formatada} em uso)"
        )

        if dias <= 1:

            st.error(f"🚨 {mensagem}")

        else:

            st.warning(f"⚠️ {mensagem}")

else:

    st.success("✅ Nenhum produto aberto próximo do vencimento.")

# =========================================================
# MOVIMENTAÇÕES CORRIGIDAS
# =========================================================

st.subheader("↩️ Correções recentes")

ajustes = correcoes_recentes(limit=10)

if ajustes:

    for a in ajustes:

        direcao = "➕" if a["direcao"] == "entrada" else "➖"
        quantidade_formatada = formatar_quantidade_estoque(a["quantidade"], a["unidade_medida"])

        st.info(
            f"{direcao} " f"{a['produto']} | " f"{quantidade_formatada} | " f"{a['motivo']}"
        )

else:

    st.success("✅ Nenhuma correção recente.")

# =========================================================
# RESUMO RÁPIDO
# =========================================================

st.divider()

st.subheader("📌 Resumo do dia")

qtd_criticos = len(baixo_minimo)
qtd_vencendo = len(proximos)

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "Produtos abaixo do mínimo",
        qtd_criticos,
    )

with col2:

    st.metric(
        "Produtos próximos do vencimento",
        qtd_vencendo,
    )
