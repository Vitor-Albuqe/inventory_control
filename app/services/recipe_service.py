from __future__ import annotations


from sqlite3 import IntegrityError


from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal

from app.database.seed import DEFAULT_TENANT_ID
from app.models import Product

from app.models import recipes
from app.models.enums import ProductType
from app.models.enums import ProductType
from app.models.recipes import RecipeItem

from app.services import _get_product

from app.repositories import listar_receitas_ativas, listar_ingredientes_disponiveis

# ---------------------------------------------------------------------------
# repositorios
# ---------------------------------------------------------------------------

def obter_receitas_ativas():

    db = SessionLocal()

    try:
        return listar_receitas_ativas(db)
    
    finally:
        db.close()

def obter_ingredientes_ativos():
    db = SessionLocal()

    try:
        return listar_ingredientes_disponiveis(db)
    
    finally:
        db.close()


def buscar_ingredientes_receita(
    session: Session,
    recipe_id: int,
    tenant_id: int = DEFAULT_TENANT_ID,
) -> list[RecipeItem]:
    """
    Retorna todos os ingredientes de uma receita.
    """

    return (
        session.query(RecipeItem)
        .join(
            Product,
            RecipeItem.recipe_id == Product.id,
        )
        .filter(
            RecipeItem.recipe_id == recipe_id,
            Product.tenant_id == tenant_id,
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Criar receita
# ---------------------------------------------------------------------------
def criar_receita_item(
    session: Session,
    recipe_id: int,
    ingredient_id: int,
    quantity: float,
    tenant_id: int = DEFAULT_TENANT_ID,
) -> RecipeItem:
    """
    Adiciona um ingrediente a uma receita.
    """

    if quantity <= 0:
        raise ValueError(
            "A quantidade deve ser maior que zero."
        )

    receita = (
        session.query(Product)
        .filter(
            Product.id == recipe_id,
            Product.tenant_id == tenant_id,
        )
        .first()
    )

    if not receita:
        raise ValueError("Receita não encontrada.")

    if receita.tipo_produto != "receita":
        raise ValueError(
            "O produto informado não é uma receita."
        )

    ingrediente = (
        session.query(Product)
        .filter(
            Product.id == ingredient_id,
            Product.tenant_id == tenant_id,
        )
        .first()
    )

    if not ingrediente:
        raise ValueError("Ingrediente não encontrado.")

    if ingrediente.tipo_produto == "receita":
        raise ValueError(
            "Uma receita não pode ser ingrediente de outra receita."
        )

    existente = (
        session.query(RecipeItem)
        .filter(
            RecipeItem.recipe_id == recipe_id,
            RecipeItem.ingredient_id == ingredient_id,
        )
        .first()
    )

    if existente:
        raise ValueError(
            "Este ingrediente já foi adicionado."
        )

    item = RecipeItem(
        tenant_id=tenant_id,
        recipe_id=recipe_id,
        ingredient_id=ingredient_id,
        quantity=quantity,
    )

    session.add(item)
    # Sem commit aqui: o chamador (salvar_produto_com_receita) faz o commit
    # depois de adicionar todos os ingredientes atomicamente.
    return item




# ---------------------------------------------------------------------------
# desativar / atualizar
# ---------------------------------------------------------------------------


def mudar_preco_receita(
    session: Session,
    receita_id: int,
    novo_preco: float,
) -> Product:

    if novo_preco <= 0:
        raise ValueError(
            "O preço deve ser maior que zero."
        )

    receita = (
        session.query(Product)
        .filter(Product.id == receita_id)
        .first()
    )

    if not receita:
        raise ValueError(
            "Receita não encontrada."
        )

    if receita.tipo_produto.value != "receita":
        raise ValueError(
            "O produto informado não é uma receita."
        )

    receita.preco_venda = novo_preco

    session.commit()
    session.refresh(receita)

    return receita

def pode_excluir_receita(receita):
    return (
        not receita.sales
        and not receita.movements
    )


def desativar_receita(session: Session, product_id: int) -> Product:
    produto = _get_product(session, product_id)
    produto.ativo = not produto.ativo
    session.commit()
    session.refresh(produto)
    return produto

def remover_receita(session: Session, receita_id: int) -> None:
    try: 
        receita = _get_product(session, receita_id)

        if receita.tipo_produto != "receita":
            raise ValueError("Produto informado não é uma receita.")

        session.delete(receita)
        session.commit()

    except IntegrityError:
        session.rollback()

        raise ValueError(
            "Não foi possível excluir o produto porque existem registros relacionados a ele."
        )

def remover_receita_item(
    session: Session,
    item_id: int,
) -> None:

    item = (
        session.query(RecipeItem)
        .filter(
            RecipeItem.id == item_id
        )
        .first()
    )

    if not item:
        raise ValueError(
            "Ingrediente não encontrado."
        )

    session.delete(item)
    session.commit()

def atualizar_quantidade_receita(
    session: Session,
    recipe_item_id: int,
    quantity: float,
) -> RecipeItem:

    item = (
        session.query(RecipeItem)
        .filter(
            RecipeItem.id == recipe_item_id
        )
        .first()
    )

    if not item:
        raise ValueError(
            "Item da receita não encontrado."
        )

    item.quantity = quantity

    session.commit()
    session.refresh(item)

    return item

def adicionar_ingrediente_receita(
    session: Session,
    recipe_id: int,
    ingredient_id: int,
    quantity: float,
) -> RecipeItem:

    if quantity <= 0:
        raise ValueError(
            "Quantidade deve ser maior que zero."
        )

    existe = (
        session.query(RecipeItem)
        .filter(
            RecipeItem.recipe_id == recipe_id,
            RecipeItem.ingredient_id == ingredient_id,
        )
        .first()
    )

    ingrediente = (
        session.query(Product)
        .filter(
            Product.id == ingredient_id,
        )
        .first()
    )
    if ingrediente.tipo_produto == ProductType.RECEITA:
        raise ValueError(
            "Receitas não podem ser usadas como ingrediente."
        )

    if existe:
        raise ValueError(
            "Ingrediente já existe na receita."
        )

    item = RecipeItem(
        tenant_id=_get_product(
            session,
            recipe_id,
        ).tenant_id,
        recipe_id=recipe_id,
        ingredient_id=ingredient_id,
        quantity=quantity,
    )

    session.add(item)
    session.commit()
    session.refresh(item)

    return item