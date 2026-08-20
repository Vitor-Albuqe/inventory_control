from __future__ import annotations

from datetime import date, timedelta

from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.seed import DEFAULT_TENANT_ID
from app.models import Expense, Product, Sale, StockLot, StockMovement
from app.models.enums import ProductType

from app.utils import _to_float

from app.services import get_estoque_aberto, get_estoque_fechado, get_estoque_total, get_lotes_abertos




def get_dashboard_estoque(session: Session) -> list[dict]:
    produtos = (
    session.query(Product)
    .filter(
        Product.ativo.is_(True),
        Product.tipo_produto.in_(
            [
                ProductType.MATERIA_PRIMA,
                ProductType.CONSUMIVEL,
                ProductType.PRODUTO_FINAL,
            ]
        ),
    )
    .all()
)
    resultado = []

    for p in produtos:
        fechado = get_estoque_fechado(session, p.id)
        # `controla_abertura` é só um toggle de UI (mostra ou não o formulário
        # "Abrir qtde" na tela de Estoque) — ele é sempre False para
        # produto_final (regra de criar_produto), mas a venda de produto_final
        # consome de lotes abertos igual a uma receita. Zerar o aberto aqui
        # quando controla_abertura=False escondia estoque real desses
        # produtos. get_estoque_aberto já retorna 0 quando não há lotes, então
        # não precisa da condição.
        aberto = get_estoque_aberto(session, p.id)
        total = fechado + aberto

        resultado.append({
            "id": p.id,
            "nome": p.nome,
            "tipo": p.tipo_produto.value,
            "unidade_medida": p.unidade_medida,
            "estoque_minimo": p.estoque_minimo,
            "estoque_fechado": fechado,
            "estoque_aberto": aberto,
            "estoque_total": total,
            "abaixo_minimo": total < p.estoque_minimo,
            "controla_abertura": p.controla_abertura,
        })

    return resultado


def get_produtos_abaixo_minimo(session: Session) -> list[dict]:
    return [p for p in get_dashboard_estoque(session) if p["abaixo_minimo"]]


def get_abertos_proximos_vencimento(session: Session, dias: int = 3) -> list[dict]:
    """Lotes abertos com validade nos próximos N dias."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)

    lotes = (
        session.query(StockLot)
        .filter(StockLot.status == "open")
        .filter(StockLot.quantidade_atual > 1e-9)
        .filter(StockLot.validade.isnot(None))
        .filter(StockLot.validade <= limite)
        .filter(StockLot.validade >= hoje)
        .order_by(StockLot.validade.asc())
        .all()
    )

    return [
        {
            "lot_id": lot.id,
            "produto": lot.product.nome,
            "unidade_medida": lot.product.unidade_medida,
            "quantidade": lot.quantidade_atual,
            "validade": lot.validade,
            "dias_restantes": (lot.validade - hoje).days,
        }
        for lot in lotes
    ]


def get_lotes_abertos_detalhados(session: Session) -> list[dict]:
    """Lista lotes abertos para exibição na UI."""
    lotes = get_lotes_abertos(session)
    return [
        {
            "lot_id": lot.id,
            "product_id": lot.product_id,
            "produto": lot.product.nome,
            "unidade_medida": lot.product.unidade_medida,
            "quantidade_atual": lot.quantidade_atual,
            "validade": lot.validade,
            "data_abertura": lot.data_abertura,
            "dias_restantes": (
                (lot.validade - date.today()).days if lot.validade else None
            ),
        }
        for lot in lotes
    ]



def get_historico_produto(
    session: Session,
    product_id: int,
    limit: int = 50,
) -> list[dict]:
    movs = (
        session.query(StockMovement)
        .filter(StockMovement.product_id == product_id)
        .order_by(
            StockMovement.data_movimento.desc(),
            StockMovement.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": m.id,
            "data": m.data_movimento,
            "tipo": m.tipo,
            "quantidade": m.get_quantidade_efetiva(),
            "fornecedor": m.fornecedor,
            "preco_unitario": _to_float(m.preco_unitario),
            "motivo": m.motivo,
            "observacao": m.observacao,
            "movimento_referencia_id": m.movimento_referencia_id,
            "lot_id": m.lot_id,
            "estoque_afetado": m.estoque_afetado,
        }
        for m in movs
    ]


def get_entradas_recentes(
    session: Session,
    product_id: int,
    limit: Optional[int] = 10,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
) -> list[dict]:
    """Compras (tipo='entrada') de um produto.

    Filtra por tipo ANTES de limitar — diferente de pegar as últimas N
    movimentações de qualquer tipo e depois filtrar por 'entrada', o que
    esconde compras antigas em produtos com muito consumo (uma compra de
    café dura semanas de consumo de poucos gramas por vez; as últimas 10
    movimentações quase sempre são só consumo, nunca mostrando a compra).

    Com data_inicio/data_fim informados, `limit` é ignorado (mostra todas
    as compras do período, não só as N mais recentes).
    """
    query = (
        session.query(StockMovement)
        .filter(StockMovement.product_id == product_id)
        .filter(StockMovement.tipo == "entrada")
    )
    if data_inicio:
        query = query.filter(StockMovement.data_movimento >= data_inicio)
    if data_fim:
        query = query.filter(StockMovement.data_movimento <= data_fim)

    query = query.order_by(StockMovement.data_movimento.desc(), StockMovement.id.desc())
    if limit and not (data_inicio or data_fim):
        query = query.limit(limit)

    entradas = query.all()
    if not entradas:
        return []

    ids = [e.id for e in entradas]
    corrigidos = {
        row[0]
        for row in session.query(StockMovement.movimento_referencia_id)
        .filter(StockMovement.movimento_referencia_id.in_(ids))
        .distinct()
        .all()
    }

    return [
        {
            "id": e.id,
            "data": e.data_movimento,
            "quantidade": e.quantidade,
            "preco_unitario": _to_float(e.preco_unitario),
            "fornecedor": e.fornecedor,
            "corrigido": e.id in corrigidos,
        }
        for e in entradas
    ]


def get_custo_medio(session: Session, product_id: int) -> Optional[float]:
    result = (
        session.query(
            func.sum(StockMovement.preco_total),
            func.sum(StockMovement.quantidade),
        )
        .filter(StockMovement.product_id == product_id)
        .filter(StockMovement.tipo == "entrada")
        .one()
    )

    total_custo, total_qty = result
    if not total_qty or total_qty == 0:
        return None

    return _to_float(total_custo) / _to_float(total_qty)


def get_valor_estoque_total(session: Session) -> float:
    produtos = session.query(Product).all()
    total = 0.0

    for p in produtos:
        qty = get_estoque_total(session, p.id)
        custo = get_custo_medio(session, p.id)
        if qty > 0 and custo:
            total += qty * custo

    return total


# ---------------------------------------------------------------------------
# Dashboard financeiro
# ---------------------------------------------------------------------------


def get_total_receita(
    db, data_inicio: Optional[date] = None, data_fim: Optional[date] = None
) -> float:
    q = db.query(func.sum(Sale.valor_total))
    if data_inicio:
        q = q.filter(Sale.data_venda >= data_inicio)
    if data_fim:
        q = q.filter(Sale.data_venda <= data_fim)
    return _to_float(q.scalar())


def get_total_investido(
    db, data_inicio: Optional[date] = None, data_fim: Optional[date] = None
) -> float:
    q = db.query(
        func.sum(
            case(
                (
                    StockMovement.tipo.in_(["entrada", "estorno"]),
                    StockMovement.quantidade * StockMovement.preco_unitario,
                ),
                (
                    (StockMovement.tipo == "ajuste")
                    & (StockMovement.direcao == "saida"),
                    -(StockMovement.quantidade * StockMovement.preco_unitario),
                ),
                (
                    (StockMovement.tipo == "ajuste")
                    & (StockMovement.direcao == "entrada"),
                    StockMovement.quantidade * StockMovement.preco_unitario,
                ),
                else_=0,
            )
        )
    )
    if data_inicio:
        q = q.filter(StockMovement.data_movimento >= data_inicio)
    if data_fim:
        q = q.filter(StockMovement.data_movimento <= data_fim)
    return _to_float(q.scalar())


def get_total_gastos(
    db, data_inicio: Optional[date] = None, data_fim: Optional[date] = None
) -> float:
    q = db.query(func.sum(Expense.valor)).filter(Expense.is_deleted.is_(False))
    if data_inicio:
        q = q.filter(Expense.data >= data_inicio)
    if data_fim:
        q = q.filter(Expense.data <= data_fim)
    return _to_float(q.scalar())


def get_total_vendas(
    db, data_inicio: Optional[date] = None, data_fim: Optional[date] = None
) -> int:
    q = db.query(func.count(Sale.id))
    if data_inicio:
        q = q.filter(Sale.data_venda >= data_inicio)
    if data_fim:
        q = q.filter(Sale.data_venda <= data_fim)
    return int(q.scalar() or 0)


def get_lucro_estimado(
    db, data_inicio: Optional[date] = None, data_fim: Optional[date] = None
) -> float:
    return (
        get_total_receita(db, data_inicio, data_fim)
        - get_total_investido(db, data_inicio, data_fim)
        - get_total_gastos(db, data_inicio, data_fim)
    )