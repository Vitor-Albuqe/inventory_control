from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.database.seed import DEFAULT_TENANT_ID
from app.models import Expense, Sale


def list_sales(session: Session, limit: int = 5000) -> list[Sale]:
    return (
        session.query(Sale)
        .order_by(Sale.data_venda.desc(), Sale.id.desc())
        .limit(limit)
        .all()
    )


def list_expenses(
    session: Session,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
) -> list[Expense]:
    q = session.query(Expense).filter(Expense.is_deleted.is_(False))
    if data_inicio:
        q = q.filter(Expense.data >= data_inicio)
    if data_fim:
        q = q.filter(Expense.data <= data_fim)
    return q.all()


def list_active_expenses(
    session: Session,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
) -> list[Expense]:
    q = (
        session.query(Expense)
        .filter(Expense.is_deleted.is_(False))
        .order_by(Expense.data.desc())
    )
    if data_inicio:
        q = q.filter(Expense.data >= data_inicio)
    if data_fim:
        q = q.filter(Expense.data <= data_fim)
    return q.all()


def get_expense(session: Session, expense_id: int) -> Expense | None:
    return session.query(Expense).filter(Expense.id == expense_id).first()


def create_expense(
    session: Session, nome: str, categoria: str, valor: float, data_gasto
):
    expense = Expense(
        tenant_id=DEFAULT_TENANT_ID,
        nome=nome,
        categoria=categoria,
        valor=valor,
        data=data_gasto,
    )
    session.add(expense)
    return expense


def soft_delete_expense(session: Session, expense: Expense) -> None:
    expense.is_deleted = True
    expense.deleted_at = datetime.utcnow()


def create_sale(
    session: Session,
    product_id: Optional[int],
    produto_nome: str,
    quantidade: float,
    valor_unitario: float,
    data_venda: date,
) -> Sale:
    vu = Decimal(str(valor_unitario))
    vt = Decimal(str(quantidade)) * vu
    sale = Sale(
        tenant_id=DEFAULT_TENANT_ID,
        product_id=product_id,
        produto_nome=produto_nome,
        quantidade=quantidade,
        valor_unitario=vu,
        valor_total=vt,
        data_venda=data_venda,
    )
    session.add(sale)
    return sale


def list_sales_filtered(
    session: Session,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    limit: int = 100,
) -> list[Sale]:
    q = (
        session.query(Sale)
        .order_by(Sale.data_venda.desc(), Sale.id.desc())
    )
    if data_inicio:
        q = q.filter(Sale.data_venda >= data_inicio)
    if data_fim:
        q = q.filter(Sale.data_venda <= data_fim)
    return q.limit(limit).all()
