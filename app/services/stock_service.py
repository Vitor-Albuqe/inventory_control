from __future__ import annotations

from datetime import date

from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.seed import DEFAULT_TENANT_ID
from app.models import  StockLot, StockMovement

from app.utils import _to_float

from app.services import _get_product


# ---------------------------------------------------------------------------
# Estoque
# ---------------------------------------------------------------------------

def get_estoque_total(session: Session, product_id: int) -> float:
    return get_estoque_fechado(session, product_id) + get_estoque_aberto(
        session, product_id
    )



# ---------------------------------------------------------------------------
# Lotes em uso (estoque aberto) vs estoque fechado (via ledger)
# ---------------------------------------------------------------------------


def get_lotes_abertos(
    session: Session,
    product_id: Optional[int] = None,
) -> list[StockLot]:
    hoje = date.today()
    q = (
        session.query(StockLot)
        .filter(StockLot.status == "open")
        .filter(StockLot.quantidade_atual > 1e-9)
        # Exclui lotes vencidos (validade None = sem vencimento, sempre válido)
        .filter(
            (StockLot.validade.is_(None)) | (StockLot.validade >= hoje)
        )
        .order_by(
            StockLot.validade.asc().nulls_last(),
            StockLot.data_abertura.asc(),
            StockLot.id.asc(),
        )
    )
    if product_id is not None:
        q = q.filter(StockLot.product_id == product_id)
    return q.all()


def get_estoque_aberto(session: Session, product_id: int) -> float:
    """Saldo em uso = soma dos lotes abertos."""
    result = (
        session.query(func.coalesce(func.sum(StockLot.quantidade_atual), 0))
        .filter(StockLot.product_id == product_id)
        .filter(StockLot.status == "open")
        .scalar()
    )
    return _to_float(result)


def get_estoque_fechado(session: Session, product_id: int) -> float:
    """Estoque fechado via ledger (perda só conta se estoque_afetado=fechado)."""
    result = (
        session.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            StockMovement.tipo.in_(["entrada", "estorno"]),
                            StockMovement.quantidade,
                        ),
                        (StockMovement.tipo == "abertura", -StockMovement.quantidade),
                        (
                            (StockMovement.tipo == "perda")
                            & (StockMovement.estoque_afetado == "fechado"),
                            -StockMovement.quantidade,
                        ),
                        (
                            StockMovement.tipo == "ajuste",
                            case(
                                (
                                    StockMovement.direcao == "entrada",
                                    StockMovement.quantidade,
                                ),
                                else_=-StockMovement.quantidade,
                            ),
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        )
        .filter(StockMovement.product_id == product_id)
        .filter(StockMovement.tipo != "consumo")
        .scalar()
    )
    return _to_float(result)





def _consumir_de_lotes(
    session: Session,
    product_id: int,
    quantidade: float,
    tipo: str,
    data_movimento: date,
    motivo: Optional[str] = None,
    observacao: Optional[str] = None,
) -> list[StockMovement]:
    """Consome/perde de lotes em FEFO; retorna movimentos gerados."""
    produto = _get_product(session, product_id)
    lotes = get_lotes_abertos(session, product_id)
    saldo_lotes = sum(l.quantidade_atual for l in lotes)

    if saldo_lotes < quantidade:
        raise ValueError(
            f"Estoque aberto insuficiente: disponível {saldo_lotes}, "
            f"solicitado {quantidade}"
        )

    restante = quantidade
    movimentos: list[StockMovement] = []

    for lot in lotes:
        if restante <= 0:
            break

        qtd = min(lot.quantidade_atual, restante)
        lot.quantidade_atual = round(lot.quantidade_atual - qtd, 6)
        if lot.quantidade_atual <= 1e-9:
            lot.quantidade_atual = 0
            lot.status = "closed"

        mov = StockMovement(
            tenant_id=produto.tenant_id,
            product_id=product_id,
            lot_id=lot.id,
            tipo=tipo,
            quantidade=qtd,
            estoque_afetado="aberto",
            motivo=motivo,
            data_movimento=data_movimento,
            observacao=observacao,
        )
        session.add(mov)
        movimentos.append(mov)
        restante -= qtd

    return movimentos