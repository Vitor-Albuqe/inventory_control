from __future__ import annotations

from datetime import date
from decimal import Decimal

from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.seed import DEFAULT_TENANT_ID
from app.models import StockLot, StockMovement

from app.services import get_custo_medio, get_estoque_aberto, get_estoque_fechado, _get_product, _consumir_de_lotes







def registrar_entrada(
    session: Session,
    product_id: int,
    quantidade: float,
    preco_unitario: float,
    data_compra: date,
    data_validade: Optional[date] = None,
    fornecedor: Optional[str] = None,
    tempo_entrega: Optional[int] = None,
    observacao: Optional[str] = None,
) -> StockMovement:
    # Validado aqui, não só pelo CHECK do banco: a UI precisa de um
    # ValueError com mensagem em português, não de um IntegrityError cru
    # depois que a transação já falhou.
    if quantidade <= 0:
        raise ValueError("Quantidade da compra deve ser maior que zero.")
    if preco_unitario < 0:
        raise ValueError("Preço unitário não pode ser negativo.")

    produto = _get_product(session, product_id)
    pu = Decimal(str(preco_unitario))
    pt = Decimal(str(quantidade)) * pu

    mov = StockMovement(
        tenant_id=produto.tenant_id,
        product_id=product_id,
        tipo="entrada",
        quantidade=quantidade,
        preco_unitario=pu,
        preco_total=pt,
        data_validade=data_validade,
        fornecedor=fornecedor,
        tempo_entrega=tempo_entrega,
        data_movimento=data_compra,
        observacao=observacao,
    )
    session.add(mov)
    session.commit()
    session.refresh(mov)
    return mov


def registrar_abertura(
    session: Session,
    product_id: int,
    quantidade: float,
    data_abertura: date,
    validade_aberto: Optional[date] = None,
    movimento_referencia_id: Optional[int] = None,
    observacao: Optional[str] = None,
) -> StockMovement:
    produto = _get_product(session, product_id)
    estoque_atual = get_estoque_fechado(session, product_id)
    if estoque_atual < quantidade:
        raise ValueError(
            f"Estoque fechado insuficiente: disponível {estoque_atual}, "
            f"solicitado {quantidade}"
        )

    mov = StockMovement(
        tenant_id=produto.tenant_id,
        product_id=product_id,
        tipo="abertura",
        quantidade=quantidade,
        validade_aberto=validade_aberto,
        movimento_referencia_id=movimento_referencia_id,
        data_movimento=data_abertura,
        observacao=observacao,
    )
    session.add(mov)
    session.flush()

    lot = StockLot(
        tenant_id=produto.tenant_id,
        product_id=product_id,
        abertura_movement_id=mov.id,
        quantidade_inicial=quantidade,
        quantidade_atual=quantidade,
        data_abertura=data_abertura,
        validade=validade_aberto,
        status="open",
    )
    session.add(lot)

    session.commit()
    session.expire_all()
    session.refresh(mov)
    return mov


def registrar_consumo(
    session: Session,
    product_id: int,
    quantidade: float,
    data_consumo: date,
    lot_id: Optional[int] = None,
    observacao: Optional[str] = None,
) -> list[StockMovement]:
    """Registra consumo; aloca em lote específico ou FEFO."""
    if lot_id is not None:
        lot = session.get(StockLot, lot_id)
        if not lot or lot.product_id != product_id or lot.status != "open":
            raise ValueError("Lote inválido ou indisponível.")
        if lot.quantidade_atual < quantidade:
            raise ValueError(
                f"Saldo do lote insuficiente: {lot.quantidade_atual}, "
                f"solicitado {quantidade}"
            )
        produto = _get_product(session, product_id)
        lot.quantidade_atual = round(lot.quantidade_atual - quantidade, 6)
        if lot.quantidade_atual <= 1e-9:
            lot.quantidade_atual = 0
            lot.status = "closed"
        mov = StockMovement(
            tenant_id=produto.tenant_id,
            product_id=product_id,
            lot_id=lot.id,
            tipo="consumo",
            quantidade=quantidade,
            estoque_afetado="aberto",
            data_movimento=data_consumo,
            observacao=observacao,
        )
        session.add(mov)
        session.commit()
        session.expire_all()
        session.refresh(mov)
        return [mov]

    movimentos = _consumir_de_lotes(
        session,
        product_id,
        quantidade,
        tipo="consumo",
        data_movimento=data_consumo,
        observacao=observacao,
    )
    session.commit()
    session.expire_all()
    for m in movimentos:
        session.refresh(m)
    return movimentos


def consumir_lote_completo(
    session: Session,
    lot_id: int,
    data_consumo: Optional[date] = None,
    observacao: Optional[str] = None,
) -> list[StockMovement]:
    """Consome 100% do saldo de um lote (atalho na UI)."""
    lot = session.get(StockLot, lot_id)
    if not lot or lot.status != "open" or lot.quantidade_atual <= 1e-9:
        raise ValueError("Lote inválido ou já encerrado.")
    return registrar_consumo(
        session,
        lot.product_id,
        lot.quantidade_atual,
        data_consumo or date.today(),
        lot_id=lot.id,
        observacao=observacao,
    )


def registrar_perda(
    session: Session,
    product_id: int,
    quantidade: float,
    motivo: str,
    data_perda: date,
    estoque_afetado: str = "fechado",
    lot_id: Optional[int] = None,
    observacao: Optional[str] = None,
) -> StockMovement | list[StockMovement]:
    if not motivo or not motivo.strip():
        raise ValueError("Motivo é obrigatório para registro de perda.")

    if estoque_afetado not in ("fechado", "aberto"):
        raise ValueError("estoque_afetado deve ser 'fechado' ou 'aberto'.")

    if estoque_afetado == "aberto":
        if lot_id is not None:
            produto = _get_product(session, product_id)
            lot = session.get(StockLot, lot_id)
            if not lot or lot.product_id != product_id or lot.status != "open":
                raise ValueError("Lote inválido ou indisponível.")
            if lot.quantidade_atual < quantidade:
                raise ValueError(
                    f"Saldo do lote insuficiente: {lot.quantidade_atual}, "
                    f"solicitado {quantidade}"
                )
            lot.quantidade_atual -= quantidade
            if lot.quantidade_atual <= 0:
                lot.quantidade_atual = 0
                lot.status = "closed"
            mov = StockMovement(
                tenant_id=produto.tenant_id,
                product_id=product_id,
                lot_id=lot.id,
                tipo="perda",
                quantidade=quantidade,
                estoque_afetado="aberto",
                motivo=motivo.strip(),
                data_movimento=data_perda,
                observacao=observacao,
            )
            session.add(mov)
            session.commit()
            session.refresh(mov)
            return mov

        movimentos = _consumir_de_lotes(
            session,
            product_id,
            quantidade,
            tipo="perda",
            data_movimento=data_perda,
            motivo=motivo.strip(),
            observacao=observacao,
        )
        session.commit()
        return movimentos

    produto = _get_product(session, product_id)
    fechado = get_estoque_fechado(session, product_id)
    if fechado < quantidade:
        raise ValueError(
            f"Estoque fechado insuficiente: disponível {fechado}, "
            f"solicitado {quantidade}"
        )

    mov = StockMovement(
        tenant_id=produto.tenant_id,
        product_id=product_id,
        tipo="perda",
        quantidade=quantidade,
        estoque_afetado="fechado",
        motivo=motivo.strip(),
        data_movimento=data_perda,
        observacao=observacao,
    )
    session.add(mov)
    session.commit()
    session.refresh(mov)
    return mov


def registrar_ajuste(
    session: Session,
    product_id: int,
    quantidade: float,
    direcao: str,
    motivo: str,
    data_ajuste: date,
    observacao: Optional[str] = None,
    movimento_referencia_id: Optional[int] = None,
) -> StockMovement:
    if direcao not in ("entrada", "saida"):
        raise ValueError("Direção deve ser 'entrada' ou 'saida'.")
    if quantidade <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    if not motivo or not motivo.strip():
        raise ValueError("Motivo é obrigatório para ajuste.")

    produto = _get_product(session, product_id)
    preco_unitario = Decimal("0")

    if movimento_referencia_id:
        movimento_original = session.get(StockMovement, movimento_referencia_id)
        if movimento_original and movimento_original.preco_unitario is not None:
            preco_unitario = Decimal(str(movimento_original.preco_unitario))

    if preco_unitario == 0:
        cm = get_custo_medio(session, product_id)
        if cm:
            preco_unitario = Decimal(str(cm))

    mov = StockMovement(
        tenant_id=produto.tenant_id,
        product_id=product_id,
        tipo="ajuste",
        direcao=direcao,
        quantidade=quantidade,
        preco_unitario=preco_unitario,
        motivo=motivo.strip(),
        observacao=observacao,
        data_movimento=data_ajuste,
        movimento_referencia_id=movimento_referencia_id,
    )
    session.add(mov)
    session.commit()
    session.refresh(mov)
    return mov


def registrar_estorno(
    session: Session,
    movimento_id: int,
    observacao: Optional[str] = None,
) -> StockMovement:
    """Estorna uma movimentação anterior (auditoria)."""
    original = session.get(StockMovement, movimento_id)
    if not original:
        raise ValueError("Movimentação não encontrada.")
    if original.tipo == "estorno":
        raise ValueError("Não é possível estornar um estorno.")

    produto = _get_product(session, original.product_id)

    mov = StockMovement(
        tenant_id=produto.tenant_id,
        product_id=original.product_id,
        tipo="estorno",
        quantidade=original.quantidade,
        movimento_referencia_id=original.id,
        data_movimento=date.today(),
        observacao=observacao or f"Estorno da movimentação #{original.id}",
    )
    session.add(mov)
    session.commit()
    session.refresh(mov)
    return mov
