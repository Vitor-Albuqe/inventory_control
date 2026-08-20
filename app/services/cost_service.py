from __future__ import annotations

from datetime import date, timedelta

from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.seed import DEFAULT_TENANT_ID
from app.models import  StockMovement, Product
from app.models.enums import ProductType

from app.services import _get_product
from app.utils import _to_float

from app.services import get_estoque_aberto, get_estoque_fechado, get_estoque_total, get_lotes_abertos





def get_custo_unitario_receita(
    session: Session,
    product_id: int,
) -> float | None:
    """Retornar o custo da menor unidade utilizada na receita"""

    CONVERSAO_CUSTO = {
    "kg": 1000,
    "litro": 1000,
    "un": 1,
    }

    custo_base = StockMovement.preco_unitario

    fator = CONVERSAO_CUSTO.get(
        Product.unidade_medida,
        1
    )
   

    return custo_base / fator


def calcular_custo_receita(
    session: Session,
    receita: Product,
):

    custo_total = 0

    detalhes = []

    ingredientes_sem_custo = []

    for item in receita.recipe_items:

        custo_unitario = get_custo_unitario_produto(
            session,
            item.ingredient_id,
        )

        if custo_unitario is None:

            ingredientes_sem_custo.append(
                item.ingredient.nome
            )

            continue

        custo_item = (
            custo_unitario
            * item.quantity
        )

        custo_total += custo_item

        detalhes.append(
            {
                "nome": item.ingredient.nome,
                "quantidade": item.quantity,
                "custo": custo_item,
            }
        )

    return {
        "custo_total": custo_total,
        "detalhes": detalhes,
        "sem_custo": ingredientes_sem_custo,
    }
    
def get_custo_unitario_produto(
    session: Session,
    product_id: int,
) -> float | None:

    movimento = (
        session.query(StockMovement)
        .filter(
            StockMovement.product_id == product_id,
            StockMovement.tipo == "entrada",
        )
        .order_by(
            StockMovement.data_movimento.desc()
        )
        .first()
    )

    if not movimento:
        return None

    return float(movimento.preco_unitario)