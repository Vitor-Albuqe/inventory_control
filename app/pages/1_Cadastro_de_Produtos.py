import html

import streamlit as st

from app.utils.unit_converter import (
    converter_para_estoque,
    formatar_receita,
    quantidade_exibicao,
    unidade_exibicao,
)

st.set_page_config(
    page_title="Controle de Estoque",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.services import (pode_excluir, 
        pode_excluir_receita,
        adicionar_ingrediente_receita_ui,
        alternar_produto_ui,
        alternar_receita_ui,
        atualizar_quantidade_receita_ui,
        catalogo_produtos,
        copiar_ingredientes_receita,
        custo_receita_ui,
        custo_unitario_produto_ui,
        excluir_produto_ui,
        mudar_preco_receita_ui,
        remover_receita_item_ui,
        remover_receita_ui,
        salvar_produto_com_receita,

)


UNIDADES_MEDIDA = ["g", "kg", "ml", "L", "un"]

TIPOS_LABEL = {
    "materia_prima": "Matéria-Prima",
    "consumivel": "Consumível",
    "produto_final": "Produto Final",
    "receita": "Receita",
}


# =========================================================
# CADASTRO
# =========================================================

st.header("1) Cadastro de Produtos")

st.write(
    "Produtos com tamanhos diferentes "
    "(ex.: Cookie 100g e Cookie 200g) "
    "devem ser cadastrados separadamente."
)

nome = st.text_input("Nome do produto")

tipo_produto = st.selectbox(
    "Tipo do Produto",
    [
        "materia_prima",
        "consumivel",
        "produto_final",
        "receita",
    ],
)

unidade_medida = st.selectbox(
    "Unidade",
    UNIDADES_MEDIDA,
)

estoque_minimo = 0

if tipo_produto != "receita":

    estoque_minimo = st.number_input(
        "Estoque mínimo",
        min_value=0.0,
    )

# =========================================================
# MATÉRIA PRIMA / CONSUMÍVEL
# =========================================================

controla_abertura = False
validade_apos_abertura = None

if tipo_produto in (
    "materia_prima",
    "consumivel",
):

    controla_abertura = st.checkbox("Controla abertura?")

    if controla_abertura:

        validade_apos_abertura = st.number_input(
            "Validade após aberto (dias)",
            min_value=1,
            step=1,
        )

# =========================================================
# PRODUTO FINAL / RECEITA
# =========================================================

preco_venda = None

if tipo_produto in (
    "produto_final",
    "receita",
):

    preco_venda = st.number_input(
        "Preço de venda",
        min_value=0.0,
        step=0.01,
        format="%.2f",
    )

# =========================================================
# RECEITAS
# =========================================================


products_catalog = catalogo_produtos()
receitas_existentes = [
    p for p in products_catalog if p.tipo_produto.value == "receita" and p.ativo
]

if tipo_produto == "receita":

    st.divider()

    st.subheader("Ingredientes da Receita")

    if "ingredientes_receita" not in st.session_state:
        st.session_state.ingredientes_receita = []

    ingredientes_disponiveis = [
        p for p in products_catalog if p.tipo_produto.value != "receita" and p.ativo
    ]

    if not ingredientes_disponiveis:

        st.warning("Cadastre produtos antes de criar receitas.")

    else:

        col1, col2, col3 = st.columns([3, 1, 1])

        ingrediente_novo = col1.selectbox(
            "Ingrediente",
            ingredientes_disponiveis,
            format_func=lambda p: f"{p.nome} ({p.unidade_medida})",
            key="novo_ingrediente",
        )

        unidade_display = unidade_exibicao(ingrediente_novo.unidade_medida)

        quantidade_digitada = float(
            st.number_input(
                f"Quantidade ({unidade_display})",
                min_value=0.001,
                step=0.1,
                format="%.0f",
            )
        )

        if col3.button(
            "➕ Adicionar",
            use_container_width=True,
        ):

            st.session_state.ingredientes_receita.append(
                {
                    "ingredient_id": ingrediente_novo.id,
                    "nome": ingrediente_novo.nome,
                    "unidade": ingrediente_novo.unidade_medida,
                    # valor digitado pelo usuário
                    "quantidade_exibicao": quantidade_digitada,
                    # valor convertido para estoque
                    "quantidade_estoque": converter_para_estoque(
                        quantidade_digitada,
                        ingrediente_novo.unidade_medida,
                    ),
                }
            )

            st.rerun()

        if st.session_state.ingredientes_receita:

            st.markdown("### Ingredientes adicionados")

            for idx, item in enumerate(st.session_state.ingredientes_receita):

                c1, c2, c3 = st.columns([4, 1, 1])

                c1.write(
                    f"{item['nome']} - "
                    f"{item['quantidade_exibicao']} "
                    f"{unidade_exibicao(item['unidade'])}"
                )

                with c2.popover("✏️"):

                    nova_quantidade = st.number_input(
                        f"Quantidade ({unidade_exibicao(item['unidade'])})",
                        min_value=0.001,
                        value=float(item["quantidade_exibicao"]),
                        step=0.1,
                        key=f"edit_qty_{idx}",
                    )

                    if st.button(
                        "Salvar",
                        key=f"save_edit_{idx}",
                    ):

                        st.session_state.ingredientes_receita[idx][
                            "quantidade_exibicao"
                        ] = nova_quantidade

                        st.session_state.ingredientes_receita[idx][
                            "quantidade_estoque"
                        ] = converter_para_estoque(
                            nova_quantidade,
                            item["unidade"],
                        )

                        st.success("Ingrediente atualizado!")

                        st.rerun()

                if c3.button("❌", key=f"remove_{idx}"):

                    st.session_state.ingredientes_receita = [
                        i
                        for j, i in enumerate(st.session_state.ingredientes_receita)
                        if j != idx
                    ]

                    st.rerun()

        if receitas_existentes:

            with st.expander("📋 Copiar receita existente"):

                opcoes_receitas = {
                    r.nome: r.id
                    for r in receitas_existentes
                }

                nome_receita = st.selectbox(
                    "Escolha uma receita",
                    list(opcoes_receitas.keys()),
                    key="copiar_receita",
                )

                receita_id = opcoes_receitas[nome_receita]

                if st.button(
                    "Copiar ingredientes",
                    key="btn_copiar_receita",
                ):

                    st.session_state.ingredientes_receita = copiar_ingredientes_receita(
                        receita_id
                    )

                    st.success(f"Receita '{nome_receita}' copiada!")

                    st.rerun()


# =========================================================
# BOTÃO SALVAR
# =========================================================

if st.button(
    "Salvar Produto",
    type="primary",
):

    if not nome.strip():

        st.error("Informe o nome do produto.")

        st.stop()

    ingredientes = (
        st.session_state.get("ingredientes_receita", [])
    )
    if tipo_produto == "receita":

        if len(st.session_state.ingredientes_receita) == 0:

            st.error("Adicione pelo menos um ingrediente.")

            st.stop()

    try:

        produto_nome = salvar_produto_com_receita(
            nome=nome,
            tipo_produto=tipo_produto,
            unidade_medida=unidade_medida,
            estoque_minimo=estoque_minimo,
            controla_abertura=controla_abertura,
            preco_venda=preco_venda,
            validade_apos_abertura=validade_apos_abertura,
            ingredientes=ingredientes,
        )

        if tipo_produto == "receita":
            st.session_state.ingredientes_receita = []

        st.success(f"{produto_nome} cadastrado com sucesso!")

        st.rerun()

    except Exception as e:

        st.error(f"Erro ao salvar produto: {e}")

with st.expander("Produtos cadastrados"):
    products = catalogo_produtos()
    produtos = [p for p in products if p.tipo_produto.value != "receita"]

    receitas = [p for p in products if p.tipo_produto.value == "receita"]

    ativos = [p for p in products if p.ativo and p.tipo_produto.value != "receita"]

    inativos = [
        p for p in products if not p.ativo and p.tipo_produto.value != "receita"
    ]

    receitas_ativas = [
        p for p in products if p.ativo and p.tipo_produto.value == "receita"
    ]

    receitas_inativas = [
        p for p in products if not p.ativo and p.tipo_produto.value == "receita"
    ]

    if products:

        header1, header2, header3, header4, header5, header6 = st.columns(
            [2, 1, 1, 1, 0.4, 1]
        )

        header1.markdown("**Nome**")
        header2.markdown("**Tipo**")
        header3.markdown("**Unidade**")
        header4.markdown("**Estoque mínimo**")
        header5.markdown("**Excluir**")
        header6.markdown("**Desativar/Ativar**")

        for product in ativos:

            col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 0.4, 1])

            col1.write(product.nome)
            col2.write(TIPOS_LABEL[product.tipo_produto.value])
            col3.write(product.unidade_medida)
            col4.write(product.estoque_minimo)

            if pode_excluir(product):

                if col5.button(
                    "🗑️",
                    key=f"delete_inactive_{product.id}",
                ):
                    try:
                        excluir_produto_ui(product.id)

                        st.success(f"{product.nome} excluído com sucesso!")

                        st.rerun()

                    except ValueError as e:
                        st.error(str(e))

            else:
                col5.button(
                    "🔒",
                    disabled=True,
                    key=f"locked_{product.id}",
                )
            if col6.button(
                "🚫" if product.ativo else "Ativar",
                key=f"toggle_{product.id}",
            ):

                estava_ativo = product.ativo

                alternar_produto_ui(product.id)

                st.success(
                    f"{product.nome} "
                    f"{'desativado' if estava_ativo else 'ativado'} com sucesso!"
                )

                st.rerun()

        if inativos:

            with st.expander(
                f"Produtos desativados ({len(inativos)})",
                expanded=False,
            ):

                for product in inativos:

                    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 1, 1])

                    col1.markdown(
                        f"""
                        <span style="opacity:0.45">
                            {html.escape(product.nome)}
                        </span>
                        """,
                        unsafe_allow_html=True,
                    )

                    col2.markdown(
                        f"""
                        <span style="opacity:0.45">
                            {TIPOS_LABEL[product.tipo_produto.value]}
                        </span>
                        """,
                        unsafe_allow_html=True,
                    )

                    col3.markdown(
                        f"""
                        <span style="opacity:0.45">
                            {product.unidade_medida}
                        </span>
                        """,
                        unsafe_allow_html=True,
                    )

                    col4.markdown(
                        f"""
                        <span style="opacity:0.45">
                            {product.estoque_minimo}
                        </span>
                        """,
                        unsafe_allow_html=True,
                    )

                    # EXCLUIR
                    if pode_excluir(product):

                        if col5.button(
                            "🗑️",
                            key=f"delete_inactive_{product.id}",
                        ):
                            try:
                                excluir_produto_ui(product.id)

                                st.success(f"{product.nome} excluído com sucesso!")

                                st.rerun()

                            except ValueError as e:
                                st.error(str(e))

                    else:
                        col5.button("🔒", disabled=True, key=f"locked_{product.id}")

                    # ATIVAR
                    if col6.button(
                        "Ativar",
                        key=f"activate_{product.id}",
                    ):

                        alternar_produto_ui(product.id)

                        st.success(f"{product.nome} ativado com sucesso!")

                        st.rerun()

    else:

        st.info("Nenhum produto cadastrado ainda.")


st.divider()
st.subheader("📖 Receitas")

for receita in receitas_ativas:

    ingredientes_disponiveis = [
        p
        for p in ativos
        if p.tipo_produto.value != "receita"
        and p.id not in [item.ingredient_id for item in receita.recipe_items]
    ]

    with st.expander(f"☕ {receita.nome} ({len(receita.recipe_items)} ingredientes)"):

        col_preço, col_mudar_preço = st.columns([1, 0.2])
        col_preço.header(f"Preço venda: R$ {receita.preco_venda:.2f}")

        custos = custo_receita_ui(receita)

        if custos["sem_custo"]:

            st.warning(
                "Ingredientes sem compra registrada: " + ", ".join(custos["sem_custo"])
            )

        else:

            lucro = float(receita.preco_venda) - custos["custo_total"]

            margem = (lucro / float(receita.preco_venda)) * 100

            c1, c2 = st.columns(2)

            c1.metric("Custo", f"R$ {custos['custo_total']:.2f}")

            c2.metric("Margem Bruta", f"{margem:.1f}%")

        with col_mudar_preço.popover("💰 Alterar preço", use_container_width=True):

            novo_preço = st.number_input(
                f"Preço de venda: R$ ({receita.preco_venda:.2f})",
                min_value=0.001,
                step=0.1,
                format="%.2f",
                value=float(receita.preco_venda),  # Valor atual como padrão
                key=f"receita_preco_{receita.id}",  # Chave única por ingrediente
            )
            if st.button("✔️ Salvar", key=f"save_price_{receita.id}", type="secondary"):
                try:
                    mudar_preco_receita_ui(receita.id, novo_preço)
                    st.success("Preço atualizado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar preço: {e}")

        st.markdown("### Ingredientes")

        with st.popover(
            "➕ Adicionar ingrediente",
        ):

            if not ingredientes_disponiveis:

                st.info("Todos os ingredientes disponíveis já foram adicionados.")

            else:

                ingrediente = st.selectbox(
                    "Ingrediente",
                    options=ingredientes_disponiveis,
                    format_func=lambda p: p.nome,
                    key=f"new_ingredient_{receita.id}",
                )

                unidade_disp = unidade_exibicao(ingrediente.unidade_medida)

                quantidade = st.number_input(
                    f"Quantidade ({unidade_disp})",
                    min_value=0.001,
                    step=0.1,
                    key=f"new_qty_{receita.id}",
                )

                if st.button(
                    "Adicionar",
                    key=f"add_ingredient_{receita.id}",
                ):

                    qtd_convertida = converter_para_estoque(
                        quantidade,
                        ingrediente.unidade_medida,
                    )

                    try:

                        adicionar_ingrediente_receita_ui(
                            receita.id,
                            ingrediente.id,
                            qtd_convertida,
                        )

                        st.success("Ingrediente adicionado!")

                        st.rerun()

                    except ValueError as e:
                        st.error(str(e))

        custo_total = 0

        for item in receita.recipe_items:
            quantidade_formatada = formatar_receita(
                item.quantity,
                item.ingredient.unidade_medida,
            )

            custo_unitario = custo_unitario_produto_ui(item.ingredient_id)
            if custo_unitario is not None:
                custo_item = custo_unitario * item.quantity
                custo_total += custo_item
            else:
                custo_item = None

            # Criando colunas para alinhar o texto e as ações por ingrediente
            col_texto, col_valor, col_edit = st.columns([2, 2, 1])

            col_texto.write(f"• {item.ingredient.nome} - {quantidade_formatada}")

            if custo_item is not None:
                col_valor.write(f"R$ {custo_item:.2f}")
            else:
                col_valor.caption("Sem custo")

            # 1) CORREÇÃO DO EDITAR: Usando Popover para coletar o novo dado
            with col_edit.popover("✏️ Editar", use_container_width=True):
                unidade_disp = unidade_exibicao(item.ingredient.unidade_medida)

                nova_quantidade = st.number_input(
                    f"Nova quantidade ({unidade_disp})",
                    min_value=0.001,
                    step=0.1,
                    format="%.2f",
                    value=float(item.quantity),  # Valor atual como padrão
                    key=f"input_{item.id}",  # Chave única por ingrediente
                )

                col1, col2 = st.columns([1, 1])
                if col1.button(
                    "🗑️ Excluir", key=f"delete_item_{item.id}", type="primary"
                ):
                    remover_receita_item_ui(item.id)
                    st.success("Ingrediente removido com sucesso!")
                    st.rerun()

                if col2.button("✔️ Salvar", key=f"save_{item.id}", type="secondary"):
                    # Se sua função espera o valor convertido para estoque:
                    qtd_convertida = converter_para_estoque(
                        nova_quantidade, item.ingredient.unidade_medida
                    )

                    atualizar_quantidade_receita_ui(item.id, qtd_convertida)
                    st.success("Atualizado!")
                    st.rerun()

        col_esquerda_Vazia, col_desativar, col_remover = st.columns([4, 1, 1])

        if pode_excluir_receita(receita):

            if col_remover.button(
                "🗑️ Excluir receita", key=f"delete_recipe_{receita.id}"
            ):
                remover_receita_ui(receita.id)
                st.success("Receita excluída com sucesso!")
                st.rerun()

        else:
            col_remover.caption("🔒 Possui histórico")

        if col_desativar.button(
            "🚫 Desativar receita" if receita.ativo else "Ativar",
            key=f"toggle_{receita.id}",
        ):

            estava_ativo = receita.ativo

            alternar_receita_ui(receita.id)

            st.success(
                f"{receita.nome} "
                f"{'desativada' if estava_ativo else 'ativada'} com sucesso!"
            )

            st.rerun()

if receitas_inativas:

    with st.expander(
        f"Receitas desativadas ({len(receitas_inativas)})",
        expanded=False,
    ):

        for receita in receitas_inativas:

            col1, col2 = st.columns([1, 1])

            with col1:
                st.markdown(
                    f"""
                    <span style="opacity:0.45">
                        ☕ {html.escape(receita.nome)}
                        ({len(receita.recipe_items)} ingredientes)
                    </span>
                    """,
                    unsafe_allow_html=True,
                )
            st.divider()
            with col2:
                if st.button(
                    "Ativar",
                    key=f"activate_recipe_{receita.id}",
                    use_container_width=True,
                ):
                    alternar_receita_ui(receita.id)

                    st.success(f"{receita.nome} ativada com sucesso!")

                    st.rerun()
