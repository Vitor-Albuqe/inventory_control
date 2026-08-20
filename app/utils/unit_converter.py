def converter_para_estoque(
    quantidade: float,
    unidade_estoque: str,
) -> float:
    """
    Converte quantidade digitada pelo usuário
    para a unidade usada no estoque.
    """

    if unidade_estoque == "kg":
        return quantidade / 1000

    if unidade_estoque == "L":
        return quantidade / 1000

    return quantidade

def unidade_exibicao(
    unidade_estoque: str,
) -> str:

    if unidade_estoque == "kg":
        return "g"

    if unidade_estoque == "L":
        return "ml"

    return unidade_estoque

def formatar_receita(
    quantidade: float,
    unidade: str,
) -> str:

    if unidade == "kg":
        return f"{quantidade * 1000:.0f} g"

    if unidade == "L":
        return f"{quantidade * 1000:.0f} ml"

    return f"{quantidade:g} {unidade}"

def formatar_quantidade_estoque(
    quantidade: float,
    unidade_estoque: str,
) -> str:
    """
    Formata uma quantidade de estoque com a unidade cadastrada do produto
    (kg/L/un), arredondando no menor incremento real: unidade inteira para
    "un", grama/ml (3 casas decimais) para "kg"/"L".
    """

    if unidade_estoque == "un":
        return f"{round(quantidade):g} un"

    valor = round(quantidade, 3)
    if valor == 0:
        valor = 0.0
    texto = f"{valor:.3f}".rstrip("0").rstrip(".")
    return f"{texto or '0'} {unidade_estoque}"


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)

def quantidade_exibicao(
    quantidade_estoque: float,
    unidade_estoque: str,
) -> float:

    if unidade_estoque == "kg":
        return quantidade_estoque * 1000

    if unidade_estoque == "L":
        return quantidade_estoque * 1000

    return quantidade_estoque