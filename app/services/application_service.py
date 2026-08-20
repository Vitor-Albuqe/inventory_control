from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.repositories import (
    create_expense,
    create_sale,
    get_expense,
    get_product,
    list_active_expenses,
    list_active_products,
    list_expenses,
    list_products_with_recipe_relationships,
    list_recent_corrections,
    list_sales_filtered,
    soft_delete_expense,
)

from app.services.cost_service import calcular_custo_receita, get_custo_unitario_produto

from app.services import (
    get_abertos_proximos_vencimento,
    get_dashboard_estoque,
    get_lotes_abertos_detalhados,
    get_produtos_abaixo_minimo,
    consumir_lote_completo,
    registrar_abertura,
    registrar_ajuste,
    registrar_consumo,
    registrar_entrada,
    registrar_perda,
    criar_produto,
    delete_product,
    desativar_produto,
    adicionar_ingrediente_receita,
    atualizar_quantidade_receita,
    criar_receita_item,
    desativar_receita,
    mudar_preco_receita,
    remover_receita,
    remover_receita_item,
    get_lucro_estimado,
    get_total_gastos,
    get_total_investido,
    get_total_receita,
    get_total_vendas,
)


from app.services.session_scope import session_scope

from app.utils.unit_converter import quantidade_exibicao


def dashboard_estoque() -> list[dict[str, Any]]:
    with session_scope() as session:
        return get_dashboard_estoque(session)


def lotes_abertos_detalhados() -> list[dict[str, Any]]:
    with session_scope() as session:
        return get_lotes_abertos_detalhados(session)


def abertos_proximos_vencimento(dias: int = 3) -> list[dict[str, Any]]:
    with session_scope() as session:
        return get_abertos_proximos_vencimento(session, dias=dias)


def produtos_abaixo_minimo() -> list[dict[str, Any]]:
    with session_scope() as session:
        return get_produtos_abaixo_minimo(session)


def produtos_ativos_opcoes() -> dict[str, int]:
    with session_scope() as session:
        return {p.nome: p.id for p in list_active_products(session)}


def abrir_produto(product_id: int, quantidade: float) -> None:
    with session_scope() as session:
        produto = get_product(session, product_id)
        validade_aberto = None
        if produto and produto.validade_apos_abertura:
            validade_aberto = date.today() + timedelta(
                days=int(produto.validade_apos_abertura)
            )
        registrar_abertura(
            session,
            product_id=product_id,
            quantidade=quantidade,
            data_abertura=date.today(),
            validade_aberto=validade_aberto,
        )


def esgotar_lote(lot_id: int) -> None:
    with session_scope() as session:
        consumir_lote_completo(session, lot_id)


def registrar_consumo_ui(
    product_id: int, quantidade: float, lot_id: int | None, observacao: str | None
) -> None:
    with session_scope() as session:
        registrar_consumo(
            session,
            product_id,
            quantidade,
            date.today(),
            lot_id=lot_id,
            observacao=observacao,
        )


def registrar_perda_ui(
    product_id: int,
    quantidade: float,
    motivo: str,
    estoque_afetado: str,
    lot_id: int | None,
    observacao: str | None,
) -> None:
    with session_scope() as session:
        registrar_perda(
            session,
            product_id,
            quantidade,
            motivo,
            date.today(),
            estoque_afetado=estoque_afetado,
            lot_id=lot_id,
            observacao=observacao,
        )


def registrar_ajuste_ui(
    product_id: int,
    quantidade: float,
    direcao: str,
    motivo: str,
    observacao: str | None = None,
    movimento_referencia_id: int | None = None,
) -> None:
    with session_scope() as session:
        registrar_ajuste(
            session,
            product_id,
            quantidade,
            direcao=direcao,
            motivo=motivo,
            data_ajuste=date.today(),
            observacao=observacao,
            movimento_referencia_id=movimento_referencia_id,
        )


def registrar_compra_ui(
    product_id: int,
    quantidade: float,
    preco_unitario: float,
    data_compra,
    data_validade,
    fornecedor: str,
    tempo_entrega: int,
):
    with session_scope() as session:
        movimento = registrar_entrada(
            session,
            product_id,
            quantidade,
            preco_unitario,
            data_compra,
            data_validade,
            fornecedor,
            tempo_entrega,
        )
        return SimpleNamespace(
            id=movimento.id,
            preco_total=movimento.preco_total,
        )


def catalogo_produtos():
    with session_scope() as session:
        return list_products_with_recipe_relationships(session)


def salvar_produto_com_receita(**kwargs):
    ingredientes = kwargs.pop("ingredientes", [])
    with session_scope() as session:
        try:
            produto = criar_produto(session=session, **kwargs)
            if kwargs.get("tipo_produto") == "receita":
                for item in ingredientes:
                    criar_receita_item(
                        session=session,
                        recipe_id=produto.id,
                        ingredient_id=item["ingredient_id"],
                        quantity=item["quantidade_estoque"],
                    )
                # Todos os ingredientes são commitados juntos: se um falha,
                # nenhum é persistido (o produto já foi commitado por criar_produto).
                session.commit()
            nome = produto.nome
            return nome
        except IntegrityError:
            session.rollback()
            raise ValueError("Já existe um produto com esse nome.")
        except Exception:
            session.rollback()
            raise


def excluir_produto_ui(product_id: int) -> None:
    with session_scope() as session:
        delete_product(session, product_id)


def alternar_produto_ui(product_id: int) -> None:
    with session_scope() as session:
        desativar_produto(session, product_id)


def copiar_ingredientes_receita(receita_id: int) -> list[dict[str, Any]]:
    with session_scope() as session:
        receita = get_product(session, receita_id)
        if not receita:
            raise ValueError("Receita não encontrada.")
        return [
            {
                "ingredient_id": item.ingredient_id,
                "nome": item.ingredient.nome,
                "unidade": item.ingredient.unidade_medida,
                "quantidade_exibicao": quantidade_exibicao(
                    item.quantity, item.ingredient.unidade_medida
                ),
                "quantidade_estoque": item.quantity,
            }
            for item in receita.recipe_items
        ]


def custo_receita_ui(receita):
    with session_scope() as session:
        receita_db = get_product(session, receita.id)
        return calcular_custo_receita(session, receita_db)


def custo_unitario_produto_ui(product_id: int):
    with session_scope() as session:
        return get_custo_unitario_produto(session, product_id)


def mudar_preco_receita_ui(receita_id: int, novo_preco: float) -> None:
    with session_scope() as session:
        mudar_preco_receita(session, receita_id, novo_preco)


def adicionar_ingrediente_receita_ui(
    recipe_id: int, ingredient_id: int, quantity: float
) -> None:
    with session_scope() as session:
        adicionar_ingrediente_receita(session, recipe_id, ingredient_id, quantity)


def remover_receita_item_ui(item_id: int) -> None:
    with session_scope() as session:
        remover_receita_item(session, item_id)


def atualizar_quantidade_receita_ui(item_id: int, quantity: float) -> None:
    with session_scope() as session:
        atualizar_quantidade_receita(session, item_id, quantity)


def remover_receita_ui(receita_id: int) -> None:
    with session_scope() as session:
        remover_receita(session, receita_id)


def alternar_receita_ui(receita_id: int) -> None:
    with session_scope() as session:
        desativar_receita(session, receita_id)


def correcoes_recentes(limit: int = 10) -> list[dict[str, Any]]:
    with session_scope() as session:
        ajustes = list_recent_corrections(session, limit=limit)
        return [
            {
                "direcao": a.direcao,
                "produto": a.product.nome,
                "unidade_medida": a.product.unidade_medida,
                "quantidade": a.quantidade,
                "motivo": a.motivo,
            }
            for a in ajustes
        ]


PERIODOS_DASHBOARD = [
    "Tudo",
    "Este mês",
    "Mês passado",
    "Últimos 30 dias",
    "Últimos 90 dias",
    "Este ano",
]


def intervalo_por_periodo(opcao: str) -> tuple[date | None, date | None]:
    """Converte um rótulo amigável ('Este mês', 'Mês passado'...) num
    intervalo [data_inicio, data_fim]. 'Tudo' devolve (None, None) — sem
    filtro."""
    hoje = date.today()

    if opcao == "Este mês":
        return hoje.replace(day=1), hoje

    if opcao == "Mês passado":
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_passado = primeiro_dia_mes_atual - timedelta(days=1)
        return ultimo_dia_mes_passado.replace(day=1), ultimo_dia_mes_passado

    if opcao == "Últimos 30 dias":
        return hoje - timedelta(days=29), hoje

    if opcao == "Últimos 90 dias":
        return hoje - timedelta(days=89), hoje

    if opcao == "Este ano":
        return hoje.replace(month=1, day=1), hoje

    return None, None


def dados_dashboard_financeiro(
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, Any]:

    with session_scope() as session:
        sales = [
            {"Data": s.data_venda, "Valor": s.valor_total}
            for s in list_sales_filtered(session, data_inicio, data_fim, limit=100_000)
        ]
        expenses_chart = [
            {"Categoria": e.categoria, "Valor": e.valor}
            for e in list_expenses(session, data_inicio, data_fim)
        ]
        expenses = [
            {
                "id": e.id,
                "nome": e.nome,
                "categoria": e.categoria,
                "valor": e.valor,
                "data": e.data,
            }
            for e in list_active_expenses(session, data_inicio, data_fim)
        ]
        return {
            "receita": get_total_receita(session, data_inicio, data_fim),
            "investimento": get_total_investido(session, data_inicio, data_fim),
            "gastos": get_total_gastos(session, data_inicio, data_fim),
            "lucro": get_lucro_estimado(session, data_inicio, data_fim),
            "vendas": get_total_vendas(session, data_inicio, data_fim),
            "sales": sales,
            "expenses_chart": expenses_chart,
            "expenses": expenses,
        }


def criar_gasto(nome: str, categoria: str, valor: float, data_gasto) -> None:
    with session_scope() as session:
        create_expense(session, nome, categoria, valor, data_gasto)
        session.commit()


def obter_gasto(expense_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        expense = get_expense(session, expense_id)
        if not expense:
            return None
        return {"id": expense.id, "nome": expense.nome}


def excluir_gasto(expense_id: int) -> None:
    with session_scope() as session:
        expense = get_expense(session, expense_id)
        if not expense:
            raise ValueError("Gasto não encontrado.")
        soft_delete_expense(session, expense)
        session.commit()


def historico_produto(product_id: int, limit: int = 50):
    from app.services.dashboard_service import get_historico_produto

    with session_scope() as session:
        return get_historico_produto(session, product_id, limit=limit)


def entradas_recentes_ui(
    product_id: int,
    limit: int | None = 10,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[dict[str, Any]]:
    from app.services.dashboard_service import get_entradas_recentes

    with session_scope() as session:
        return get_entradas_recentes(
            session, product_id, limit=limit, data_inicio=data_inicio, data_fim=data_fim
        )


def listar_produtos_vendaveis() -> list[dict[str, Any]]:
    from app.models import Product
    from app.models.enums import ProductType

    with session_scope() as session:
        produtos = (
            session.query(Product)
            .filter(
                Product.ativo.is_(True),
                Product.tipo_produto.in_([ProductType.PRODUTO_FINAL, ProductType.RECEITA]),
            )
            .order_by(Product.nome)
            .all()
        )
        return [
            {
                "id": p.id,
                "nome": p.nome,
                "preco_venda": float(p.preco_venda) if p.preco_venda is not None else None,
                "tipo": p.tipo_produto.value,
            }
            for p in produtos
        ]


def registrar_venda_ui(
    product_id: int,
    quantidade: float,
    valor_unitario: float,
    data_venda,
) -> dict[str, Any]:
    with session_scope() as session:
        produto = get_product(session, product_id)
        if not produto:
            raise ValueError("Produto não encontrado.")
        sale = create_sale(
            session,
            product_id=product_id,
            produto_nome=produto.nome,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            data_venda=data_venda,
        )
        session.commit()
        session.refresh(sale)
        return {"id": sale.id, "valor_total": float(sale.valor_total)}


def listar_vendas_ui(
    data_inicio=None,
    data_fim=None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        sales = list_sales_filtered(session, data_inicio, data_fim, limit=limit)
        return [
            {
                "id": s.id,
                "data": s.data_venda,
                "produto_nome": s.produto_nome or (
                    s.product.nome if s.product else "Produto removido"
                ),
                "quantidade": s.quantidade,
                "valor_unitario": float(s.valor_unitario),
                "valor_total": float(s.valor_total),
            }
            for s in sales
        ]


def resumo_vendas_hoje() -> dict[str, Any]:
    hoje = date.today()
    vendas = listar_vendas_ui(data_inicio=hoje, data_fim=hoje)
    total = sum(v["valor_total"] for v in vendas)
    count = len(vendas)
    ticket_medio = total / count if count > 0 else 0.0
    return {"total": total, "count": count, "ticket_medio": ticket_medio}


def registrar_venda_com_consumo_ui(
    product_id: int,
    quantidade: float,
    valor_unitario: float,
    data_venda,
) -> dict[str, Any]:
    """
    Registra a venda e tenta consumir automaticamente o estoque:
    - Receitas: desconta cada ingrediente via FEFO em uma única transação.
    - Produto Final: tenta descontar de lotes abertos se existirem.
    A venda SEMPRE é registrada. Falhas de estoque viram avisos, não erros fatais.
    """
    if quantidade <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    if valor_unitario < 0:
        raise ValueError("Valor unitário não pode ser negativo.")

    from app.services import buscar_ingredientes_receita, _consumir_de_lotes, get_lotes_abertos

    avisos: list[str] = []

    with session_scope() as session:
        produto = get_product(session, product_id)
        if not produto:
            raise ValueError("Produto não encontrado.")

        tipo = produto.tipo_produto.value

        if tipo == "receita":
            itens = buscar_ingredientes_receita(session, product_id)
            if not itens:
                avisos.append(
                    f"Receita '{produto.nome}' sem ingredientes cadastrados — "
                    "estoque não foi ajustado."
                )
            else:
                for item in itens:
                    qtd_necessaria = round(item.quantity * quantidade, 6)
                    try:
                        _consumir_de_lotes(
                            session,
                            item.ingredient_id,
                            qtd_necessaria,
                            tipo="consumo",
                            data_movimento=data_venda,
                            observacao=f"Venda automática — {produto.nome}",
                        )
                    except ValueError as e:
                        avisos.append(f"⚠️ {item.ingredient.nome}: {e}")

        elif tipo == "produto_final":
            lotes = get_lotes_abertos(session, product_id)
            if lotes:
                try:
                    _consumir_de_lotes(
                        session,
                        product_id,
                        quantidade,
                        tipo="consumo",
                        data_movimento=data_venda,
                        observacao="Venda",
                    )
                except ValueError as e:
                    avisos.append(f"⚠️ Estoque insuficiente: {e}")
            else:
                avisos.append(
                    f"'{produto.nome}' não possui lotes abertos — "
                    "ajuste o estoque fechado manualmente na página Estoque."
                )

        sale = create_sale(
            session,
            product_id=product_id,
            produto_nome=produto.nome,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            data_venda=data_venda,
        )
        session.commit()
        session.refresh(sale)

        return {
            "id": sale.id,
            "valor_total": float(sale.valor_total),
            "avisos": avisos,
        }
